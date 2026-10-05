"""Background worker for WebRTC transfer events from Redis."""
import asyncio
import json
import redis.asyncio as aioredis
from agent.config import logger
from agent.transfer.transfer_bot import handle_webrtc_transfer_session


async def transfer_events_worker(r: aioredis.Redis, shutdown_event: asyncio.Event):
    """Listen for transfer events on Redis and dispatch WebRTC hold music and ring-back sessions."""
    logger.info("Starting Transfer Events Background Worker in agent service...")
    while not shutdown_event.is_set():
        try:
            item = await r.brpop("transfer_events", timeout=1.0)
            if not item:
                continue
            _, raw_ev = item
            data = json.loads(raw_ev)
            from_user = data.get("from_user")
            target = data.get("target")
            call_id = data.get("call_id")
            room_name = data.get("room_name")

            # Resolve active room of from_user or call_id if not explicitly provided
            if not room_name and from_user:
                r_val = await r.get(f"agent_room:{from_user}")
                if r_val:
                    room_name = r_val.decode() if isinstance(r_val, bytes) else str(r_val)

            if not room_name and call_id:
                r_val = await r.get(f"call_room:{call_id}")
                if r_val:
                    room_name = r_val.decode() if isinstance(r_val, bytes) else str(r_val)

            if not room_name:
                logger.warning(f"[TRANSFER WORKER] Could not find active room for from_user '{from_user}'")
                continue

            data["room_name"] = room_name

            # Spawn transfer session with hold music and ring-back
            asyncio.create_task(handle_webrtc_transfer_session(data))

        except asyncio.CancelledError:
            break
        except Exception as ex:
            logger.error(f"Error in transfer worker: {ex}")
            await asyncio.sleep(1)
