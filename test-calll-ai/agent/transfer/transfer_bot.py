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
    REDIS_URL,
)
import redis.asyncio as aioredis
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
    sip_host = WAZO_SIP_HOST
    # Asterisk inside docker listens on 5060; 5070 is only exposed externally on the host
    if sip_host in ("asterisk", "wazo-docker-asterisk-1", "voice_sip", "127.0.0.1") or not sip_host:
        sip_port = 5060
    else:
        sip_port = WAZO_SIP_PORT
    transfer_uri = f"sip:{queue_code}@{sip_host}:{sip_port}"
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
                sip_candidates = [
                    p.identity for p in parts_res.participants
                    if p.identity.startswith("sip_")
                ]
                if caller_phone and f"sip_{caller_phone}" in sip_candidates:
                    part_identity = f"sip_{caller_phone}"
                elif sip_candidates:
                    part_identity = sip_candidates[0]
                else:
                    for p in parts_res.participants:
                        ident = p.identity or ""
                        if not ident.startswith(("ai-", "transfer-", "queue-", "EG_", "egress-", "recorder-", "pipecat-")):
                            part_identity = ident
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

        # 3. Stop active LiveKit Egress recording for this room immediately so AI recording stops cleanly without trailing silence
        try:
            active_egresses = await lk.egress.list_egress(api.ListEgressRequest(room_name=room_name, active=True))
            if active_egresses and active_egresses.items:
                for eg in active_egresses.items:
                    logger.info(f"[WAZO SIP TRANSFER] Stopping active egress {eg.egress_id} for room '{room_name}' upon transfer")
                    await lk.egress.stop_egress(api.StopEgressRequest(egress_id=eg.egress_id))
            else:
                logger.info(f"[WAZO SIP TRANSFER] No active egress found to stop for room '{room_name}'")
        except Exception as eg_err:
            logger.warning(f"[WAZO SIP TRANSFER] Could not stop egress for room '{room_name}': {eg_err}")

        # 4. Store transfer mapping in Redis so Asterisk Hangup CDR can link the human recording back to this CallSession
        try:
            r_client = aioredis.from_url(REDIS_URL, decode_responses=True)
            await r_client.set(f"ai_transfer_room:{room_name}", queue_code, ex=3600)
            clean_caller = (caller_phone or "").lstrip("+").strip()
            if clean_caller:
                await r_client.set(f"ai_transfer_caller:{clean_caller}", room_name, ex=3600)
                await r_client.set(f"ai_transfer_caller:{caller_phone}", room_name, ex=3600)
            if part_identity:
                await r_client.set(f"ai_transfer_caller:{part_identity}", room_name, ex=3600)
                if part_identity.startswith("sip_"):
                    await r_client.set(f"ai_transfer_caller:{part_identity[4:]}", room_name, ex=3600)
            await r_client.aclose()
            logger.info(f"[WAZO SIP TRANSFER] Stored transfer mapping in Redis for room '{room_name}' and caller '{caller_phone}'")
        except Exception as r_err:
            logger.warning(f"[WAZO SIP TRANSFER] Failed to record transfer state in Redis: {r_err}")

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

