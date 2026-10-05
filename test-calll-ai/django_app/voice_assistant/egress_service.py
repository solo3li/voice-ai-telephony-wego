"""LiveKit Egress Service for automated room composite recording to MinIO/S3."""
import asyncio
import logging
import threading
import time
from typing import Optional
import redis
from django.conf import settings
from livekit import api
from .s3_storage import ensure_minio_bucket

logger = logging.getLogger(__name__)


def get_livekit_api_client() -> api.LiveKitAPI:
    """Build LiveKitAPI client pointing to internal LiveKit server."""
    raw_url = getattr(settings, 'LIVEKIT_INTERNAL_URL', 'ws://livekit:7880')
    http_url = raw_url.replace('ws://', 'http://').replace('wss://', 'https://')
    return api.LiveKitAPI(
        http_url,
        settings.LIVEKIT_API_KEY,
        settings.LIVEKIT_API_SECRET
    )


async def _start_room_recording_async(room_name: str) -> Optional[str]:
    """
    Asynchronously start an audio-only RoomCompositeEgress for the given room,
    outputting standard MP3 file directly to MinIO.
    """
    if not room_name:
        return None

    # Distributed lock in Redis to avoid duplicate triggers for the same room
    try:
        r = redis.Redis.from_url(settings.REDIS_URL)
        lock_acquired = r.set(f"egress_lock:{room_name}", "1", nx=True, ex=3600)
        if not lock_acquired:
            logger.info(f"Egress recording already initiated for room '{room_name}'. Skipping.")
            return None
    except Exception as ex:
        logger.warning(f"Redis lock error in egress_service for room '{room_name}': {ex}")

    # Ensure MinIO bucket exists
    ensure_minio_bucket()

    timestamp = int(time.time())
    filepath = f"recordings/{room_name}_{timestamp}.mp3"

    s3_upload = api.S3Upload(
        endpoint=getattr(settings, 'MINIO_ENDPOINT', 'http://minio:9000'),
        access_key=getattr(settings, 'MINIO_ACCESS_KEY', 'minioadmin'),
        secret=getattr(settings, 'MINIO_SECRET_KEY', 'minioadmin123'),
        bucket=getattr(settings, 'MINIO_BUCKET_NAME', 'call-recordings'),
        region='us-east-1',
        force_path_style=True
    )

    req = api.RoomCompositeEgressRequest(
        room_name=room_name,
        audio_only=True,
        file_outputs=[
            api.EncodedFileOutput(
                file_type=api.EncodedFileType.MP3,
                filepath=filepath,
                s3=s3_upload
            )
        ]
    )

    try:
        async with get_livekit_api_client() as lk:
            # Check if active egress already exists for this room
            try:
                active_list = await lk.egress.list_egress(api.ListEgressRequest(room_name=room_name, active=True))
                if active_list and active_list.items:
                    egress_id = active_list.items[0].egress_id
                    logger.info(f"Egress already active for room '{room_name}' (ID: {egress_id})")
                    return egress_id
            except Exception as e:
                logger.debug(f"Could not check active egress list for '{room_name}': {e}")

            res = await lk.egress.start_room_composite_egress(req)
            logger.info(f"Started RoomCompositeEgress {res.egress_id} for room '{room_name}' -> {filepath}")
            return res.egress_id
    except Exception as ex:
        logger.error(f"Failed to start RoomCompositeEgress for room '{room_name}': {ex}", exc_info=True)
        # Release lock on failure so it can be retried if needed
        try:
            r = redis.Redis.from_url(settings.REDIS_URL)
            r.delete(f"egress_lock:{room_name}")
        except Exception:
            pass
        return None


def start_room_recording(room_name: str) -> None:
    """Non-blocking fire-and-forget trigger for room recording."""
    def _run():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_start_room_recording_async(room_name))
            loop.close()
        except Exception as e:
            logger.error(f"Error in start_room_recording thread for room '{room_name}': {e}")

    threading.Thread(target=_run, daemon=True, name=f"egress-{room_name}").start()


async def _stop_egress_async(egress_id: str) -> bool:
    """Stop active egress recording."""
    if not egress_id:
        return False
    try:
        async with get_livekit_api_client() as lk:
            await lk.egress.stop_egress(api.StopEgressRequest(egress_id=egress_id))
            logger.info(f"Requested stop for egress {egress_id}")
            return True
    except Exception as ex:
        logger.error(f"Failed to stop egress {egress_id}: {ex}")
        return False


def stop_egress(egress_id: str) -> None:
    """Non-blocking call to stop an egress."""
    def _run():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_stop_egress_async(egress_id))
            loop.close()
        except Exception as e:
            logger.error(f"Error stopping egress {egress_id}: {e}")

    threading.Thread(target=_run, daemon=True).start()
