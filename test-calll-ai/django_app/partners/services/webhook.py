import json
import hmac
import hashlib
import logging
import threading
import requests

logger = logging.getLogger(__name__)


def _send_webhook_sync(url: str, secret: str, payload: dict) -> tuple[bool, int]:
    """Synchronously send signed webhook HTTP request."""
    try:
        data_bytes = json.dumps(payload, separators=(',', ':'), default=str).encode('utf-8')
        signature = hmac.new(secret.encode('utf-8'), data_bytes, hashlib.sha256).hexdigest()
        headers = {
            'Content-Type': 'application/json',
            'X-Signature': f"sha256={signature}",
            'User-Agent': 'Voice-AI-Partner-Platform/1.0',
        }
        res = requests.post(url, data=data_bytes, headers=headers, timeout=6)
        logger.info(f"Webhook dispatched to {url} [Event: {payload.get('event')}] - Status: {res.status_code}")
        return (res.status_code < 400, res.status_code)
    except Exception as e:
        logger.warning(f"Failed to dispatch webhook to {url}: {e}")
        return (False, 0)


def _send_webhook_async(url: str, secret: str, payload: dict):
    _send_webhook_sync(url, secret, payload)


def dispatch_partner_webhook(partner, event: str, data: dict):
    """
    Dispatches a signed webhook to the partner's configured webhook_url.
    Prefers Inngest durable queue with automatic retries, with fallback to background thread.
    """
    if not partner or not partner.webhook_url:
        return

    payload = {
        "event": event,
        "partner_code": partner.partner_code,
        "timestamp": data.get("timestamp") or "",
        "data": data,
    }
    secret = partner.webhook_secret or partner.api_key or ''

    # 1. Try Inngest for guaranteed durable delivery and retries
    try:
        import inngest
        from asgiref.sync import async_to_sync
        from common.inngest_client import inngest_client

        async_to_sync(inngest_client.send)(
            inngest.Event(
                name="partner/webhook.send",
                data={
                    "url": partner.webhook_url,
                    "secret": secret,
                    "payload": payload,
                }
            )
        )
        return
    except Exception as inngest_err:
        logger.debug(f"Inngest dispatch unavailable for webhook ({inngest_err}), falling back to background thread.")

    # 2. Fallback to background thread
    t = threading.Thread(
        target=_send_webhook_async,
        args=(partner.webhook_url, secret, payload),
        daemon=True
    )
    t.start()
