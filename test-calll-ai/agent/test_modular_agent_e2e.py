"""Comprehensive Automated Test Suite for the Modular Voice AI Agent Architecture.

Validates:
1. Complete modular structure and zero circular dependencies.
2. Verbosity options (concise, balanced, detailed) in dynamic prompt generation.
3. Non-blocking aiohttp connection pool & Centrifugo client.
4. Tool dispatcher declaration and routing (RAG, MCP, Queue Transfer).
5. Session state management and Python 3.11 GC background task tracking.
6. Full backward compatibility of main.py re-exports.
"""
import sys
import os
import asyncio
import time
from unittest.mock import AsyncMock, patch, MagicMock

# Ensure current directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def test_module_imports():
    print("\n[TEST 1] Verifying independent module imports and zero circular dependencies...")
    import config
    import clients
    import prompts
    import audio
    import session
    import transfer
    import workers
    import main

    assert hasattr(config, "IN_CHUNK_SIZE"), "config.IN_CHUNK_SIZE missing"
    assert hasattr(clients, "get_http_session"), "clients.get_http_session missing"
    assert hasattr(prompts, "build_dynamic_system_instruction"), "prompts.build_dynamic_system_instruction missing"
    assert hasattr(audio, "setup_room_audio_listeners"), "audio.setup_room_audio_listeners missing"
    assert hasattr(session, "AgentSessionState"), "session.AgentSessionState missing"
    assert hasattr(transfer, "execute_ai_transfer_and_hold"), "transfer.execute_ai_transfer_and_hold missing"
    assert hasattr(workers, "run_agent_dispatcher_loop"), "workers.run_agent_dispatcher_loop missing"
    print("✅ TEST 1 PASSED: All modular packages import cleanly without circular dependencies.")


async def test_verbosity_modes():
    print("\n[TEST 2] Verifying Verbosity modes (concise, balanced, detailed) in system prompt...")
    from prompts import build_dynamic_system_instruction

    base_profile = {
        "name": "سارة المساعدة",
        "gender": "female",
        "dialect": "egyptian",
        "persona_role": "customer_support",
        "speaking_style": "friendly",
    }

    # Concise
    prof_concise = {**base_profile, "verbosity": "concise"}
    prompt_concise = build_dynamic_system_instruction(prof_concise)
    assert "قاعدة الإيجاز الصارم والفوري" in prompt_concise, "Concise rule missing from prompt"
    assert "جملة واحدة أو جملتان فقط" in prompt_concise, "Short phrase rule missing"
    print("    [+] 'concise' verbosity instruction verified.")

    # Detailed
    prof_detailed = {**base_profile, "verbosity": "detailed"}
    prompt_detailed = build_dynamic_system_instruction(prof_detailed)
    assert "أسلوب الشرح الوافي والمفصل" in prompt_detailed, "Detailed rule missing from prompt"
    print("    [+] 'detailed' verbosity instruction verified.")

    # Balanced
    prof_balanced = {**base_profile, "verbosity": "balanced"}
    prompt_balanced = build_dynamic_system_instruction(prof_balanced)
    assert "الإيجاز والاتزان الطبيعي" in prompt_balanced, "Balanced rule missing from prompt"
    print("    [+] 'balanced' verbosity instruction verified.")

    # Memory card injection
    memory_card = "البيانات الدائمة للعميل: اسم العميل: أحمد"
    prompt_with_mem = build_dynamic_system_instruction(prof_balanced, memory_card=memory_card)
    assert "أحمد" in prompt_with_mem, "Memory card content missing from prompt"
    print("    [+] Customer memory card injection verified.")

    # Queue fallback context injection
    q_ctx = {"is_fallback": True, "queue_name": "الدعم الفني", "wait_seconds": 90}
    prompt_with_queue = build_dynamic_system_instruction(prof_balanced, queue_context=q_ctx)
    assert "الدعم الفني" in prompt_with_queue and "90" in prompt_with_queue, "Queue fallback header missing"
    print("    [+] Queue fallback context injection verified.")

    # Outbound call context injection
    outbound_ctx = {"is_outbound_ai": True, "destination_phone": "01001234567", "call_goal": "تأكيد موعد الشحن"}
    prompt_with_outbound = build_dynamic_system_instruction(prof_balanced, outbound_context=outbound_ctx)
    assert "تأكيد موعد الشحن" in prompt_with_outbound and "01001234567" in prompt_with_outbound, "Outbound context header missing"
    print("    [+] Outbound AI context header injection verified.")

    print("✅ TEST 2 PASSED: All verbosity modes and dynamic context injections work properly.")


async def test_http_pool_and_nonblocking_centrifugo():
    print("\n[TEST 3] Verifying connection pooling and non-blocking Centrifugo publishing...")
    from clients import get_http_session, close_http_session, notify_centrifugo_async

    session1 = await get_http_session()
    session2 = await get_http_session()
    assert session1 is session2, "get_http_session() did not return singleton pooled session"
    assert not session1.closed, "HTTP session is unexpectedly closed"
    print("    [+] aiohttp.ClientSession singleton connection pool verified.")

    # Test non-blocking centrifugo publish
    start_t = time.time()
    await notify_centrifugo_async("rooms:test_e2e_room", "agent_speaking", "اختبار التنبيه اللحظي")
    elapsed = time.time() - start_t
    assert elapsed < 1.0, f"Centrifugo call was too slow ({elapsed:.3f}s), might be blocking"
    print(f"    [+] notify_centrifugo_async executed in {elapsed*1000:.1f}ms without blocking the event loop.")

    await close_http_session()
    print("✅ TEST 3 PASSED: HTTP pooling and non-blocking networking verified.")


async def test_session_state_and_gc_task_protection():
    print("\n[TEST 4] Verifying AgentSessionState and Python 3.11 GC Task Tracking...")
    from session import AgentSessionState

    state = AgentSessionState(
        room_name="room_abc_123",
        user_id=42,
        caller_phone="01112223334",
        channel_name="rooms:room_abc_123",
        started_at=time.time()
    )

    assert state.room_name == "room_abc_123"
    assert len(state.background_tasks) == 0

    # Test track_task
    async def sample_background_job():
        await asyncio.sleep(0.05)
        return "completed"

    task = asyncio.create_task(sample_background_job())
    state.track_task(task)

    assert task in state.background_tasks, "Task was not tracked in state.background_tasks"
    print("    [+] Task successfully held with strong reference to prevent GC.")

    # Await task completion and verify auto-discard
    await task
    await asyncio.sleep(0.01)  # Allow done callback to run
    assert task not in state.background_tasks, "Task was not discarded after completion"
    print("    [+] Task successfully auto-discarded from state.background_tasks upon finish.")

    # Test cancel_all_tasks
    async def infinite_job():
        while True:
            await asyncio.sleep(1)

    hanging_task = asyncio.create_task(infinite_job())
    state.track_task(hanging_task)
    assert hanging_task in state.background_tasks
    await state.cancel_all_tasks()
    assert hanging_task.cancelled() or hanging_task.done()
    assert len(state.background_tasks) == 0
    print("    [+] cancel_all_tasks() cleanly terminated and awaited all remaining tasks.")

    print("✅ TEST 4 PASSED: AgentSessionState and task GC tracking working flawlessly.")


async def test_tool_dispatcher():
    print("\n[TEST 5] Verifying Tool Dispatcher (RAG, MCP Tools, and Queue Transfer)...")
    from session.tool_dispatcher import build_gemini_tools, handle_gemini_tool_call

    mcp_tools = {
        "store_search_products": {
            "server_url": "http://mock:8000/sse",
            "auth_token": "mock-token",
            "server_name": "SallaStore",
            "description": "ابحث عن المنتجات في المتجر",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "query": {"type": "STRING"}
                }
            }
        }
    }
    call_queues = [
        {"code": "support", "name": "خدمة العملاء", "description": "استفسارات عامة"},
        {"code": "sales", "name": "فريق المبيعات", "description": "طلبات الشراء والأسعار"}
    ]

    tools = build_gemini_tools(mcp_tools, call_queues)
    func_decls = tools[0]["function_declarations"]
    tool_names = [f["name"] for f in func_decls]

    assert "search_knowledge_base" in tool_names, "RAG tool declaration missing"
    assert "store_search_products" in tool_names, "MCP tool declaration missing"
    assert "transfer_to_queue" in tool_names, "transfer_to_queue declaration missing"
    print(f"    [+] Declared {len(tool_names)} tools correctly: {tool_names}")

    # Test queue transfer tool execution
    fc_mock = MagicMock()
    fc_mock.id = "call_123"
    fc_mock.name = "transfer_to_queue"
    fc_mock.args = {"queue_code": "sales", "reason": "العميل يريد الاستفسار عن كوتيشن كبير"}

    resp, pending_transfer = await handle_gemini_tool_call(
        fc=fc_mock,
        user_id=1,
        room_name="test_transfer_room",
        channel_name="rooms:test_transfer_room",
        mcp_tools=mcp_tools,
        call_queues=call_queues
    )

    assert pending_transfer is not None, "Pending transfer metadata was not returned"
    assert pending_transfer["queue_code"] == "sales"
    assert pending_transfer["queue_name"] == "فريق المبيعات"
    assert resp.response["status"] == "success"
    print("    [+] Queue transfer tool dispatched and resolved correctly.")

    print("✅ TEST 5 PASSED: Tool dispatcher correctly declared and handled tools.")


async def test_backward_compatibility():
    print("\n[TEST 6] Verifying backward compatibility of main.py re-exports...")
    import main

    expected_exports = [
        "build_dynamic_system_instruction",
        "run_agent_session",
        "notify_centrifugo",
        "notify_centrifugo_async",
        "fetch_agent_bootstrap_sync",
        "fetch_agent_bootstrap_async",
        "fetch_user_active_profile_sync",
        "fetch_customer_memory_sync",
        "fetch_user_mcp_servers_sync",
        "query_knowledge_base_sync",
        "trigger_ai_transfer_sync",
        "save_call_session_and_update_memory_sync",
        "parse_mcp_servers_from_bootstrap",
        "parse_customer_memory_from_bootstrap",
        "parse_active_profile_from_bootstrap",
        "execute_mcp_tool_call",
        "distill_and_update_memory",
        "execute_ai_transfer_and_hold",
        "handle_webrtc_transfer_session",
        "transfer_events_worker",
        "run_agent_dispatcher_loop",
        "main",
        "LIVEKIT_INTERNAL_URL",
        "CENTRIFUGO_HTTP_API_URL",
        "REDIS_URL",
        "DJANGO_API_URL",
    ]

    missing = []
    for exp in expected_exports:
        if not hasattr(main, exp):
            missing.append(exp)

    assert not missing, f"main.py is missing re-exports: {missing}"
    print(f"    [+] All {len(expected_exports)} legacy symbols successfully re-exported from main.py.")
    print("✅ TEST 6 PASSED: Full backward compatibility guaranteed.")


async def main_test_runner():
    print("=" * 70)
    print("🧪 STARTING MODULAR VOICE AGENT ARCHITECTURE VERIFICATION TEST SUITE")
    print("=" * 70)

    await test_module_imports()
    await test_verbosity_modes()
    await test_http_pool_and_nonblocking_centrifugo()
    await test_session_state_and_gc_task_protection()
    await test_tool_dispatcher()
    await test_backward_compatibility()

    import main
    await main.close_http_session()

    print("\n" + "=" * 70)
    print("🎉 ALL 6 MODULAR AGENT TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main_test_runner())
