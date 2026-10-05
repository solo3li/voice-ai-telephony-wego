import time
import asyncio
import requests
from config import CENTRIFUGO_HTTP_API_URL, CENTRIFUGO_API_KEY, logger
from .http_pool import get_http_session

def _build_payload(channel: str, event: str, message: str = "", extra: dict = None) -> dict:
    if isinstance(event, dict):
        extra_data = event
        event_name = extra_data.get("event", "notification")
        msg = extra_data.get("message", message or "")
    else:
        event_name = event
        msg = message or ""
        extra_data = extra or {}

    return {
        "channel": channel,
        "data": {
            "event": event_name,
            "message": msg,
            "timestamp": time.time(),
            **extra_data
        }
    }

async def notify_centrifugo_async(channel: str, event: str, message: str = "", extra: dict = None):
    """Publish real-time event to Centrifugo WebSocket non-blockingly via shared aiohttp pool."""
    payload = _build_payload(channel, event, message, extra)
    headers = {
        "Authorization": f"apikey {CENTRIFUGO_API_KEY}",
        "Content-Type": "application/json"
    }
    url = f"{CENTRIFUGO_HTTP_API_URL}/publish"
    try:
        session = await get_http_session()
        async with session.post(url, json=payload, headers=headers, timeout=2.0) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.warning(f"Centrifugo async publish returned status {resp.status}: {text}")
    except Exception as e:
        logger.debug(f"Failed to publish to Centrifugo asynchronously: {e}")

def notify_centrifugo(channel: str, event: str, message: str = "", extra: dict = None):
    """
    Publish event to Centrifugo. If called from inside a running async loop, schedules
    a non-blocking task so the audio stream event loop is NEVER frozen!
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(notify_centrifugo_async(channel, event, message, extra))
    except RuntimeError:
        # Fallback for synchronous CLI scripts or offline unit tests
        try:
            url = f"{CENTRIFUGO_HTTP_API_URL}/publish"
            payload = _build_payload(channel, event, message, extra)
            headers = {
                "Authorization": f"apikey {CENTRIFUGO_API_KEY}",
                "Content-Type": "application/json"
            }
            requests.post(url, json=payload, headers=headers, timeout=2)
        except Exception as e:
            logger.debug(f"Sync fallback Centrifugo publish failed: {e}")
