"""LiveKit Native Agent Dispatcher for Telephony and Call Center.

Creates native agent dispatches in LiveKit Server, triggering the Multi-Process
LiveKit Agents Worker pool without relying on custom Redis worker polling.
Includes dual-stack Redis fallback for graceful backwards compatibility.
"""
import json
import logging
from typing import Dict, Any, Optional

from django.conf import settings
from asgiref.sync import async_to_sync
from livekit import api
import redis

logger = logging.getLogger(__name__)


async def async_dispatch_agent(room_name: str, payload: Dict[str, Any]) -> Optional[str]:
    """Dispatch LiveKit Agent natively to a room with structured metadata."""
    lk = api.LiveKitAPI(settings.LIVEKIT_INTERNAL_URL, settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
    try:
        metadata_str = json.dumps(payload, ensure_ascii=False)
        req = api.CreateAgentDispatchRequest(
            agent_name="ai-agent",
            room=room_name,
            metadata=metadata_str,
        )
        dispatch = await lk.agent_dispatch.create_dispatch(req)
        logger.info(f"==> [NATIVE DISPATCH] Created LiveKit Agent dispatch '{dispatch.id}' for room '{room_name}'")
        return dispatch.id
    except Exception as e:
        logger.error(f"==> [NATIVE DISPATCH ERROR] Failed to dispatch agent to room '{room_name}': {e}", exc_info=True)
        return None
    finally:
        await lk.aclose()


def dispatch_agent_to_room(room_name: str, payload: Dict[str, Any]) -> bool:
    """Synchronous dispatch helper called from Django views, signals, and services.
    
    1. Prevents duplicate concurrent dispatches for the same room.
    2. Triggers LiveKit Native Agent Dispatch via gRPC/HTTP API.
    3. Falls back to Redis 'agent_jobs' only if native dispatch fails.
    """
    try:
        r = redis.Redis.from_url(settings.REDIS_URL)
        # Deduplication check: prevent multiple dispatches to the same room within 60s
        dedup_key = f"agent_dispatched:{room_name}"
        if not r.set(dedup_key, "1", nx=True, ex=60):
            logger.info(f"[DISPATCH] Room '{room_name}' was already dispatched recently. Skipping duplicate.")
            return True

        participant_identity = payload.get("participant_identity")
        if participant_identity and participant_identity.startswith("sip_"):
            clean = participant_identity.replace("sip_sip_", "sip_")
            r.set(f"agent_room:{participant_identity}", room_name, ex=7200)
            r.set(f"agent_room:{clean}", room_name, ex=7200)
        # Always cache full job metadata for worker fallback lookups
        r.set(f"room_job_meta:{room_name}", json.dumps(payload, ensure_ascii=False), ex=3600)
    except Exception as redis_ex:
        logger.error(f"[DISPATCH] Redis setup failed: {redis_ex}")

    dispatch_id = None
    try:
        dispatch_id = async_to_sync(async_dispatch_agent)(room_name, payload)
    except Exception as ex:
        logger.warning(f"[NATIVE DISPATCH] Exception in async_to_sync dispatch: {ex}")

    # Fallback to Redis only if native dispatch failed
    if not dispatch_id:
        try:
            r = redis.Redis.from_url(settings.REDIS_URL)
            job_payload = json.dumps(payload, ensure_ascii=False)
            r.rpush("agent_jobs", job_payload)
            logger.info(f"[DISPATCH] Falling back to Redis 'agent_jobs' for room '{room_name}'.")
            return True
        except Exception as fallback_err:
            logger.error(f"[DISPATCH] Redis fallback push failed: {fallback_err}")
            return False

    logger.debug(f"[DISPATCH] Room '{room_name}' natively dispatched (native_id={dispatch_id}).")
    return True
