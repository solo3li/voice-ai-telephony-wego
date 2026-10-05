"""End-to-End Test Suite for Structured Live Context Feature (In-Memory Redis Cache & APIs)."""
import os
import sys
import json
import django

# Setup Django Environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from django.conf import settings
from agents.models import TenantLiveContext
from agents.live_context_service import (
    get_user_live_context_cached,
    set_user_live_context,
    delete_user_live_context,
    format_live_context_for_prompt,
    get_redis_client,
    MAX_LIVE_CONTEXT_BYTES,
    REDIS_KEY_TEMPLATE
)
from agents.views import (
    api_internal_agent_bootstrap,
    api_user_live_context_web,
    api_user_live_context_preview_web
)
from developer.models import UserApiKey
from developer.views import api_user_live_context
from partners.models import PartnerProfile, PartnerClientRelationship
from partners.views import api_partner_client_live_context

SAMPLE_RESTAURANT_DATA = {
    "restaurant_name": "مطعم بيسترو إيطاليانو",
    "out_of_stock": [
        "بيتزا باربيكيو دجاج حجم كبير",
        "سلطة سيزر بالدجاج"
    ],
    "branches": [
        {
            "name": "فرع المعادي (الرئيسي)",
            "status": "مفتوح حالياً",
            "hours": "11:00 ص حتى 02:00 ص",
            "address": "شارع 9، المعادي",
            "phone": "+201011112222"
        },
        {
            "name": "فرع التجمع الخامس",
            "status": "مفتوح حالياً",
            "hours": "12:00 م حتى 01:00 ص",
            "address": "شارع التسعين الشمالي",
            "phone": "+201033334444"
        }
    ],
    "delivery_zones": [
        {
            "zone": "المعادي ودجلة",
            "fee": "20 جنيه",
            "min_order": "100 جنيه",
            "estimated_time": "35 - 45 دقيقة"
        },
        {
            "zone": "التجمع الخامس والرحاب",
            "fee": "35 جنيه",
            "min_order": "150 جنيه",
            "estimated_time": "45 - 60 دقيقة"
        }
    ],
    "offers": [
        {
            "title": "عرض الويك إند الذهبي",
            "price": "299 جنيه",
            "description": "2 بيتزا لارج + لتر كوكاكولا + بطاطس ويدجز مجاناً"
        }
    ],
    "menu": {
        "البيتزا الإيطالية": [
            { "name": "مارجريتا كلاسيك", "price": "140ج وسط / 190ج كبير" },
            { "name": "بيبروني سوبريم", "price": "170ج وسط / 230ج كبير" }
        ],
        "المشروبات": [
            { "name": "كوكاكولا", "price": "25 جنيه" },
            { "name": "عصير برتقال طبيعي", "price": "45 جنيه" }
        ]
    }
}


def run_all_tests():
    print("======================================================================")
    print("🚀 STARTING E2E TESTS: Structured Live Context (Redis Cache & APIs)")
    print("======================================================================")
    factory = RequestFactory()

    # Create / Fetch Test Users
    user, _ = User.objects.get_or_create(username="test_live_ctx_user", defaults={"email": "ctx@test.com"})
    partner_user, _ = User.objects.get_or_create(username="test_live_partner_user", defaults={"email": "partner_ctx@test.com"})
    client_user, _ = User.objects.get_or_create(username="test_live_client_user", defaults={"email": "client_ctx@test.com"})

    # Setup Developer API Key
    dev_key_obj = UserApiKey.objects.filter(user=user).first()
    if not dev_key_obj or not dev_key_obj.key:
        if dev_key_obj:
            dev_key_obj.delete()
        dev_key_obj = UserApiKey.generate_for_user(user=user, name="Test Context Dev Key")
    dev_api_key = dev_key_obj.key

    # Setup Partner Profile & Relationship
    partner_profile = PartnerProfile.objects.filter(user=partner_user).first()
    if not partner_profile:
        partner_profile = PartnerProfile.objects.create(
            user=partner_user,
            company_name="Context Partner Co",
            status="approved",
            custom_rate_per_minute=0.05
        )
    elif partner_profile.status != "approved" or not partner_profile.api_key:
        partner_profile.status = "approved"
        partner_profile.save()
    partner_api_key = partner_profile.api_key

    PartnerClientRelationship.objects.get_or_create(
        partner=partner_profile,
        client=client_user,
        defaults={"external_reference": "POS-STORE-001"}
    )

    # -------------------------------------------------------------------------
    # TEST 1: Dual-Write & In-Memory Redis Storage
    # -------------------------------------------------------------------------
    print("\n--- TEST 1: Service Dual-Write (PostgreSQL & Redis Sync) ---")
    result = set_user_live_context(user.id, SAMPLE_RESTAURANT_DATA)
    assert result["size_bytes"] > 0, "size_bytes must be computed"

    # Verify DB
    db_ctx = TenantLiveContext.objects.filter(user=user).first()
    assert db_ctx is not None, "TenantLiveContext must exist in DB"
    assert db_ctx.data["restaurant_name"] == "مطعم بيسترو إيطاليانو"

    # Verify Redis
    r = get_redis_client()
    redis_key = REDIS_KEY_TEMPLATE.format(user_id=user.id)
    cached_raw = r.get(redis_key)
    assert cached_raw is not None, "Redis key must be set"
    cached_dict = json.loads(cached_raw)
    assert cached_dict["restaurant_name"] == "مطعم بيسترو إيطاليانو"
    print(f"✅ TEST 1 PASSED: Data written to DB ({db_ctx.size_bytes} bytes) and cached in Redis.")

    # -------------------------------------------------------------------------
    # TEST 2: Cache Hydration (Cache Miss Fallback)
    # -------------------------------------------------------------------------
    print("\n--- TEST 2: Cache Hydration (Postgres -> Redis upon Cache Miss) ---")
    r.delete(redis_key)
    assert r.get(redis_key) is None, "Redis key must be deleted"

    hydrated_data = get_user_live_context_cached(user.id)
    assert hydrated_data.get("restaurant_name") == "مطعم بيسترو إيطاليانو", "Must retrieve from DB"
    # Verify Redis was re-hydrated
    assert r.get(redis_key) is not None, "Redis key must be re-hydrated automatically"
    print("✅ TEST 2 PASSED: Automatic cache hydration verified.")

    # -------------------------------------------------------------------------
    # TEST 3: Payload Size Guardrail & Atomic Overwrites
    # -------------------------------------------------------------------------
    print("\n--- TEST 3: Payload Size Limit & Atomic Overwrite ---")
    oversized_data = {"giant_blob": "X" * (MAX_LIVE_CONTEXT_BYTES + 500)}
    try:
        set_user_live_context(user.id, oversized_data)
        assert False, "Should have raised ValueError for payload exceeding 100KB"
    except ValueError as e:
        print(f"Expected size validation error caught: {e}")

    # Atomic Overwrite with new data
    new_data = {
        "restaurant_name": "مطعم البرجر السريع الجديد",
        "out_of_stock": ["برجر دبل بيف"]
    }
    set_user_live_context(user.id, new_data)
    fresh_cached = get_user_live_context_cached(user.id)
    assert fresh_cached["restaurant_name"] == "مطعم البرجر السريع الجديد"
    assert "branches" not in fresh_cached, "Old branches must be completely removed by atomic overwrite"
    print("✅ TEST 3 PASSED: Size guardrail enforced & atomic overwrite confirmed (no state drift).")

    # -------------------------------------------------------------------------
    # TEST 4: Prompt Formatter / Compiler
    # -------------------------------------------------------------------------
    print("\n--- TEST 4: Prompt Compiler (format_live_context_for_prompt) ---")
    compiled_prompt = format_live_context_for_prompt(SAMPLE_RESTAURANT_DATA)
    assert "بيانات النشاط اللحظية المحدثة والمنظمة (Ground Truth)" in compiled_prompt
    assert "مطعم بيسترو إيطاليانو" in compiled_prompt
    assert "أصناف غير متوفرة اليوم نهائياً (Out of Stock)" in compiled_prompt
    assert "بيتزا باربيكيو دجاج حجم كبير" in compiled_prompt
    assert "فرع المعادي" in compiled_prompt
    assert "المعادي ودجلة" in compiled_prompt
    assert "مارجريتا كلاسيك" in compiled_prompt
    print("✅ TEST 4 PASSED: Prompt compiled into structured, unambiguous Markdown instructions.")

    # -------------------------------------------------------------------------
    # TEST 5: Developer REST API (/api/v1/context/)
    # -------------------------------------------------------------------------
    print("\n--- TEST 5: Developer REST API (PUT, GET, DELETE) ---")
    # PUT
    put_req = factory.put(
        "/api/v1/context/",
        data=json.dumps(SAMPLE_RESTAURANT_DATA),
        content_type="application/json",
        HTTP_X_API_KEY=dev_api_key
    )
    put_resp = api_user_live_context(put_req)
    assert put_resp.status_code == 200, f"Expected 200, got {put_resp.status_code}"
    put_json = json.loads(put_resp.content.decode('utf-8'))
    assert put_json["status"] == "success"

    # GET
    get_req = factory.get(
        "/api/v1/context/",
        HTTP_X_API_KEY=dev_api_key
    )
    get_resp = api_user_live_context(get_req)
    assert get_resp.status_code == 200
    get_json = json.loads(get_resp.content.decode('utf-8'))
    assert get_json["cached_in_redis"] is True
    assert get_json["context"]["data"]["restaurant_name"] == "مطعم بيسترو إيطاليانو"

    # DELETE
    del_req = factory.delete(
        "/api/v1/context/",
        HTTP_X_API_KEY=dev_api_key
    )
    del_resp = api_user_live_context(del_req)
    assert del_resp.status_code == 200
    # Verify cleared in Redis
    assert r.get(redis_key) is None
    print("✅ TEST 5 PASSED: Developer API CRUD verified with X-API-Key auth.")

    # -------------------------------------------------------------------------
    # TEST 6: Partner REST API (/api/partner/v1/clients/<id>/context/)
    # -------------------------------------------------------------------------
    print("\n--- TEST 6: Partner REST API (Multi-Tenant Client Scoped) ---")
    client_ctx_data = {
        "restaurant_name": "سوشي بار الشريك",
        "out_of_stock": ["سالمون رول"],
        "branches": [{"name": "الزمالك", "status": "مفتوح"}]
    }
    p_put_req = factory.put(
        f"/api/partner/v1/clients/{client_user.id}/context/",
        data=json.dumps(client_ctx_data),
        content_type="application/json",
        HTTP_X_PARTNER_KEY=partner_api_key
    )
    p_put_resp = api_partner_client_live_context(p_put_req, client_id=client_user.id)
    assert p_put_resp.status_code == 200, f"Expected 200, got {p_put_resp.status_code}"

    # Verify Redis for client
    client_redis_key = REDIS_KEY_TEMPLATE.format(user_id=client_user.id)
    assert r.get(client_redis_key) is not None

    p_get_req = factory.get(
        f"/api/partner/v1/clients/{client_user.id}/context/",
        HTTP_X_PARTNER_KEY=partner_api_key
    )
    p_get_resp = api_partner_client_live_context(p_get_req, client_id=client_user.id)
    assert p_get_resp.status_code == 200
    p_get_json = json.loads(p_get_resp.content.decode('utf-8'))
    assert p_get_json["context"]["data"]["restaurant_name"] == "سوشي بار الشريك"

    # Negative test: unauthorized client
    unauth_req = factory.get(
        f"/api/partner/v1/clients/{user.id}/context/",
        HTTP_X_PARTNER_KEY=partner_api_key
    )
    unauth_resp = api_partner_client_live_context(unauth_req, client_id=user.id)
    assert unauth_resp.status_code in (403, 404), "Should not allow partner to access foreign client"
    print("✅ TEST 6 PASSED: Partner API multi-tenant client isolation verified.")

    # -------------------------------------------------------------------------
    # TEST 7: Web Internal Dashboard API & Prompt Preview
    # -------------------------------------------------------------------------
    print("\n--- TEST 7: Internal Dashboard UI Web Endpoints ---")
    web_post_req = factory.post(
        "/api/agents/context/",
        data=json.dumps(SAMPLE_RESTAURANT_DATA),
        content_type="application/json"
    )
    web_post_req.user = user
    web_post_resp = api_user_live_context_web(web_post_req)
    assert web_post_resp.status_code == 200

    # Preview API
    preview_req = factory.post(
        "/api/agents/context/preview/",
        data=json.dumps({"data": SAMPLE_RESTAURANT_DATA}),
        content_type="application/json"
    )
    preview_req.user = user
    preview_resp = api_user_live_context_preview_web(preview_req)
    assert preview_resp.status_code == 200
    preview_json = json.loads(preview_resp.content.decode('utf-8'))
    assert "مطعم بيسترو إيطاليانو" in preview_json["preview"]
    print("✅ TEST 7 PASSED: Internal Web Dashboard endpoints & preview working seamlessly.")

    # -------------------------------------------------------------------------
    # TEST 8: Agent Bootstrap & Dynamic System Prompt Injection
    # -------------------------------------------------------------------------
    print("\n--- TEST 8: Agent Session Bootstrap & Dynamic Prompt Injection ---")
    from config.settings import INTERNAL_API_KEY
    b_req = factory.post(
        "/api/agents/internal/bootstrap/",
        data=json.dumps({"user_id": user.id}),
        content_type="application/json",
        HTTP_X_INTERNAL_API_KEY=INTERNAL_API_KEY
    )
    b_resp = api_internal_agent_bootstrap(b_req)
    assert b_resp.status_code == 200
    b_json = json.loads(b_resp.content.decode('utf-8'))
    assert "live_context" in b_json, "live_context must be returned in bootstrap"
    assert b_json["live_context"]["restaurant_name"] == "مطعم بيسترو إيطاليانو"

    # Compile prompt with live_context format service
    system_instruction = format_live_context_for_prompt(b_json["live_context"])
    assert "بيانات النشاط اللحظية المحدثة والمنظمة (Ground Truth)" in system_instruction
    assert "بيتزا باربيكيو دجاج حجم كبير" in system_instruction
    assert "فرع المعادي (الرئيسي)" in system_instruction
    print("✅ TEST 8 PASSED: Live context included in Agent Bootstrap and dynamically compiled into prompt!")

    print("\n======================================================================")
    print("🎉 ALL 8 E2E LIVE CONTEXT TEST SUITES PASSED FLAWLESSLY!")
    print("======================================================================\n")


if __name__ == "__main__":
    run_all_tests()
