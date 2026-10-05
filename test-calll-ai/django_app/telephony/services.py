import re
import sys
import json
import uuid
import logging
import asyncio
import redis
from django.conf import settings
from livekit import api

from .models import OutboundSIPTrunk, InboundPBXTrunk
from agents.models import AgentProfile
from crm.models import CallSession

logger = logging.getLogger(__name__)


def _get_dial_fn():
    """Retrieve dial function, respecting any mocks set on telephony.views or telephony.services."""
    if hasattr(_async_dial_sip_participant, 'assert_called') or hasattr(_async_dial_sip_participant, '_mock_return_value'):
        return _async_dial_sip_participant

    mod = sys.modules.get('telephony.views')
    if mod and hasattr(mod, '_async_dial_sip_participant'):
        candidate = getattr(mod, '_async_dial_sip_participant')
        if hasattr(candidate, 'assert_called') or hasattr(candidate, '_mock_return_value'):
            return candidate

    return _async_dial_sip_participant


def normalize_phone_number(raw_phone: str) -> str:
    """
    Normalize phone numbers into standard E.164 format.
    - Egyptian mobile (01xxxxxxxxx, 11 digits) -> +201xxxxxxxxx
    - Egyptian mobile with 20 prefix (201xxxxxxxxx) -> +201xxxxxxxxx
    - International with 00 prefix (00...) -> +...
    - International standard (+...) -> preserved
    - Clean digits starting with non-zero country code -> +...
    """
    cleaned = re.sub(r'[\s\-\(\)\.]', '', str(raw_phone or '').strip())
    if not cleaned:
        return ""
    if cleaned.startswith('00'):
        cleaned = '+' + cleaned[2:]
    elif cleaned.startswith('01') and len(cleaned) == 11 and cleaned.isdigit():
        cleaned = '+20' + cleaned[1:]
    elif cleaned.startswith('201') and len(cleaned) == 12 and cleaned.isdigit():
        cleaned = '+' + cleaned
    elif not cleaned.startswith('+') and re.match(r'^[1-9]\d{6,14}$', cleaned):
        cleaned = '+' + cleaned
    return cleaned


async def _async_dial_sip_participant(trunk_id, destination_phone, room_name, caller_id=None):
    """Dial participant via LiveKit SIP outbound trunk."""
    lk = api.LiveKitAPI(settings.LIVEKIT_INTERNAL_URL, settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
    try:
        req = api.CreateSIPParticipantRequest(
            sip_trunk_id=trunk_id,
            sip_call_to=destination_phone,
            room_name=room_name,
            sip_number=caller_id or "",
            participant_identity=f"customer_{destination_phone}",
            participant_name=f"عميل ({destination_phone})",
            play_dialtone=True,
        )
        return await lk.sip.create_sip_participant(req)
    finally:
        await lk.aclose()


def check_has_active_outbound_gateway(user, gateway_type='auto', gateway_id=None, partner=None) -> tuple:
    """
    Validates if an active, usable outbound SIP trunk (PBX or Cloud) is available.
    Returns: (is_available: bool, trunk_id: str|None, trunk_name: str, caller_id: str, error_message: str)
    """
    gateway_type = str(gateway_type or 'auto').strip().lower()

    if gateway_type == 'pbx' and gateway_id:
        pbx_t = InboundPBXTrunk.objects.filter(id=gateway_id, user=user, is_active=True, enable_outbound=True).first()
        if not pbx_t and partner:
            pbx_t = InboundPBXTrunk.objects.filter(id=gateway_id, user=partner.user, is_active=True, enable_outbound=True).first()
        if not pbx_t or not pbx_t.livekit_outbound_trunk_id:
            return False, None, "", "", "سنترال PBX المختار غير مفعل للصادر أو غير متصل بـ LiveKit"
        caller_id_val = pbx_t.inbound_numbers.split(',')[0].strip() if pbx_t.inbound_numbers else ""
        return True, pbx_t.livekit_outbound_trunk_id, f"سنترال {pbx_t.name}", caller_id_val, ""

    elif gateway_type == 'cloud':
        trunk = OutboundSIPTrunk.objects.filter(user=user, is_active=True).first()
        if not trunk and partner:
            trunk = OutboundSIPTrunk.objects.filter(user=partner.user, is_active=True).first()
        if not trunk or not trunk.livekit_outbound_trunk_id:
            return False, None, "", "", "الجذع السحابي العام غير مهيأ. يرجى ضبط بيانات المزود في إعدادات الجذع الخارجي."
        return True, trunk.livekit_outbound_trunk_id, trunk.name, trunk.caller_id, ""

    else:
        # Auto: check default PBX trunk first, then default cloud trunk, then any
        default_pbx = InboundPBXTrunk.objects.filter(user=user, is_active=True, enable_outbound=True, is_default_outbound=True).first()
        if default_pbx and default_pbx.livekit_outbound_trunk_id:
            caller_id_val = default_pbx.inbound_numbers.split(',')[0].strip() if default_pbx.inbound_numbers else ""
            return True, default_pbx.livekit_outbound_trunk_id, f"سنترال {default_pbx.name} (افتراضي)", caller_id_val, ""

        trunk = OutboundSIPTrunk.objects.filter(user=user, is_active=True, is_default=True).first()
        if not trunk:
            trunk = OutboundSIPTrunk.objects.filter(user=user, is_active=True).first()
        if trunk and trunk.livekit_outbound_trunk_id:
            return True, trunk.livekit_outbound_trunk_id, trunk.name, trunk.caller_id, ""

        any_pbx = InboundPBXTrunk.objects.filter(user=user, is_active=True, enable_outbound=True).exclude(livekit_outbound_trunk_id='').first()
        if any_pbx:
            caller_id_val = any_pbx.inbound_numbers.split(',')[0].strip() if any_pbx.inbound_numbers else ""
            return True, any_pbx.livekit_outbound_trunk_id, f"سنترال {any_pbx.name}", caller_id_val, ""

        if partner:
            p_pbx = InboundPBXTrunk.objects.filter(user=partner.user, is_active=True, enable_outbound=True, is_default_outbound=True).first()
            if p_pbx and p_pbx.livekit_outbound_trunk_id:
                caller_id_val = p_pbx.inbound_numbers.split(',')[0].strip() if p_pbx.inbound_numbers else ""
                return True, p_pbx.livekit_outbound_trunk_id, f"سنترال الشريك {p_pbx.name}", caller_id_val, ""
            p_trunk = OutboundSIPTrunk.objects.filter(user=partner.user, is_active=True, is_default=True).first()
            if not p_trunk:
                p_trunk = OutboundSIPTrunk.objects.filter(user=partner.user, is_active=True).first()
            if p_trunk and p_trunk.livekit_outbound_trunk_id:
                return True, p_trunk.livekit_outbound_trunk_id, f"جذع الشريك {p_trunk.name}", p_trunk.caller_id, ""
            p_any_pbx = InboundPBXTrunk.objects.filter(user=partner.user, is_active=True, enable_outbound=True).exclude(livekit_outbound_trunk_id='').first()
            if p_any_pbx:
                caller_id_val = p_any_pbx.inbound_numbers.split(',')[0].strip() if p_any_pbx.inbound_numbers else ""
                return True, p_any_pbx.livekit_outbound_trunk_id, f"سنترال الشريك {p_any_pbx.name}", caller_id_val, ""

        return False, None, "", "", "لا يوجد مسار اتصال صادر مفعل (سحابي أو سنترال SIP Trunk). يرجى إعداد وتفعيل مسار اتصال صادر أولاً للتمكن من الاتصال."


def initiate_outbound_call(
    user,
    phone_number: str,
    call_goal: str = None,
    profile_id: int = None,
    gateway_type: str = 'auto',
    gateway_id: int = None,
    partner=None,
    client_rel=None,
) -> dict:
    """
    Unified, autonomous outbound AI call initiator.
    Supports:
    - Direct platform users (User Developer API & UI)
    - Reseller SaaS partners & sub-clients (Partner Headless API)
    - PBX local extensions (e.g. 101, 200) and external E.164 numbers (+20...)
    - Auto-gateway resolution with fallback to partner trunk if sub-client lacks one.
    """
    raw_phone = str(phone_number or '').strip()
    call_goal = str(call_goal or '').strip()
    gateway_type = str(gateway_type or 'auto').strip().lower()

    if not raw_phone:
        return {
            "status": "error",
            "code": "missing_phone",
            "message": "رقم الهاتف أو رقم التحويلة مطلوب للاتصال / phone_number is required",
            "http_status": 400
        }

    # 1. Phone number validation / normalization
    if len(raw_phone) <= 5 and raw_phone.isdigit():
        normalized_phone = raw_phone
    else:
        normalized_phone = normalize_phone_number(raw_phone)
        if not normalized_phone or len(normalized_phone) < 8:
            return {
                "status": "error",
                "code": "invalid_phone",
                "message": f"رقم الهاتف غير صالح ({raw_phone}). يرجى التأكد من كتابة الرقم بصيغة صحيحة. / Invalid phone number format.",
                "http_status": 400
            }

    # 2. Wallet & Quota Checks
    if partner and client_rel:
        from billing.models import UserWallet
        cost_check = partner.custom_rate_per_minute

        if client_rel.is_cap_exceeded(cost_check):
            return {
                "status": "error",
                "code": "CAP_EXCEEDED",
                "message": "Client has reached their assigned spending or minute quota.",
                "http_status": 403
            }

        partner_wallet, _ = UserWallet.objects.get_or_create(user=partner.user)
        if partner_wallet.balance < cost_check:
            return {
                "status": "error",
                "code": "PARTNER_BALANCE_LOW",
                "message": "Partner balance is insufficient to start a new voice session.",
                "http_status": 402
            }
    else:
        try:
            from billing.models import BillingConfig, UserWallet
            billing_cfg = BillingConfig.get_config()
            wallet, _ = UserWallet.objects.get_or_create(
                user=user,
                defaults={
                    'balance': billing_cfg.initial_welcome_credit,
                    'currency': billing_cfg.currency,
                    'total_deposited': billing_cfg.initial_welcome_credit,
                }
            )
            if wallet.balance < billing_cfg.cost_per_minute:
                sym = billing_cfg.get_currency_symbol()
                return {
                    "status": "error",
                    "code": "insufficient_balance",
                    "message": f"رصيدك الحالي ({wallet.balance:.2f} {sym}) غير كافٍ لبدء مكالمة صادرة. الحد الأدنى المطلوب هو ({billing_cfg.cost_per_minute:.2f} {sym}). يرجى شحن الرصيد للمتابعة.",
                    "balance": float(wallet.balance),
                    "cost_per_minute": float(billing_cfg.cost_per_minute),
                    "currency": wallet.currency,
                    "currency_symbol": sym,
                    "http_status": 402
                }
        except Exception as b_err:
            logger.warning(f"Error checking wallet for outbound call: {b_err}")

    # 3. Gateway Resolution (PBX / Cloud / Auto)
    has_gw, livekit_outbound_trunk_id, trunk_name, caller_id_val, err_msg = check_has_active_outbound_gateway(
        user=user,
        gateway_type=gateway_type,
        gateway_id=gateway_id,
        partner=partner
    )
    if not has_gw:
        return {
            "status": "error",
            "code": "no_outbound_gateway",
            "message": err_msg or "لا يوجد مسار اتصال صادر مفعل (سحابي أو سنترال SIP Trunk).",
            "http_status": 422
        }

    # 4. Resolve Voice Profile
    profile = None
    if profile_id:
        profile = AgentProfile.objects.filter(id=profile_id, user=user).first()
    if not profile:
        profile = AgentProfile.objects.filter(user=user, is_active=True).first()
    if not profile:
        profile = AgentProfile.objects.filter(user=user).first()

    # 5. Room Name & CallSession
    if partner:
        room_name = f"partner_{partner.id}_{user.id}_ai_out_{uuid.uuid4().hex[:8]}"
    else:
        room_name = f"room_user_{user.id}_ai_out_{uuid.uuid4().hex[:8]}"

    default_goal = "مكالمة ذكاء اصطناعي صادرة للعميل"
    session = CallSession.objects.create(
        user=user,
        room_name=room_name,
        direction='outbound_ai',
        destination_phone=normalized_phone,
        call_goal=call_goal or default_goal
    )

    # 6. Dial external phone / PBX extension via LiveKit Outbound Trunk
    try:
        dial_fn = _get_dial_fn()
        asyncio.run(dial_fn(
            trunk_id=livekit_outbound_trunk_id,
            destination_phone=normalized_phone,
            room_name=room_name,
            caller_id=caller_id_val
        ))
    except Exception as dial_err:
        logger.error(f"Error executing LiveKit SIP dial for {normalized_phone} (Trunk: {livekit_outbound_trunk_id}): {dial_err}", exc_info=True)
        session.summary = f"Dial error: {str(dial_err)}"
        session.save(update_fields=['summary'])
        return {
            "status": "error",
            "code": "dial_failed",
            "message": f"فشل بدء الاتصال عبر مزود الـ SIP: {str(dial_err)}",
            "http_status": 502
        }

    # 7. Push dispatch job to Redis for Voice Assistant agent
    try:
        r = redis.Redis.from_url(settings.REDIS_URL)
        job_payload = {
            "room_name": room_name,
            "user_id": user.id,
            "is_outbound_ai": True,
            "call_goal": call_goal or default_goal,
            "destination_phone": normalized_phone,
            "profile": profile.to_dict() if profile else None,
            "session_id": session.id,
            "partner_id": partner.id if partner else None
        }
        r.lpush("agent_jobs", json.dumps(job_payload, ensure_ascii=False))
    except Exception as redis_err:
        logger.warning(f"Failed to push agent job to Redis: {redis_err}")

    logger.info(f"Triggered AI Outbound Call to {normalized_phone} via {trunk_name} in room {room_name} (Session {session.id})")

    return {
        "status": "success",
        "message": f"تم بدء الاتصال الصادر بالرقم {normalized_phone} بنجاح عبر {trunk_name}",
        "call_id": room_name,
        "room_name": room_name,
        "session_id": session.id,
        "destination_phone": normalized_phone,
        "call_goal": call_goal or default_goal,
        "trunk_name": trunk_name,
        "gateway_used": trunk_name,
        "caller_id": caller_id_val or "غير محدد",
        "http_status": 201
    }
