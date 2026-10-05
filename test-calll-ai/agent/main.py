"""Standalone Voice Agent Service entrypoint with modular architecture.

Provides backward-compatible re-exports and runs the background daemon loops.
"""
import os
import sys
import types

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

import asyncio
import signal
import redis.asyncio as aioredis

# Core Configuration & Logging
from agent.config import (
    logger,
    LIVEKIT_INTERNAL_URL,
    LIVEKIT_API_KEY,
    LIVEKIT_API_SECRET,
    CENTRIFUGO_HTTP_API_URL,
    CENTRIFUGO_API_KEY,
    GEMINI_API_KEY,
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

__all__ = [
    # Config
    "logger",
    "LIVEKIT_INTERNAL_URL",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
    "CENTRIFUGO_HTTP_API_URL",
    "CENTRIFUGO_API_KEY",
    "GEMINI_API_KEY",
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
    "main",
]


async def main():
    """Main daemon runner for Voice AI Agent service."""
    logger.info("Starting Modular Standalone Voice Agent Service...")
    logger.info(f"LiveKit Internal URL: {LIVEKIT_INTERNAL_URL}")
    logger.info(f"Centrifugo API URL: {CENTRIFUGO_HTTP_API_URL}")
    logger.info(f"Redis URL: {REDIS_URL}")
    logger.info(f"Django API URL: {DJANGO_API_URL}")

    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    active_sessions: dict[str, asyncio.Task] = {}
    shutdown_event = asyncio.Event()

    def handle_signal():
        logger.info("Received termination signal. Shutting down agent daemon...")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except NotImplementedError:
            pass

    # Launch Transfer Worker and Agent Jobs Dispatcher concurrently
    transfer_task = asyncio.create_task(transfer_events_worker(r, shutdown_event))
    dispatcher_task = asyncio.create_task(
        run_agent_dispatcher_loop(r, shutdown_event, active_sessions)
    )

    await shutdown_event.wait()

    logger.info("Stopping dispatcher and transfer workers...")
    transfer_task.cancel()
    dispatcher_task.cancel()
    await asyncio.gather(transfer_task, dispatcher_task, return_exceptions=True)

    logger.info(f"Stopping {len(active_sessions)} active agent session tasks...")
    for rm, t in active_sessions.items():
        t.cancel()
    if active_sessions:
        await asyncio.gather(*active_sessions.values(), return_exceptions=True)

    # Cleanly await any background tasks (like memory distillation)
    if BACKGROUND_TASKS:
        logger.info(f"Awaiting {len(BACKGROUND_TASKS)} active background memory tasks...")
        await asyncio.gather(*BACKGROUND_TASKS, return_exceptions=True)

    await close_http_session()
    await r.aclose()
    logger.info("Voice Agent service stopped gracefully.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
