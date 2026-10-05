"""Wazo SIP Blind Transfer Implementation via LiveKit SIP REFER."""
import asyncio
from typing import Dict, Any, Optional
from livekit import api
from agent.config import (
    logger,
    LIVEKIT_INTERNAL_URL,
    LIVEKIT_API_KEY,
    LIVEKIT_API_SECRET,
    WAZO_SIP_HOST,
    WAZO_SIP_PORT,
)
from agent.clients.centrifugo_client import notify_centrifugo_async


async def execute_wazo_sip_blind_transfer(
    room_name: str,
    user_id: int,
    queue_code: str,
    caller_phone: str = "web",
    caller_name: str = "العميل",
    reason: str = "",
    target_participant_identity: Optional[str] = None
) -> bool:
    """
    Executes a pure, immediate Blind Transfer (SIP REFER) to Wazo Call Queue.
    Sends SIP REFER to Wazo with 'sip:<queue_code>@<WAZO_HOST>:<WAZO_PORT>',
    allowing Asterisk in Wazo to pull the caller into the queue natively.
    """
    channel_name = f"rooms:{room_name}"
    transfer_uri = f"sip:{queue_code}@{WAZO_SIP_HOST}:{WAZO_SIP_PORT}"
    logger.info(f"[WAZO SIP TRANSFER] Initiating Blind Transfer (REFER) for room '{room_name}' to '{transfer_uri}' (reason: {reason})")

    await notify_centrifugo_async(
        channel_name,
        "agent_transferring",
        f"جاري تحويل المكالمة إلى طابور {queue_code} في سنترال Wazo..."
    )

    lk = api.LiveKitAPI(LIVEKIT_INTERNAL_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        # 1. Resolve target participant identity if not provided
        part_identity = target_participant_identity
        if not part_identity:
            try:
                parts_res = await lk.room.list_participants(api.ListParticipantsRequest(room=room_name))
                for p in parts_res.participants:
                    if not p.identity.startswith("ai-") and not p.identity.startswith("transfer-"):
                        part_identity = p.identity
                        break
            except Exception as e:
                logger.warning(f"[WAZO SIP TRANSFER] Error listing participants in room {room_name}: {e}")

        if not part_identity:
            part_identity = f"sip_{caller_phone}" if caller_phone else "customer"

        logger.info(f"[WAZO SIP TRANSFER] Sending SIP REFER for participant '{part_identity}' to '{transfer_uri}'")

        # 2. Issue LiveKit SIP Transfer (Blind Transfer / REFER)
        req = api.TransferSIPParticipantRequest(
            participant_identity=part_identity,
            room_name=room_name,
            transfer_to=transfer_uri,
            play_dialtone=False
        )
        await lk.sip.transfer_sip_participant(req)

        await notify_centrifugo_async(
            channel_name,
            "agent_transferred_to_wazo",
            f"تم إرسال أمر التحويل بنجاح إلى طابور {queue_code}."
        )
        logger.info(f"[WAZO SIP TRANSFER] SIP REFER sent successfully for '{part_identity}' to '{transfer_uri}'")
        return True

    except Exception as ex:
        logger.error(f"[WAZO SIP TRANSFER] Failed to execute SIP REFER: {ex}", exc_info=True)
        await notify_centrifugo_async(
            channel_name,
            "agent_error",
            f"تعذر تنفيذ تحويل المكالمة في السنترال: {str(ex)}"
        )
        return False
    finally:
        await lk.aclose()


# Backward-compatible alias for existing callers
execute_ai_transfer_and_hold = execute_wazo_sip_blind_transfer


async def handle_webrtc_transfer_session(data: Dict[str, Any]) -> bool:
    """
    Adapter for transfer events originating from Redis/WebRTC.
    Delegates to pure SIP Blind Transfer to Wazo PBX call queue.
    """
    room_name = data.get("room_name", "")
    target = data.get("target") or data.get("queue_code") or data.get("queue_id", "200")
    user_id = data.get("from_user") or data.get("user_id") or 0
    caller_phone = data.get("caller_phone", "web")
    caller_name = data.get("caller_name", "العميل")
    reason = data.get("reason", "Manual or automated transfer request")
    participant_identity = data.get("participant_identity")

    return await execute_wazo_sip_blind_transfer(
        room_name=room_name,
        user_id=int(user_id) if str(user_id).isdigit() else 0,
        queue_code=str(target),
        caller_phone=caller_phone,
        caller_name=caller_name,
        reason=reason,
        target_participant_identity=participant_identity
    )

