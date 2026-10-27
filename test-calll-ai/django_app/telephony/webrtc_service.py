import os
import json
import uuid
import time
import logging
import asyncio
import datetime
import threading
from typing import Optional, Dict, Any

from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from livekit import api

logger = logging.getLogger(__name__)


async def async_terminate_room(room_name: str) -> bool:
    """Terminates an active LiveKit room via LiveKit Server API."""
    raw_url = getattr(settings, 'LIVEKIT_INTERNAL_URL', 'ws://livekit:7880')
    http_url = raw_url.replace('wss://', 'https://').replace('ws://', 'http://')
    lk = api.LiveKitAPI(http_url, settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
    try:
        await lk.room.delete_room(api.DeleteRoomRequest(room=room_name))
        logger.info(f"[WEBRTC_MAX_DURATION] Room '{room_name}' closed successfully.")
        return True
    except Exception as e:
        logger.warning(f"[WEBRTC_MAX_DURATION] Error deleting room '{room_name}': {e}")
        return False
    finally:
        await lk.aclose()


def schedule_room_termination(room_name: str, delay_seconds: int):
    """Schedules automatic room deletion after max duration limit expires."""
    def _timer_callback():
        try:
            from crm.models import CallSession
            session = CallSession.objects.filter(room_name=room_name).first()
            if session and session.ended_at:
                return  # already closed naturally
            asyncio.run(async_terminate_room(room_name))
        except Exception as err:
            logger.warning(f"Error in room termination timer for '{room_name}': {err}")

    t = threading.Timer(delay_seconds, _timer_callback)
    t.daemon = True
    t.start()


def initiate_webrtc_session(
    user: User,
    caller_name: str = "",
    caller_phone: str = "",
    profile_id: Optional[int] = None,
    welcome_message: str = "",
    context: str = "",
    max_duration_seconds: int = 300,
    partner=None,
    client_rel=None,
) -> Dict[str, Any]:
    """
    Initiates a direct browser-to-agent WebRTC voice session over LiveKit.
    Returns LiveKit connection URL and scoped AccessToken.
    """
    # 1. Bounds & Defaults
    max_duration = max(30, min(3600, int(max_duration_seconds or 300)))
    clean_name = str(caller_name or "زائر الموقع").strip()[:100]
    clean_phone = str(caller_phone or "webrtc_web").strip()[:64]
    clean_welcome = str(welcome_message or "").strip()
    clean_context = str(context or "").strip()

    # 2. Wallet & Balance Checks
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
                    "message": f"رصيدك الحالي ({wallet.balance:.2f} {sym}) غير كافٍ لبدء جلسة صوتية جديدة. الحد الأدنى المطلوب هو تكلفة دقيقة واحدة ({billing_cfg.cost_per_minute:.2f} {sym}). يرجى شحن الرصيد للمتابعة.",
                    "balance": float(wallet.balance),
                    "cost_per_minute": float(billing_cfg.cost_per_minute),
                    "http_status": 402
                }
        except Exception as b_err:
            logger.warning(f"Error checking user wallet balance: {b_err}")

    # 3. Resolve Agent Profile
    from agents.models import AgentProfile
    if profile_id:
        profile = AgentProfile.objects.filter(user=user, id=profile_id, is_active=True).first()
        if not profile:
            return {
                "status": "error",
                "code": "PROFILE_NOT_FOUND",
                "message": f"شخصية الذكاء الاصطناعي برقم #{profile_id} غير موجودة أو غير مفعلة لهذا الحساب.",
                "http_status": 404
            }
    else:
        profile = AgentProfile.objects.filter(user=user, is_active=True).first()
        if not profile:
            profile = AgentProfile.objects.create(
                user=user,
                name="المساعد الصوتي الذكي",
                voice_name="Aoede",
                gender="female",
                dialect="egyptian",
                persona_role="customer_support",
                speaking_style="friendly",
                is_active=True
            )

    # 4. Construct Profile Dict with Overrides
    profile_data = profile.to_dict()
    if clean_welcome:
        profile_data["welcome_message"] = clean_welcome
        profile_data["is_welcome_message_enabled"] = True

    if clean_context:
        existing_instructions = profile_data.get("custom_instructions") or ""
        profile_data["custom_instructions"] = f"{existing_instructions}\n\n[سياق الجلسة الحالية / Session Context]:\n{clean_context}".strip()

    # 5. Room Name & Identity
    session_uuid = uuid.uuid4().hex[:8]
    if partner and client_rel:
        room_name = f"room_webrtc_prt_{partner.id}_{client_rel.client_id}_{session_uuid}"
    else:
        room_name = f"room_webrtc_dev_{user.id}_{session_uuid}"

    user_identity = f"webrtc_{user.id}_{session_uuid}"

    # 6. Generate LiveKit Access Token
    meta_dict = {
        "user_id": user.id,
        "caller_name": clean_name,
        "caller_phone": clean_phone,
        "max_duration_seconds": max_duration,
        "role": "caller"
    }
    token = api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET) \
        .with_identity(user_identity) \
        .with_name(clean_name) \
        .with_ttl(datetime.timedelta(seconds=max_duration + 60)) \
        .with_metadata(json.dumps(meta_dict, ensure_ascii=False)) \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
        ))
    livekit_jwt = token.to_jwt()

    # 7. Pre-create CallSession in DB
    from crm.models import CallSession, CustomerMemory
    session = CallSession.objects.create(
        user=user,
        room_name=room_name,
        direction="inbound",
        caller_phone=clean_phone,
        call_goal=f"WebRTC voice call with {clean_name}" if clean_name else "WebRTC voice call",
        started_at=timezone.now(),
        is_internal_test=False,
        summary=f"مكالمة WebRTC مباشرة عبر الـ API ({clean_name})...",
    )
    if clean_phone and clean_name:
        try:
            CustomerMemory.objects.update_or_create(
                user=user,
                phone_number=clean_phone,
                defaults={"customer_name": clean_name}
            )
        except Exception as cm_err:
            logger.warning(f"Could not update CustomerMemory: {cm_err}")

    # 8. Dispatch AI Voice Agent to Room
    from telephony.agent_dispatch import dispatch_agent_to_room
    job_payload = {
        "room_name": room_name,
        "user_id": user.id,
        "caller_phone": clean_phone,
        "profile": profile_data,
        "is_queue": False,
        "queue_code": None,
        "queue_data": None,
        "participant_identity": user_identity,
        "is_off_hours": False,
        "off_hours_data": None,
        "max_duration_seconds": max_duration,
        "session_id": session.id,
    }
    dispatch_agent_to_room(room_name, job_payload)

    # 9. Schedule Auto-Termination for Max Duration Enforcer
    schedule_room_termination(room_name, max_duration)

    return {
        "status": "success",
        "call_id": session.id,
        "room_name": room_name,
        "livekit_url": settings.LIVEKIT_URL,
        "livekit_token": livekit_jwt,
        "max_duration_seconds": max_duration,
        "expires_in": max_duration,
        "agent_profile": {
            "id": profile.id,
            "name": profile.name,
            "voice": profile.voice_name,
            "dialect": profile.dialect,
            "welcome_message": profile_data.get("welcome_message", "")
        },
        "http_status": 201
    }
