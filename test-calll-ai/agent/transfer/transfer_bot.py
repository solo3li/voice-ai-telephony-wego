"""AI Call Transfer & WebRTC Hold Music Bot."""
import asyncio
import time
from typing import Dict, Any
from livekit import api, rtc
from agent.config import logger, LIVEKIT_INTERNAL_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
from agent.clients.centrifugo_client import notify_centrifugo_async
from agent.clients.django_client import trigger_ai_transfer_async
from agent.queue_manager import HOLD_CHIME_FRAMES, play_hold_audio_loop


async def execute_ai_transfer_and_hold(
    room_name: str,
    user_id: int,
    queue_code: str,
    caller_phone: str = "web",
    caller_name: str = "العميل",
    reason: str = ""
):
    """
    Executes AI transfer:
    1. Triggers Inngest call transfer in Django asynchronously.
    2. Connects a transfer hold bot into room_name to play calming hold chime.
    3. Exits as soon as an employee answers and joins the room.
    """
    logger.info(f"[AI TRANSFER] Starting AI transfer for room '{room_name}' to queue '{queue_code}' (caller: {caller_phone})")

    # 1. Trigger Django API to dispatch Inngest
    res = await trigger_ai_transfer_async(room_name, user_id, queue_code, caller_phone, caller_name, reason)
    logger.info(f"[AI TRANSFER] Django transfer response: {res}")

    # 2. Connect transfer-bot to play hold music to customer
    token = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET) \
        .with_identity("transfer-bot") \
        .with_name("نغمة الانتظار") \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
        ))
    bot_jwt = token.to_jwt()

    room = rtc.Room()
    stop_hold_event = asyncio.Event()
    hold_playback_task = None

    try:
        await room.connect(LIVEKIT_INTERNAL_URL, bot_jwt)
        logger.info(f"[AI TRANSFER] Transfer hold bot connected to room '{room_name}' to play chime")

        audio_source = rtc.AudioSource(sample_rate=24000, num_channels=1)
        audio_track = rtc.LocalAudioTrack.create_audio_track("transfer-hold-audio", audio_source)
        publish_options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
        await room.local_participant.publish_track(audio_track, publish_options)

        hold_playback_task = asyncio.create_task(play_hold_audio_loop(audio_source, stop_hold_event, HOLD_CHIME_FRAMES))

        # 3. Wait until human employee answers and joins room or customer leaves
        start_time = time.time()
        max_wait = 330  # Support up to 5.5 minutes of queue hold music
        MIN_HOLD_SECONDS = 2.0  # Guard: ensure audio track is fully negotiated before polling

        while (time.time() - start_time) < max_wait:
            elapsed = time.time() - start_time

            # Always honour the minimum hold time so the WebRTC negotiation fully
            # completes before we check for participants (fixes the race condition
            # where Inngest dispatches an employee faster than publish_track settles).
            if elapsed < MIN_HOLD_SECONDS:
                await asyncio.sleep(0.1)
                continue

            remote_parts = list(room.remote_participants.values())
            customer_present = any(
                not p.identity.startswith("transfer-")
                and not p.identity.startswith("queue-")
                and not p.identity.startswith("agent_")
                and not p.identity.startswith("ai-")
                and not p.identity.startswith("pipecat-")
                for p in remote_parts
            )
            if room.connection_state == rtc.ConnectionState.CONN_CONNECTED and not customer_present and len(remote_parts) == 0:
                logger.info(f"[AI TRANSFER] Customer left room '{room_name}'. Ending hold bot.")
                break

            employee_answered = any(
                p.identity.startswith("employee_")
                for p in remote_parts
            )
            if employee_answered:
                logger.info(f"[AI TRANSFER] Human employee answered and joined room '{room_name}'! Stopping hold bot.")
                break

            await asyncio.sleep(0.5)

    except Exception as e:
        logger.error(f"[AI TRANSFER] Error in transfer hold bot: {e}")
    finally:
        stop_hold_event.set()
        if hold_playback_task:
            hold_playback_task.cancel()
        try:
            await room.disconnect()
        except Exception:
            pass
        logger.info(f"[AI TRANSFER] Transfer hold bot disconnected from room '{room_name}'.")


async def handle_webrtc_transfer_session(data: Dict[str, Any]):
    """
    Handle WebRTC Call Transfer:
    1. Connect hold audio bot to room so the customer hears pleasant hold music.
    2. Ring target employee or queue.
    3. If target answers within 15s -> bot disconnects and target connects to customer.
    4. If target does NOT answer -> Ring back to original employee so customer is not lost.
    """
    room_name = data.get("room_name")
    from_user = str(data.get("from_user", ""))
    from_name = data.get("from_name", f"موظف {from_user}")
    from_employee_id = data.get("from_employee_id")
    target = str(data.get("target", ""))
    target_type = data.get("target_type", "employee")
    target_id = data.get("target_id")
    target_name = data.get("target_name", f"تحويلة {target}")

    logger.info(f"[TRANSFER SESSION] Starting transfer for room '{room_name}': '{from_name}' ({from_user}) -> '{target_name}' ({target})")

    # 1. Connect hold audio bot to room
    token = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET) \
        .with_identity("transfer-bot") \
        .with_name("نغمة الانتظار - تحويل المكالمة") \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
        ))
    bot_jwt = token.to_jwt()

    room = rtc.Room()
    stop_hold_event = asyncio.Event()
    hold_playback_task = None

    try:
        await room.connect(LIVEKIT_INTERNAL_URL, bot_jwt)
        logger.info(f"[TRANSFER SESSION] Transfer bot connected to room '{room_name}' to play hold music")

        audio_source = rtc.AudioSource(sample_rate=24000, num_channels=1)
        audio_track = rtc.LocalAudioTrack.create_audio_track("transfer-hold-audio", audio_source)
        publish_options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
        await room.local_participant.publish_track(audio_track, publish_options)

        hold_playback_task = asyncio.create_task(play_hold_audio_loop(audio_source, stop_hold_event, HOLD_CHIME_FRAMES))
    except Exception as e:
        logger.error(f"[TRANSFER SESSION] Error connecting transfer hold bot: {e}")

    # 2. Ring target employee or queue
    channels_to_notify = []
    if target_type == "queue":
        channels_to_notify.append("queues:broadcast")
    else:
        if target_id:
            channels_to_notify.append(f"employee:{target_id}")
        if target:
            channels_to_notify.append(f"employee:{target}")

    for ch in channels_to_notify:
        await notify_centrifugo_async(
            ch,
            "incoming_call",
            f"مكالمة محولة من {from_name} ({from_user})",
            {
                "room_name": room_name,
                "call_id": room_name,
                "caller_name": f"محولة من {from_name} ({from_user})",
                "caller_extension": from_user,
                "caller_department": "مكالمة محولة",
                "call_type": "transfer",
                "original_employee_id": from_employee_id,
                "original_extension": from_user
            }
        )

    # 3. Wait up to 15s for target to answer
    timeout_seconds = 15
    start_time = time.time()
    target_answered = False

    while (time.time() - start_time) < timeout_seconds:
        remote_parts = list(room.remote_participants.values())
        # Check if customer hung up
        customer_present = any(
            not p.identity.startswith("transfer-")
            and not p.identity.startswith("queue-")
            and p.identity != f"employee_{from_employee_id}_{from_user}"
            for p in remote_parts
        )
        if room.connection_state == rtc.ConnectionState.CONN_CONNECTED and not customer_present and len(remote_parts) == 0:
            logger.info(f"[TRANSFER SESSION] Customer left room '{room_name}'. Ending transfer.")
            break

        # Check if target employee answered
        for p in remote_parts:
            if (target_id and p.identity.startswith(f"employee_{target_id}_")) or (target and p.identity.endswith(f"_{target}")):
                logger.info(f"[TRANSFER SESSION] Target employee answered and joined room '{room_name}' (identity={p.identity})!")
                target_answered = True
                break

        if target_answered:
            break

        await asyncio.sleep(0.5)

    # 4. If target answered -> disconnect hold bot cleanly
    if target_answered:
        logger.info(f"[TRANSFER SESSION] Transfer completed successfully to '{target}' in room '{room_name}'.")
        stop_hold_event.set()
        if hold_playback_task:
            hold_playback_task.cancel()
        try:
            await room.disconnect()
        except Exception:
            pass
        return

    # 5. If target did NOT answer -> Ring Back to Original Employee!
    logger.info(f"[TRANSFER SESSION] Target '{target}' did not answer within {timeout_seconds}s. Initiating RING-BACK to '{from_name}' ({from_user}).")

    # Cancel ringing on target employee
    for ch in channels_to_notify:
        await notify_centrifugo_async(
            ch,
            "call_ended",
            "انتهت مهلة تحويل المكالمة",
            {"room_name": room_name, "ended_by": "timeout"}
        )

    # Check if customer is still in room before ringing back
    remote_parts = list(room.remote_participants.values())
    customer_present = any(
        not p.identity.startswith("transfer-")
        and not p.identity.startswith("queue-")
        for p in remote_parts
    )
    if not customer_present:
        logger.info(f"[TRANSFER SESSION] Customer already left room '{room_name}'. Ending transfer.")
        stop_hold_event.set()
        if hold_playback_task:
            hold_playback_task.cancel()
        try:
            await room.disconnect()
        except Exception:
            pass
        return

    # Send Ring Back notification to original employee
    ring_back_channels = []
    if from_employee_id:
        ring_back_channels.append(f"employee:{from_employee_id}")
    if from_user:
        ring_back_channels.append(f"employee:{from_user}")

    for ch in ring_back_channels:
        await notify_centrifugo_async(
            ch,
            "incoming_call",
            f"استرجاع: {target_name} لم يرد على التحويل",
            {
                "room_name": room_name,
                "call_id": room_name,
                "caller_name": f"استرجاع: لم يرد {target_name} ({target})",
                "caller_extension": str(target),
                "caller_department": "فشل التحويل",
                "call_type": "ring_back"
            }
        )

    # Wait for original employee to re-join (up to 20s)
    rb_start = time.time()
    while (time.time() - rb_start) < 20:
        remote_parts = list(room.remote_participants.values())
        if any(
            (from_employee_id and p.identity.startswith(f"employee_{from_employee_id}_"))
            or (from_user and p.identity.endswith(f"_{from_user}"))
            for p in remote_parts
        ):
            logger.info(f"[TRANSFER SESSION] Original employee '{from_name}' re-joined room '{room_name}' after ring back!")
            break
        await asyncio.sleep(0.5)

    # Cleanup bot
    stop_hold_event.set()
    if hold_playback_task:
        hold_playback_task.cancel()
    try:
        await room.disconnect()
    except Exception:
        pass
    logger.info(f"[TRANSFER SESSION] Transfer session finished for room '{room_name}'.")
