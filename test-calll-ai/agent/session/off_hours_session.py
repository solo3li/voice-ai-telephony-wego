"""Off-Hours Call Session Handler.
Plays designated audio file or speaks AI message to the caller outside business hours,
then hangs up cleanly and closes the LiveKit room.
"""
import asyncio
import os
import time
from typing import Dict, Any, Optional
from livekit import api, rtc
from google import genai
from google.genai import types

from agent.config import (
    logger,
    LIVEKIT_INTERNAL_URL,
    LIVEKIT_API_KEY,
    LIVEKIT_API_SECRET,
    GEMINI_API_KEY,
    GEMINI_LIVE_MODEL,
)
from agent.clients.centrifugo_client import notify_centrifugo_async


async def run_off_hours_session(
    room_name: str,
    user_id: Optional[int],
    caller_phone: str,
    off_hours_data: Dict[str, Any],
    profile_data: Optional[Dict[str, Any]] = None,
):
    """
    Connects to the LiveKit room when an incoming call arrives outside business hours.
    Executes the configured action (audio_file or ai_message) and closes the room.
    """
    action_type = off_hours_data.get("action_type", "ai_message")
    ai_message = off_hours_data.get("ai_message") or "مرحباً بك، نتأسف لاتصالك خارج أوقات العمل الرسمية. نسعد بتواصلك معنا مجدداً خلال أوقات العمل."
    audio_file_url = off_hours_data.get("audio_file_url") or ""
    voice_name = off_hours_data.get("voice_name") or (profile_data.get("voice_name") if profile_data else "Aoede") or "Aoede"

    channel_name = f"rooms:{room_name}"
    logger.info(f"[OFF-HOURS] Starting off-hours handling in room '{room_name}' (action: {action_type}, caller: {caller_phone})")

    # 1. Connect to LiveKit Room as ai-agent
    token = (
        api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity("ai-agent")
        .with_name("المساعد الآلي (خارج الدوام)")
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            )
        )
    )
    bot_jwt = token.to_jwt()

    room = rtc.Room()
    try:
        await room.connect(LIVEKIT_INTERNAL_URL, bot_jwt)
        logger.info(f"[OFF-HOURS] Connected to LiveKit room '{room_name}'")

        audio_source = rtc.AudioSource(sample_rate=24000, num_channels=1)
        audio_track = rtc.LocalAudioTrack.create_audio_track("off-hours-audio", audio_source)
        publish_options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
        await room.local_participant.publish_track(audio_track, publish_options)

        # Notify Centrifugo
        await notify_centrifugo_async(
            channel_name,
            "off_hours_started",
            "تم استقبال المكالمة خارج أوقات العمل الرسمية. جاري تشغيل رسالة الإشعار..."
        )

        # Wait 1.0s for caller track subscriptions to stabilize
        await asyncio.sleep(1.0)

        played_successfully = False

        # Mode A: Audio File Playback via ffmpeg
        if action_type == "audio_file" and audio_file_url:
            resolved_source = audio_file_url
            # Check local media mount if url is /media/xxx
            if "/media/" in audio_file_url:
                rel = audio_file_url.split("/media/", 1)[1]
                local_path = os.path.join("/app/media", rel)
                if os.path.exists(local_path):
                    resolved_source = local_path

            logger.info(f"[OFF-HOURS] Playing audio file from '{resolved_source}'")
            try:
                proc = await asyncio.create_subprocess_exec(
                    "ffmpeg",
                    "-re",
                    "-i", resolved_source,
                    "-f", "s16le",
                    "-acodec", "pcm_s16le",
                    "-ac", "1",
                    "-ar", "24000",
                    "pipe:1",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL
                )

                chunk_size = 480 * 2  # 20ms at 24000Hz 16-bit mono = 960 bytes
                while True:
                    chunk = await proc.stdout.read(chunk_size)
                    if not chunk:
                        break
                    frame = rtc.AudioFrame(
                        data=chunk,
                        sample_rate=24000,
                        num_channels=1,
                        samples_per_channel=len(chunk) // 2
                    )
                    await audio_source.capture_frame(frame)
                    await asyncio.sleep(0.018)  # Real-time pacing

                await proc.wait()
                played_successfully = True
                logger.info(f"[OFF-HOURS] Finished streaming audio file to room '{room_name}'")
            except Exception as stream_err:
                logger.error(f"[OFF-HOURS] Failed streaming audio file: {stream_err}")

        # Mode B: AI Message via Gemini Live
        if not played_successfully:
            logger.info(f"[OFF-HOURS] Speaking AI message via Gemini Live: '{ai_message}'")
            active_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY_FALLBACK", "")
            try:
                client = genai.Client(api_key=active_key)
                live_config = types.LiveConnectConfig(
                    response_modalities=[types.LiveServerContentModality.AUDIO],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                        )
                    ),
                    system_instruction=types.Content(
                        parts=[types.Part(
                            text="أنت مساعد صوتي لبق. انطق الجملة المطلوبة منك حرفياً بنبرة مهذبة وواضحة فقط وتوقف بعدها تماماً."
                        )]
                    )
                )

                async with client.aio.live.connect(model=GEMINI_LIVE_MODEL, config=live_config) as session:
                    # Instruct Gemini to speak the exact off-hours text
                    prompt = f"المتصل اتصل بالشركة خارج مواعيد العمل. انطق له هذه الرسالة بدقة: '{ai_message}'"
                    await session.send_client_content(
                        turns=[
                            types.Content(
                                role="user",
                                parts=[types.Part(text=prompt)]
                            )
                        ],
                        turn_complete=True
                    )

                    # Stream output audio until turn completes
                    async for response in session.receive():
                        server_content = response.server_content
                        if server_content is not None:
                            model_turn = server_content.model_turn
                            if model_turn is not None:
                                for part in model_turn.parts:
                                    if part.inline_data and part.inline_data.data:
                                        raw_pcm = part.inline_data.data
                                        chunk_size = 480 * 2  # 960 bytes = 20ms @24kHz mono
                                        for i in range(0, len(raw_pcm), chunk_size):
                                            pcm_slice = raw_pcm[i:i + chunk_size]
                                            # Pad last short chunk so AudioFrame is always full
                                            if len(pcm_slice) < chunk_size:
                                                pcm_slice = pcm_slice + b'\x00' * (chunk_size - len(pcm_slice))
                                            frame = rtc.AudioFrame(
                                                data=pcm_slice,
                                                sample_rate=24000,
                                                num_channels=1,
                                                samples_per_channel=480
                                            )
                                            await audio_source.capture_frame(frame)
                                            await asyncio.sleep(0.015)

                            if server_content.turn_complete:
                                logger.info(f"[OFF-HOURS] Gemini Live finished speaking off-hours message")
                                played_successfully = True
                                break
            except Exception as gemini_err:
                logger.error(f"[OFF-HOURS] Error speaking AI message: {gemini_err}")

        # Wait 1.5 seconds after playback before hanging up
        await asyncio.sleep(1.5)

    except Exception as exc:
        logger.error(f"[OFF-HOURS] Unexpected error in off-hours session: {exc}")
    finally:
        # Disconnect bot and close room
        try:
            await room.disconnect()
        except Exception:
            pass

        try:
            lk_api = api.RoomServiceClient(LIVEKIT_INTERNAL_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
            await lk_api.delete_room(api.DeleteRoomRequest(room=room_name))
            logger.info(f"[OFF-HOURS] Deleted LiveKit room '{room_name}' after off-hours playback.")
        except Exception as del_err:
            logger.warning(f"[OFF-HOURS] Error deleting room {room_name}: {del_err}")

        await notify_centrifugo_async(
            channel_name,
            "call_ended",
            "تم إنهاء المكالمة بنجاح خارج أوقات العمل."
        )
