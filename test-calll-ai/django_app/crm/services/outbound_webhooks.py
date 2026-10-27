import json
import hmac
import hashlib
import logging
import threading
import datetime
import requests
from typing import Optional, Dict, Any
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


def _send_signed_post(url: str, secret: str, payload: dict, timeout: float = 6.0) -> tuple[bool, int]:
    """Synchronously send signed webhook HTTP POST request."""
    try:
        data_bytes = json.dumps(payload, separators=(',', ':'), default=str).encode('utf-8')
        signature = hmac.new(secret.encode('utf-8'), data_bytes, hashlib.sha256).hexdigest()
        headers = {
            'Content-Type': 'application/json',
            'X-Signature': f"sha256={signature}",
            'User-Agent': 'Voice-AI-Platform/1.0',
        }
        res = requests.post(url, data=data_bytes, headers=headers, timeout=timeout)
        logger.info(f"Outbound webhook dispatched to {url} [Event: {payload.get('event')}] - Status: {res.status_code}")
        return (res.status_code < 400, res.status_code)
    except Exception as e:
        logger.warning(f"Failed to dispatch outbound webhook to {url}: {e}")
        return (False, 0)


def dispatch_outbound_webhook(user: User, event: str, payload: Dict[str, Any], sync: bool = False):
    """
    Dispatches outbound webhook to:
    1. Developer webhook endpoint (if UserWebhookEndpoint is active for this user).
    2. Partner webhook endpoint (if user is a sub-client in PartnerClientRelationship, or partner user).
    """
    if not user:
        return

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 1. Developer Webhook
    try:
        from developer.models import UserWebhookEndpoint
        dev_endpoint = UserWebhookEndpoint.objects.filter(user=user, is_active=True).first()
        if dev_endpoint and dev_endpoint.url:
            dev_payload = {
                "event": event,
                "timestamp": now_iso,
                "user_id": user.id,
                "data": payload
            }
            sec = dev_endpoint.secret or ""
            if sync:
                _send_signed_post(dev_endpoint.url, sec, dev_payload)
            else:
                threading.Thread(
                    target=_send_signed_post,
                    args=(dev_endpoint.url, sec, dev_payload),
                    daemon=True
                ).start()
    except Exception as dev_err:
        logger.warning(f"Error checking developer webhook for user {user.id}: {dev_err}")

    # 2. Partner Webhook (if user is a client of a partner)
    try:
        from partners.models import PartnerClientRelationship, PartnerProfile
        # Check if user is a sub-client
        rel = PartnerClientRelationship.objects.select_related('partner').filter(client=user).first()
        if rel and rel.partner and rel.partner.webhook_url:
            partner = rel.partner
            partner_payload = {
                "event": event,
                "partner_code": partner.partner_code,
                "client_id": rel.client_id,
                "external_reference": rel.external_reference or "",
                "timestamp": now_iso,
                "data": payload
            }
            sec = partner.webhook_secret or partner.api_key or ""
            if sync:
                _send_signed_post(partner.webhook_url, sec, partner_payload)
            else:
                threading.Thread(
                    target=_send_signed_post,
                    args=(partner.webhook_url, sec, partner_payload),
                    daemon=True
                ).start()
        else:
            # Check if user is the partner himself
            partner = PartnerProfile.objects.filter(user=user).first()
            if partner and partner.webhook_url:
                partner_payload = {
                    "event": event,
                    "partner_code": partner.partner_code,
                    "timestamp": now_iso,
                    "data": payload
                }
                sec = partner.webhook_secret or partner.api_key or ""
                if sync:
                    _send_signed_post(partner.webhook_url, sec, partner_payload)
                else:
                    threading.Thread(
                        target=_send_signed_post,
                        args=(partner.webhook_url, sec, partner_payload),
                        daemon=True
                    ).start()
    except Exception as prt_err:
        logger.warning(f"Error checking partner webhook for user {user.id}: {prt_err}")
