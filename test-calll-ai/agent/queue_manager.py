import asyncio
import os
import time
import math
import wave
import struct
import logging
import inspect
import redis
from livekit import rtc, api

logger = logging.getLogger("QueueManager")

async def _redis_exec(coro):
    if coro is not None and inspect.isawaitable(coro):
        return await coro
    return coro

def generate_hold_chime_frames(sample_rate=24000, frame_duration_ms=20, total_duration_s=4.0):
    """
    Generate smooth, calming harmonic chords (C major chord: 523Hz, 659Hz, 784Hz)
    fading in and out in 24kHz 16-bit mono PCM frames.
    """
    samples_per_frame = int(sample_rate * (frame_duration_ms / 1000.0))
    total_samples = int(sample_rate * total_duration_s)
    frames = []

    # Frequencies for pleasant chord: C5 (523.25), E5 (659.25), G5 (783.99)
    freqs = [523.25, 659.25, 783.99]

    pcm_data = bytearray()
    for i in range(total_samples):
        t = i / sample_rate
        # Gentle envelope: attack and decay
        envelope = math.sin(math.pi * (i / total_samples))
        sample_val = 0.0
        for f in freqs:
            sample_val += math.sin(2.0 * math.pi * f * t)
        sample_val = (sample_val / len(freqs)) * envelope * 0.45

        val_int = int(max(-32768, min(32767, sample_val * 32767)))
        pcm_data.extend(struct.pack('<h', val_int))

    frame_bytes_len = samples_per_frame * 2
    for offset in range(0, len(pcm_data), frame_bytes_len):
        chunk = bytes(pcm_data[offset:offset + frame_bytes_len])
        if len(chunk) == frame_bytes_len:
            frames.append(chunk)

    return frames

HOLD_CHIME_FRAMES = generate_hold_chime_frames()

async def play_hold_audio_loop(audio_source, stop_event: asyncio.Event, custom_audio_frames=None):
    """Play hold music / chime repeatedly until stop_event is set."""
    frames = custom_audio_frames or HOLD_CHIME_FRAMES
    frame_samples = 480
    while not stop_event.is_set():
        for frame_bytes in frames:
            if stop_event.is_set():
                break
            frame = rtc.AudioFrame(
                data=frame_bytes,
                sample_rate=24000,
                num_channels=1,
                samples_per_channel=frame_samples
            )
            await audio_source.capture_frame(frame)
            await asyncio.sleep(0.019)
        # Brief 0.5s pause between chime cycles
        for _ in range(25):
            if stop_event.is_set():
                break
            await asyncio.sleep(0.02)

async def run_queue_session(
    room_name: str,
    user_id: int,
    caller_phone: str = "web_dashboard",
    queue_data: dict = None,
    profile_data: dict = None,
    livekit_url: str = "",
    api_key: str = "",
    api_secret: str = "",
    redis_client: redis.Redis = None,
    notify_func = None,
    fallback_agent_func = None
):
    channel_name = f"rooms:{room_name}"
    queue_name = queue_data.get("name", "طابور الانتظار") if queue_data else "طابور الانتظار"
    queue_code = queue_data.get("code", "0") if queue_data else "0"
    total_timeout = queue_data.get("total_timeout_seconds", 60) if queue_data else 60
    ring_timeout = queue_data.get("ring_timeout_seconds", 15) if queue_data else 15
    members = queue_data.get("members", []) if queue_data else []

    logger.info(f"Starting Queue Session for room '{room_name}' (Queue: {queue_name} [{queue_code}], Timeout: {total_timeout}s, Members: {len(members)})")
    notify_func(channel_name, "queue_started", f"مرحباً بك في {queue_name}. جاري تشغيل نغمة الانتظار والاتصال بالموظفين...")

    # Register in Redis waiting list
    waiting_key = f"queue:{queue_code}:waiting"
    try:
        await _redis_exec(redis_client.rpush(waiting_key, room_name))
    except Exception:
        pass

    # 1. Connect Queue Manager to the room to play hold audio
    token = api.AccessToken(api_key, api_secret) \
        .with_identity("queue-manager") \
        .with_name(f"Hold Music - {queue_name}") \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
        ))
    agent_jwt = token.to_jwt()

    room = rtc.Room()
    stop_hold_event = asyncio.Event()
    hold_playback_task = None

    try:
        await room.connect(livekit_url, agent_jwt)
        logger.info(f"Queue Manager connected to LiveKit room '{room_name}'")

        audio_source = rtc.AudioSource(sample_rate=24000, num_channels=1)
        audio_track = rtc.LocalAudioTrack.create_audio_track("hold-audio", audio_source)
        publish_options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
        await room.local_participant.publish_track(audio_track, publish_options)

        # Check if custom hold music audio exists in /app/media
        custom_frames = None
        hold_url = queue_data.get("hold_music_url") if queue_data else None
        if hold_url:
            # Map /media/hold_music/xxx to /app/media/hold_music/xxx
            relative_path = hold_url.lstrip("/media/").lstrip("/")
            local_path = os.path.join("/app/media", relative_path)
            if os.path.exists(local_path) and local_path.lower().endswith(".wav"):
                try:
                    with wave.open(local_path, "rb") as wf:
                        if wf.getnchannels() == 1 and wf.getframerate() == 24000 and wf.getsampwidth() == 2:
                            raw = wf.readframes(wf.getnframes())
                            chunk_size = 480 * 2
                            custom_frames = [raw[i:i+chunk_size] for i in range(0, len(raw), chunk_size) if len(raw[i:i+chunk_size]) == chunk_size]
                            logger.info(f"Loaded custom WAV hold music from {local_path} ({len(custom_frames)} frames)")
                except Exception as ex:
                    logger.warning(f"Could not parse custom WAV file {local_path}: {ex}")

        hold_playback_task = asyncio.create_task(play_hold_audio_loop(audio_source, stop_hold_event, custom_frames))

    except Exception as e:
        logger.error(f"Error connecting queue manager audio: {e}")

    # 2. Round-Robin Dialing Engine
    start_time = time.time()
    agent_answered = False
    member_idx = 0

    try:
        while (time.time() - start_time) < total_timeout:
            # Check if customer has disconnected
            remote_parts = list(room.remote_participants.values())
            customer_present = any(p.identity != "queue-manager" and not p.identity.startswith("agent_") for p in remote_parts)
            if room.connection_state == rtc.ConnectionState.CONN_CONNECTED and not customer_present and len(remote_parts) == 0:
                logger.info(f"Caller disconnected from room '{room_name}'. Ending queue session.")
                break

            if not members:
                logger.info("No members configured for this queue. Breaking directly to AI fallback.")
                break

            member = members[member_idx % len(members)]
            member_idx += 1
            extension = str(member.get("extension") or member.get("sip_username") or "")
            agent_name = member.get("name") or member.get("sip_account_name") or f"موظف {extension}"
            status = member.get("status", "ready")

            # Check agent presence in Redis or status
            state = "AVAILABLE"
            try:
                s = await _redis_exec(redis_client.get(f"agent_state:{extension}"))
                if s:
                    state = s.decode() if isinstance(s, bytes) else str(s)
            except Exception:
                pass

            if status in ["busy", "break", "offline"] or state == "BUSY":
                logger.info(f"Employee '{agent_name}' ({extension}) is BUSY/UNAVAILABLE (status={status}, state={state}). Checking next employee.")
                await asyncio.sleep(1.0)
                continue

            logger.info(f"[ROUND-ROBIN] Ringing employee '{agent_name}' ({extension}) via WebRTC for up to {ring_timeout}s...")
            try:
                await _redis_exec(redis_client.set(f"agent_state:{extension}", "RINGING", ex=ring_timeout + 5))
            except Exception:
                pass

            notify_func(channel_name, "queue_ringing", f"جاري الاتصال بـ {agent_name}...")

            # Dispatch WebRTC incoming call signaling to employee's Centrifugo channel
            notify_func(
                f"employee:{extension}",
                "incoming_call",
                f"مكالمة واردة من {queue_name}",
                {
                    "caller_name": f"طابور {queue_name}",
                    "caller_number": queue_code,
                    "room_name": room_name,
                    "call_id": room_name,
                    "call_type": "queue"
                }
            )

            # Wait for employee to answer and join LiveKit WebRTC room
            wait_start = time.time()
            while (time.time() - wait_start) < ring_timeout:
                remote_parts = list(room.remote_participants.values())
                if any(p.identity.startswith("employee_") or p.identity.startswith(f"agent_{extension}") for p in remote_parts):
                    logger.info(f"Employee '{agent_name}' ({extension}) answered and joined room '{room_name}'!")
                    agent_answered = True
                    try:
                        await _redis_exec(redis_client.set(f"agent_state:{extension}", "BUSY"))
                    except Exception:
                        pass
                    notify_func(channel_name, "agent_connected", f"تم الرد بواسطة {agent_name}. المحادثة جارية الآن.")
                    break
                await asyncio.sleep(0.5)

            if agent_answered:
                break
            else:
                logger.info(f"Employee '{agent_name}' ({extension}) did not answer within {ring_timeout}s. Advancing to next employee.")
                # Cancel ringing on employee UI
                notify_func(
                    f"employee:{extension}",
                    "call_ended",
                    "انتهت مهلة الرنين",
                    {"room_name": room_name, "ended_by": "timeout"}
                )
                try:
                    await _redis_exec(redis_client.set(f"agent_state:{extension}", "AVAILABLE"))
                except Exception:
                    pass

            await asyncio.sleep(1.0)

    finally:
        # Stop hold music
        stop_hold_event.set()
        if hold_playback_task:
            hold_playback_task.cancel()
        try:
            await _redis_exec(redis_client.lrem(waiting_key, 0, room_name))
        except Exception:
            pass
        try:
            await room.disconnect()
        except Exception:
            pass

    # 3. If agent answered -> Call successfully connected to human!
    if agent_answered:
        logger.info(f"Queue session for room '{room_name}' handed off to human agent successfully.")
        return

    # 4. If timed out without human answer -> Fallback to Gemini Live AI Assistant!
    elapsed = int(time.time() - start_time)
    logger.info(f"Queue timeout ({elapsed}s >= {total_timeout}s) reached with no agent answer for room '{room_name}'. Triggering Gemini Live Fallback!")
    notify_func(channel_name, "queue_fallback", "الموظفون غير متاحين حالياً، جاري تحويلك للمساعد الصوتي الذكي...")

    # Launch AI assistant with queue context
    queue_context = {
        "is_fallback": True,
        "queue_name": queue_name,
        "queue_code": queue_code,
        "wait_seconds": elapsed,
    }
    await fallback_agent_func(room_name, user_id=user_id, caller_phone=caller_phone, profile_data=profile_data, queue_context=queue_context)
