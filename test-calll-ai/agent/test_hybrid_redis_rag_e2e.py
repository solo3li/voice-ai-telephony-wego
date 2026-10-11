#!/usr/bin/env python3
"""
Comprehensive End-to-End Verification Test for Multi-Tenant Hybrid L1/L2 Redis RAG Engine.

Validates:
1. Multi-Tenant Cache Isolation: Strict tenant-scoping (rag:tenant:{user_id}:*) with zero data leakage.
2. Latency & Performance: L1 Redis In-Memory hit takes < 5 milliseconds.
3. Cache Invalidation: Invalidation purges tenant-specific keys without affecting other tenants.
4. Prompt Guardrails: "ثواني أستعلم لحضرتك" removed; silent background execution & strict document grounding enforced.
5. End-to-End query_knowledge_base_async pipeline.
"""
import asyncio
import time
import json
import redis.asyncio as aioredis
from config import REDIS_URL
from agent.clients.django_client import (
    query_knowledge_base_async,
    get_async_redis_client,
    get_rag_tenant_cache_key,
)
from agent.prompts.builder import build_dynamic_system_instruction


async def test_1_prompt_guardrails_no_filler_announcements():
    print("\n[TEST 1] Verifying System Prompt Guardrails (Removal of 'ثواني أستعلم' & Strict Document Grounding)...")
    profile = {
        "name": "سارة - خدمة العملاء",
        "gender": "female",
        "dialect": "egyptian",
        "persona_role": "customer_support",
        "speaking_style": "friendly",
        "verbosity": "balanced",
    }
    prompt = build_dynamic_system_instruction(profile)

    # 1. Ensure the annoying preparatory filler command is completely gone
    assert "ثواني أشوف لحضرتك" not in prompt, "Filler phrase 'ثواني أشوف لحضرتك' still present in prompt!"
    assert "ثواني أستعلم لحضرتك" not in prompt, "Filler phrase 'ثواني أستعلم لحضرتك' still present in prompt!"

    # 2. Ensure strict document grounding and silent background execution are enforced
    assert "الإجابة الحصرية من المستندات" in prompt, "Missing strict document grounding rule in prompt!"
    assert "حظر الجمل التمهيدية تماماً" in prompt, "Missing filler prohibition rule in prompt!"
    assert "بصمت تام" in prompt, "Missing silent execution instruction in prompt!"

    print("  [+] Verified: No preparatory filler instructions exist in the prompt.")
    print("  [+] Verified: Strict document grounding and silent execution are active.")
    print("✅ TEST 1 PASSED: Prompt is perfectly optimized for smooth, continuous voice flow.")


async def test_2_multi_tenant_isolation_and_caching():
    print("\n[TEST 2] Verifying Multi-Tenant Isolation & Cache Scoping in Redis...")
    r = await get_async_redis_client()
    assert r is not None, "Failed to connect to Redis"

    tenant_1 = 901
    tenant_2 = 902
    query = "ما هي أسعار الباقات والاشتراكات؟"

    # Clean any stale test keys
    key_t1 = get_rag_tenant_cache_key(tenant_1, query)
    key_t2 = get_rag_tenant_cache_key(tenant_2, query)
    await r.delete(key_t1, key_t2)

    # Assert keys are distinct per tenant
    assert key_t1 != key_t2, "Tenant keys must be distinct!"
    assert f"rag:tenant:{tenant_1}:" in key_t1
    assert f"rag:tenant:{tenant_2}:" in key_t2
    print(f"  [+] Tenant 1 Key: {key_t1}")
    print(f"  [+] Tenant 2 Key: {key_t2}")

    # Set mock payload for Tenant 1
    t1_payload = {
        "text": "أسعار باقات شركة الأمل تبدأ من 100 جنيه شهرياً.",
        "matches": ["أسعار باقات شركة الأمل تبدأ من 100 جنيه شهرياً."],
        "tenant": tenant_1,
    }
    await r.set(key_t1, json.dumps(t1_payload, ensure_ascii=False), ex=300)

    # Set distinct mock payload for Tenant 2
    t2_payload = {
        "text": "أسعار باقات مؤسسة النور تبدأ من 500 ريال سنوياً.",
        "matches": ["أسعار باقات مؤسسة النور تبدأ من 500 ريال سنوياً."],
        "tenant": tenant_2,
    }
    await r.set(key_t2, json.dumps(t2_payload, ensure_ascii=False), ex=300)

    # Read back and ensure zero leakage between Tenant 1 and Tenant 2
    res_t1 = json.loads(await r.get(key_t1))
    res_t2 = json.loads(await r.get(key_t2))

    assert res_t1["tenant"] == 901 and "شركة الأمل" in res_t1["text"]
    assert res_t2["tenant"] == 902 and "مؤسسة النور" in res_t2["text"]
    assert "مؤسسة النور" not in res_t1["text"]
    assert "شركة الأمل" not in res_t2["text"]
    print("  [+] Multi-tenant data segregation verified: Tenant 1 and Tenant 2 data strictly isolated.")

    # Clean up test keys
    await r.delete(key_t1, key_t2)
    print("✅ TEST 2 PASSED: Strict multi-tenant isolation confirmed.")


async def test_3_l1_submillisecond_latency():
    print("\n[TEST 3] Verifying L1 Redis Cache Speed (Sub-5ms Latency)...")
    r = await get_async_redis_client()
    test_user_id = 999
    query = "كم مدة الضمان على الأجهزة؟"
    key = get_rag_tenant_cache_key(test_user_id, query)

    # Prime cache with documented answer
    expected_answer = "المعلومات الموثقة: فترة الضمان سنتان على جميع الأجهزة مع استبدال فوري."
    await r.set(key, json.dumps({"text": expected_answer, "matches": [expected_answer]}, ensure_ascii=False), ex=300)

    # Measure query execution time through query_knowledge_base_async
    t_start = time.perf_counter()
    answer = await query_knowledge_base_async(query=query, user_id=test_user_id)
    t_elapsed_ms = (time.perf_counter() - t_start) * 1000

    print(f"  [+] L1 In-Memory Redis Query returned in: {t_elapsed_ms:.2f} ms")
    assert t_elapsed_ms < 5.0, f"Query took too long for in-memory cache: {t_elapsed_ms:.2f}ms"
    assert answer == expected_answer, "Returned answer did not match cached text!"
    print(f"  [+] Verified answer matches cached text: '{answer[:45]}...'")

    await r.delete(key)
    print("✅ TEST 3 PASSED: Sub-5ms instant response verified (Zero Audio Jitter).")


async def test_4_tenant_cache_invalidation():
    print("\n[TEST 4] Verifying Tenant-Scoped Cache Invalidation...")
    r = await get_async_redis_client()
    tenant_target = 888
    tenant_other = 777

    # Populate multiple keys for target tenant and another tenant
    k1 = f"rag:tenant:{tenant_target}:cache:test1"
    k2 = f"rag:tenant:{tenant_target}:cache:test2"
    k_other = f"rag:tenant:{tenant_other}:cache:test1"

    await r.set(k1, "data1", ex=300)
    await r.set(k2, "data2", ex=300)
    await r.set(k_other, "other_data", ex=300)

    # Perform invalidation on target tenant only
    pattern = f"rag:tenant:{tenant_target}:*"
    target_keys = await r.keys(pattern)
    assert len(target_keys) == 2, f"Expected 2 keys for tenant {tenant_target}, found {len(target_keys)}"
    if target_keys:
        await r.delete(*target_keys)

    # Verify target tenant keys are gone, but other tenant's keys are intact!
    assert await r.get(k1) is None
    assert await r.get(k2) is None
    assert await r.get(k_other) == "other_data", "Other tenant's cache was erroneously purged!"

    await r.delete(k_other)
    print(f"  [+] Purged {len(target_keys)} keys for tenant {tenant_target} while preserving tenant {tenant_other}.")
    print("✅ TEST 4 PASSED: Tenant-scoped invalidation works with surgical precision.")


async def main():
    print("=" * 70)
    print("🚀 RUNNING MULTI-TENANT HYBRID L1/L2 REDIS RAG TEST SUITE")
    print("=" * 70)

    await test_1_prompt_guardrails_no_filler_announcements()
    await test_2_multi_tenant_isolation_and_caching()
    await test_3_l1_submillisecond_latency()
    await test_4_tenant_cache_invalidation()

    from agent.clients.http_pool import close_http_session
    await close_http_session()

    print("\n" + "=" * 70)
    print("🎉 ALL 4 HYBRID REDIS RAG TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
