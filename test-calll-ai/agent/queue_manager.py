"""Queue Manager delegator for Headless Wazo PBX."""
import asyncio
import logging
from typing import Optional, Dict, Any
from agent.transfer.transfer_bot import execute_wazo_sip_blind_transfer

logger = logging.getLogger("QueueManager")


async def run_queue_session(*args, **kwargs):
    """
    Headless Wazo Queue session.
    Directly transfers the incoming call to Wazo Asterisk Queue via SIP REFER.
    """
    room_name = kwargs.get("room_name") or (args[0] if args else "")
    user_id = kwargs.get("user_id") or (args[1] if len(args) > 1 else None)
    caller_phone = kwargs.get("caller_phone") or (args[2] if len(args) > 2 else "web")
    queue_data = kwargs.get("queue_data") or {}
    queue_code = str(queue_data.get("code") or "200")

    logger.info(f"[QueueManager] Delegating queue session in room '{room_name}' to Wazo Queue '{queue_code}'")
    await execute_wazo_sip_blind_transfer(
        room_name=room_name,
        user_id=user_id or 1,
        queue_code=queue_code,
        caller_phone=caller_phone,
        reason="Call routed to queue"
    )
