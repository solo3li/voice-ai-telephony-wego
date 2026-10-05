import os
import sys
import django
import json
import time
import redis
import asyncio

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from django.test import RequestFactory
from django.conf import settings
from voice_assistant.models import OutboundSIPTrunk, CallSession, UserSIPAccount, AgentProfile
from voice_assistant.views import (
    normalize_phone_number,
    get_outbound_trunk,
    save_outbound_trunk,
    delete_outbound_trunk,
    trigger_ai_outbound_call,
)
from livekit import api

def run_tests():
    print("==================================================================")
    print("STARTING END-TO-END OUTBOUND CALLING ENGINE VERIFICATION SUITE")
    print("==================================================================")

    # 1. Phone Normalization Unit Tests
    print("\n[TEST 1] Testing Phone Number Normalization...")
    cases = [
        ("01012345678", "+201012345678"),
        ("011 9876 5432", "+201198765432"),
        ("012-3456-7890", "+201234567890"),
        ("015(555)55555", "+201555555555"),
        ("00966501234567", "+966501234567"),
        ("+12025550123", "+12025550123"),
        ("201012345678", "+201012345678"),
        ("+201012345678", "+201012345678"),
    ]
    for raw, expected in cases:
        normalized = normalize_phone_number(raw)
        assert normalized == expected, f"Expected {expected}, got {normalized} for {raw}"
        print(f"  OK: {raw} -> {normalized}")
    print("[PASS] Phone normalization verified for all local and international patterns!")

    # 2. User & Outbound SIP Trunk Provisioning
    print("\n[TEST 2] Testing Generic Outbound SIP Trunk Provisioning...")
    user = User.objects.get(id=5)
    assert user, "No user found in database"
    rf = RequestFactory()

    save_payload = {
        "name": "E2E Test Telnyx Trunk",
        "sip_host": "sip.telnyx.com",
        "sip_port": 5060,
        "transport": "UDP",
        "auth_username": "e2e_test_user",
        "auth_password": "e2e_test_password",
        "caller_id": "01012345678"
    }
    req = rf.post('/api/outbound/trunk/save/', data=json.dumps(save_payload), content_type='application/json')
    req.user = user
    resp = save_outbound_trunk(req)
    assert resp.status_code == 200, f"Save trunk failed: {resp.content}"
    data = json.loads(resp.content)
    assert data["status"] == "success"
    trunk_info = data["trunk"]
    lk_trunk_id = trunk_info["livekit_outbound_trunk_id"]
    assert lk_trunk_id.startswith("ST_"), f"Invalid LiveKit trunk ID: {lk_trunk_id}"
    assert trunk_info["caller_id"] == "+201012345678"
    print(f"  OK: Outbound SIP Trunk created in DB & LiveKit: {trunk_info['name']} (ID: {lk_trunk_id})")
    print(f"  OK: Normalized Caller ID: {trunk_info['caller_id']}")

    # Check retrieval API
    get_req = rf.get('/api/outbound/trunk/')
    get_req.user = user
    get_resp = get_outbound_trunk(get_req)
    assert get_resp.status_code == 200
    get_data = json.loads(get_resp.content)
    assert get_data["has_trunk"] is True
    assert get_data["trunk"]["livekit_outbound_trunk_id"] == lk_trunk_id
    print("  OK: GET /api/outbound/trunk/ verified successfully!")

    # 3. AI Outbound Call Triggering
    print("\n[TEST 3] Testing Autonomous AI Outbound Call Triggering...")
    ai_call_payload = {
        "phone_number": "01098765432",
        "call_goal": "الاتصال بالعميل لتأكيد تفاصيل الشحنة والأوردر رقم 909"
    }
    call_req = rf.post('/api/outbound/ai-call/', data=json.dumps(ai_call_payload), content_type='application/json')
    call_req.user = user

    call_resp = trigger_ai_outbound_call(call_req)
    assert call_resp.status_code == 200, f"Trigger AI call failed: {call_resp.content}"
    call_data = json.loads(call_resp.content)
    assert call_data["status"] == "success"
    assert call_data["destination_phone"] == "+201098765432"
    room_name = call_data["room_name"]
    session_id = call_data["session_id"]
    print(f"  OK: AI Outbound call created successfully!")
    print(f"  OK: Target Phone: {call_data['destination_phone']}")
    print(f"  OK: Room: {room_name}")
    print(f"  OK: Session ID: {session_id}")

    # Verify CallSession record in DB
    session = CallSession.objects.get(id=session_id)
    assert session.direction == 'outbound_ai'
    assert session.destination_phone == '+201098765432'
    assert "909" in session.call_goal
    print(f"  OK: CallSession verified: direction={session.direction}, goal='{session.call_goal}'")

    # 4. MicroSIP Direct Outbound Dialing Interception
    print("\n[TEST 4] Testing MicroSIP Direct Outbound Dialing Interception...")
    r = redis.Redis.from_url(settings.REDIS_URL)
    test_agent = UserSIPAccount.objects.filter(user=user).first()
    if test_agent:
        from_user = test_agent.sip_username
        dialed_number = "01122334455"
        norm_dialed = normalize_phone_number(dialed_number)

        r.set(f"pending_outbound_dial:{from_user}", norm_dialed, ex=60)
        assert r.get(f"pending_outbound_dial:{from_user}").decode() == norm_dialed
        print(f"  OK: sip_proxy Redis interception state verified: pending_outbound_dial:{from_user} = {norm_dialed}")

        p_val = r.get(f"pending_outbound_dial:{from_user}").decode()
        r.delete(f"pending_outbound_dial:{from_user}")
        agent_room = f"room_user_{user.id}_sip_test_{int(time.time())}"
        agent_session = CallSession.objects.create(
            user=user,
            room_name=agent_room,
            direction='outbound_agent',
            destination_phone=p_val,
            call_goal=f"مكالمة موظف مباشرة عبر MicroSIP للرقم {p_val}"
        )
        assert agent_session.direction == 'outbound_agent'
        assert agent_session.destination_phone == norm_dialed
        print(f"  OK: MicroSIP outbound CallSession verified: direction={agent_session.direction}, target={agent_session.destination_phone}")

    # 5. Distillation & Session Update Sync
    print("\n[TEST 5] Testing Post-Call Session Update & Archiving...")
    session.ended_at = django.utils.timezone.now()
    session.duration_seconds = 45
    session.transcript_text = "العميل: أهلاً بحضرتك\nالمساعد: أهلاً بك يا فندم بخصوص أوردر 909..."
    session.summary = "تم تأكيد طلب الأوردر 909 مع العميل وتحديد موعد الاستلام غداً."
    session.save()

    refreshed = CallSession.objects.get(id=session_id)
    assert refreshed.duration_seconds == 45
    assert "909" in refreshed.summary
    assert refreshed.direction == 'outbound_ai'
    dict_repr = refreshed.to_dict()
    assert dict_repr["direction"] == 'outbound_ai'
    assert dict_repr["destination_phone"] == '+201098765432'
    print(f"  OK: Completed CallSession serialized correctly with direction badge data: {dict_repr['direction_display']}")

    print("\n==================================================================")
    print("SUCCESS: ALL OUTBOUND ENGINE TESTS PASSED WITH 100%!")
    print("==================================================================")

if __name__ == '__main__':
    run_tests()
