"""Redis job dispatcher for AI Voice Agent calls and queue sessions."""
import asyncio
import json
from typing import Dict
import redis.asyncio as aioredis
from agent.config import (
    logger,
    LIVEKIT_INTERNAL_URL,
    LIVEKIT_API_KEY,
    LIVEKIT_API_SECRET,
)
from agent.clients.centrifugo_client import notify_centrifugo
from agent.session.gemini_session import run_agent_session
from agent.session.off_hours_session import run_off_hours_session
from agent.queue_manager import run_queue_session


async def run_agent_dispatcher_loop(
    r: aioredis.Redis,
    shutdown_event: asyncio.Event,
    active_sessions: Dict[str, asyncio.Task]
):
    """Poll Redis 'agent_jobs' queue and launch agent or queue sessions."""
    logger.info("Agent dispatcher loop listening for jobs on 'agent_jobs'...")
    while not shutdown_event.is_set():
        try:
            # Non-blocking pop with 1s timeout
            item = await r.brpop("agent_jobs", timeout=1.0)
            if item:
                _, raw_data = item
                raw_data = raw_data.strip()
                if not raw_data:
                    continue

                room_name = raw_data
                user_id = None
                profile_data = None
                is_queue = False
                queue_data = None
                is_outbound_ai = False
                call_goal = None
                destination_phone = None
                caller_phone = "web_dashboard"
                try:
                    parsed = json.loads(raw_data)
                    room_name = parsed.get("room_name", raw_data)
                    user_id = parsed.get("user_id")
                    caller_phone = parsed.get("caller_phone") or "web_dashboard"
                    profile_data = parsed.get("profile")
                    is_queue = parsed.get("is_queue", False)
                    queue_data = parsed.get("queue_data")
                    is_outbound_ai = parsed.get("is_outbound_ai", False)
                    call_goal = parsed.get("call_goal")
                    destination_phone = parsed.get("destination_phone")
                    is_off_hours = parsed.get("is_off_hours", False)
                    off_hours_data = parsed.get("off_hours_data") or {}
                    if is_outbound_ai and destination_phone:
                        caller_phone = destination_phone
                except Exception:
                    pass

                room_name = room_name.strip()
                if not room_name:
                    continue

                # Defensive check: Do not dispatch AI agent for direct human-to-human calls
                if (
                    room_name.startswith("call_ext_")
                    or room_name.startswith("call_tr_")
                    or room_name.startswith("call_rst_")
                    or room_name.startswith("pstn_out_")
                ):
                    logger.info(f"Skipping direct human call room '{room_name}' in agent dispatcher.")
                    continue

                # Check if session is already running for this room
                if room_name in active_sessions and not active_sessions[room_name].done():
                    logger.info(f"Session for room '{room_name}' is already running. Skipping duplicate dispatch.")
                    continue

                logger.info(
                    f"Received new dispatch for room: {room_name} "
                    f"(user_id={user_id}, caller_phone={caller_phone}, is_queue={is_queue}, is_outbound_ai={is_outbound_ai})"
                )

                def make_cleanup(rm):
                    def _cleanup(fut):
                        logger.info(f"Session task finished for room: {rm}")
                        active_sessions.pop(rm, None)
                    return _cleanup

                outbound_ctx = None
                if is_outbound_ai:
                    outbound_ctx = {
                        "is_outbound_ai": True,
                        "call_goal": call_goal,
                        "destination_phone": destination_phone,
                    }

                if is_off_hours:
                    task = asyncio.create_task(
                        run_off_hours_session(
                            room_name=room_name,
                            user_id=user_id,
                            caller_phone=caller_phone,
                            off_hours_data=off_hours_data,
                            profile_data=profile_data,
                        )
                    )
                elif is_queue:
                    task = asyncio.create_task(
                        run_queue_session(
                            room_name=room_name,
                            user_id=user_id,
                            caller_phone=caller_phone,
                            queue_data=queue_data,
                            profile_data=profile_data,
                            livekit_url=LIVEKIT_INTERNAL_URL,
                            api_key=LIVEKIT_API_KEY,
                            api_secret=LIVEKIT_API_SECRET,
                            redis_client=r,
                            notify_func=notify_centrifugo,
                            fallback_agent_func=run_agent_session,
                        )
                    )
                else:
                    task = asyncio.create_task(
                        run_agent_session(
                            room_name=room_name,
                            user_id=user_id,
                            caller_phone=caller_phone,
                            profile_data=profile_data,
                            outbound_context=outbound_ctx,
                        )
                    )

                task.add_done_callback(make_cleanup(room_name))
                active_sessions[room_name] = task

            # Periodically prune any finished tasks
            for rm, t in list(active_sessions.items()):
                if t.done():
                    active_sessions.pop(rm, None)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in agent dispatcher loop: {e}")
            await asyncio.sleep(1)
