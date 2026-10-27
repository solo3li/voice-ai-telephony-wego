import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Tuple, Optional, Union, Dict, Any
from django.db.models import QuerySet, Q
from django.contrib.auth.models import User

from crm.models import CRMSupportTicket, CustomerMemory
from call_center.models import EmployeeProfile
from telephony.models import BusinessHoursSchedule

logger = logging.getLogger(__name__)


class AgentPresence:
    AVAILABLE = 'AVAILABLE'
    READY = 'ready'
    BUSY = 'busy'
    BREAK = 'break'
    OFFLINE = 'offline'

    ONLINE_STATUSES = ['ready', 'AVAILABLE', 'available']

    @classmethod
    def is_available(cls, status: Optional[str]) -> bool:
        if not status or not isinstance(status, str):
            return False
        s = status.strip()
        return s in cls.ONLINE_STATUSES or s.lower() in ('ready', 'available')


def get_available_agents(user_id: Optional[Union[int, User]] = None) -> QuerySet:
    """
    Query all active human agents for the given user whose status is ready or AVAILABLE.
    Supports either integer user_id, User instance, or None.
    """
    uid = user_id.id if hasattr(user_id, 'id') else user_id

    qs = EmployeeProfile.objects.filter(
        is_active=True,
        status__in=['ready', 'AVAILABLE', 'available', 'Ready', 'READY', 'Available']
    ).filter(
        Q(user__isnull=True) | Q(user__is_active=True)
    )
    if uid is not None:
        qs = qs.filter(Q(employer_id=uid) | Q(user_id=uid))

    return qs.order_by('id')


def is_operating_hours(user_id: Optional[Union[int, User]], dt: Optional[datetime] = None) -> Tuple[bool, str]:
    """
    Evaluate BusinessHoursSchedule for the user.
    Returns:
        (is_open: bool, operating_hours_text: str)
    If schedule does not exist or is disabled, defaults to 24/7 open.
    """
    uid = user_id.id if hasattr(user_id, 'id') else user_id
    sched = BusinessHoursSchedule.objects.filter(user_id=uid).first() if uid else None

    if not sched or not sched.is_enabled:
        return True, "متاح على مدار الساعة (24/7)"

    try:
        tz_str = sched.timezone or "Africa/Cairo"
        tz = ZoneInfo(tz_str)
    except Exception:
        tz_str = "UTC"
        tz = ZoneInfo("UTC")

    now_dt = dt or datetime.now(tz)
    if now_dt.tzinfo is not None:
        now_dt = now_dt.astimezone(tz)
    else:
        now_dt = now_dt.replace(tzinfo=tz)

    is_open = sched.is_within_business_hours(now_dt)

    day_keys_ar = {
        "saturday": "السبت", "sunday": "الأحد", "monday": "الاثنين",
        "tuesday": "الثلاثاء", "wednesday": "الأربعاء", "thursday": "الخميس", "friday": "الجمعة"
    }
    curr_day_key = now_dt.strftime('%A').lower()
    curr_day_ar = day_keys_ar.get(curr_day_key, curr_day_key)
    curr_time_str = now_dt.strftime('%I:%M %p')

    days_cfg = sched.days_config or {}
    today_cfg = days_cfg.get(curr_day_key, {})
    start_t = today_cfg.get("start_time", "09:00")
    end_t = today_cfg.get("end_time", "17:00")
    is_workday = today_cfg.get("is_workday", False) if today_cfg else False

    if not is_workday:
        hours_text = f"اليوم ({curr_day_ar}) عطلة رسمية. ساعات العمل الاعتيادية: من {start_t} إلى {end_t} ({tz_str})."
    elif is_open:
        hours_text = f"ساعات العمل الرسمية اليوم ({curr_day_ar}): من {start_t} إلى {end_t} ({tz_str}). التوقيت الحالي: {curr_time_str}."
    else:
        hours_text = f"خارج أوقات العمل الرسمية. ساعات العمل اليوم ({curr_day_ar}): من {start_t} إلى {end_t} ({tz_str}). التوقيت الحالي: {curr_time_str}."

    return is_open, hours_text


def create_support_ticket(
    user_id: Union[int, User],
    phone_number: str,
    customer_name: str = "",
    reason: str = "طلب دعم بشري / شكوى",
    urgency: str = "normal",
    summary: str = "",
    operating_hours_text: str = "",
    assigned_employee=None,
    assigned_agent=None,
    status: str = "OPEN"
) -> CRMSupportTicket:
    """
    Create a CRM support ticket when human agents are unavailable or outside working hours.
    Returns the created CRMSupportTicket instance.
    """
    if not user_id:
        raise ValueError("user_id is required")
    if not phone_number or not str(phone_number).strip():
        raise ValueError("phone_number is required")

    uid = user_id.id if hasattr(user_id, 'id') else user_id
    user = user_id if isinstance(user_id, User) else User.objects.get(id=uid)

    clean_urgency = urgency if urgency in ('normal', 'urgent') else 'normal'
    assigned = assigned_employee or assigned_agent

    clean_phone = str(phone_number).strip()[:64]
    clean_name = str(customer_name or "").strip()[:150]
    clean_reason = str(reason or "طلب دعم بشري / شكوى").strip()[:255]

    ticket = CRMSupportTicket.objects.create(
        user=user,
        customer_phone=clean_phone,
        customer_name=clean_name,
        reason=clean_reason,
        urgency=clean_urgency,
        summary=summary or "",
        operating_hours_snapshot=operating_hours_text or "",
        assigned_employee=assigned,
        status=status or "OPEN"
    )
    logger.info(f"Created CRMSupportTicket #{ticket.ticket_number} for customer {phone_number}")
    return ticket


def get_agent_active_count(emp: EmployeeProfile) -> int:
    """
    Count active escalated chats assigned to this employee profile.
    """
    employer = emp.employer or emp.user
    user_id = emp.user.id if emp.user else emp.id
    return CustomerMemory.objects.filter(
        user=employer,
        whatsapp_memory__conversation_state__in=["PENDING_AGENT_REPLY", "ACTIVE_SUPPORT"],
        whatsapp_memory__assigned_agent_id=user_id
    ).count()


def select_least_busy_agent(user_id: Union[int, User]) -> Optional[EmployeeProfile]:
    """
    Select available online agent with the lowest number of active chats.
    Tie-breaking resolves deterministically using employee id.
    """
    available_qs = get_available_agents(user_id)
    if not available_qs.exists():
        return None
    ready_agents = list(available_qs)
    sorted_agents = sorted(ready_agents, key=lambda a: (get_agent_active_count(a), a.id))
    return sorted_agents[0]


def dispatch_whatsapp_escalation(
    user_id: Union[int, User],
    phone_number: str,
    customer_name: str = "",
    reason: str = "طلب دعم بشري / شكوى",
    urgency: str = "normal",
    summary: str = "",
    now_dt: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Dispatch an escalated WhatsApp conversation:
    1. If outside operating hours or 0 agents online:
       - Creates CRMSupportTicket
       - Keeps AI active (ai_auto_reply_enabled=True)
       - Returns status="ticket_created"
    2. If agents are online:
       - Assigns least-busy agent
       - Sets conversation_state="PENDING_AGENT_REPLY"
       - Pauses AI (ai_auto_reply_enabled=False)
       - Broadcasts Centrifugo alert to user_{agent_id}
       - Returns status="success"
    """
    uid = user_id.id if hasattr(user_id, 'id') else user_id
    user = user_id if isinstance(user_id, User) else User.objects.get(id=uid)
    clean_phone = str(phone_number).strip()
    clean_urgency = urgency if urgency in ('normal', 'urgent') else 'normal'

    # Check operating hours and available online agents
    is_open, hours_text = is_operating_hours(user, dt=now_dt)
    available_agents = get_available_agents(user)

    # If no human agents are online -> create support ticket & keep AI active
    if not available_agents.exists():
        ticket = create_support_ticket(
            user_id=user,
            phone_number=clean_phone,
            customer_name=customer_name,
            reason=reason,
            urgency=clean_urgency,
            summary=summary,
            operating_hours_text=hours_text,
            status="OPEN"
        )
        mem, _ = CustomerMemory.objects.get_or_create(user=user, phone_number=clean_phone)
        wm = mem.whatsapp_memory or {}
        wm["ai_auto_reply_enabled"] = True
        wm["last_ticket_number"] = ticket.ticket_number
        mem.whatsapp_memory = wm
        if customer_name and not mem.customer_name:
            mem.customer_name = customer_name
        mem.save()

        try:
            from crm.services.evolution_client import send_whatsapp_message
            auto_msg = (
                f"نعتذر منك، فريق خدمة العملاء غير متاح حالياً ({hours_text}). "
                f"تم تسجيل تذكرة دعم برقم #{ticket.ticket_number} وسيقوم الفريق بمتابعتها. "
                f"يمكنني الاستمرار في الإجابة على استفساراتك هنا في أي وقت!"
            )
            send_whatsapp_message(clean_phone, auto_msg)
        except Exception as e:
            logger.warning(f"Could not send off-hours notification WhatsApp message: {e}")

        try:
            from crm.services.outbound_webhooks import dispatch_outbound_webhook
            dispatch_outbound_webhook(user, "whatsapp.ticket_created", {
                "ticket_number": ticket.ticket_number,
                "phone_number": clean_phone,
                "customer_name": customer_name or clean_phone,
                "reason": reason,
                "urgency": clean_urgency,
                "summary": summary,
                "operating_hours_text": hours_text,
                "status": "OPEN",
                "created_at": ticket.created_at.isoformat() if hasattr(ticket, 'created_at') else now_dt
            })
        except Exception as wh_err:
            logger.warning(f"Could not dispatch outbound webhook for ticket creation: {wh_err}")

        return {
            "status": "ticket_created",
            "action": "ticket_created",
            "ticket_number": ticket.ticket_number,
            "ticket": ticket,
            "is_operating_hours": is_open,
            "operating_hours_text": hours_text,
            "ai_auto_reply_enabled": True
        }

    # Agents online & within hours -> assign least busy
    least_busy = select_least_busy_agent(user)
    if not least_busy:
        ticket = create_support_ticket(
            user_id=user,
            phone_number=clean_phone,
            customer_name=customer_name,
            reason=reason,
            urgency=clean_urgency,
            summary=summary,
            status="OPEN"
        )
        return {
            "status": "ticket_created",
            "ticket_number": ticket.ticket_number,
            "ticket": ticket,
            "ai_auto_reply_enabled": True
        }

    now_iso = (now_dt or datetime.now(timezone.utc)).isoformat()
    agent_user_id = least_busy.user.id if least_busy.user else least_busy.id

    mem, _ = CustomerMemory.objects.get_or_create(user=user, phone_number=clean_phone)
    wm = mem.whatsapp_memory or {}
    wm["conversation_state"] = "PENDING_AGENT_REPLY"
    wm["assigned_agent_id"] = agent_user_id
    wm["ai_auto_reply_enabled"] = False
    wm["escalated_at"] = now_iso
    wm["sla_seconds"] = 120
    wm["escalation_reason"] = reason
    wm["escalation_urgency"] = clean_urgency
    wm["escalation_summary"] = summary
    mem.whatsapp_memory = wm
    if customer_name and not mem.customer_name:
        mem.customer_name = customer_name
    mem.save()

    alert_payload = {
        "event": "whatsapp_escalation_assigned",
        "phone_number": clean_phone,
        "customer_name": customer_name or mem.customer_name or clean_phone,
        "reason": reason,
        "urgency": clean_urgency,
        "summary": summary,
        "assigned_agent_id": agent_user_id,
        "conversation_state": "PENDING_AGENT_REPLY",
        "escalated_at": now_iso,
        "sla_seconds": 120,
    }
    try:
        from common.centrifugo import publish_to_centrifugo
        publish_to_centrifugo(f"user_{agent_user_id}", alert_payload)
        publish_to_centrifugo(f"tenant_{user.id}", alert_payload)
    except Exception as cent_err:
        logger.warning(f"Failed to publish Centrifugo escalation alert: {cent_err}")

    try:
        from crm.services.outbound_webhooks import dispatch_outbound_webhook
        dispatch_outbound_webhook(user, "whatsapp.escalation_assigned", alert_payload)
    except Exception as wh_err:
        logger.warning(f"Failed to dispatch outbound webhook for escalation: {wh_err}")

    return {
        "status": "success",
        "action": "assigned",
        "assigned_agent_id": agent_user_id,
        "assigned_agent": least_busy,
        "conversation_state": "PENDING_AGENT_REPLY",
        "ai_auto_reply_enabled": False,
        "sla_seconds": 120,
        "escalated_at": now_iso
    }


def is_sla_breached(memory_rec: CustomerMemory, now_dt: Optional[datetime] = None) -> bool:
    """
    Check if a conversation in PENDING_AGENT_REPLY has exceeded its SLA window.
    """
    wm = memory_rec.whatsapp_memory or {}
    if wm.get("conversation_state") != "PENDING_AGENT_REPLY":
        return False
    esc_str = wm.get("escalated_at")
    if not esc_str:
        return False
    try:
        esc_time = datetime.fromisoformat(esc_str)
        now = now_dt or datetime.now(timezone.utc)
        delta_sec = (now - esc_time).total_seconds()
        return delta_sec >= wm.get("sla_seconds", 120)
    except Exception:
        return False


def failover_breached_conversation(
    memory_rec: CustomerMemory,
    now_dt: Optional[datetime] = None
) -> Optional[EmployeeProfile]:
    """
    Reassign a breached conversation to the next available online agent.
    """
    wm = memory_rec.whatsapp_memory or {}
    current_assigned = wm.get("assigned_agent_id")
    alt_agents = get_available_agents(memory_rec.user).exclude(user_id=current_assigned)
    if not alt_agents.exists():
        return None
    new_agent = sorted(list(alt_agents), key=lambda a: (get_agent_active_count(a), a.id))[0]
    now_iso = (now_dt or datetime.now(timezone.utc)).isoformat()
    new_agent_uid = new_agent.user.id if new_agent.user else new_agent.id

    wm["assigned_agent_id"] = new_agent_uid
    wm["escalated_at"] = now_iso
    wm["failover_count"] = wm.get("failover_count", 0) + 1
    memory_rec.whatsapp_memory = wm
    memory_rec.save()

    try:
        from crm.services.evolution_client import send_whatsapp_message
        reassurance_text = (
            "عزيزي العميل، نعتذر عن التأخير البسيط في الرد. تم توجيه محادثتك فوراً لزميل آخر في فريق الدعم وسيتواصل معك الآن."
        )
        send_whatsapp_message(memory_rec.phone_number, reassurance_text)
    except Exception as e:
        logger.warning(f"Could not send reassurance WhatsApp message: {e}")

    try:
        from common.centrifugo import publish_to_centrifugo
        reassign_payload = {
            "event": "whatsapp_escalation_assigned",
            "phone_number": memory_rec.phone_number,
            "customer_name": memory_rec.customer_name or memory_rec.phone_number,
            "reason": wm.get("escalation_reason", "SLA Failover"),
            "urgency": wm.get("escalation_urgency", "urgent"),
            "summary": wm.get("escalation_summary", "Reassigned due to agent response timeout"),
            "assigned_agent_id": new_agent_uid,
            "conversation_state": "PENDING_AGENT_REPLY",
            "escalated_at": now_iso,
            "sla_seconds": 120,
            "is_failover": True
        }
        publish_to_centrifugo(f"user_{new_agent_uid}", reassign_payload)
    except Exception as cent_err:
        logger.warning(f"Failed to publish Centrifugo failover alert: {cent_err}")

    return new_agent


def claim_conversation(
    user_id: Union[int, User],
    phone_number: str,
    agent_user_id: int,
    now_dt: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Atomically claims an escalated conversation for the specific agent user.
    Transitions state to ACTIVE_SUPPORT and broadcasts claim event via Centrifugo.
    """
    uid = user_id.id if hasattr(user_id, 'id') else user_id
    user = user_id if isinstance(user_id, User) else User.objects.get(id=uid)
    clean_phone = str(phone_number).strip()

    mem, _ = CustomerMemory.objects.get_or_create(user=user, phone_number=clean_phone)
    wm = mem.whatsapp_memory or {}
    now_iso = (now_dt or datetime.now(timezone.utc)).isoformat()

    wm["conversation_state"] = "ACTIVE_SUPPORT"
    wm["assigned_agent_id"] = agent_user_id
    wm["claimed_at"] = now_iso
    wm["ai_auto_reply_enabled"] = False
    wm["sla_seconds"] = 300
    mem.whatsapp_memory = wm
    mem.save()

    claim_payload = {
        "event": "whatsapp_chat_claimed",
        "phone_number": clean_phone,
        "assigned_agent_id": agent_user_id,
        "conversation_state": "ACTIVE_SUPPORT",
        "claimed_at": now_iso
    }
    try:
        from common.centrifugo import publish_to_centrifugo
        publish_to_centrifugo(f"tenant_{user.id}", claim_payload)
        publish_to_centrifugo(f"user_{agent_user_id}", claim_payload)
    except Exception as e:
        logger.warning(f"Could not publish claim event: {e}")

    try:
        from crm.services.outbound_webhooks import dispatch_outbound_webhook
        dispatch_outbound_webhook(user, "whatsapp.conversation_claimed", claim_payload)
    except Exception as wh_err:
        logger.warning(f"Could not dispatch outbound webhook for claim: {wh_err}")

    return {
        "status": "success",
        "phone_number": clean_phone,
        "assigned_agent_id": agent_user_id,
        "conversation_state": "ACTIVE_SUPPORT",
        "claimed_at": now_iso
    }


def release_conversation_to_pool(
    user_id: Union[int, User],
    phone_number: str,
    reason: str = "Unassigned / Timeout",
    now_dt: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Releases a claimed conversation back into the shared ringing queue.
    """
    uid = user_id.id if hasattr(user_id, 'id') else user_id
    user = user_id if isinstance(user_id, User) else User.objects.get(id=uid)
    clean_phone = str(phone_number).strip()

    mem, _ = CustomerMemory.objects.get_or_create(user=user, phone_number=clean_phone)
    wm = mem.whatsapp_memory or {}
    now_iso = (now_dt or datetime.now(timezone.utc)).isoformat()

    wm["conversation_state"] = "PENDING_AGENT_REPLY"
    wm["assigned_agent_id"] = None
    wm["escalated_at"] = now_iso
    wm["sla_seconds"] = 300
    wm["released_at"] = now_iso
    wm["release_reason"] = reason
    mem.whatsapp_memory = wm
    mem.save()

    alert_payload = {
        "event": "whatsapp_escalation_assigned",
        "phone_number": clean_phone,
        "customer_name": mem.customer_name or clean_phone,
        "reason": wm.get("escalation_reason", reason),
        "urgency": wm.get("escalation_urgency", "urgent"),
        "summary": wm.get("escalation_summary", "Re-entered broadcast queue"),
        "assigned_agent_id": None,
        "conversation_state": "PENDING_AGENT_REPLY",
        "escalated_at": now_iso,
        "sla_seconds": 300,
    }
    try:
        from common.centrifugo import publish_to_centrifugo
        publish_to_centrifugo(f"tenant_{user.id}", alert_payload)
    except Exception as e:
        logger.warning(f"Could not publish release event: {e}")

    try:
        from crm.services.outbound_webhooks import dispatch_outbound_webhook
        dispatch_outbound_webhook(user, "whatsapp.conversation_released", alert_payload)
    except Exception as wh_err:
        logger.warning(f"Could not dispatch outbound webhook for release: {wh_err}")

    return {
        "status": "success",
        "phone_number": clean_phone,
        "conversation_state": "PENDING_AGENT_REPLY",
        "assigned_agent_id": None
    }


def resolve_conversation(
    user_id: Union[int, User],
    phone_number: str,
    resolution_notes: str = "",
    resolution_status: str = "RESOLVED",
    now_dt: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Resolves an active support conversation:
    - Sets conversation_state = resolution_status ('RESOLVED')
    - Reactivates AI auto-reply: ai_auto_reply_enabled = True
    - Saves resolution notes and timestamp in CustomerMemory
    - Synchronizes any OPEN CRMSupportTicket for this phone to RESOLVED
    - Broadcasts Centrifugo resolution event
    - Dispatches outbound webhook event whatsapp.conversation_resolved
    """
    uid = user_id.id if hasattr(user_id, 'id') else user_id
    user = user_id if isinstance(user_id, User) else User.objects.get(id=uid)
    clean_phone = str(phone_number).strip()

    mem, _ = CustomerMemory.objects.get_or_create(user=user, phone_number=clean_phone)
    wm = mem.whatsapp_memory or {}
    now_iso = (now_dt or datetime.now(timezone.utc)).isoformat()

    prev_assigned = wm.get("assigned_agent_id")
    wm["conversation_state"] = resolution_status
    wm["ai_auto_reply_enabled"] = True
    wm["resolution_notes"] = resolution_notes
    wm["resolved_at"] = now_iso
    wm["sla_breached"] = False
    mem.whatsapp_memory = wm
    mem.save()

    from crm.models import CRMSupportTicket
    from django.utils import timezone as dj_timezone
    CRMSupportTicket.objects.filter(
        user=user,
        customer_phone=clean_phone,
        status="OPEN"
    ).update(
        status="RESOLVED",
        resolution_notes=resolution_notes,
        resolved_at=dj_timezone.now()
    )

    resolve_payload = {
        "event": "whatsapp_chat_resolved",
        "phone_number": clean_phone,
        "conversation_state": resolution_status,
        "ai_auto_reply_enabled": True,
        "resolved_at": now_iso,
        "resolution_notes": resolution_notes
    }
    try:
        from common.centrifugo import publish_to_centrifugo
        publish_to_centrifugo(f"tenant_{user.id}", resolve_payload)
        if prev_assigned:
            publish_to_centrifugo(f"user_{prev_assigned}", resolve_payload)
    except Exception as e:
        logger.warning(f"Could not publish resolve event: {e}")

    try:
        from crm.services.outbound_webhooks import dispatch_outbound_webhook
        dispatch_outbound_webhook(user, "whatsapp.conversation_resolved", resolve_payload)
    except Exception as wh_err:
        logger.warning(f"Could not dispatch outbound webhook for resolve: {wh_err}")

    return {
        "status": "success",
        "phone_number": clean_phone,
        "ai_auto_reply_enabled": True,
        "conversation_state": resolution_status,
        "resolved_at": now_iso
    }



