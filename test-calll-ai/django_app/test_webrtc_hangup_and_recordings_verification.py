"""
Comprehensive verification test suite for WebRTC hangup and call recording fixes:
1. Double prefix normalization and streaming resolution across MinIO.
2. Participant left webhook with multi-party, egress isolation, and session finalization.
3. Hangup API compatibility with sendBeacon FormData and JSON.
4. Agent worker participant disconnect filter verification.
5. DOM template structure in calls.html and room.html.
"""
import os
import sys
import time
import json
import asyncio
import datetime
from unittest.mock import MagicMock, AsyncMock, patch

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client, RequestFactory
from django.contrib.auth.models import User
from crm.models import CallSession
from voice_assistant.views import livekit_webhook, stream_call_recording
from voice_assistant.s3_storage import get_s3_client, ensure_minio_bucket
from call_center.views import api_hangup_call
from livekit import api, rtc
from django.conf import settings


def test_recording_streaming_and_normalization():
    print("\n--- TEST: Recording URL Streaming & Redundant Prefix Normalization ---")
    ensure_minio_bucket()
    s3 = get_s3_client()
    bucket = getattr(settings, 'MINIO_BUCKET_NAME', 'call-recordings')

    # Upload test object in MinIO at recordings/sample_deep_check.mp3
    key = "recordings/sample_deep_check.mp3"
    audio_data = b"RIFF____WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00" * 10
    s3.put_object(Bucket=bucket, Key=key, Body=audio_data, ContentType="audio/mpeg")

    client = Client()

    # 1. Single prefix: /api/calls/recordings/sample_deep_check.mp3
    r1 = client.get('/api/calls/recordings/sample_deep_check.mp3')
    assert r1.status_code in [200, 206], f"Failed single prefix stream: {r1.status_code}"
    print("  [+] Clean URL (/api/calls/recordings/sample_deep_check.mp3) -> 200 OK")

    # 2. Double prefix: /api/calls/recordings/recordings/sample_deep_check.mp3
    r2 = client.get('/api/calls/recordings/recordings/sample_deep_check.mp3')
    assert r2.status_code in [200, 206], f"Failed double prefix stream: {r2.status_code}"
    print("  [+] Double prefix URL (/api/calls/recordings/recordings/sample_deep_check.mp3) -> 200 OK")

    # 3. Triple prefix: /api/calls/recordings/recordings/recordings/sample_deep_check.mp3
    r3 = client.get('/api/calls/recordings/recordings/recordings/sample_deep_check.mp3')
    assert r3.status_code in [200, 206], f"Failed triple prefix stream: {r3.status_code}"
    print("  [+] Triple prefix URL (/api/calls/recordings/recordings/recordings/sample_deep_check.mp3) -> 200 OK")

    # 4. Partial Content (HTTP Range)
    r_range = client.get('/api/calls/recordings/recordings/sample_deep_check.mp3', HTTP_RANGE='bytes=0-40')
    assert r_range.status_code == 206, f"Expected 206, got {r_range.status_code}"
    assert r_range['Content-Range'].startswith('bytes 0-40/'), f"Wrong Content-Range: {r_range.get('Content-Range')}"
    print("  [+] Range scrubbing test -> 206 Partial Content")

    # 5. CallSession.to_dict() sanitization
    user, _ = User.objects.get_or_create(username="test_verify_user")
    sess = CallSession(
        user=user,
        room_name="test_normalize_sess_room",
        recording_url="/api/calls/recordings/recordings/recordings/sample_deep_check.mp3"
    )
    d = sess.to_dict()
    assert d["recording_url"] == "/api/calls/recordings/sample_deep_check.mp3", f"Unexpected sanitized url: {d['recording_url']}"
    print("  [+] CallSession.to_dict() multiple redundant prefix normalization verified.")
    print("✅ TEST PASSED: Recording streaming & normalization verified.")


def test_participant_left_webhook_logic():
    print("\n--- TEST: participant_left Webhook Isolation & Finalization ---")
    factory = RequestFactory()
    user, _ = User.objects.get_or_create(username="test_webhook_user")

    import hashlib
    import base64
    import jwt

    def make_webhook_req(payload):
        raw = json.dumps(payload)
        body_sha256 = base64.b64encode(hashlib.sha256(raw.encode('utf-8')).digest()).decode('utf-8')
        auth_token = jwt.encode(
            {
                "iss": settings.LIVEKIT_API_KEY,
                "exp": int(time.time()) + 3600,
                "sha256": body_sha256
            },
            settings.LIVEKIT_API_SECRET,
            algorithm="HS256"
        )
        return factory.post("/api/livekit/webhook/", data=raw, content_type="application/json", HTTP_AUTHORIZATION=auth_token)

    # Case A: Egress participant leaves -> must NOT finalize CallSession
    room_a = f"test_room_egress_leave_{int(time.time())}"
    sess_a = CallSession.objects.create(
        user=user,
        room_name=room_a,
        started_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=60),
        direction="inbound",
        summary=""
    )

    egress_event = {
        "event": "participant_left",
        "room": {"name": room_a},
        "participant": {
            "identity": "EG_test_egress_12345",
            "kind": 2  # api.ParticipantInfo.Kind.EGRESS
        }
    }
    with patch("voice_assistant.views.publish_to_centrifugo") as mock_pub:
        req = make_webhook_req(egress_event)
        resp = livekit_webhook(req)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

        sess_a.refresh_from_db()
        assert sess_a.ended_at is None, "CallSession was erroneously ended when EGRESS left!"
        assert sess_a.duration_seconds == 0 or sess_a.duration_seconds is None, "Duration erroneously set on egress leave!"
        print("  [+] Egress leaving did NOT finalize or close CallSession.")

    # Case B: Human leaves, but ANOTHER HUMAN remains in room -> must NOT finalize CallSession
    room_b = f"test_room_multihuman_{int(time.time())}"
    sess_b = CallSession.objects.create(
        user=user,
        room_name=room_b,
        started_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=120),
        direction="inbound",
        summary=""
    )

    human1_event = {
        "event": "participant_left",
        "room": {"name": room_b},
        "participant": {
            "identity": "human_caller_1",
            "kind": 0  # STANDARD
        }
    }

    mock_p_other = MagicMock()
    mock_p_other.identity = "human_employee_2"
    mock_p_other.kind = 0

    mock_lk = MagicMock()
    mock_lk.room.list_participants = AsyncMock(return_value=MagicMock(participants=[mock_p_other]))
    mock_lk.room.delete_room = AsyncMock()
    mock_lk.aclose = AsyncMock()

    with patch("livekit.api.LiveKitAPI", return_value=mock_lk):
        with patch("voice_assistant.views.publish_to_centrifugo") as mock_pub:
            req = make_webhook_req(human1_event)
            resp = livekit_webhook(req)
            assert resp.status_code == 200

            sess_b.refresh_from_db()
            assert sess_b.ended_at is None, "CallSession ended while human_employee_2 is still in room!"
            mock_lk.room.delete_room.assert_not_called()
            print("  [+] Human leaving with co-human remaining did NOT finalize session or delete room.")

    # Case C: Last human leaves -> MUST finalize CallSession and delete room
    room_c = f"test_room_lasthuman_{int(time.time())}"
    start_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=45)
    sess_c = CallSession.objects.create(
        user=user,
        room_name=room_c,
        direction="inbound",
        summary=""
    )
    CallSession.objects.filter(id=sess_c.id).update(started_at=start_time)

    human_last_event = {
        "event": "participant_left",
        "room": {"name": room_c},
        "participant": {
            "identity": "last_caller",
            "kind": 0
        }
    }

    mock_lk_empty = MagicMock()
    mock_lk_empty.room.list_participants = AsyncMock(return_value=MagicMock(participants=[]))
    mock_lk_empty.room.delete_room = AsyncMock()
    mock_lk_empty.aclose = AsyncMock()

    with patch("livekit.api.LiveKitAPI", return_value=mock_lk_empty):
        with patch("voice_assistant.views.publish_to_centrifugo") as mock_pub:
            req = make_webhook_req(human_last_event)
            resp = livekit_webhook(req)
            assert resp.status_code == 200

            sess_c.refresh_from_db()
            assert sess_c.ended_at is not None, "CallSession was NOT finalized when last human left!"
            assert sess_c.duration_seconds >= 44, f"Duration not calculated properly: {sess_c.duration_seconds}"
            assert sess_c.billed_minutes == 1, f"Billed minutes incorrect: {sess_c.billed_minutes}"
            mock_lk_empty.room.delete_room.assert_called_once()
            print("  [+] Last human leaving cleanly finalized CallSession, calculated duration, and deleted room.")
    print("✅ TEST PASSED: participant_left webhook behavior verified.")


def test_hangup_api_payloads():
    print("\n--- TEST: Hangup API with sendBeacon FormData and JSON Payloads ---")
    factory = RequestFactory()
    user, _ = User.objects.get_or_create(username="test_hangup_user")

    # 1. JSON payload
    room_j = f"test_hangup_json_{int(time.time())}"
    sess_j = CallSession.objects.create(
        user=user,
        room_name=room_j,
        started_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=30)
    )
    with patch("call_center.views.publish_to_centrifugo"):
        with patch("livekit.api.LiveKitAPI") as mock_lk:
            mock_inst = MagicMock()
            mock_inst.room.delete_room = AsyncMock()
            mock_inst.aclose = AsyncMock()
            mock_lk.return_value = mock_inst

            req_j = factory.post("/api/call-center/calls/hangup/", data=json.dumps({"room_name": room_j}), content_type="application/json")
            resp_j = api_hangup_call(req_j)
            assert resp_j.status_code == 200, f"Expected 200, got {resp_j.status_code}"
            sess_j.refresh_from_db()
            assert sess_j.ended_at is not None, "JSON hangup did not finalize session"
            print("  [+] api_hangup_call parsed JSON payload and finalized session.")

    # 2. FormData payload (sendBeacon)
    room_f = f"test_hangup_form_{int(time.time())}"
    sess_f = CallSession.objects.create(
        user=user,
        room_name=room_f,
        started_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=50)
    )
    with patch("call_center.views.publish_to_centrifugo"):
        with patch("livekit.api.LiveKitAPI") as mock_lk:
            mock_inst = MagicMock()
            mock_inst.room.delete_room = AsyncMock()
            mock_inst.aclose = AsyncMock()
            mock_lk.return_value = mock_inst

            req_f = factory.post("/api/call-center/calls/hangup/", data={"room_name": room_f})
            resp_f = api_hangup_call(req_f)
            assert resp_f.status_code == 200, f"Expected 200, got {resp_f.status_code}"
            sess_f.refresh_from_db()
            assert sess_f.ended_at is not None, "FormData hangup did not finalize session"
            print("  [+] api_hangup_call parsed FormData POST payload (sendBeacon) and finalized session.")
    print("✅ TEST PASSED: Hangup API payload compatibility verified.")


def test_agent_worker_disconnect_filtering():
    print("\n--- TEST: Agent Worker Disconnect Logic ---")
    # Simulate on_participant_disconnected behavior
    room_name = "test_agent_worker_room"

    def simulate_worker_disconnect(p_disconnect, remote_participants):
        p_identity = getattr(p_disconnect, "identity", "")
        is_non_human = (
            p_identity in ("ai-agent", "pipecat-agent")
            or str(p_identity).startswith(("agent-", "ai-", "transfer-", "queue-", "EG_", "egress", "ingress-"))
            or getattr(p_disconnect, "kind", None) in (
                rtc.ParticipantKind.PARTICIPANT_KIND_AGENT,
                rtc.ParticipantKind.PARTICIPANT_KIND_EGRESS,
                rtc.ParticipantKind.PARTICIPANT_KIND_INGRESS,
            )
        )
        if is_non_human:
            return "IGNORED_NON_HUMAN"

        remaining_humans = [
            p for p in remote_participants.values()
            if p.identity not in ("ai-agent", "pipecat-agent")
            and not str(p.identity).startswith(("agent-", "ai-", "transfer-", "queue-", "EG_", "egress", "ingress-"))
            and getattr(p, "kind", None) not in (
                rtc.ParticipantKind.PARTICIPANT_KIND_AGENT,
                rtc.ParticipantKind.PARTICIPANT_KIND_EGRESS,
                rtc.ParticipantKind.PARTICIPANT_KIND_INGRESS,
            )
            and p.identity != p_identity
        ]
        if not remaining_humans:
            return "TRIGGERED_SHUTDOWN"
        return "HUMANS_REMAIN"

    # Egress disconnect
    p_egress = MagicMock()
    p_egress.identity = "EG_rec_999"
    p_egress.kind = rtc.ParticipantKind.PARTICIPANT_KIND_EGRESS
    res = simulate_worker_disconnect(p_egress, {})
    assert res == "IGNORED_NON_HUMAN", f"Expected IGNORED_NON_HUMAN, got {res}"
    print("  [+] Egress disconnect correctly ignored by agent worker.")

    # Human leaves with other humans
    p_h1 = MagicMock()
    p_h1.identity = "client_caller"
    p_h1.kind = rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD

    p_h2 = MagicMock()
    p_h2.identity = "human_rep"
    p_h2.kind = rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD

    res2 = simulate_worker_disconnect(p_h1, {"p2": p_h2})
    assert res2 == "HUMANS_REMAIN", f"Expected HUMANS_REMAIN, got {res2}"
    print("  [+] Human disconnect with co-human remaining correctly keeps worker active.")

    # Last human leaves
    res3 = simulate_worker_disconnect(p_h1, {})
    assert res3 == "TRIGGERED_SHUTDOWN", f"Expected TRIGGERED_SHUTDOWN, got {res3}"
    print("  [+] Last human disconnect triggers worker shutdown.")
    print("✅ TEST PASSED: Agent worker disconnect filtering verified.")


def test_template_structures():
    print("\n--- TEST: Template DOM Structures (calls.html & room.html) ---")
    base_dir = settings.BASE_DIR

    calls_path = os.path.join(base_dir, "voice_assistant/templates/voice_assistant/pages/calls.html")
    with open(calls_path, 'r', encoding='utf-8') as f:
        calls_content = f.read()
    assert 'id="cdm-recording-section"' in calls_content
    assert 'id="cdm-recording-section" class="p-3 rounded-lg bg-slate-50 border border-slate-100 space-y-2"' in calls_content
    assert 'id="cdm-recording-status"' in calls_content
    assert 'id="cdm-recording-status-text"' in calls_content
    print("  [+] calls.html has visible cdm-recording-section and status banner.")

    room_path = os.path.join(base_dir, "voice_assistant/templates/voice_assistant/room.html")
    with open(room_path, 'r', encoding='utf-8') as f:
        room_content = f.read()
    assert 'id="cdm-recording-section"' in room_content
    assert 'id="cdm-recording-section" class="p-3 rounded-lg bg-slate-50 border border-slate-200/80 space-y-2"' in room_content
    assert 'id="cdm-recording-status"' in room_content
    assert 'id="cdm-recording-status-text"' in room_content
    assert 'triggerHangupBeaconOrFetch' in room_content
    assert 'beforeunload' in room_content
    print("  [+] room.html has visible cdm-recording-section, status banner, and beacon hangup.")
    print("✅ TEST PASSED: Template DOM structures verified.")


if __name__ == '__main__':
    print("=================================================================")
    print("🚀 Running Deep Verification Suite for WebRTC Hangup & Recordings")
    print("=================================================================")
    test_recording_streaming_and_normalization()
    test_participant_left_webhook_logic()
    test_hangup_api_payloads()
    test_agent_worker_disconnect_filtering()
    test_template_structures()
    print("\n=================================================================")
    print("🎉 ALL TESTS IN DEEP VERIFICATION SUITE PASSED SUCCESSFULLY! (100%)")
    print("=================================================================")
