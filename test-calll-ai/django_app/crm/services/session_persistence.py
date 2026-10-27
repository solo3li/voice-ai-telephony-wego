"""Asynchronous Call Session Persistence & Customer Memory Updates.

Handles persisting CallSession records, billing deduction, CustomerMemory updates,
lead scoring for campaign contacts, and follow-up job triggers in PostgreSQL.
Used both by HTTP endpoints and background Inngest consumers.
"""
import json
import logging
import datetime
from decimal import Decimal
from typing import Dict, Any

from django.conf import settings
from django.db import transaction
from django.contrib.auth.models import User

from crm.models import CallSession, CustomerMemory

logger = logging.getLogger(__name__)


def persist_call_session_and_memory(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Persist completed CallSession and update CustomerMemory for (user, caller_phone).
    Calculates billing, deducts from wallet, triggers partner webhook and campaigns.
    """
    user_id = data.get('user_id')
    room_name = data.get('room_name')
    if not user_id or not room_name:
        return {"status": "error", "message": "user_id and room_name are required"}

    user = User.objects.filter(id=user_id).first() if user_id else None
    if not user:
        return {"status": "error", "message": f"User with id '{user_id}' not found."}

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

    # Resolve employee phone number if caller is employee extension
    if caller_extension or caller_phone.startswith('emp'):
        try:
            from call_center.models import EmployeeProfile
            from django.db.models import Q
            ext_q = caller_extension or caller_phone.replace('emp', '')
            emp_obj = EmployeeProfile.objects.filter(Q(extension=ext_q) | Q(sip_username__icontains=caller_phone)).first()
            if emp_obj and emp_obj.phone_number:
                caller_phone = emp_obj.phone_number
                if not customer_name:
                    customer_name = emp_obj.display_name
        except Exception:
            pass

    # Check if permanent_profile contains extracted phone or name
    if isinstance(permanent_profile, str):
        try:
            permanent_profile = json.loads(permanent_profile)
        except Exception:
            pass

    if isinstance(permanent_profile, dict):
        extracted_phone = str(permanent_profile.get('phone') or '').strip()
        extracted_name = str(permanent_profile.get('customer_name') or '').strip()
        if extracted_name and not customer_name:
            customer_name = extracted_name
        if extracted_phone and caller_phone in ['web_dashboard', 'anonymous', 'unknown', '', '+201000000000']:
            caller_phone = extracted_phone

    if caller_phone == 'web_dashboard':
        caller_phone = '+201000000000'

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
    total_calls_count = 0
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
        total_calls_count = memory.total_calls_count

        # Enrich call_memory with structured call recap
        cm = memory.call_memory or {}
        cm["last_call_summary"] = summary
        cm["last_call_at"] = now_dt.strftime("%Y-%m-%d %H:%M")
        cm["total_calls_count"] = memory.total_calls_count
        if isinstance(permanent_profile, dict) and permanent_profile.get("agreed_next_steps"):
            cm["agreed_next_steps"] = permanent_profile.get("agreed_next_steps")
        memory.call_memory = cm
        memory.save()

        # Trigger LangGraph autonomous follow-up via durable Inngest job
        try:
            from crm.inngest_jobs import dispatch_whatsapp_followup_job
            dispatch_whatsapp_followup_job(
                user_id=user.id,
                phone_number=caller_phone,
                trigger_type="post_call",
                call_summary=summary,
                call_transcript=transcript_text,
                customer_name=customer_name,
            )
            logger.info(f"Dispatched Inngest autonomous follow-up for caller {caller_phone}")
        except Exception as lg_err:
            logger.warning(f"Failed to dispatch Inngest follow-up: {lg_err}")

    # 3. Check and update matching CampaignContact
    try:
        from crm.models import CampaignContact
        from crm.scoring import score_and_extract_lead
        from crm.inngest_jobs import broadcast_campaign_update, schedule_contact_retry

        contact = None
        if session:
            contact = CampaignContact.objects.filter(call_session=session).first()

        target_phone = destination_phone or caller_phone
        if not contact and target_phone:
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
                score_res = score_and_extract_lead(
                    call_prompt=campaign.call_prompt,
                    transcript=transcript_text,
                    customer_name=contact.customer_name,
                    attributes=contact.attributes
                )
                contact.interest_level = score_res.get("interest_level", "warm")
                contact.call_summary = score_res.get("call_summary") or summary
                contact.extracted_data = score_res.get("extracted_data", {})
                contact.save()
                campaign.update_metrics()
                broadcast_campaign_update(campaign.id, "contact_updated", contact.to_dict())
                logger.info(f"Updated CampaignContact #{contact.id} ({contact.phone_number}) as {contact.call_status} / {contact.interest_level}")

                # Hybrid Campaign: Send WhatsApp follow-up if hybrid
                if campaign.channel == 'hybrid' and contact.whatsapp_status in ['pending', 'failed']:
                    from crm.services.campaign_whatsapp import send_campaign_contact_whatsapp
                    try:
                        send_campaign_contact_whatsapp(contact.id)
                    except Exception as hw_err:
                        logger.warning(f"Error in hybrid campaign WhatsApp follow-up dispatch: {hw_err}")
            else:
                contact.call_status = 'no_answer'
                contact.interest_level = 'unreached'
                contact.call_summary = "لم يرد العميل على الاتصال."
                contact.save()
                campaign.update_metrics()
                broadcast_campaign_update(campaign.id, "contact_updated", contact.to_dict())
                logger.info(f"Updated CampaignContact #{contact.id} ({contact.phone_number}) as {contact.call_status} / {contact.interest_level}")

                if campaign.channel == 'hybrid' and contact.whatsapp_status in ['pending', 'failed']:
                    from crm.services.campaign_whatsapp import send_campaign_contact_whatsapp
                    try:
                        send_campaign_contact_whatsapp(contact.id)
                    except Exception as hw_err:
                        logger.warning(f"Error in hybrid campaign WhatsApp missed-call dispatch: {hw_err}")

                schedule_contact_retry(contact.id)
    except Exception as c_err:
        logger.warning(f"Error updating CampaignContact on call completion: {c_err}")

    logger.info(f"Successfully persisted CallSession #{session.id} and updated CustomerMemory for ({user.id}, {caller_phone})")

    return {
        "status": "success",
        "session_id": session.id,
        "caller_phone": caller_phone,
        "phone_number": caller_phone,
        "duration_seconds": duration_seconds,
        "billed_minutes": billed_minutes,
        "cost": call_cost,
        "total_calls_count": total_calls_count
    }
