"""Trinity Post-Call Event Bridge & Call-as-a-Tool Dispatcher."""
import json
import logging
import os
import requests
import redis
from typing import Dict, Any, Optional
from django.conf import settings
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)

TRINITY_WEBHOOK_URL = os.getenv("TRINITY_WEBHOOK_URL", "http://trinity:8000/api/webhooks/call-completed")


def get_redis_client():
    return redis.Redis.from_url(settings.REDIS_URL)


def dispatch_post_call_to_trinity(call_session) -> Dict[str, Any]:
    """
    Bridge call completion event from CallSession to Trinity Autonomous Agent.
    
    Publishes event to Redis channel 'trinity:events' and invokes Trinity Webhook.
    Also executes automated digital coworker follow-ups (WhatsApp/Email/Approval)
    if the tenant has 'digital_coworker' mode enabled.
    """
    if not call_session:
        return {"status": "error", "message": "No session provided"}

    user = call_session.user
    from agents.models import DigitalCoworkerConfig
    from crm.models import CustomerMemory, OmnichannelMessage

    coworker_cfg = DigitalCoworkerConfig.get_or_create_config(user)
    phone = call_session.destination_phone or call_session.caller_phone or "unknown"

    # Resolve or link CustomerMemory
    mem = None
    if phone and phone != "web_dashboard":
        mem = CustomerMemory.objects.filter(user=user, phone_number=phone).first()

    customer_name = mem.customer_name if mem else ""
    event_payload = {
        "event": "call.completed",
        "tenant_id": user.id,
        "tenant_username": user.username,
        "room_name": call_session.room_name,
        "direction": call_session.direction,
        "phone_number": phone,
        "customer_name": customer_name,
        "duration_seconds": call_session.duration_seconds,
        "billed_minutes": call_session.billed_minutes,
        "summary": call_session.summary or "تمت المكالمة بنجاح.",
        "transcript_text": call_session.transcript_text or "",
        "dialogue_turns": call_session.dialogue_turns,
        "recording_url": call_session.recording_url or "",
        "service_mode": coworker_cfg.service_mode,
        "coworker_role": coworker_cfg.coworker_role,
    }

    # 1. Publish to Redis for Trinity Consumer
    try:
        r = get_redis_client()
        r.publish("trinity:events", json.dumps(event_payload, ensure_ascii=False))
        r.rpush("trinity:event_queue", json.dumps(event_payload, ensure_ascii=False))
        logger.info(f"[Trinity Bridge] Published call.completed for room {call_session.room_name} to Redis.")
    except Exception as re:
        logger.warning(f"[Trinity Bridge] Redis publish error: {re}")

    # 2. HTTP Webhook to Trinity container (fire-and-forget with short timeout)
    try:
        requests.post(TRINITY_WEBHOOK_URL, json=event_payload, timeout=1.5)
        logger.info(f"[Trinity Bridge] Dispatched HTTP webhook to {TRINITY_WEBHOOK_URL}")
    except Exception as he:
        logger.debug(f"[Trinity Bridge] Trinity HTTP webhook skipped or unreachable: {he}")

    # 3. Log Call to OmnichannelMessage audit trail
    try:
        OmnichannelMessage.objects.create(
            user=user,
            customer_memory=mem,
            channel='phone',
            direction='outbound' if call_session.direction in ('outbound_ai', 'outbound_agent') else 'inbound',
            sender=user.username,
            recipient=phone,
            content=f"مكالمة هاتفية مدتها {call_session.duration_seconds} ثانية. الملخص: {call_session.summary[:200]}",
            metadata={"room_name": call_session.room_name, "session_id": call_session.id},
            status='delivered'
        )
    except Exception as me:
        logger.debug(f"[Trinity Bridge] OmnichannelMessage log error: {me}")

    # 4. If tenant has Digital Coworker mode active, trigger automatic post-call action
    action_result = {"status": "dispatched", "event": "call.completed"}
    if coworker_cfg.service_mode == 'digital_coworker' and coworker_cfg.auto_call_followup_enabled:
        from .whatsapp import send_whatsapp_message
        from .approval_gate import create_approval_request

        summary_lower = (call_session.summary or "").lower()
        
        # Check if conversation warrants an approval gate (e.g. discount, refund, cancellation)
        if any(w in summary_lower for w in ["خصم", "discount", "استرجاع", "refund", "إلغاء", "cancel"]):
            approval_obj = create_approval_request(
                user=user,
                action_type="post_call_discount_review",
                title=f"طلب موافقة على خصم للعميل {phone}",
                description=f"أثناء المكالمة طلب العميل خصماً أو تعديلاً خاصاً. ملخص المحادثة: {call_session.summary[:300]}",
                payload={"phone": phone, "session_id": call_session.id, "summary": call_session.summary},
                customer_memory=mem
            )
            action_result["approval_id"] = approval_obj.id
            logger.info(f"[Trinity Bridge] Created ApprovalRequest #{approval_obj.id} for sensitive post-call action.")
        else:
            # Send polite automated post-call summary message on WhatsApp if connected
            if coworker_cfg.has_whatsapp:
                followup_msg = (
                    f"مرحباً بك يا فندم! سعدنا بتواصلك معنا هاتفياً. "
                    f"هذا ملخص سريع لما تم في المكالمة:\n{call_session.summary or 'تمت خدمتكم بنجاح.'}\n"
                    f"نسعد دائماً بخدمتك!"
                )
                wa_res = send_whatsapp_message(to_phone=phone, message=followup_msg, tenant_user=user)
                action_result["whatsapp_followup"] = wa_res

    return action_result
