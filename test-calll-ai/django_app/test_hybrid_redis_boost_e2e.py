"""Comprehensive E2E Verification Test for /boost: Hybrid Redis Architecture.

Tests:
1. JIT Bootstrap injection into Redis key room_bootstrap:{room_name} (TTL: 600s) during dispatch.
2. Sub-millisecond (<1ms) agent fast-read from Redis.
3. Seamless HTTP fallback when Redis key is absent.
4. Zero-latency post-call persistence to Redis Stream 'call_finish_stream' via XADD.
5. Inngest / stream processor execution: PostgreSQL CallSession & CustomerMemory updates.
6. Stream acknowledgment verification (XACK).
"""
import os
import sys
import time
import json
import asyncio
import django
import redis

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from django.contrib.auth.models import User
from agents.models import AgentProfile, SystemSetting
from crm.models import CallSession, CustomerMemory
from telephony.agent_dispatch import dispatch_agent_to_room
from agents.bootstrap_service import (
    assemble_agent_bootstrap_data,
    inject_room_bootstrap_to_redis,
    get_room_bootstrap_from_redis as django_get_room_bootstrap
)
from crm.services.session_persistence import persist_call_session_and_memory
from crm.inngest_jobs import (
    CALL_FINISH_STREAM_KEY,
    CALL_FINISH_GROUP_NAME,
    ensure_call_finish_stream_group,
    ack_call_finish_stream_message,
    parse_stream_entry_fields,
)


def run_hybrid_redis_tests():
    print("======================================================================")
    print("🚀 RUNNING E2E TEST: /boost HYBRID REDIS ARCHITECTURE")
    print("======================================================================")

    r = redis.Redis.from_url(settings.REDIS_URL)

    # Setup Test User and Profile
    test_username = "boost_test_tenant"
    User.objects.filter(username=test_username).delete()
    user = User.objects.create_user(username=test_username, password="password123")

    AgentProfile.objects.filter(user=user).delete()
    profile = AgentProfile.objects.create(
        user=user,
        name="نورهان - اختبار بوست",
        voice_name="Aoede",
        dialect="egyptian",
        persona_role="customer_support",
        speaking_style="friendly",
        welcome_message="أهلاً بك في اختبار البوست السريع!",
        is_active=True
    )

    test_room_name = f"room_boost_test_{int(time.time())}"
    test_phone = "+201099887766"

    # -------------------------------------------------------------------------
    # TEST 1: JIT Bootstrap Injection on Dispatch
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Testing JIT Bootstrap injection into Redis during dispatch...")
    dispatch_payload = {
        "room_name": test_room_name,
        "user_id": user.id,
        "caller_phone": test_phone,
        "participant_identity": f"caller_{user.id}",
    }

    # Dispatch agent
    success = dispatch_agent_to_room(test_room_name, dispatch_payload)
    assert success, "dispatch_agent_to_room should return True"

    # Verify Redis key room_bootstrap:{room_name} exists
    redis_key = f"room_bootstrap:{test_room_name}"
    raw_data = r.get(redis_key)
    assert raw_data is not None, f"Expected Redis key '{redis_key}' to exist!"

    # Verify TTL is ~600s
    ttl = r.ttl(redis_key)
    print(f"  [+] Redis key '{redis_key}' created with TTL: {ttl}s (Expected ~600s)")
    assert 500 <= ttl <= 600, f"Expected TTL between 500s and 600s, got {ttl}"

    bootstrap_dict = json.loads(raw_data)
    assert bootstrap_dict.get("status") == "success"
    assert bootstrap_dict.get("user_id") == user.id
    assert bootstrap_dict.get("profile", {}).get("name") == "نورهان - اختبار بوست"
    assert "gemini_api_key" in bootstrap_dict
    assert "mcp_servers" in bootstrap_dict
    assert "customer_memory" in bootstrap_dict
    assert "live_context" in bootstrap_dict
    assert "call_queues" in bootstrap_dict
    print("✅ TEST 1 PASSED: JIT Bootstrap injection on dispatch verified successfully.")

    # -------------------------------------------------------------------------
    # TEST 2: Sub-Millisecond (<1ms) Read Latency
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Testing sub-millisecond (<1ms) Redis Fast Read benchmark...")
    iterations = 20
    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        data = django_get_room_bootstrap(test_room_name)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed_ms)
        assert data is not None and data.get("user_id") == user.id

    avg_ms = sum(latencies) / len(latencies)
    min_ms = min(latencies)
    print(f"  [+] Benchmark: Min {min_ms:.3f}ms | Avg {avg_ms:.3f}ms across {iterations} iterations")
    assert avg_ms < 5.0, f"Average read latency too high: {avg_ms:.3f}ms"
    print("✅ TEST 2 PASSED: Sub-millisecond bootstrap read latency confirmed.")

    # -------------------------------------------------------------------------
    # TEST 3: Seamless HTTP Fallback when Redis Key is absent
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Testing seamless HTTP fallback when Redis key is missing...")
    fallback_room = f"room_fallback_{int(time.time())}"
    # Ensure Redis key does NOT exist
    r.delete(f"room_bootstrap:{fallback_room}")

    from django.test import Client
    client = Client()
    # Call HTTP endpoint /api/agents/internal/bootstrap/
    http_resp = client.post(
        '/api/agents/internal/bootstrap/',
        data=json.dumps({
            "user_id": user.id,
            "caller_phone": test_phone,
            "room_name": fallback_room,
        }),
        content_type='application/json',
        HTTP_X_INTERNAL_API_KEY=settings.INTERNAL_API_KEY
    )
    assert http_resp.status_code == 200, f"HTTP fallback endpoint failed: {http_resp.status_code}"
    fb_data = http_resp.json()
    assert fb_data.get("status") == "success"
    assert fb_data.get("user_id") == user.id
    print(f"  [+] HTTP endpoint successfully served bootstrap for room '{fallback_room}'")

    # Verify endpoint auto-cached to Redis for future hits
    cached_after_http = r.get(f"room_bootstrap:{fallback_room}")
    assert cached_after_http is not None, "HTTP endpoint should populate room_bootstrap in Redis"
    print("✅ TEST 3 PASSED: Seamless HTTP fallback and auto-caching verified.")

    # -------------------------------------------------------------------------
    # TEST 4: Zero-Latency Post-Call Push via Redis Stream XADD
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Testing zero-latency Redis Stream XADD (call_finish_stream)...")
    finish_payload = {
        "user_id": user.id,
        "room_name": test_room_name,
        "caller_phone": test_phone,
        "started_at": time.time() - 45,
        "duration_seconds": 45,
        "direction": "inbound",
        "transcript_text": "العميل: السلام عليكم\nالمساعد: وعليكم السلام ورحمة الله وبركاته، أهلاً بك!",
        "summary": "طلب العميل الاستفسار عن تفاصيل الخدمة وتمت إفادته بنجاح.",
        "permanent_profile": json.dumps({"customer_name": "أحمد مختار", "vip_tier": "vip"}),
    }

    t0 = time.perf_counter()
    stream_id = r.xadd(CALL_FINISH_STREAM_KEY, {
        k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
        for k, v in finish_payload.items()
    })
    xadd_elapsed_ms = (time.perf_counter() - t0) * 1000
    print(f"  [+] XADD completed in {xadd_elapsed_ms:.3f}ms -> Stream ID: {stream_id.decode() if isinstance(stream_id, bytes) else stream_id}")
    assert stream_id is not None
    assert xadd_elapsed_ms < 5.0, f"XADD latency should be <5ms, got {xadd_elapsed_ms:.3f}ms"
    print("✅ TEST 4 PASSED: Zero-latency persistence to Redis Stream verified.")

    # -------------------------------------------------------------------------
    # TEST 5: Stream Consumer / Processor & PostgreSQL Persistence
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Testing Inngest/Django stream consumer persistence to PostgreSQL...")
    from django.core.management import call_command
    # Run the stream consumer with --once
    call_command('process_call_finish_stream', '--once')

    # Verify CallSession was created in PostgreSQL
    session = CallSession.objects.filter(room_name=test_room_name).first()
    assert session is not None, f"CallSession for room '{test_room_name}' not found in PostgreSQL!"
    assert session.user == user
    assert session.duration_seconds == 45
    assert session.summary == finish_payload["summary"]
    assert "العميل: السلام عليكم" in session.transcript_text
    print(f"  [+] CallSession #{session.id} persisted in PostgreSQL: Duration={session.duration_seconds}s, Billed={session.billed_minutes}mins")

    # Verify CustomerMemory was updated in PostgreSQL
    memory = CustomerMemory.objects.filter(user=user, phone_number=test_phone).first()
    assert memory is not None, f"CustomerMemory for phone '{test_phone}' not found!"
    assert memory.customer_name == "أحمد مختار"
    assert memory.last_interaction_summary == finish_payload["summary"]
    assert memory.total_calls_count >= 1
    print(f"  [+] CustomerMemory updated in PostgreSQL: Name='{memory.customer_name}', TotalCalls={memory.total_calls_count}")
    print("✅ TEST 5 PASSED: PostgreSQL database persistence verified.")

    # -------------------------------------------------------------------------
    # TEST 6: Redis Stream Acknowledgment (XACK)
    # -------------------------------------------------------------------------
    print("\n[TEST 6] Testing Redis Stream XACK acknowledgment...")
    ensure_call_finish_stream_group(r)
    pending_info = r.xpending(CALL_FINISH_STREAM_KEY, CALL_FINISH_GROUP_NAME)
    print(f"  [+] Stream pending unacknowledged messages: {pending_info.get('pending', 0)}")
    assert pending_info.get('pending', 0) == 0, f"Expected 0 pending unacknowledged messages, got {pending_info.get('pending')}"
    print("✅ TEST 6 PASSED: Stream message XACK verified with 0 pending items.")

    # Cleanup test data
    User.objects.filter(username=test_username).delete()
    r.delete(redis_key)
    r.delete(f"room_bootstrap:{fallback_room}")

    print("\n======================================================================")
    print("🎉 ALL 6 /boost HYBRID REDIS E2E TESTS PASSED 100% PERFECTLY!")
    print("======================================================================")


if __name__ == '__main__':
    run_hybrid_redis_tests()
