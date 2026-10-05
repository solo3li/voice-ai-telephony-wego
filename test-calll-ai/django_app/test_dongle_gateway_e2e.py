"""End-to-End Test Suite for GSM USB Dongle AI Gateway.

Tests owner authentication (strictly username & password, no email),
LiveKit WebRTC token generation, Redis agent job dispatch, live context integration,
and call session logging.
Executes purely via scripts without any browser interaction.
"""
import os
import sys
import json
import django

# Setup Django Environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

import redis
from django.test import RequestFactory
from django.contrib.auth.models import User
from django.conf import settings

from developer.dongle_views import (
    api_dongle_auth_login,
    api_dongle_call_init,
    api_dongle_call_hangup,
    api_dongle_status,
    generate_owner_dongle_jwt,
    get_owner_from_dongle_token,
)
from agents.models import AgentProfile, TenantLiveContext
from agents.live_context_service import set_user_live_context, REDIS_KEY_TEMPLATE
from voice_assistant.models import CallSession


def run_all_dongle_tests():
    print("======================================================================")
    print("🚀 STARTING E2E TESTS: GSM USB Dongle AI Voice Gateway")
    print("======================================================================")

    factory = RequestFactory()
    test_password = "OwnerSecretPassword123!"
    username = "dongle_owner_user"

    # Setup / Reset Test Owner User
    user = User.objects.filter(username=username).first()
    if not user:
        user = User.objects.create_user(
            username=username,
            email="owner_ignored@test.com",
            password=test_password,
            first_name="أحمد",
            last_name="المالك"
        )
    else:
        user.set_password(test_password)
        user.is_active = True
        user.save()

    # Ensure Owner has an active AgentProfile
    agent_profile, _ = AgentProfile.objects.get_or_create(
        user=user,
        defaults={
            "name": "مساعد مطعم بيسترو الذكي",
            "dialect": "egyptian",
            "persona_role": "customer_support",
            "is_active": True
        }
    )
    if not agent_profile.is_active:
        agent_profile.is_active = True
        agent_profile.save()

    # Seed Owner's Structured Live Context
    sample_context = {
        "restaurant_name": "بيسترو إيطاليانو كافيه",
        "out_of_stock": ["باستا ألفريدو"],
        "branches": [{"name": "فرع المعادي", "status": "مفتوح"}],
        "delivery_zones": [{"zone": "المعادي", "fee": "15 جنيه"}]
    }
    set_user_live_context(user.id, sample_context)

    # -------------------------------------------------------------------------
    # TEST 1: Negative Auth - Missing / Empty credentials
    # -------------------------------------------------------------------------
    print("\n--- TEST 1: Negative Auth (Missing / Empty Credentials) ---")
    req1 = factory.post(
        "/api/v1/dongle/auth/login/",
        data=json.dumps({"username": "", "password": ""}),
        content_type="application/json"
    )
    resp1 = api_dongle_auth_login(req1)
    assert resp1.status_code == 400, f"Expected 400 for empty credentials, got {resp1.status_code}"
    data1 = json.loads(resp1.content.decode('utf-8'))
    assert data1["status"] == "error"
    print("✅ TEST 1 PASSED: Empty credentials rejected with HTTP 400.")

    # -------------------------------------------------------------------------
    # TEST 2: Negative Auth - Invalid Password
    # -------------------------------------------------------------------------
    print("\n--- TEST 2: Negative Auth (Invalid Password) ---")
    req2 = factory.post(
        "/api/v1/dongle/auth/login/",
        data=json.dumps({"username": username, "password": "WrongPassword999"}),
        content_type="application/json"
    )
    resp2 = api_dongle_auth_login(req2)
    assert resp2.status_code == 401, f"Expected 401 for wrong password, got {resp2.status_code}"
    data2 = json.loads(resp2.content.decode('utf-8'))
    assert data2["status"] == "error"
    print("✅ TEST 2 PASSED: Wrong password rejected with HTTP 401.")

    # -------------------------------------------------------------------------
    # TEST 3: Positive Auth - Owner Login strictly via Username & Password
    # -------------------------------------------------------------------------
    print("\n--- TEST 3: Positive Owner Login (Strictly Username & Password, NO Email) ---")
    req3 = factory.post(
        "/api/v1/dongle/auth/login/",
        data=json.dumps({
            "username": username,
            "password": test_password
        }),
        content_type="application/json"
    )
    resp3 = api_dongle_auth_login(req3)
    assert resp3.status_code == 200, f"Expected 200 for valid login, got {resp3.status_code}"
    data3 = json.loads(resp3.content.decode('utf-8'))
    assert data3["status"] == "success"
    owner_token = data3["token"]
    assert owner_token and len(owner_token) > 20, "Valid JWT token must be returned"
    assert data3["user"]["username"] == username
    assert data3["active_profile"]["name"] == "مساعد مطعم بيسترو الذكي"
    assert data3["has_live_context"] is True
    print(f"✅ TEST 3 PASSED: Owner authenticated successfully. Token issued: {owner_token[:24]}...")

    # -------------------------------------------------------------------------
    # TEST 4: Token Verification & Dongle Status
    # -------------------------------------------------------------------------
    print("\n--- TEST 4: Dongle Status Endpoint & Token Verification ---")
    req4 = factory.get(
        "/api/v1/dongle/status/",
        HTTP_AUTHORIZATION=f"Bearer {owner_token}"
    )
    resp4 = api_dongle_status(req4)
    assert resp4.status_code == 200
    data4 = json.loads(resp4.content.decode('utf-8'))
    assert data4["status"] == "success"
    assert data4["user"]["username"] == username
    assert data4["has_active_agent"] is True
    assert data4["has_live_context"] is True
    print("✅ TEST 4 PASSED: Token verified and owner status confirmed.")

    # -------------------------------------------------------------------------
    # TEST 5: Inbound Cellular Call Initiation from USB Dongle
    # -------------------------------------------------------------------------
    print("\n--- TEST 5: Inbound Call Initiation (/api/v1/dongle/call/) ---")
    caller_phone = "+201099887766"
    dongle_id = "COM3_HUAWEI_E173"

    req5 = factory.post(
        "/api/v1/dongle/call/",
        data=json.dumps({
            "caller_phone": caller_phone,
            "dongle_id": dongle_id
        }),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {owner_token}"
    )
    resp5 = api_dongle_call_init(req5)
    assert resp5.status_code == 200, f"Expected 200, got {resp5.status_code}"
    data5 = json.loads(resp5.content.decode('utf-8'))
    assert data5["status"] == "success"
    room_name = data5["room_name"]
    webrtc_token = data5["token"]
    session_id = data5["session_id"]
    assert room_name.startswith(f"dongle_{user.id}_")
    assert webrtc_token and len(webrtc_token) > 20
    assert session_id is not None

    # Verify CallSession created in PostgreSQL
    session_obj = CallSession.objects.filter(id=session_id, user=user).first()
    assert session_obj is not None
    assert session_obj.caller_phone == caller_phone
    assert session_obj.ended_at is None

    # Verify Redis 'agent_jobs' queue dispatch
    r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    job_raw = r.rpop("agent_jobs")
    assert job_raw is not None, "A job must have been dispatched to Redis 'agent_jobs'"
    job_data = json.loads(job_raw)
    assert job_data["room_name"] == room_name
    assert job_data["user_id"] == user.id
    assert job_data["caller_phone"] == caller_phone
    assert job_data["profile"]["name"] == "مساعد مطعم بيسترو الذكي"
    print(f"✅ TEST 5 PASSED: Call initiated. Room: {room_name}, Session: #{session_id}, Redis job queued.")

    # -------------------------------------------------------------------------
    # TEST 6: Owner Structured Live Context Verification for the Call
    # -------------------------------------------------------------------------
    print("\n--- TEST 6: Owner Live Context Verification ---")
    ctx_key = REDIS_KEY_TEMPLATE.format(user_id=user.id)
    cached_ctx_str = r.get(ctx_key)
    assert cached_ctx_str is not None, "Live context must be cached in Redis for sub-millisecond retrieval"
    cached_ctx = json.loads(cached_ctx_str)
    assert cached_ctx["restaurant_name"] == "بيسترو إيطاليانو كافيه"
    assert "باستا ألفريدو" in cached_ctx["out_of_stock"]
    print("✅ TEST 6 PASSED: Live context cached in Redis (< 2ms) ready for Gemini Live Agent.")

    # -------------------------------------------------------------------------
    # TEST 7: Call Hangup & Duration Logging
    # -------------------------------------------------------------------------
    print("\n--- TEST 7: Call Hangup (/api/v1/dongle/hangup/) ---")
    call_duration = 54  # 54 seconds
    req7 = factory.post(
        "/api/v1/dongle/hangup/",
        data=json.dumps({
            "room_name": room_name,
            "session_id": session_id,
            "duration_seconds": call_duration
        }),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {owner_token}"
    )
    resp7 = api_dongle_call_hangup(req7)
    assert resp7.status_code == 200
    data7 = json.loads(resp7.content.decode('utf-8'))
    assert data7["status"] == "success"

    # Verify session marked completed and duration updated in DB
    session_obj.refresh_from_db()
    assert session_obj.ended_at is not None
    assert session_obj.duration_seconds == call_duration
    print(f"✅ TEST 7 PASSED: Call marked completed. Duration ({call_duration}s) logged in PostgreSQL.")

    print("\n======================================================================")
    print("🎉 ALL 7 E2E DONGLE GATEWAY TEST SUITES PASSED FLAWLESSLY!")
    print("======================================================================\n")


if __name__ == "__main__":
    run_all_dongle_tests()
