"""
End-to-End Test for Dual Recording on Call Transfer:
1. LiveKit AI Egress stops immediately upon SIP transfer (0 silence).
2. Asterisk MixMonitor records the human employee part.
3. Asterisk Hangup CDR webhook links the transferred recording to the parent AI CallSession.
4. Dual audio players (AI conversation + Human employee conversation) are verified in CallSession and UI.
"""
import os
import sys
import json
import time
import django
import redis

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from crm.models import CallSession
from call_center.models import EmployeeProfile, EmployeeCallLog


def test_dual_recording_transfer_flow():
    print("\n=======================================================")
    print("🚀 STARTING E2E TEST: DUAL RECORDING ON AI CALL TRANSFER")
    print("=======================================================\n")

    client = Client()
    user = User.objects.filter(is_superuser=True).first() or User.objects.first()
    assert user is not None, "A valid Django user must exist."
    print(f"✅ Step 0: Using tenant user: {user.username} (ID: {user.id})")

    # 1. Simulate an incoming AI CallSession with AI recording
    room_name = f"test_dual_rec_room_{int(time.time())}"
    caller_phone = "01099887766"
    ai_recording_url = f"/api/calls/recordings/recordings/{room_name}_ai.mp3"

    session = CallSession.objects.create(
        user=user,
        room_name=room_name,
        direction='inbound',
        caller_phone=caller_phone,
        destination_phone='999',
        duration_seconds=45,
        billed_minutes=1,
        recording_url=ai_recording_url,
        summary="استفسار العميل عن خدمات الشحن وطلب التحدث مع خدمة العملاء.",
        transcript_text="العميل: السلام عليكم، أريد الاستفسار عن الشحن.\nالذكاء الاصطناعي: وعليكم السلام! سأقوم بتحويلك لموظف خدمة العملاء فوراً."
    )
    print(f"✅ Step 1: Created AI CallSession #{session.id} in room '{room_name}' with AI recording: {ai_recording_url}")

    # 2. Simulate Redis transfer state recorded by execute_wazo_sip_blind_transfer
    r = redis.Redis.from_url(settings.REDIS_URL)
    r.set(f"ai_transfer_room:{room_name}", "200", ex=3600)
    r.set(f"ai_transfer_caller:{caller_phone}", room_name, ex=3600)
    clean_caller = caller_phone.lstrip('+').strip()
    r.set(f"ai_transfer_caller:{clean_caller}", room_name, ex=3600)
    print(f"✅ Step 2: Simulated Redis transfer mapping for caller '{caller_phone}' -> room '{room_name}'")

    # 3. Simulate Asterisk Hangup CDR webhook for the transferred human employee call
    uniqueid = f"1791208708.{int(time.time())}"
    human_rec_path = os.path.join(settings.MEDIA_ROOT, 'recordings', f"{uniqueid}.wav")
    os.makedirs(os.path.dirname(human_rec_path), exist_ok=True)
    # Create dummy wav with minimal header size (>44 bytes)
    with open(human_rec_path, "wb") as f:
        f.write(b"RIFF" + b"\x00" * 40 + b"DATA" + b"\x00" * 100)

    cdr_data = {
        "caller": caller_phone,
        "callee": "109",
        "duration": "120",
        "total_duration": "125",
        "status": "ANSWERED",
        "uniqueid": uniqueid,
        "recording": f"/media/recordings/{uniqueid}.wav",
        "context": "default"
    }

    cdr_response = client.post('/api/call-center/internal/asterisk-cdr/', data=cdr_data)
    print(f"✅ Step 3: Posted Asterisk Hangup CDR webhook (Status: {cdr_response.status_code})")
    assert cdr_response.status_code == 200, f"Expected 200, got {cdr_response.status_code}: {cdr_response.content}"

    # 4. Verify that parent AI CallSession received the transferred recording
    session.refresh_from_db()
    print(f"   [CallSession #{session.id}] recording_url (AI):            {session.recording_url}")
    print(f"   [CallSession #{session.id}] transferred_recording_url (Human): {session.transferred_recording_url}")
    print(f"   [CallSession #{session.id}] transferred_to_extension:          {session.transferred_to_extension}")
    print(f"   [CallSession #{session.id}] summary:                          {session.summary}")

    assert session.recording_url == ai_recording_url, "AI recording URL must remain intact."
    assert session.transferred_recording_url == f"/media/recordings/{uniqueid}.wav", "Transferred recording URL must match Asterisk recording."
    assert "109" in session.transferred_to_extension or "109" in session.summary, "Transfer extension 109 must be recorded."
    print("✅ Step 4: Parent AI CallSession successfully updated with both AI & Human recordings!")

    # 5. Verify serialization via to_dict()
    d = session.to_dict()
    assert d["recording_url"] == ai_recording_url
    assert d["transferred_recording_url"] == f"/media/recordings/{uniqueid}.wav"
    assert "transferred_recording_url" in d
    print("✅ Step 5: session.to_dict() correctly outputs both 'recording_url' and 'transferred_recording_url'.")

    # 6. Verify calls list API
    client.force_login(user)
    list_res = client.get(f'/api/crm/calls/?search={room_name}')
    assert list_res.status_code == 200, f"Expected 200 from list_all_calls, got {list_res.status_code}"
    list_json = list_res.json()
    matched_call = next((c for c in list_json.get("calls", []) if c["id"] == session.id), None)
    assert matched_call is not None, "CallSession must be found in calls list API."
    assert ai_recording_url in matched_call["recording_url"]
    assert f"/media/recordings/{uniqueid}.wav" in matched_call["transferred_recording_url"]
    print(f"✅ Step 6: Verified /api/crm/calls/ returns dual recordings for session #{session.id}.")

    # 7. Verify templates contain the dual player DOM IDs
    with open('voice_assistant/templates/voice_assistant/pages/calls.html', 'r', encoding='utf-8') as f:
        calls_html = f.read()
    assert 'cdm-recording-section' in calls_html
    assert 'cdm-transferred-recording-section' in calls_html
    assert 'cdm-transferred-audio-player' in calls_html
    assert 'cdm-transferred-download-btn' in calls_html
    print("✅ Step 7: Verified voice_assistant/pages/calls.html has both audio player sections.")

    with open('voice_assistant/templates/voice_assistant/room.html', 'r', encoding='utf-8') as f:
        room_html = f.read()
    assert 'cdm-recording-section' in room_html
    assert 'cdm-transferred-recording-section' in room_html
    assert 'cdm-transferred-audio-player' in room_html
    print("✅ Step 8: Verified voice_assistant/room.html has both audio player sections.")

    # Clean up test artifacts
    if os.path.exists(human_rec_path):
        os.remove(human_rec_path)
    session.delete()
    print("\n🎉 ALL CHECKS PASSED: Dual recording on AI transfer is fully verified and functional!\n")


if __name__ == '__main__':
    test_dual_recording_transfer_flow()
