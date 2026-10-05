import json
import logging
import datetime
import re
from decimal import Decimal
from django.conf import settings
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.db.models import Q

from .models import CustomerMemory, CallSession
from common.auth import verify_internal_api_key

logger = logging.getLogger(__name__)


@login_required(login_url='/login/')
def list_customers_memory(request):
    """List all customers (by phone number) for the authenticated user with search."""
    query = request.GET.get('q', '').strip()
    memories = CustomerMemory.objects.filter(user=request.user)
    if query:
        from django.db.models import Q
        memories = memories.filter(
            Q(phone_number__icontains=query) |
            Q(customer_name__icontains=query) |
            Q(last_interaction_summary__icontains=query)
        )
    
    results = [m.to_dict() for m in memories]
    return JsonResponse({
        "status": "success",
        "customers": results,
        "count": len(results)
    })


@login_required(login_url='/login/')
def get_customer_memory(request):
    """Retrieve the customer memory card and recent call history for a specific phone number."""
    phone = request.GET.get('phone', '').strip()
    if not phone:
        # Default to web_dashboard or the most recently updated customer
        latest = CustomerMemory.objects.filter(user=request.user).first()
        phone = latest.phone_number if latest else 'web_dashboard'

    memory, _ = CustomerMemory.objects.get_or_create(user=request.user, phone_number=phone)
    recent_calls = CallSession.objects.filter(user=request.user)
    if phone != 'web_dashboard':
        from django.db.models import Q
        recent_calls = recent_calls.filter(Q(caller_phone=phone) | Q(destination_phone=phone))
    recent_calls = recent_calls[:5]

    return JsonResponse({
        "status": "success",
        "phone_number": phone,
        "memory": memory.to_dict(),
        "recent_calls": [c.to_dict() for c in recent_calls]
    })


@login_required(login_url='/login/')
def reset_customer_memory(request):
    """Reset customer memory for a specific phone number."""
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "طريقة الطلب غير مسموحة"}, status=405)

    data = json.loads(request.body.decode('utf-8')) if request.body else {}
    phone = (data.get('phone') or request.POST.get('phone') or '').strip()
    if not phone:
        phone = 'web_dashboard'

    memory = CustomerMemory.objects.filter(user=request.user, phone_number=phone).first()
    if memory:
        memory.permanent_profile = {}
        memory.customer_name = ""
        memory.last_interaction_summary = ""
        memory.last_interaction_at = None
        memory.save()
        res_dict = memory.to_dict()
    else:
        res_dict = {}

    return JsonResponse({
        "status": "success",
        "message": f"تمت إعادة تعيين ذاكرة العميل ({phone}) بنجاح.",
        "memory": res_dict
    })


# ==================== Internal Agent Call Completion & Memory API ====================

@csrf_exempt
def api_internal_get_customer_memory(request):
    """Internal API to get or search customer memory by user_id, caller_phone, or query identifier."""
    if request.method not in ['GET', 'POST']:
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    if not verify_internal_api_key(request):
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    try:
        user_id = None
        caller_phone = 'web_dashboard'
        query = ''
        if request.method == 'POST':
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
            user_id = data.get('user_id') or request.POST.get('user_id')
            raw_phone = str(data.get('caller_phone') or request.POST.get('caller_phone') or 'web_dashboard')
            query = str(data.get('query') or data.get('identifier') or request.POST.get('query') or '').strip()
        else:
            user_id = request.GET.get('user_id')
            raw_phone = str(request.GET.get('caller_phone') or 'web_dashboard')
            query = str(request.GET.get('query') or request.GET.get('identifier') or '').strip()

        caller_phone = raw_phone.strip()
        if raw_phone.startswith(' ') and not caller_phone.startswith('+'):
            caller_phone = '+' + caller_phone

        if not user_id:
            return JsonResponse({"status": "error", "message": "user_id is required"}, status=400)

        memory = None
        # 1. Search by query/identifier if provided
        if query:
            # A. Exact phone match
            memory = CustomerMemory.objects.filter(user_id=user_id, phone_number=query).first()
            # B. Suffix phone match (last 8 digits)
            if not memory:
                clean_digits = re.sub(r'\D', '', query)
                if len(clean_digits) >= 7:
                    memory = CustomerMemory.objects.filter(user_id=user_id, phone_number__endswith=clean_digits[-8:]).first()
            # C. Name match
            if not memory:
                memory = CustomerMemory.objects.filter(user_id=user_id, customer_name__icontains=query).first()
            # D. Profile text match
            if not memory:
                memory = CustomerMemory.objects.filter(user_id=user_id, permanent_profile__icontains=query).first()

        # 2. Fallback to caller_phone lookup only if query was not provided
        if not memory and not query and caller_phone:
            memory = CustomerMemory.objects.filter(user_id=user_id, phone_number=caller_phone).first()
            if not memory and caller_phone != 'web_dashboard' and len(caller_phone) >= 7:
                clean_digits = re.sub(r'\D', '', caller_phone)
                suffix = clean_digits[-8:] if len(clean_digits) >= 8 else caller_phone[-8:]
                memory = CustomerMemory.objects.filter(user_id=user_id, phone_number__endswith=suffix).first()

        found = bool(memory)
        card_text = memory.format_for_system_instruction() if memory else ""
        mem_dict = memory.to_dict() if memory else {
            "phone_number": caller_phone,
            "customer_name": "",
            "permanent_profile": {},
            "last_interaction_summary": "",
            "total_calls_count": 0
        }

        return JsonResponse({
            "status": "success",
            "found": found,
            "phone_number": memory.phone_number if memory else caller_phone,
            "card_text": card_text,
            "memory": mem_dict
        })
    except Exception as e:
        logger.error(f"Error in api_internal_get_customer_memory: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
def api_internal_save_call_session_and_memory(request):
    """
    Internal API called by Voice Agent upon call completion to persist
    the CallSession details and update CustomerMemory for (user, caller_phone).
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    if not verify_internal_api_key(request):
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        user_id = data.get('user_id')
        room_name = data.get('room_name')
        if not user_id or not room_name:
            return JsonResponse({"status": "error", "message": "user_id and room_name are required"}, status=400)

        user = User.objects.filter(id=user_id).first() if user_id else None
        if not user:
            return JsonResponse({"status": "error", "message": f"User with id '{user_id}' not found."}, status=404)

        duration_seconds = int(data.get('duration_seconds', 0))
        direction = data.get('direction', 'inbound')
        is_internal_test = bool(data.get('is_internal_test')) or direction == 'internal_test'
        caller_extension = str(data.get('caller_extension') or '').strip()
        caller_phone = str(data.get('caller_phone') or 'web_dashboard').strip()
        destination_phone = str(data.get('destination_phone') or '').strip()
        customer_name = str(data.get('customer_name') or '').strip()
        call_goal = str(data.get('call_goal') or '')
        transcript_text = str(data.get('transcript_text') or '')
        summary = str(data.get('summary') or '')
        permanent_profile = data.get('permanent_profile') or data.get('distilled_profile')

        now_dt = datetime.datetime.now(datetime.timezone.utc)

        # Check if permanent_profile contains extracted phone or name
        if isinstance(permanent_profile, dict):
            extracted_phone = str(permanent_profile.get('phone') or '').strip()
            extracted_name = str(permanent_profile.get('customer_name') or '').strip()
            if extracted_name and not customer_name:
                customer_name = extracted_name
            if extracted_phone and caller_phone in ['web_dashboard', 'anonymous', 'unknown', '']:
                caller_phone = extracted_phone

        # Check if recording_url is available from request or Redis cache
        req_recording_url = str(data.get('recording_url') or '').strip()
        if not req_recording_url:
            try:
                import redis
                r = redis.Redis.from_url(settings.REDIS_URL)
                cached_rec = r.get(f"recording_url:{room_name}")
                if cached_rec:
                    req_recording_url = cached_rec.decode() if isinstance(cached_rec, bytes) else str(cached_rec)
            except Exception:
                pass

        # 1. Update existing CallSession (e.g. created by outbound dialer) or create a new record
        session = CallSession.objects.filter(room_name=room_name).first()
        if session:
            session.ended_at = now_dt
            session.duration_seconds = duration_seconds
            session.transcript_text = transcript_text
            session.summary = summary
            if caller_phone:
                session.caller_phone = caller_phone
            if destination_phone:
                session.destination_phone = destination_phone
            if is_internal_test:
                session.is_internal_test = True
                session.direction = 'internal_test'
            if caller_extension:
                session.caller_extension = caller_extension
            update_fields = ['ended_at', 'duration_seconds', 'transcript_text', 'summary', 'caller_phone', 'destination_phone', 'is_internal_test', 'caller_extension', 'direction']
            if req_recording_url and not session.recording_url:
                session.recording_url = req_recording_url
                update_fields.append('recording_url')
            session.save(update_fields=update_fields)
        else:
            session = CallSession.objects.create(
                user=user,
                room_name=room_name,
                direction='internal_test' if is_internal_test else direction,
                caller_phone=caller_phone,
                destination_phone=destination_phone,
                call_goal=call_goal,
                ended_at=now_dt,
                duration_seconds=duration_seconds,
                transcript_text=transcript_text,
                summary=summary,
                recording_url=req_recording_url,
                is_internal_test=is_internal_test,
                caller_extension=caller_extension
            )

        # 1.1 Calculate billing with strict ceiling rounding and deduct from wallet (Partner or User)
        billed_minutes = 0
        call_cost = 0.0
        try:
            from billing.models import BillingConfig, UserWallet, BillingTransaction
            config = BillingConfig.get_config()
            b_mins, cost_dec = config.calculate_cost(duration_seconds)
            billed_minutes = b_mins
            call_cost = float(cost_dec)

            # Check if user is a sub-client under an approved partner
            partner_rel = None
            try:
                from partners.models import PartnerClientRelationship
                partner_rel = PartnerClientRelationship.objects.select_related('partner', 'partner__user').filter(
                    client=user,
                    partner__status='approved'
                ).first()
            except Exception:
                pass

            if partner_rel and partner_rel.partner:
                partner = partner_rel.partner
                rate = partner.custom_rate_per_minute
                cost_dec = round(Decimal(str(billed_minutes)) * rate, 4)
                call_cost = float(cost_dec)

                # Deduct from Partner's pooled wallet with atomic row lock
                target_user = partner.user
                with transaction.atomic():
                    wallet = UserWallet.objects.select_for_update().filter(user=target_user).first()
                    if not wallet:
                        wallet = UserWallet.objects.create(
                            user=target_user,
                            balance=config.initial_welcome_credit,
                            currency=partner.currency,
                            total_deposited=config.initial_welcome_credit,
                            total_spent=Decimal('0.0000'),
                        )
                    wallet.balance -= cost_dec
                    wallet.total_spent += cost_dec
                    wallet.save(update_fields=['balance', 'total_spent', 'updated_at'])

                    # Track sub-client stats atomically
                    partner_rel.total_spent += cost_dec
                    partner_rel.total_minutes += billed_minutes
                    partner_rel.save(update_fields=['total_spent', 'total_minutes', 'updated_at'])

                    BillingTransaction.objects.create(
                        wallet=wallet,
                        call_session=session,
                        transaction_type='call_deduction',
                        amount=-cost_dec,
                        balance_after=wallet.balance,
                        currency=wallet.currency,
                        actual_seconds=duration_seconds,
                        billed_minutes=billed_minutes,
                        rate_applied=rate,
                        description=f"مكالمة عميل الساس '{user.first_name or user.username}' ({billed_minutes} دقيقة - بسعر الشريك المخصص {rate}$)"
                    )

                # Dispatch Webhook to partner's SaaS backend
                try:
                    from partners.services.webhook import dispatch_partner_webhook
                    dispatch_partner_webhook(partner, "call.completed", {
                        "client_id": user.id,
                        "client_name": user.first_name or user.username,
                        "external_reference": partner_rel.external_reference,
                        "call_id": room_name,
                        "caller_phone": caller_phone,
                        "duration_seconds": duration_seconds,
                        "billed_minutes": billed_minutes,
                        "cost": float(cost_dec),
                        "summary": summary,
                        "partner_remaining_balance": float(wallet.balance),
                    })
                except Exception as wh_e:
                    logger.warning(f"Error triggering partner webhook: {wh_e}")
            else:
                with transaction.atomic():
                    wallet = UserWallet.objects.select_for_update().filter(user=user).first()
                    if not wallet:
                        wallet = UserWallet.objects.create(
                            user=user,
                            balance=config.initial_welcome_credit,
                            currency=config.currency,
                            total_deposited=config.initial_welcome_credit,
                            total_spent=Decimal('0.0000'),
                        )
                    wallet.balance -= cost_dec
                    wallet.total_spent += cost_dec
                    wallet.save(update_fields=['balance', 'total_spent', 'updated_at'])

                    BillingTransaction.objects.create(
                        wallet=wallet,
                        call_session=session,
                        transaction_type='call_deduction',
                        amount=-cost_dec,
                        balance_after=wallet.balance,
                        currency=wallet.currency,
                        actual_seconds=duration_seconds,
                        billed_minutes=billed_minutes,
                        rate_applied=config.cost_per_minute,
                        description=f"مكالمة {session.get_direction_display()} ({billed_minutes} دقيقة تقريب لأعلى - {duration_seconds} ثانية)"
                    )

            session.billed_minutes = billed_minutes
            session.cost = cost_dec
            session.save(update_fields=['billed_minutes', 'cost'])
            logger.info(f"Billed {billed_minutes} mins ({cost_dec} {wallet.currency}) for room {room_name} from user {user.username}")
        except Exception as b_err:
            logger.error(f"Error processing call billing for room {room_name}: {b_err}", exc_info=True)

        # 2. Upsert CustomerMemory for (user, caller_phone) (Skip for internal employee test calls)
        if not is_internal_test and caller_phone:
            memory, _ = CustomerMemory.objects.get_or_create(user=user, phone_number=caller_phone)
            if customer_name:
                memory.customer_name = customer_name
            if permanent_profile is not None:
                if isinstance(permanent_profile, dict):
                    memory.permanent_profile = permanent_profile
                elif isinstance(permanent_profile, str):
                    try:
                        memory.permanent_profile = json.loads(permanent_profile)
                    except Exception:
                        pass
            if summary:
                memory.last_interaction_summary = summary
            memory.last_interaction_at = now_dt
            memory.total_calls_count = (memory.total_calls_count or 0) + 1
            memory.save()

        # 3. Check and update matching CampaignContact
        try:
            from .models import CampaignContact
            from .scoring import score_and_extract_lead
            from .inngest_jobs import broadcast_campaign_update

            target_phone = destination_phone or caller_phone
            if target_phone:
                contact = CampaignContact.objects.filter(
                    campaign__user=user,
                    phone_number=target_phone
                ).exclude(call_status='answered').first()

                if contact:
                    campaign = contact.campaign
                    contact.duration_seconds = duration_seconds
                    contact.call_session = session

                    if duration_seconds > 0:
                        contact.call_status = 'answered'
                        # Score lead with Gemini
                        score_res = score_and_extract_lead(
                            call_prompt=campaign.call_prompt,
                            transcript=transcript_text,
                            customer_name=contact.customer_name,
                            attributes=contact.attributes
                        )
                        contact.interest_level = score_res.get("interest_level", "warm")
                        contact.call_summary = score_res.get("call_summary") or summary
                        contact.extracted_data = score_res.get("extracted_data", {})
                    else:
                        contact.call_status = 'no_answer'
                        contact.interest_level = 'unreached'
                        contact.call_summary = "لم يرد العميل على الاتصال."

                    contact.save()
                    campaign.update_metrics()
                    broadcast_campaign_update(campaign.id, "contact_updated", contact.to_dict())
                    logger.info(f"Updated CampaignContact #{contact.id} ({contact.phone_number}) as {contact.call_status} / {contact.interest_level}")
        except Exception as c_err:
            logger.warning(f"Error updating CampaignContact on call completion: {c_err}")

        logger.info(f"Successfully saved CallSession #{session.id} and updated CustomerMemory for ({user.id}, {caller_phone})")

        return JsonResponse({
            "status": "success",
            "session_id": session.id,
            "caller_phone": caller_phone,
            "phone_number": caller_phone,
            "duration_seconds": duration_seconds,
            "billed_minutes": billed_minutes,
            "cost": call_cost,
            "total_calls_count": memory.total_calls_count
        })

    except Exception as e:
        logger.error(f"Error saving CallSession and memory: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


# ==================== Call Detail Records (CDR) API ====================

@login_required(login_url='/login/')
def list_all_calls(request):
    """
    List and filter all Call Detail Records (CDR) for the authenticated user
    with advanced filters (search, direction, date presets, duration ranges).
    """
    try:
        from django.db.models import Q, Sum
        from django.utils import timezone

        calls = CallSession.objects.filter(user=request.user)

        # 1. Search filter
        search = request.GET.get('search', '').strip()
        if search:
            calls = calls.filter(
                Q(caller_phone__icontains=search) |
                Q(destination_phone__icontains=search) |
                Q(room_name__icontains=search) |
                Q(call_goal__icontains=search) |
                Q(summary__icontains=search)
            )

        # 2. Direction filter
        direction = request.GET.get('direction', '').strip()
        if direction and direction != 'all':
            calls = calls.filter(direction=direction)

        # 3. Date presets / range
        date_preset = request.GET.get('date_preset', '').strip()
        now = timezone.now()

        if date_preset == 'today':
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            calls = calls.filter(started_at__gte=start_of_day)
        elif date_preset == 'last_7_days':
            start_7 = now - datetime.timedelta(days=7)
            calls = calls.filter(started_at__gte=start_7)
        elif date_preset == 'this_month':
            start_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            calls = calls.filter(started_at__gte=start_month)
        else:
            from_date = request.GET.get('from_date', '').strip()
            to_date = request.GET.get('to_date', '').strip()
            if from_date:
                try:
                    f_dt = datetime.datetime.strptime(from_date, '%Y-%m-%d')
                    calls = calls.filter(started_at__date__gte=f_dt.date())
                except ValueError:
                    pass
            if to_date:
                try:
                    t_dt = datetime.datetime.strptime(to_date, '%Y-%m-%d')
                    calls = calls.filter(started_at__date__lte=t_dt.date())
                except ValueError:
                    pass

        # 4. Duration filter
        duration_filter = request.GET.get('duration', '').strip()
        if duration_filter == 'under_1m':
            calls = calls.filter(duration_seconds__lt=60)
        elif duration_filter == '1m_to_5m':
            calls = calls.filter(duration_seconds__gte=60, duration_seconds__lte=300)
        elif duration_filter == 'over_5m':
            calls = calls.filter(duration_seconds__gt=300)

        # Compute aggregate metrics on filtered set
        stats = calls.aggregate(
            total_duration=Sum('duration_seconds'),
            total_minutes=Sum('billed_minutes'),
            total_cost=Sum('cost')
        )

        limit = int(request.GET.get('limit', 100))
        results = [c.to_dict() for c in calls[:limit]]

        return JsonResponse({
            "status": "success",
            "calls": results,
            "count": len(results),
            "stats": {
                "total_calls": calls.count(),
                "total_duration_seconds": stats.get('total_duration') or 0,
                "total_billed_minutes": stats.get('total_minutes') or 0,
                "total_cost": float(stats.get('total_cost') or 0.0),
            }
        })
    except Exception as e:
        logger.error(f"Error in list_all_calls: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

