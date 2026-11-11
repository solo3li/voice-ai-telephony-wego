import json
import logging
from decimal import Decimal
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

from .models import BillingConfig, UserWallet, BillingTransaction

logger = logging.getLogger(__name__)


def _get_or_create_user_wallet(user):
    """Retrieve existing user wallet or initialize with welcome credit."""
    config = BillingConfig.get_config()
    wallet, created = UserWallet.objects.get_or_create(
        user=user,
        defaults={
            'balance': config.initial_welcome_credit,
            'currency': config.currency,
            'total_deposited': config.initial_welcome_credit,
            'total_spent': Decimal('0.0000'),
        }
    )
    if created and config.initial_welcome_credit > 0:
        BillingTransaction.objects.create(
            wallet=wallet,
            transaction_type='welcome_bonus',
            amount=config.initial_welcome_credit,
            balance_after=wallet.balance,
            currency=wallet.currency,
            description="رصيد ترحيبي مجاني لتجربة النظام"
        )
    return wallet, config


@login_required(login_url='/login/')
def get_wallet_status(request):
    """
    Get the authenticated user's wallet balance, current minute rate,
    billing settings, and recent transactions.
    """
    try:
        wallet, config = _get_or_create_user_wallet(request.user)
        recent_txs = wallet.transactions.all()[:10]
        can_call = wallet.balance >= config.cost_per_minute

        return JsonResponse({
            "status": "success",
            "wallet": wallet.to_dict(),
            "config": {
                "cost_per_minute": float(config.cost_per_minute),
                "currency": config.currency,
                "currency_symbol": config.get_currency_symbol(),
                "rounding_mode": config.rounding_mode,
                "min_balance_to_call": float(config.min_balance_to_call),
            },
            "can_call": can_call,
            "recent_transactions": [tx.to_dict() for tx in recent_txs]
        })
    except Exception as e:
        logger.error(f"Error fetching wallet status: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required(login_url='/login/')
def topup_wallet(request):
    """
    Process instant wallet top-up (OpenRouter style prepaid deposit).
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "طريقة الطلب غير مسموحة"}, status=405)

    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        else:
            data = request.POST

        raw_amount = data.get('amount')
        if raw_amount is None:
            return JsonResponse({"status": "error", "message": "المبلغ المطلوب شحنه مفقود"}, status=400)

        try:
            amount = Decimal(str(raw_amount).strip())
        except Exception:
            return JsonResponse({"status": "error", "message": "قيمة المبلغ غير صالحة"}, status=400)

        if amount <= 0:
            return JsonResponse({"status": "error", "message": "يجب أن يكون مبلغ الشحن أكبر من الصفر"}, status=400)

        # In non-staff mode, restrict instant simulated deposits above reasonable sandbox threshold
        if not (request.user.is_staff or request.user.is_superuser) and amount > Decimal('500.00'):
            return JsonResponse({
                "status": "error",
                "message": "عمليات الشحن المباشرة التي تتجاوز 500$ تتطلب ربط بوابة دفع معتمدة أو موافقة المسؤول."
            }, status=403)

        from django.db import transaction
        with transaction.atomic():
            wallet, config = _get_or_create_user_wallet(request.user)
            locked_wallet = UserWallet.objects.select_for_update().get(id=wallet.id)

            # Update wallet balances atomically
            locked_wallet.balance += amount
            locked_wallet.total_deposited += amount
            locked_wallet.save(update_fields=['balance', 'total_deposited', 'updated_at'])

            # Document transaction in ledger
            tx = BillingTransaction.objects.create(
                wallet=locked_wallet,
                transaction_type='topup',
                amount=amount,
                balance_after=locked_wallet.balance,
                currency=locked_wallet.currency,
                description=f"شحن رصيد ({amount:.2f} {locked_wallet.get_currency_symbol()})"
            )

        return JsonResponse({
            "status": "success",
            "message": f"تم شحن رصيدك بنجاح بمبلغ {amount:.2f} {locked_wallet.get_currency_symbol()}.",
            "wallet": locked_wallet.to_dict(),
            "transaction": tx.to_dict()
        })

    except Exception as e:
        logger.error(f"Error topping up wallet: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required(login_url='/login/')
def list_transactions(request):
    """
    List billing transactions history for the authenticated user's wallet.
    """
    try:
        wallet, _ = _get_or_create_user_wallet(request.user)
        tx_type = request.GET.get('type', '').strip()
        limit = int(request.GET.get('limit', 50))

        queryset = wallet.transactions.all()
        if tx_type and tx_type != 'all':
            queryset = queryset.filter(transaction_type=tx_type)

        transactions = queryset[:limit]
        return JsonResponse({
            "status": "success",
            "transactions": [tx.to_dict() for tx in transactions],
            "count": len(transactions),
            "wallet": wallet.to_dict()
        })
    except Exception as e:
        logger.error(f"Error listing transactions: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
def chatwoot_webhook(request):
    """
    Webhook receiver for Chatwoot message_created events.
    Calculates per-character cost for outgoing, non-private messages
    and deducts from tenant wallet or partner wholesale wallet.
    Guarantees idempotency via unique chatwoot_message_id and atomic row locks.
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    try:
        body = request.body.decode('utf-8') if request.body else ''
        payload = json.loads(body) if body else {}
    except Exception as e:
        logger.warning(f"[ChatwootWebhook] Invalid JSON payload: {e}")
        return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)

    # 1. Event verification: only process message_created
    event = payload.get('event')
    if event and event != 'message_created':
        return JsonResponse({"status": "ignored", "reason": f"unsupported_event_{event}"}, status=200)

    # 2. Direction & Privacy check: bill outgoing messages only, ignore private internal notes
    message_type_raw = payload.get('message_type')
    message_type_str = str(message_type_raw).strip().lower() if message_type_raw is not None else ''
    is_outgoing = message_type_str in ('outgoing', '1')

    private_raw = payload.get('private', False)
    if isinstance(private_raw, str):
        is_private = private_raw.strip().lower() in ('true', '1')
    else:
        is_private = bool(private_raw)

    if not is_outgoing or is_private:
        return JsonResponse({
            "status": "ignored",
            "reason": "not_outgoing_or_private",
            "message_type": message_type_raw,
            "private": private_raw
        }, status=200)

    # 3. Message ID & Idempotency check
    msg_id = payload.get('id')
    try:
        msg_id = int(msg_id) if msg_id is not None else None
    except (ValueError, TypeError):
        msg_id = None

    if not msg_id:
        return JsonResponse({"status": "error", "message": "Missing message id in payload"}, status=400)

    # Fast idempotency check before acquiring DB locks
    if BillingTransaction.objects.filter(chatwoot_message_id=msg_id).exists():
        return JsonResponse({
            "status": "ignored",
            "reason": "already_billed",
            "chatwoot_message_id": msg_id
        }, status=200)

    # 4. Resolve account_id -> tenant User -> Partner
    account_id = None
    account_data = payload.get('account')
    if isinstance(account_data, dict):
        account_id = account_data.get('id')
    elif isinstance(account_data, (int, str)):
        account_id = account_data
    if not account_id:
        account_id = payload.get('account_id')
    try:
        account_id = int(account_id) if account_id is not None else None
    except (ValueError, TypeError):
        account_id = None

    if not account_id:
        return JsonResponse({"status": "error", "message": "Missing account id"}, status=400)

    from voice_assistant.models import TenantChatwootConfig
    from partners.models import PartnerClientRelationship
    from django.contrib.auth.models import User
    from django.db import transaction, IntegrityError

    tenant_config = TenantChatwootConfig.objects.filter(account_id=account_id).select_related('user').first()
    if not tenant_config:
        # Fallback for account 2 if not yet explicitly linked in TenantChatwootConfig
        if account_id == 2:
            superuser = User.objects.filter(is_superuser=True).order_by('id').first()
            if superuser:
                tenant_user = superuser
            else:
                return JsonResponse({"status": "error", "message": "No superuser found for account 2"}, status=404)
        else:
            logger.warning(f"[ChatwootWebhook] No TenantChatwootConfig found for account #{account_id}")
            return JsonResponse({"status": "error", "message": f"Tenant config not found for account {account_id}"}, status=404)
    else:
        tenant_user = tenant_config.user

    # 5. Extract inbox details (strictly non-null string for database constraint)
    inbox_data = payload.get('inbox')
    if isinstance(inbox_data, dict):
        inbox_name = str(inbox_data.get('name') or '').strip()
    elif isinstance(inbox_data, str):
        inbox_name = inbox_data.strip()
    else:
        inbox_name = str(payload.get('inbox_name') or '').strip()
    inbox_name = inbox_name[:128]

    # 6. Character calculation
    config = BillingConfig.get_config()
    content = (payload.get('content') or '').strip()
    attachments = payload.get('attachments') or []
    has_media = bool(attachments)

    actual_chars, billed_chars = config.calculate_message_characters(content=content, has_media=has_media)
    if billed_chars <= 0:
        return JsonResponse({
            "status": "ignored",
            "reason": "empty_message",
            "chatwoot_message_id": msg_id
        }, status=200)

    # 7. Pricing resolution: check if tenant is a sub-client of a Partner SaaS
    partner_rel = getattr(tenant_user, 'partner_client_rel', None)
    if not partner_rel:
        partner_rel = PartnerClientRelationship.objects.filter(client=tenant_user).select_related('partner__user').first()

    is_partner_client = False
    partner = None
    if partner_rel and partner_rel.partner and partner_rel.partner.status == 'approved':
        partner = partner_rel.partner
        payer_user = partner.user
        rate = partner.custom_rate_per_1k_chars
        is_partner_client = True
    else:
        payer_user = tenant_user
        rate = config.cost_per_1k_chars

    # Cost = (billed_chars / 1000) * rate
    cost_dec = config.calculate_message_cost(billed_chars, rate=rate)

    # 8. Atomic wallet lock & ledger entry
    with transaction.atomic():
        wallet, _ = UserWallet.objects.select_for_update().get_or_create(
            user=payer_user,
            defaults={
                'balance': config.initial_welcome_credit,
                'currency': config.currency,
                'total_deposited': config.initial_welcome_credit,
                'total_spent': Decimal('0.0000'),
            }
        )

        # Re-check under wallet lock to serialize against duplicate concurrent requests
        if BillingTransaction.objects.filter(chatwoot_message_id=msg_id).exists():
            return JsonResponse({
                "status": "ignored",
                "reason": "already_billed",
                "chatwoot_message_id": msg_id
            }, status=200)

        # Lock partner_rel under transaction if partner client
        if is_partner_client and partner_rel:
            locked_rel = PartnerClientRelationship.objects.select_for_update().filter(id=partner_rel.id).first()
            if locked_rel:
                partner_rel = locked_rel

        # Zero / insufficient balance safety check
        if wallet.balance < cost_dec:
            deduct_amount = max(Decimal('0.0000'), wallet.balance)
            insufficient = True
        else:
            deduct_amount = cost_dec
            insufficient = False

        wallet.balance -= deduct_amount
        wallet.total_spent += deduct_amount
        wallet.save(update_fields=['balance', 'total_spent', 'updated_at'])

        if is_partner_client and partner_rel:
            partner_rel.total_spent += deduct_amount
            partner_rel.total_messages += 1
            partner_rel.total_message_chars += billed_chars
            partner_rel.save(update_fields=['total_spent', 'total_messages', 'total_message_chars', 'updated_at'])

        desc_suffix = f" (رصيد غير كافٍ: المطلوب {cost_dec}$ - المخصوم {deduct_amount}$)" if insufficient else ""
        client_tag = f" - عميل الساس '{tenant_user.username}'" if is_partner_client else ""
        inbox_tag = f" عبر {inbox_name}" if inbox_name else ""
        description = f"خصم رسالة شات ووت #{msg_id}{inbox_tag} ({billed_chars} حرف){client_tag}{desc_suffix}"

        try:
            with transaction.atomic():
                tx = BillingTransaction.objects.create(
                    wallet=wallet,
                    transaction_type='message_deduction',
                    amount=-deduct_amount,
                    balance_after=wallet.balance,
                    currency=wallet.currency,
                    chatwoot_message_id=msg_id,
                    actual_characters=actual_chars,
                    billed_characters=billed_chars,
                    rate_applied=rate,
                    inbox_name=inbox_name,
                    description=description[:255]
                )
        except IntegrityError:
            return JsonResponse({
                "status": "ignored",
                "reason": "already_billed",
                "chatwoot_message_id": msg_id
            }, status=200)

    # 9. Dispatch partner webhook if partner client
    if is_partner_client and partner:
        try:
            from partners.services.webhook import dispatch_partner_webhook
            dispatch_partner_webhook(partner, "message.billed", {
                "client_id": tenant_user.id,
                "client_name": tenant_user.first_name or tenant_user.username,
                "external_reference": partner_rel.external_reference,
                "chatwoot_message_id": msg_id,
                "inbox_name": inbox_name,
                "actual_characters": actual_chars,
                "billed_characters": billed_chars,
                "cost": float(cost_dec),
                "deducted_amount": float(deduct_amount),
                "rate_applied": float(rate),
                "partner_remaining_balance": float(wallet.balance),
                "insufficient_balance": insufficient,
            })
        except Exception as wh_err:
            logger.warning(f"[ChatwootWebhook] Failed to dispatch partner webhook: {wh_err}")

    logger.info(
        f"[ChatwootWebhook] Billed message #{msg_id} ({billed_chars} chars, {deduct_amount} {wallet.currency}) "
        f"for user {tenant_user.username} (Payer: {payer_user.username})"
    )

    return JsonResponse({
        "status": "insufficient_balance" if insufficient else "success",
        "chatwoot_message_id": msg_id,
        "actual_characters": actual_chars,
        "billed_characters": billed_chars,
        "rate_applied": float(rate),
        "cost": float(cost_dec),
        "deducted": float(deduct_amount),
        "balance_after": float(wallet.balance),
        "transaction_id": tx.id
    }, status=200)
