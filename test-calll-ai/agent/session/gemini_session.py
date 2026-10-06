"""Gemini 3.8 Live bidirectional audio streaming session."""
import asyncio
import time
from typing import Dict, Any, Optional, Set
from google import genai
from google.genai import types
from livekit import api, rtc

from agent.config import (
    logger,
    LIVEKIT_INTERNAL_URL,
    LIVEKIT_API_KEY,
    LIVEKIT_API_SECRET,
    GEMINI_API_KEY,
    GEMINI_LIVE_MODEL,
    IN_CHUNK_SIZE,
    OUT_SAMPLE_RATE,
    OUT_FRAME_BYTES,
    OUT_FRAME_SAMPLES,
    AUDIO_FRAME_INTERVAL,
    AUDIO_SILENCE_THRESHOLD,
)
from agent.clients.centrifugo_client import notify_centrifugo_async
from agent.clients.django_client import (
    fetch_agent_bootstrap_async,
    parse_mcp_servers_from_bootstrap,
    parse_customer_memory_from_bootstrap,
    parse_active_profile_from_bootstrap,
)
from agent.prompts import build_dynamic_system_instruction, generate_welcome_greeting
from agent.audio.stream_handler import setup_room_audio_listeners
from agent.session.state import AgentSessionState
from agent.session.tool_dispatcher import build_gemini_tools, handle_gemini_tool_call
from agent.session.memory import distill_and_update_memory
from agent.transfer.transfer_bot import execute_ai_transfer_and_hold

# Global strong references for background tasks (e.g. memory distillation) to prevent Python 3.11 GC
BACKGROUND_TASKS: Set[asyncio.Task] = set()


def track_background_task(task: asyncio.Task) -> asyncio.Task:
    """Retain strong reference to async task until completion."""
    BACKGROUND_TASKS.add(task)
    task.add_done_callback(BACKGROUND_TASKS.discard)
    return task


async def run_agent_session(
    room_name: str,
    user_id: Optional[int] = None,
    caller_phone: str = "web_dashboard",
    profile_data: Optional[Dict[str, Any]] = None,
    queue_context: Optional[Dict[str, Any]] = None,
    outbound_context: Optional[Dict[str, Any]] = None
):
    """Run full-duplex conversational AI voice agent in LiveKit room powered by Gemini Live."""
    channel_name = f"rooms:{room_name}"
    logger.info(f"Starting Gemini Live Voice Agent session for room: {room_name} (user_id={user_id}, caller_phone={caller_phone})")
    await notify_centrifugo_async(channel_name, "agent_starting", "جاري تهيئة المساعدة الصوتية وتجهيز قاعدة المستندات والإجراءات...")

    # 1. Create LiveKit Access Token for Agent
    token = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET) \
        .with_identity("ai-agent") \
        .with_name("Gemini Voice Assistant") \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
        ))
    agent_jwt = token.to_jwt()

    # 2. Connect to LiveKit Room
    room = rtc.Room()
    try:
        await room.connect(LIVEKIT_INTERNAL_URL, agent_jwt)
        logger.info(f"Connected to LiveKit room '{room_name}'")
    except Exception as e:
        logger.error(f"Failed to connect to LiveKit: {e}")
        await notify_centrifugo_async(channel_name, "agent_error", f"فشل الاتصال بخادم LiveKit: {e}")
        return

    # 3. Prepare Local Audio Track (Agent output: 24kHz mono)
    audio_source = rtc.AudioSource(sample_rate=OUT_SAMPLE_RATE, num_channels=1)
    audio_track = rtc.LocalAudioTrack.create_audio_track("agent-audio", audio_source)
    publish_options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    await room.local_participant.publish_track(audio_track, publish_options)
    logger.info(f"Published agent audio track to room '{room_name}'")

    # 4. Fetch unified Bootstrap bundle ONCE asynchronously (profile, mcp_servers, customer_memory, gemini_api_key)
    bootstrap = {}
    if user_id:
        bootstrap = await fetch_agent_bootstrap_async(user_id, caller_phone)

    # 4.1 Resolve active Gemini API key: prioritize Django SystemSetting from bootstrap, fallback to .env
    active_api_key = (bootstrap.get("gemini_api_key") or "").strip() or GEMINI_API_KEY
    if not active_api_key or active_api_key.startswith("your_"):
        err = "GEMINI_API_KEY is not configured in Django Admin (SystemSetting) or .env"
        logger.error(err)
        await notify_centrifugo_async(channel_name, "agent_error", err)
        await room.disconnect()
        return

    client = genai.Client(api_key=active_api_key)

    # 4.2 Parse MCP Tools dynamically from unified bootstrap
    mcp_servers_list = parse_mcp_servers_from_bootstrap(bootstrap) if user_id else []
    mcp_tools = {}
    for s in mcp_servers_list:
        s_url = s.get("server_url")
        s_token = s.get("auth_token", "")
        s_name = s.get("name", "FastMCP")
        for t in s.get("tools", []):
            t_name = t.get("name")
            if not t_name:
                continue
            mcp_tools[t_name] = {
                "server_url": s_url,
                "auth_token": s_token,
                "server_name": s_name,
                "description": t.get("description", ""),
                "parameters": t.get("parameters")
            }

    # 4.3 Parse Customer Memory dynamically from unified bootstrap
    memory_data = parse_customer_memory_from_bootstrap(bootstrap, caller_phone) if user_id else {}
    memory_card_text = memory_data.get("card_text", "")
    if memory_card_text:
        logger.info(f"Loaded customer memory for user {user_id} [phone={caller_phone}] ({len(memory_card_text)} chars)")

    # 4.4 Resolve Active Profile dynamically from unified bootstrap
    active_profile = None
    if profile_data and isinstance(profile_data, dict):
        active_profile = profile_data
    elif user_id:
        active_profile = parse_active_profile_from_bootstrap(bootstrap)

    if not active_profile:
        active_profile = parse_active_profile_from_bootstrap({})

    chosen_voice = active_profile.get("voice_name") or "Aoede"
    logger.info(
        f"Using Google voice '{chosen_voice}', language '{active_profile.get('language', 'arabic')}', "
        f"dialect '{active_profile.get('dialect')}', gender '{active_profile.get('gender')}', "
        f"verbosity '{active_profile.get('verbosity', 'balanced')}' for user {user_id}"
    )

    speech_config = types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                voice_name=chosen_voice
            )
        )
    )

    call_queues = bootstrap.get("call_queues", []) if bootstrap else []
    tools = build_gemini_tools(mcp_tools, call_queues)

    live_context = bootstrap.get("live_context") or {}
    if not live_context and user_id:
        try:
            from agent.config import REDIS_URL
            import redis.asyncio as aioredis
            import json
            r_temp = aioredis.from_url(REDIS_URL, decode_responses=True)
            cached_ctx = await r_temp.get(f"tenant:{user_id}:live_context")
            await r_temp.aclose()
            if cached_ctx:
                live_context = json.loads(cached_ctx) if isinstance(cached_ctx, str) else cached_ctx
        except Exception as e:
            logger.debug(f"Redis live_context fallback error: {e}")

    system_instruction_text = build_dynamic_system_instruction(
        active_profile,
        memory_card_text,
        queue_context=queue_context,
        outbound_context=outbound_context,
        call_queues=call_queues,
        live_context=live_context
    )
    logger.info(f"Dynamic system instruction compiled (length={len(system_instruction_text)} chars, live_context={bool(live_context)})")

    live_config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        speech_config=speech_config,
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        tools=tools,
        system_instruction=types.Content(
            parts=[types.Part(text=system_instruction_text)]
        )
    )

    in_audio_queue = asyncio.Queue()
    out_audio_queue = asyncio.Queue()
    stop_event = asyncio.Event()

    session_state = AgentSessionState(
        room_name=room_name,
        user_id=user_id,
        caller_phone=caller_phone,
        channel_name=channel_name,
        started_at=time.time()
    )

    # Register room audio listeners & employee guardrail
    setup_room_audio_listeners(room, in_audio_queue, stop_event, room_name)

    # 5. Connect to Gemini Live Session
    try:
        logger.info(f"Connecting to Gemini Live API ({GEMINI_LIVE_MODEL}) for room {room_name}...")
        async with client.aio.live.connect(model=GEMINI_LIVE_MODEL, config=live_config) as session:
            logger.info(f"Gemini Live session connected for room '{room_name}'!")
            await notify_centrifugo_async(channel_name, "agent_ready", "المساعدة الصوتية وقاعدة المستندات جاهزة للاستماع إليك الآن!")

            # Proactive greeting trigger for human callers (inbound, ai_test, and outbound)
            greeting_triggered = False
            async def trigger_proactive_greeting():
                nonlocal greeting_triggered
                # Poll for up to 20 seconds waiting for the human participant to connect
                for _ in range(40):
                    if stop_event.is_set() or greeting_triggered:
                        return
                    humans = [p for p in room.remote_participants.values() if p.identity not in ("ai-agent", "pipecat-agent")]
                    if humans:
                        # Allow 1.0s for audio tracks, WebRTC subscriptions and media pipelines to settle
                        await asyncio.sleep(1.0)
                        if not greeting_triggered and not stop_event.is_set():
                            greeting_triggered = True
                            # Explicit bool cast to handle any truthy/falsy edge cases
                            raw_flag = active_profile.get("is_welcome_message_enabled")
                            is_welcome_enabled = bool(raw_flag) if raw_flag is not None else True
                            custom_welcome = (active_profile.get("welcome_message") or "").strip()
                            logger.info(
                                f"[GREETING] profile='{active_profile.get('name')}' "
                                f"is_welcome_enabled={is_welcome_enabled} "
                                f"custom_welcome='{custom_welcome[:50] if custom_welcome else '(none)'}'"
                            )
                            if not is_welcome_enabled:
                                logger.info(f"[GREETING] Welcome message disabled for profile '{active_profile.get('name')}'. Waiting for caller.")
                                return
                            is_outbound = bool(outbound_context and outbound_context.get("is_outbound_ai"))
                            welcome_msg = generate_welcome_greeting(active_profile, is_outbound, outbound_context)
                            logger.info(f"[GREETING] Triggering proactive greeting in room {room_name}: '{welcome_msg[:80]}'")

                            c_name = ""
                            if memory_data:
                                c_name = (memory_data.get("customer_name") or (memory_data.get("permanent_profile") or {}).get("customer_name") or "").strip()

                            try:
                                if c_name:
                                    prompt = (
                                        f"المتصل قام بالرد أو الاتصال للتو وهو ينتظر سماعك الآن. "
                                        f"هذا عميل مسجل لديك مسبقاً واسمه ({c_name}). "
                                        f"ابدأ المحادثة فوراً بالترحيب به باسمه بلباقة مع توظيف رسالة الترحيب التالية بشكل طبيعي: '{welcome_msg}'."
                                    )
                                else:
                                    prompt = f"المتصل قام بالرد أو الاتصال للتو وهو ينتظر سماعك الآن. ابدأ المحادثة فوراً وتحدث بهذه الجملة الترحيبية: '{welcome_msg}'"
                                await session.send_realtime_input(text=prompt)
                            except Exception as ge:
                                logger.warning(f"Error triggering proactive greeting: {ge}")
                        return
                    await asyncio.sleep(0.5)

            session_state.track_task(asyncio.create_task(trigger_proactive_greeting()))

            # Worker 1: Stream user PCM audio frames to Gemini Live (continuous full-duplex streaming)
            async def send_audio_worker():
                buffer = bytearray()
                while not stop_event.is_set():
                    try:
                        chunk = await asyncio.wait_for(in_audio_queue.get(), timeout=0.05)
                        buffer.extend(chunk)

                        while len(buffer) >= IN_CHUNK_SIZE:
                            to_send = bytes(buffer[:IN_CHUNK_SIZE])
                            del buffer[:IN_CHUNK_SIZE]
                            await session.send_realtime_input(
                                audio=types.Blob(data=to_send, mime_type="audio/pcm;rate=16000")
                            )

                    except asyncio.TimeoutError:
                        if buffer:
                            to_send = bytes(buffer)
                            buffer.clear()
                            try:
                                await session.send_realtime_input(
                                    audio=types.Blob(data=to_send, mime_type="audio/pcm;rate=16000")
                                )
                            except Exception:
                                pass
                    except Exception as ex:
                        if not stop_event.is_set():
                            logger.error(f"Error sending audio to Gemini: {ex}")
                            await asyncio.sleep(0.05)

            # Worker 2: Receive audio, transcripts & handle tool calls from Gemini Live across multiple turns
            async def receive_audio_worker():
                while not stop_event.is_set():
                    try:
                        async for response in session.receive():
                            if stop_event.is_set():
                                break

                            # Handle Tool Calls
                            if response.tool_call:
                                logger.info(f"Gemini requested tool call in room {room_name}: {response.tool_call}")
                                function_responses = []
                                for fc in response.tool_call.function_calls:
                                    resp, transfer_info = await handle_gemini_tool_call(
                                        fc,
                                        user_id=user_id,
                                        room_name=room_name,
                                        channel_name=channel_name,
                                        mcp_tools=mcp_tools,
                                        call_queues=call_queues,
                                        genai_client=client,
                                        session_state=session_state
                                    )
                                    function_responses.append(resp)
                                    if transfer_info:
                                        session_state.pending_transfer = transfer_info

                                await session.send_tool_response(function_responses=function_responses)
                                continue

                            content = response.server_content
                            if not content:
                                continue

                            # Interruption handling (Barge-in triggered by Gemini Live)
                            if content.interrupted:
                                logger.info(f"Gemini playback interrupted by user in room {room_name}")
                                session_state.interrupted = True
                                session_state.is_agent_speaking = False
                                session_state.turn_complete = True
                                while not out_audio_queue.empty():
                                    try:
                                        out_audio_queue.get_nowait()
                                    except asyncio.QueueEmpty:
                                        break
                                await notify_centrifugo_async(channel_name, "agent_interrupted", "المساعد استمع لمقاطعتك...")
                                continue

                            # Transcriptions
                            if content.input_transcription and content.input_transcription.text:
                                user_text = content.input_transcription.text.strip()
                                logger.info(f"[{room_name}] User: {user_text}")
                                session_state.dialogue_turns.append({"speaker": "user", "text": user_text})
                                await notify_centrifugo_async(channel_name, "transcription_user", user_text, {"speaker": "user"})

                            if content.output_transcription and content.output_transcription.text:
                                bot_text = content.output_transcription.text.strip()
                                logger.info(f"[{room_name}] Gemini: {bot_text}")
                                session_state.dialogue_turns.append({"speaker": "agent", "text": bot_text})
                                await notify_centrifugo_async(channel_name, "transcription_agent", bot_text, {"speaker": "agent"})

                            # Audio response from Gemini
                            if content.model_turn:
                                session_state.turn_complete = False
                                session_state.agent_last_audio_time = time.time()
                                if not session_state.is_agent_speaking:
                                    session_state.is_agent_speaking = True
                                    await notify_centrifugo_async(channel_name, "agent_speaking", "المساعدة تتحدث الآن...")
                                for part in content.model_turn.parts:
                                    if part.inline_data and part.inline_data.data:
                                        await out_audio_queue.put(part.inline_data.data)

                            if content.turn_complete:
                                logger.info(f"Gemini model turn complete for room {room_name}")
                                session_state.turn_complete = True
                                if session_state.pending_transfer:
                                    logger.info(f"Pending transfer detected after turn complete in {room_name}. Launching execute_ai_transfer_and_hold...")
                                    wait_start = time.time()
                                    while (session_state.is_agent_speaking or not out_audio_queue.empty()) and (time.time() - wait_start < 4.0):
                                        await asyncio.sleep(0.1)
                                    await asyncio.sleep(0.3)

                                    pt = session_state.pending_transfer
                                    target_ident = f"sip_{caller_phone}" if caller_phone else None
                                    track_background_task(asyncio.create_task(execute_ai_transfer_and_hold(
                                        room_name=room_name,
                                        user_id=user_id,
                                        queue_code=pt["queue_code"],
                                        caller_phone=caller_phone,
                                        caller_name="العميل",
                                        reason=pt.get("reason", ""),
                                        target_participant_identity=target_ident
                                    )))
                                    logger.info(f"AI voice agent transfer launched. Exiting Voice Agent cleanly from room '{room_name}'.")
                                    stop_event.set()
                                    break

                    except asyncio.CancelledError:
                        break
                    except Exception as ex:
                        if not stop_event.is_set():
                            logger.error(f"Error receiving from Gemini Live in room {room_name}: {ex}")
                            logger.warning(f"Closing Gemini Live session cleanly for room {room_name}.")
                            stop_event.set()
                            break

            # Worker 3: Enhanced Smooth Audio Pacer (sub-millisecond jitter-smoothed clock)
            async def audio_pacer_worker():
                buffer = bytearray()
                prebuffered = False
                # 200ms initial cushion on turn start (10 frames x 20ms = 200ms = 9,600 bytes)
                PREBUFFER_FRAMES = 10
                PREBUFFER_BYTES = OUT_FRAME_BYTES * PREBUFFER_FRAMES
                next_frame_time = time.monotonic()

                while not stop_event.is_set():
                    try:
                        # 1. Handle Barge-in Interruption immediately
                        if session_state.interrupted:
                            buffer.clear()
                            prebuffered = False
                            session_state.interrupted = False
                            next_frame_time = time.monotonic()

                        # 2. Gather audio from queue into buffer
                        while not out_audio_queue.empty():
                            try:
                                chunk = out_audio_queue.get_nowait()
                                buffer.extend(chunk)
                            except asyncio.QueueEmpty:
                                break

                        # 3. Prebuffer on speech turn start to absorb network jitter from Gemini
                        if not prebuffered:
                            if len(buffer) >= PREBUFFER_BYTES or (len(buffer) >= OUT_FRAME_BYTES and session_state.turn_complete):
                                prebuffered = True
                                next_frame_time = time.monotonic()
                            elif not session_state.turn_complete:
                                try:
                                    chunk = await asyncio.wait_for(out_audio_queue.get(), timeout=0.15)
                                    buffer.extend(chunk)
                                    while not out_audio_queue.empty():
                                        buffer.extend(out_audio_queue.get_nowait())
                                    if len(buffer) >= PREBUFFER_BYTES or session_state.turn_complete:
                                        prebuffered = True
                                        next_frame_time = time.monotonic()
                                    else:
                                        continue
                                except asyncio.TimeoutError:
                                    if len(buffer) >= OUT_FRAME_BYTES:
                                        prebuffered = True
                                        next_frame_time = time.monotonic()
                                    else:
                                        continue
                            elif len(buffer) == 0:
                                # Idle state between speech turns
                                if session_state.is_agent_speaking and (time.time() - session_state.agent_last_audio_time > AUDIO_SILENCE_THRESHOLD):
                                    session_state.is_agent_speaking = False
                                    logger.info(f"Agent playback finished for room {room_name}. Mic listening active.")
                                    await notify_centrifugo_async(channel_name, "agent_listening", "المساعدة تستمع إليكِ الآن...")
                                await asyncio.sleep(0.01)
                                next_frame_time = time.monotonic()
                                continue

                        # 4. Emit 20ms audio frame if buffer has data
                        if len(buffer) >= OUT_FRAME_BYTES:
                            frame_bytes = bytes(buffer[:OUT_FRAME_BYTES])
                            del buffer[:OUT_FRAME_BYTES]

                            frame = rtc.AudioFrame(
                                data=frame_bytes,
                                sample_rate=OUT_SAMPLE_RATE,
                                num_channels=1,
                                samples_per_channel=OUT_FRAME_SAMPLES
                            )
                            await audio_source.capture_frame(frame)
                            session_state.agent_last_audio_time = time.time()

                            # High-precision drift-compensated clock (20ms interval)
                            next_frame_time += AUDIO_FRAME_INTERVAL
                            now = time.monotonic()
                            sleep_duration = next_frame_time - now
                            if sleep_duration > 0:
                                await asyncio.sleep(sleep_duration)
                            elif sleep_duration < -0.04:
                                # Resynchronize clock smoothly if delayed
                                next_frame_time = time.monotonic()

                        elif session_state.turn_complete and out_audio_queue.empty():
                            # Turn complete: only trailing sub-frame remaining in buffer
                            if len(buffer) > 0:
                                pad = OUT_FRAME_BYTES - len(buffer)
                                frame_bytes = bytes(buffer + b'\x00' * pad)
                                buffer.clear()
                                frame = rtc.AudioFrame(
                                    data=frame_bytes,
                                    sample_rate=OUT_SAMPLE_RATE,
                                    num_channels=1,
                                    samples_per_channel=OUT_FRAME_SAMPLES
                                )
                                await audio_source.capture_frame(frame)
                                session_state.agent_last_audio_time = time.time()

                            prebuffered = False
                            next_frame_time = time.monotonic()

                        else:
                            # ACTIVE TURN MICRO-PAUSE:
                            # Gemini is still speaking, but the next burst packet was slightly delayed.
                            # DO NOT inject silence frames! Seamlessly await next burst packet.
                            try:
                                chunk = await asyncio.wait_for(out_audio_queue.get(), timeout=0.25)
                                buffer.extend(chunk)
                                while not out_audio_queue.empty():
                                    buffer.extend(out_audio_queue.get_nowait())
                                next_frame_time = time.monotonic()
                            except asyncio.TimeoutError:
                                next_frame_time = time.monotonic()
                                await asyncio.sleep(0.01)

                    except Exception as ex:
                        if not stop_event.is_set():
                            logger.error(f"Error in audio pacer for room {room_name}: {ex}")
                        break

            sender_task = asyncio.create_task(send_audio_worker())
            receiver_task = asyncio.create_task(receive_audio_worker())
            pacer_task = asyncio.create_task(audio_pacer_worker())

            await stop_event.wait()
            sender_task.cancel()
            receiver_task.cancel()
            pacer_task.cancel()
            await asyncio.gather(sender_task, receiver_task, pacer_task, return_exceptions=True)

    except Exception as e:
        logger.error(f"Gemini Live session error in room {room_name}: {e}")
        err_str = str(e)
        if "1008" in err_str or "API_KEY" in err_str or "policy violation" in err_str.lower() or "aborted" in err_str.lower():
            friendly_err = "فشل الاتصال بـ Gemini Live: يرجى التحقق من صلاحية مفتاح Gemini API Key في إعدادات النظام في لوحة التحكم (SystemSetting)."
        else:
            friendly_err = f"خطأ في جلسة Gemini Live: {e}"
        await notify_centrifugo_async(channel_name, "agent_error", friendly_err)
    finally:
        logger.info(f"Cleaning up and disconnecting from room '{room_name}'...")
        await session_state.cancel_all_tasks()
        try:
            await room.disconnect()
        except Exception:
            pass
        await notify_centrifugo_async(channel_name, "agent_disconnected", "تم إنهاء جلسة المساعدة الصوتية.")

        if user_id and session_state.dialogue_turns:
            final_phone = session_state.caller_phone or caller_phone
            logger.info(f"Triggering background memory distillation for user {user_id} [phone={final_phone}] with {len(session_state.dialogue_turns)} turns.")
            track_background_task(
                asyncio.create_task(
                    distill_and_update_memory(
                        user_id=user_id,
                        caller_phone=final_phone,
                        room_name=room_name,
                        started_at=session_state.started_at,
                        messages=list(session_state.dialogue_turns),
                        current_profile=dict(memory_data.get("permanent_profile", {}) if memory_data else {}),
                        genai_client=client,
                        outbound_context=outbound_context
                    )
                )
            )
