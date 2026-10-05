"""Inngest Client for sending background audit events from Voice Agent."""
import asyncio
from config import INNGEST_EVENT_URL, logger
from .http_pool import get_http_session


async def emit_inngest_event_async(event_name: str, data: dict):
    """Fire-and-forget event emission to Inngest Event API."""
    try:
        session = await get_http_session()
        payload = {
            "name": event_name,
            "data": data
        }
        async with session.post(INNGEST_EVENT_URL, json=payload, timeout=2.0) as resp:
            if resp.status == 200:
                logger.debug(f"[Inngest] Successfully emitted event '{event_name}'")
            else:
                text = await resp.text()
                logger.warning(f"[Inngest] Event emission returned status {resp.status}: {text}")
    except Exception as e:
        logger.warning(f"[Inngest] Failed to emit event '{event_name}': {e}")


def dispatch_tool_log_to_inngest(data: dict):
    """Dispatch tool execution log event in background non-blocking task."""
    try:
        asyncio.create_task(emit_inngest_event_async("agent/tool.executed", data))
    except Exception as e:
        logger.warning(f"[Inngest] Error scheduling tool log event: {e}")
