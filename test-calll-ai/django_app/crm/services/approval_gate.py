"""Conditional Approval Gates Execution Engine for Digital Coworkers."""
import datetime
import logging
from typing import Dict, Any, Optional
from django.conf import settings
from django.contrib.auth.models import User
from agents.models import DigitalCoworkerConfig
from crm.models import ApprovalRequest, CustomerMemory
from .telegram import send_telegram_approval_message, update_telegram_message_status

logger = logging.getLogger(__name__)


def create_approval_request(
    user: User,
    action_type: str,
    title: str,
    description: str,
    payload: Optional[Dict[str, Any]] = None,
    customer_memory: Optional[CustomerMemory] = None
) -> ApprovalRequest:
    """Create a pending approval request and notify the manager on Telegram."""
    coworker_cfg = DigitalCoworkerConfig.get_or_create_config(user)
    
    req_obj = ApprovalRequest.objects.create(
        user=user,
        customer_memory=customer_memory,
        action_type=action_type,
        title=title,
        description=description,
        payload=payload or {},
        status='pending',
        telegram_chat_id=coworker_cfg.telegram_manager_chat_id
    )

    host_domain = getattr(settings, 'EXTERNAL_IP', '169.58.32.179')
    dashboard_url = f"https://app.{host_domain}.nip.io/approval/{req_obj.id}/"

    # Send interactive Telegram notification if token & chat configured
    if coworker_cfg.telegram_bot_token and coworker_cfg.telegram_manager_chat_id:
        tg_res = send_telegram_approval_message(
            bot_token=coworker_cfg.telegram_bot_token,
            chat_id=coworker_cfg.telegram_manager_chat_id,
            title=title,
            description=description,
            approval_id=req_obj.id,
            dashboard_url=dashboard_url
        )
        if tg_res.get("message_id"):
            req_obj.telegram_message_id = tg_res["message_id"]
            req_obj.save(update_fields=['telegram_message_id'])

    logger.info(f"[ApprovalGate] Created ApprovalRequest #{req_obj.id} for user {user.username} ({action_type})")
    return req_obj


def execute_approval_decision(
    approval_id: int,
    decision: str,
    reviewer: Optional[User] = None,
    reason: str = ""
) -> Dict[str, Any]:
    """Execute decision ('approved' or 'rejected') and trigger downstream actions."""
    req_obj = ApprovalRequest.objects.select_related('user', 'customer_memory').filter(id=approval_id).first()
    if not req_obj:
        return {"status": "error", "message": "Approval request not found"}

    if req_obj.status in ('approved', 'rejected', 'executed'):
        return {"status": "already_handled", "current_status": req_obj.status}

    now = datetime.datetime.now(datetime.timezone.utc)
    req_obj.status = 'approved' if decision == 'approved' else 'rejected'
    req_obj.reviewed_at = now
    req_obj.reviewed_by = reviewer
    req_obj.decision_reason = reason

    exec_result = {}
    coworker_cfg = DigitalCoworkerConfig.get_or_create_config(req_obj.user)

    # Execute specific action based on decision
    if decision == 'approved':
        if req_obj.action_type == 'post_call_discount_review':
            # Auto-send discount code via WhatsApp to the customer
            dest_phone = (req_obj.payload or {}).get("phone") or (req_obj.customer_memory.phone_number if req_obj.customer_memory else "")
            if dest_phone:
                from .whatsapp import send_whatsapp_message
                promo_code = f"DISC-{req_obj.id * 7 + 100}"
                msg = (
                    f"أهلاً بك يا فندم! بناءً على تواصلنا معك، يسعدنا إعلامك "
                    f"بالموافقة على تقديم خصم خاص لحضرتك بقيمة 15% باستخدام الكود: {promo_code}. "
                    f"نسعد دائماً بخدمتك!"
                )
                wa_res = send_whatsapp_message(dest_phone, msg, req_obj.user)
                exec_result = {"whatsapp_sent": True, "promo_code": promo_code, "wa_result": wa_res}

        req_obj.status = 'executed'
        decision_label = "✅ تمت الموافقة والتنفيذ بنجاح"
    else:
        decision_label = f"❌ تم الرفض بواسطة المدير: {reason or 'لا ينطبق العرض'}"
        exec_result = {"rejected": True}

    req_obj.execution_result = exec_result
    req_obj.save(update_fields=['status', 'reviewed_at', 'reviewed_by', 'decision_reason', 'execution_result', 'updated_at'])

    # Update Telegram message text and remove inline buttons
    if coworker_cfg.telegram_bot_token and req_obj.telegram_chat_id and req_obj.telegram_message_id:
        update_telegram_message_status(
            bot_token=coworker_cfg.telegram_bot_token,
            chat_id=req_obj.telegram_chat_id,
            message_id=req_obj.telegram_message_id,
            original_text=f"📌 *{req_obj.title}*\n{req_obj.description}",
            decision_text=decision_label
        )

    logger.info(f"[ApprovalGate] Executed decision '{decision}' for ApprovalRequest #{approval_id}")
    return {
        "status": "success",
        "approval_id": approval_id,
        "final_status": req_obj.status,
        "execution_result": exec_result
    }
