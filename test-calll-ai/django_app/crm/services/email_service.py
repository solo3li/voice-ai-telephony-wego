"""Email Communication Service for Post-Call Follow-ups and Notifications."""
import logging
from typing import Dict, Any, Optional
from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth.models import User
from agents.models import DigitalCoworkerConfig
from crm.models import CustomerMemory, CustomerChannelIdentifier, OmnichannelMessage

logger = logging.getLogger(__name__)


def send_followup_email(
    to_email: str,
    subject: str,
    body: str,
    tenant_user: User,
    customer_phone: str = ""
) -> Dict[str, Any]:
    """Send official email follow-up and record in OmnichannelMessage audit trail."""
    if not to_email or not subject or not body:
        return {"status": "failed", "error": "Missing recipient, subject, or body"}

    coworker_cfg = DigitalCoworkerConfig.get_or_create_config(tenant_user)
    sender_name = coworker_cfg.email_sender_name or coworker_cfg.coworker_name or tenant_user.username
    sender_email = getattr(settings, 'DEFAULT_FROM_EMAIL', f"{tenant_user.username}@voice.local")
    from_header = f"{sender_name} <{sender_email}>"

    # Resolve or link CustomerMemory
    mem = None
    if customer_phone:
        mem = CustomerMemory.objects.filter(user=tenant_user, phone_number=customer_phone).first()

    if mem:
        CustomerChannelIdentifier.objects.get_or_create(
            customer_memory=mem,
            channel='email',
            identifier=to_email.strip().lower()
        )

    send_status = "delivered"
    error_msg = ""
    try:
        # Django email backend (supports SMTP / Console / In-memory)
        send_mail(
            subject=subject,
            message=body,
            from_email=from_header,
            recipient_list=[to_email.strip().lower()],
            fail_silently=False
        )
        logger.info(f"[Email Service] Sent follow-up email to {to_email} (Subject: {subject})")
    except Exception as e:
        send_status = "failed"
        error_msg = str(e)
        logger.warning(f"[Email Service] Failed to send email to {to_email}: {e}")

    # Log in OmnichannelMessage audit trail
    msg_obj = OmnichannelMessage.objects.create(
        user=tenant_user,
        customer_memory=mem,
        channel='email',
        direction='outbound',
        sender=from_header,
        recipient=to_email.strip().lower(),
        content=f"Subject: {subject}\n\n{body}",
        metadata={"subject": subject, "error": error_msg},
        status=send_status
    )

    return {
        "status": "success" if send_status == "delivered" else "failed",
        "message_id": msg_obj.id,
        "recipient": to_email,
        "error": error_msg
    }


def send_email_followup(*args, **kwargs):
    """Alias for send_followup_email handling both parameter naming styles."""
    if 'recipient_email' in kwargs:
        kwargs['to_email'] = kwargs.pop('recipient_email')
    return send_followup_email(*args, **kwargs)
