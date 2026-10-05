"""LiveKit audio stream listeners and customer audio capture."""
import asyncio
from typing import Set
from livekit import rtc
from agent.config import logger, IN_SAMPLE_RATE


async def stream_user_audio_to_queue(
    audio_stream: rtc.AudioStream,
    queue: asyncio.Queue,
    stop_event: asyncio.Event,
    identity: str
):
    """Read user audio frames from LiveKit stream and push PCM bytes to queue."""
    logger.info(f"Started reading audio frames from participant: {identity}")
    try:
        async for frame_event in audio_stream:
            if stop_event.is_set():
                break
            frame: rtc.AudioFrame = frame_event.frame
            queue.put_nowait(bytes(frame.data))
    except Exception as e:
        logger.debug(f"Audio stream for {identity} ended: {e}")


def setup_room_audio_listeners(
    room: rtc.Room,
    in_audio_queue: asyncio.Queue,
    stop_event: asyncio.Event,
    room_name: str
) -> Set[str]:
    """Register all participant and track listeners on the LiveKit room with employee guardrails."""
    subscribed_sids: Set[str] = set()
    is_ai_test_call = room_name.startswith("ai_test_")

    def subscribe_track(track: rtc.Track, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
        p_identity = participant.identity or ""
        # Never subscribe to hold music or queue announcement bots
        if p_identity.startswith("transfer-") or p_identity.startswith("queue-"):
            return
        # Strict Human Employee Guardrail: If an employee joins in a regular customer call, AI must immediately disconnect!
        # BUT if this is an AI test call (ai_test_*), the employee IS the caller testing the agent!
        if p_identity.startswith("employee_") and not is_ai_test_call:
            logger.info(f"Human employee '{p_identity}' detected in room '{room_name}'. Immediately terminating AI Voice Agent session.")
            stop_event.set()
            return

        sid = publication.sid or (track.sid if track else None)
        if not sid or sid in subscribed_sids:
            return
        if track and track.kind == rtc.TrackKind.KIND_AUDIO:
            subscribed_sids.add(sid)
            logger.info(f"Subscribing to audio track {sid} from participant {participant.identity} (test_call={is_ai_test_call})")
            audio_stream = rtc.AudioStream(track, sample_rate=IN_SAMPLE_RATE, num_channels=1)
            asyncio.create_task(stream_user_audio_to_queue(audio_stream, in_audio_queue, stop_event, participant.identity))

    @room.on("participant_connected")
    def on_participant_connected(participant: rtc.RemoteParticipant):
        p_identity = participant.identity or ""
        logger.info(f"Participant connected: {p_identity} in room {room_name}")
        if p_identity.startswith("employee_") and not is_ai_test_call:
            logger.info(f"Human employee '{p_identity}' joined room '{room_name}'! Immediately disconnecting AI Voice Agent.")
            stop_event.set()

    @room.on("track_published")
    def on_track_published(publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
        p_identity = participant.identity or ""
        if p_identity.startswith("employee_") and not is_ai_test_call:
            logger.info(f"Human employee '{p_identity}' published track in room '{room_name}'. Disconnecting AI.")
            stop_event.set()
            return
        if p_identity.startswith("transfer-") or p_identity.startswith("queue-"):
            return
        publication.set_subscribed(True)
        if publication.track:
            subscribe_track(publication.track, publication, participant)

    @room.on("track_subscribed")
    def on_track_subscribed(track: rtc.Track, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
        subscribe_track(track, publication, participant)

    @room.on("participant_disconnected")
    def on_participant_disconnected(participant: rtc.RemoteParticipant):
        logger.info(f"Participant disconnected: {participant.identity} from room {room_name}")
        if is_ai_test_call:
            remaining_humans = [
                p for p in room.remote_participants.values()
                if p.identity not in ("ai-agent", "pipecat-agent")
                and not p.identity.startswith("transfer-")
                and not p.identity.startswith("queue-")
            ]
        else:
            remaining_humans = [
                p for p in room.remote_participants.values()
                if p.identity not in ("ai-agent", "pipecat-agent")
                and not p.identity.startswith("transfer-")
                and not p.identity.startswith("queue-")
                and not p.identity.startswith("employee_")
            ]
        if not remaining_humans:
            logger.info(f"No human participants left in room '{room_name}'. Terminating agent session.")
            stop_event.set()

    # Subscribe to already present participants
    for participant in room.remote_participants.values():
        p_identity = participant.identity or ""
        if p_identity.startswith("employee_") and not is_ai_test_call:
            logger.info(f"Human employee '{p_identity}' already present in room '{room_name}'. Terminating AI Voice Agent session.")
            stop_event.set()
            break
        if p_identity.startswith("transfer-") or p_identity.startswith("queue-"):
            continue
        for publication in participant.track_publications.values():
            publication.set_subscribed(True)
            if publication.track:
                subscribe_track(publication.track, publication, participant)

    return subscribed_sids
