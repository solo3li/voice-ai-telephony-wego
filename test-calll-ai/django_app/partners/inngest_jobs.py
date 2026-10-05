import logging
import inngest
from asgiref.sync import sync_to_async
from common.inngest_client import inngest_client
from .services.webhook import _send_webhook_sync

logger = logging.getLogger(__name__)


@inngest_client.create_function(
    fn_id="send-partner-webhook",
    name="Send Partner Webhook",
    trigger=inngest.TriggerEvent(event="partner/webhook.send"),
    retries=3,
)
async def fn_send_partner_webhook(ctx: inngest.Context) -> dict:
    """Inngest background job to reliably dispatch signed partner webhooks with retries."""
    url = ctx.event.data.get("url")
    secret = ctx.event.data.get("secret")
    payload = ctx.event.data.get("payload")

    if not url or not payload:
        logger.warning("[Inngest Partner Webhook] Missing url or payload, skipping.")
        return {"status": "skipped", "reason": "missing url or payload"}

    success, status_code = await sync_to_async(_send_webhook_sync)(url, secret or '', payload)
    if not success and status_code >= 500:
        raise Exception(f"Webhook delivery to {url} failed with server error {status_code}; triggering Inngest retry.")

    return {"status": "dispatched" if success else "failed", "status_code": status_code}


all_partner_inngest_functions = [fn_send_partner_webhook]
