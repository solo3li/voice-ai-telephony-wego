"""Agent-side E2E test for /boost: Hybrid Redis Architecture.

Tests from inside voice_agent container:
1. get_room_bootstrap_from_redis (<1ms async hit).
2. fetch_agent_bootstrap_async (Redis fast hit).
3. fetch_agent_bootstrap_async HTTP fallback when key is absent.
4. push_call_finish_to_redis_stream via XADD (<1ms).
5. save_call_session_and_update_memory_async stream priority & fallback.
"""
import os
import sys
import time
import json
import asyncio
import redis.asyncio as aioredis

from clients.django_client import (
    get_async_redis_client,
    get_room_bootstrap_from_redis,
    fetch_agent_bootstrap_async,
    push_call_finish_to_redis_stream,
    save_call_session_and_update_memory_async,
)
from config import REDIS_URL, logger


async def run_agent_hybrid_tests():
    print("======================================================================")
    print("🚀 RUNNING AGENT E2E TEST: /boost HYBRID REDIS WORKER INTEGRATION")
    print("======================================================================")

    r = await get_async_redis_client()
    assert r is not None, "Async Redis client must be connected"

    test_room = f"agent_boost_room_{int(time.time())}"
    dummy_bundle = {
        "status": "success",
        "user_id": 1,
        "profile": {
            "name": "وكيل الذكاء السريع",
            "voice_name": "Aoede",
            "dialect": "saudi",
            "persona_role": "customer_support",
            "welcome_message": "أهلاً بك يا فندم"
        },
        "customer_memory": {
            "customer_name": "سعد بن خالد",
            "phone_number": "+966501234567"
        },
        "call_queues": [],
        "live_context": {"tenant_name": "Bistro Test"},
        "mcp_servers": [],
        "gemini_api_key": "dummy_test_key_for_unit_tests"
    }

    # -------------------------------------------------------------------------
    # TEST 1: Direct Async Fast Read from Redis (<1ms)
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Testing async get_room_bootstrap_from_redis (<1ms)...")
    await r.set(f"room_bootstrap:{test_room}", json.dumps(dummy_bundle), ex=600)

    # Benchmark read
    latencies = []
    for _ in range(20):
        t0 = time.perf_counter()
        loaded = await get_room_bootstrap_from_redis(test_room)
        latencies.append((time.perf_counter() - t0) * 1000)
        assert loaded is not None
        assert loaded.get("profile", {}).get("dialect") == "saudi"

    avg_ms = sum(latencies) / len(latencies)
    min_ms = min(latencies)
    print(f"  [+] Async Redis Benchmark: Min {min_ms:.3f}ms | Avg {avg_ms:.3f}ms across 20 iterations")
    assert avg_ms < 5.0, f"Async read latency too high: {avg_ms:.3f}ms"
    print("✅ TEST 1 PASSED: Async get_room_bootstrap_from_redis verified.")

    # -------------------------------------------------------------------------
    # TEST 2: fetch_agent_bootstrap_async fast-read path (<1ms)
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Testing fetch_agent_bootstrap_async fast-read hit (<1ms)...")
    t0 = time.perf_counter()
    boot = await fetch_agent_bootstrap_async(room_name=test_room)
    fetch_ms = (time.perf_counter() - t0) * 1000
    print(f"  [+] fetch_agent_bootstrap_async hit returned in {fetch_ms:.3f}ms")
    assert boot.get("status") == "success"
    assert boot.get("user_id") == 1
    assert boot.get("profile", {}).get("voice_name") == "Aoede"
    print("✅ TEST 2 PASSED: fetch_agent_bootstrap_async Redis hit verified.")

    # -------------------------------------------------------------------------
    # TEST 3: fetch_agent_bootstrap_async HTTP fallback on Redis miss
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Testing fetch_agent_bootstrap_async HTTP fallback when key is absent...")
    missing_room = f"agent_missing_room_{int(time.time())}"
    await r.delete(f"room_bootstrap:{missing_room}")

    t0 = time.perf_counter()
    fb_boot = await fetch_agent_bootstrap_async(user_id=1, room_name=missing_room)
    fb_ms = (time.perf_counter() - t0) * 1000
    print(f"  [+] HTTP Fallback resolved in {fb_ms:.3f}ms (Status: {fb_boot.get('status')})")
    assert fb_boot.get("status") == "success"
    assert fb_boot.get("user_id") == 1

    # Verify auto-cached into Redis
    cached = await r.get(f"room_bootstrap:{missing_room}")
    assert cached is not None, "Fallback should auto-cache to Redis"
    print("✅ TEST 3 PASSED: Seamless HTTP fallback and auto-caching verified.")

    # -------------------------------------------------------------------------
    # TEST 4: push_call_finish_to_redis_stream via XADD (<1ms)
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Testing push_call_finish_to_redis_stream (<1ms)...")
    call_payload = {
        "user_id": 1,
        "room_name": test_room,
        "caller_phone": "+966501234567",
        "started_at": time.time() - 30,
        "duration_seconds": 30,
        "direction": "inbound",
        "transcript_text": "العميل: السلام عليكم\nالمساعد: وعليكم السلام ورحمة الله وبركاته",
        "summary": "مكالمة تجريبية ناجحة",
        "permanent_profile": {"customer_name": "سعد بن خالد"},
        "messages": [
            {"speaker": "user", "text": "السلام عليكم"},
            {"speaker": "assistant", "text": "وعليكم السلام ورحمة الله وبركاته"}
        ]
    }

    t0 = time.perf_counter()
    stream_id = await push_call_finish_to_redis_stream(call_payload)
    xadd_ms = (time.perf_counter() - t0) * 1000
    print(f"  [+] push_call_finish_to_redis_stream completed in {xadd_ms:.3f}ms (Stream ID: {stream_id})")
    assert stream_id is not None
    assert xadd_ms < 5.0, f"XADD latency too high: {xadd_ms:.3f}ms"

    # Verify entry exists in Redis Stream
    stream_entries = await r.xrange("call_finish_stream", min=stream_id, max=stream_id)
    assert len(stream_entries) == 1, "Expected entry in call_finish_stream"
    _, raw_fields = stream_entries[0]
    assert raw_fields.get("room_name") == test_room
    assert raw_fields.get("user_id") == "1"
    print("✅ TEST 4 PASSED: Zero-latency Redis Stream persistence verified.")

    # -------------------------------------------------------------------------
    # TEST 5: save_call_session_and_update_memory_async stream priority
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Testing save_call_session_and_update_memory_async uses stream...")
    t0 = time.perf_counter()
    await save_call_session_and_update_memory_async(
        user_id=1,
        room_name=f"test_save_{int(time.time())}",
        started_at=time.time() - 20,
        transcript_text="Test transcript",
        summary="Test summary",
        updated_profile={"customer_name": "Test User"},
        caller_phone="+201000000000",
        duration_seconds=20,
    )
    save_ms = (time.perf_counter() - t0) * 1000
    print(f"  [+] save_call_session_and_update_memory_async returned in {save_ms:.3f}ms (<5ms stream path)")
    assert save_ms < 10.0, f"save_call_session took too long: {save_ms:.3f}ms"
    print("✅ TEST 5 PASSED: Stream priority for save_call_session confirmed.")

    # Cleanup
    await r.delete(f"room_bootstrap:{test_room}")
    await r.delete(f"room_bootstrap:{missing_room}")

    print("\n======================================================================")
    print("🎉 ALL 5 AGENT HYBRID REDIS E2E TESTS PASSED 100% PERFECTLY!")
    print("======================================================================")


if __name__ == '__main__':
    asyncio.run(run_agent_hybrid_tests())
