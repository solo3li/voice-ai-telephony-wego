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
