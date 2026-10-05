"""
End-to-End Automated Test for Call Recordings, LiveKit Egress, MinIO S3 Storage,
Webhook Pipeline, CallSession Persistence, and Audio Streaming.
"""
import os
import sys
import time
import json
import asyncio
import django
from django.conf import settings

# Initialize Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from crm.models import CallSession
from voice_assistant.s3_storage import get_s3_client, ensure_minio_bucket
from voice_assistant.egress_service import _start_room_recording_async, get_livekit_api_client
from livekit import api


def test_minio_storage_and_bucket():
    print("\n--- TEST 1: MinIO Storage & Bucket Verification ---")
    ok = ensure_minio_bucket()
    assert ok, "ensure_minio_bucket() returned False"
    
    s3 = get_s3_client()
    bucket = getattr(settings, 'MINIO_BUCKET_NAME', 'call-recordings')
    
    # Upload test audio fixture
    test_key = "recordings/test_sample_audio.mp3"
    dummy_audio_bytes = b"ID3\x03\x00\x00\x00\x00\x00#TSSE\x00\x00\x00\x0f\x00\x00\x01\xff\xfeLavf60.16.100\x00\xff\xfb\x90d\x00\x00\x00" * 20
    
    s3.put_object(
        Bucket=bucket,
        Key=test_key,
        Body=dummy_audio_bytes,
        ContentType="audio/mpeg"
    )
    print(f"✅ Uploaded test audio object to MinIO bucket '{bucket}': {test_key} ({len(dummy_audio_bytes)} bytes)")
    
    # Fetch object
    obj = s3.get_object(Bucket=bucket, Key=test_key)
    body = obj['Body'].read()
    assert body == dummy_audio_bytes, "Retrieved object body does not match uploaded data!"
    print("✅ Retrieved test audio object from MinIO and verified data integrity!")


def test_audio_streaming_proxy_endpoint():
    print("\n--- TEST 2: Django Audio Streaming & Scrubbing Proxy ---")
    client = Client()
    
    # Standard GET
    resp = client.get('/api/calls/recordings/recordings/test_sample_audio.mp3')
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    assert resp['Content-Type'] == 'audio/mpeg', f"Unexpected Content-Type: {resp.get('Content-Type')}"
    assert resp['Accept-Ranges'] == 'bytes', "Accept-Ranges header missing!"
    print("✅ Streaming endpoint /api/calls/recordings/... returned 200 with Content-Type: audio/mpeg")
    
    # Range GET (Audio player scrubbing test)
    resp_range = client.get('/api/calls/recordings/recordings/test_sample_audio.mp3', HTTP_RANGE='bytes=0-49')
    assert resp_range.status_code == 206, f"Expected 206 Partial Content, got {resp_range.status_code}"
    print("✅ Streaming endpoint returned 206 Partial Content for HTTP Range scrubbing!")


def test_livekit_egress_service_connectivity():
    print("\n--- TEST 3: LiveKit Egress Service Connectivity & Node Health ---")
    
    async def _check():
        async with get_livekit_api_client() as lk:
            # Query active egress sessions
            res = await lk.egress.list_egress(api.ListEgressRequest())
            print(f"✅ Connected to LiveKit Server via LiveKitAPI. Total egress jobs listed: {len(res.items)}")
            return True
            
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    success = loop.run_until_complete(_check())
    loop.close()
    assert success, "Failed to connect to LiveKit Egress service"


def test_webhook_egress_ended_and_callsession_persistence():
    print("\n--- TEST 4: Egress Ended Webhook & CallSession Persistence ---")
    test_user, _ = User.objects.get_or_create(username="test_egress_user", defaults={"email": "egress@example.com"})
    
    test_room = f"test_room_egress_{int(time.time())}"
    expected_filename = f"recordings/{test_room}.mp3"
    
    # Create an initial CallSession
    session = CallSession.objects.create(
        user=test_user,
        room_name=test_room,
        direction='inbound',
        caller_phone='+15551234567',
        call_goal='اختبار تسجيل Egress',
        duration_seconds=45,
        summary='تمت مكالمة اختبار التسجيل بنجاح'
    )
    assert not session.recording_url, "recording_url should initially be empty"
    print(f"✅ Created test CallSession #{session.id} for room '{test_room}'")
    
    # Simulate LiveKit sending egress_ended webhook
    client = Client()
    token = api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
    
    webhook_payload = {
        "event": "egress_ended",
        "egress_info": {
            "egress_id": f"EG_test_{int(time.time())}",
            "room_name": test_room,
            "status": "EGRESS_COMPLETE",
            "file_results": [
                {
                    "filename": expected_filename,
                    "location": f"http://minio:9000/call-recordings/{expected_filename}",
                    "duration": 45000000000,
                    "size": 184500
                }
            ]
        }
    }
    raw_body = json.dumps(webhook_payload)
    
    # Generate valid LiveKit Webhook Authorization header using WebhookReceiver / TokenVerifier format
    import hashlib
    import base64
    import jwt

    body_sha256 = base64.b64encode(hashlib.sha256(raw_body.encode('utf-8')).digest()).decode('utf-8')
    auth_token = jwt.encode(
        {
            "iss": settings.LIVEKIT_API_KEY,
            "exp": int(time.time()) + 3600,
            "sha256": body_sha256
        },
        settings.LIVEKIT_API_SECRET,
        algorithm="HS256"
    )
    
    headers = {
        'HTTP_AUTHORIZATION': auth_token,
        'CONTENT_TYPE': 'application/json'
    }
    resp = client.post('/api/livekit/webhook/', data=raw_body, content_type='application/json', **headers)
    assert resp.status_code == 200, f"Expected 200 from webhook, got {resp.status_code}: {resp.content}"
    print("✅ LiveKit webhook processed 'egress_ended' event successfully with 200 OK")
    
    # Verify CallSession was updated in Postgres
    session.refresh_from_db()
    expected_url = f"/api/calls/recordings/{expected_filename}"
    assert session.recording_url == expected_url, f"Expected recording_url '{expected_url}', got '{session.recording_url}'"
    print(f"✅ CallSession #{session.id} recording_url successfully updated to: {session.recording_url}")
    
    # Test CDR serialization via /api/crm/calls/
    client.force_login(test_user)
    cdr_resp = client.get(f'/api/crm/calls/?search={test_room}')
    assert cdr_resp.status_code == 200
    cdr_data = cdr_resp.json()
    assert cdr_data['status'] == 'success'
    assert len(cdr_data['calls']) > 0
    matched = next((c for c in cdr_data['calls'] if c['room_name'] == test_room), None)
    assert matched is not None, "CallSession not found in CDR API response"
    assert matched['recording_url'] == expected_url, f"CDR serialized recording_url mismatch: {matched['recording_url']}"
    print(f"✅ CDR API (/api/crm/calls/) correctly returns recording_url in serialized payload!")


if __name__ == '__main__':
    print("=================================================================")
    print("🚀 Starting End-to-End LiveKit Egress & MinIO Test Suite")
    print("=================================================================")
    test_minio_storage_and_bucket()
    test_audio_streaming_proxy_endpoint()
    test_livekit_egress_service_connectivity()
    test_webhook_egress_ended_and_callsession_persistence()
    print("\n=================================================================")
    print("🎉 ALL END-TO-END EGRESS & MINIO TESTS PASSED SUCCESSFULLY! (100%)")
    print("=================================================================\n")
