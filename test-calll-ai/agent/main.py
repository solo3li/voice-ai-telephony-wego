"""Standalone Voice Agent Service entrypoint with LiveKit Agents 1.8+ Architecture.

Runs the official Multi-Process LiveKit Agents Worker Pool with Gemini 3.8 Multimodal Live API,
while concurrently maintaining background Redis transfer listeners and legacy dispatch bridges.
"""
import os
import sys
import types
import asyncio
import threading
import json
import redis.asyncio as aioredis

# Ensure current directory is on sys.path and register 'agent' module alias if needed
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
for p in [current_dir, parent_dir]:
    if p and p not in sys.path:
        sys.path.insert(0, p)

if "agent" not in sys.modules:
    agent_pkg = types.ModuleType("agent")
    agent_pkg.__path__ = [current_dir]
    sys.modules["agent"] = agent_pkg

# Core Configuration & Logging
from agent.config import (
    logger,
    LIVEKIT_INTERNAL_URL,
    LIVEKIT_API_KEY,
    LIVEKIT_API_SECRET,
    CENTRIFUGO_HTTP_API_URL,
    CENTRIFUGO_API_KEY,
    GEMINI_API_KEY,
    GEMINI_LIVE_MODEL,
    REDIS_URL,
    DJANGO_API_URL,
    INTERNAL_API_KEY,
)

# Clients & Network Pool
from agent.clients import (
    notify_centrifugo,
    notify_centrifugo_async,
    fetch_agent_bootstrap_sync,
    fetch_agent_bootstrap_async,
    trigger_ai_transfer_sync,
    trigger_ai_transfer_async,
    query_knowledge_base_sync,
    query_knowledge_base_async,
    fetch_user_active_profile_sync,
    fetch_customer_memory_sync,
    fetch_user_mcp_servers_sync,
    fetch_user_mcp_server_sync,
    save_call_session_and_update_memory_sync,
    save_call_session_and_update_memory_async,
    parse_mcp_servers_from_bootstrap,
    parse_customer_memory_from_bootstrap,
    parse_active_profile_from_bootstrap,
    execute_mcp_tool_call,
    close_http_session,
)

# Prompts & Instruction Builders
from agent.prompts import (
    build_dynamic_system_instruction,
    DIALECT_RULES_MAP,
    VERBOSITY_INSTRUCTIONS,
    generate_welcome_greeting,
)

# Audio Handling
from agent.audio import (
    stream_user_audio_to_queue,
    setup_room_audio_listeners,
)

# Session Management
from agent.session import (
    AgentSessionState,
    distill_and_update_memory,
    build_gemini_tools,
    handle_gemini_tool_call,
    run_agent_session,
    BACKGROUND_TASKS,
    track_background_task,
)

# Transfer & Queue
from agent.transfer import (
    execute_ai_transfer_and_hold,
    handle_webrtc_transfer_session,
)
from agent.queue_manager import run_queue_session

# Workers
from agent.workers import (
    transfer_events_worker,
    run_agent_dispatcher_loop,
)

# Official LiveKit Worker
from agent.livekit_worker import main as livekit_worker_main, entrypoint as livekit_entrypoint

from livekit import api

__all__ = [
    # Config
    "logger",
    "LIVEKIT_INTERNAL_URL",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
    "CENTRIFUGO_HTTP_API_URL",
    "CENTRIFUGO_API_KEY",
    "GEMINI_API_KEY",
    "GEMINI_LIVE_MODEL",
    "REDIS_URL",
    "DJANGO_API_URL",
    "INTERNAL_API_KEY",
    # Clients
    "notify_centrifugo",
    "notify_centrifugo_async",
    "fetch_agent_bootstrap_sync",
    "fetch_agent_bootstrap_async",
    "trigger_ai_transfer_sync",
    "trigger_ai_transfer_async",
    "query_knowledge_base_sync",
    "query_knowledge_base_async",
    "fetch_user_active_profile_sync",
    "fetch_customer_memory_sync",
    "fetch_user_mcp_servers_sync",
    "fetch_user_mcp_server_sync",
    "save_call_session_and_update_memory_sync",
    "save_call_session_and_update_memory_async",
    "parse_mcp_servers_from_bootstrap",
    "parse_customer_memory_from_bootstrap",
    "parse_active_profile_from_bootstrap",
    "execute_mcp_tool_call",
    # Prompts
    "build_dynamic_system_instruction",
    "DIALECT_RULES_MAP",
    "VERBOSITY_INSTRUCTIONS",
    "generate_welcome_greeting",
    # Audio
    "stream_user_audio_to_queue",
    "setup_room_audio_listeners",
    # Session
    "AgentSessionState",
    "distill_and_update_memory",
    "build_gemini_tools",
    "handle_gemini_tool_call",
    "run_agent_session",
    "BACKGROUND_TASKS",
    "track_background_task",
    # Transfer & Queue
    "execute_ai_transfer_and_hold",
    "handle_webrtc_transfer_session",
    "run_queue_session",
    # Workers & Entrypoint
    "transfer_events_worker",
    "run_agent_dispatcher_loop",
    "livekit_worker_main",
    "livekit_entrypoint",
    "main",
]


async def _run_background_services(shutdown_event: asyncio.Event):
    """Run WebRTC Transfer worker and Redis bridge concurrently in background thread."""
    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    transfer_task = asyncio.create_task(transfer_events_worker(r, shutdown_event))

    async def bridge_legacy_redis_jobs():
        logger.info("[Bridge] Listening on Redis 'agent_jobs' to forward to LiveKit Native Dispatch...")
        while not shutdown_event.is_set():
            try:
                item = await r.brpop("agent_jobs", timeout=1.0)
                if item:
                    _, raw = item
                    if raw and raw.strip():
                        raw_str = raw.strip()
                        parsed = {}
                        try:
                            parsed = json.loads(raw_str) if raw_str.startswith("{") else {"room_name": raw_str}
                        except Exception:
                            parsed = {"room_name": raw_str}
                        room_name = parsed.get("room_name", raw_str)
                        if not room_name:
                            continue

                        # Deduplicate: avoid forwarding if already dispatched natively
                        dedup_key = f"agent_dispatched:{room_name}"
                        if not await r.set(dedup_key, "1", nx=True, ex=60):
                            logger.info(f"[Bridge] Room '{room_name}' already dispatched. Skipping duplicate.")
                            continue

                        # Trigger LiveKit Native Agent Dispatch
                        lk = api.LiveKitAPI(LIVEKIT_INTERNAL_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
                        try:
                            req = api.CreateAgentDispatchRequest(
                                agent_name="ai-agent",
                                room=room_name,
                                metadata=raw_str if raw_str.startswith("{") else json.dumps(parsed),
                            )
                            disp = await lk.agent_dispatch.create_dispatch(req)
                            logger.info(f"[Bridge] Forwarded Redis job to LiveKit Native Dispatch ({disp.id}) for room '{room_name}'")
                        except Exception as lk_err:
                            logger.error(f"[Bridge] LiveKit dispatch error for '{room_name}': {lk_err}")
                        finally:
                            await lk.aclose()
            except asyncio.CancelledError:
                break
            except Exception as ex:
                logger.error(f"[Bridge] Error in legacy Redis bridge: {ex}")
                await asyncio.sleep(1.0)

    bridge_task = asyncio.create_task(bridge_legacy_redis_jobs())

    await shutdown_event.wait()
    transfer_task.cancel()
    bridge_task.cancel()
    await asyncio.gather(transfer_task, bridge_task, return_exceptions=True)
    await r.aclose()


def start_background_workers_thread() -> tuple[threading.Thread, asyncio.Event]:
    """Start background WebRTC transfer and Redis bridge tasks in a daemon thread."""
    shutdown_ev = asyncio.Event()

    def _worker_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run_background_services(shutdown_ev))
        finally:
            loop.close()

    t = threading.Thread(target=_worker_loop, daemon=True, name="BackgroundServicesThread")
    t.start()
    return t, shutdown_ev


def main():
    """Main process entrypoint: starts background thread and LiveKit Worker Pool."""
    # Start WebRTC transfer worker and Redis bridge in background thread
    bg_thread, shutdown_ev = start_background_workers_thread()

    # Run Official LiveKit Agents Worker Daemon (Process Isolation pool)
    try:
        livekit_worker_main()
    finally:
        shutdown_ev.set()


if __name__ == "__main__":
    main()
