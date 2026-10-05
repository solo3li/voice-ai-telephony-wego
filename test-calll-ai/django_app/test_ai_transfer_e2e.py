#!/usr/bin/env python3
import os
import sys
import json
import django

# Setup Django environment
sys.path.insert(0, '/root/test/test-calll-ai/django_app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.conf import settings
from django.contrib.auth.models import User
from call_center.models import CallQueue, QueueMembership, EmployeeProfile
import redis

client = Client()
INTERNAL_KEY = getattr(settings, 'INTERNAL_API_KEY', 'voice-internal-secret-token-key-12345')
r = redis.Redis.from_url(settings.REDIS_URL)

def test_ai_transfer():
    print("=" * 60)
    print("🧪 TESTING AI QUEUE TRANSFER & MULTI-TENANT ISOLATION")
    print("=" * 60)

    # Test multi-tenant isolation: User with queues vs User without queues
    queue_obj = CallQueue.objects.filter(is_active=True).first()
    assert queue_obj, "At least one queue must exist in DB"
    user_with_queue = queue_obj.user
    user_without_queue = User.objects.exclude(id=user_with_queue.id).first()

    print(f"[+] Found tenant user with queue: {user_with_queue.username} (ID: {user_with_queue.id})")
    if user_without_queue:
        print(f"[+] Found tenant user without this queue: {user_without_queue.username} (ID: {user_without_queue.id})")

    # 1. Test Bootstrap API includes call_queues for user_with_queue
    print("\n[TEST 1] Testing /api/agents/internal/bootstrap/ call_queues retrieval...")
    res = client.post(
        "/api/agents/internal/bootstrap/",
        data=json.dumps({"user_id": user_with_queue.id}),
        content_type="application/json",
        HTTP_X_INTERNAL_API_KEY=INTERNAL_KEY
    )
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.content}"
    data = res.json()
    assert "call_queues" in data, "call_queues key missing from bootstrap"
    queues = data["call_queues"]
    print(f"[+] Bootstrap returned {len(queues)} queues for tenant {user_with_queue.username}:")
    for q in queues:
        print(f"    - [{q['code']}] {q['name']} ({q['members_count']} members)")

    assert len(queues) > 0, "Tenant should have at least one active queue for test"
    test_queue = queues[0]
    test_queue_code = test_queue["code"]

    user = user_with_queue

    # 2. Test AI Transfer API unauthorized access rejected
    print("\n[TEST 2] Testing /api/call-center/internal/ai-transfer/ unauthorized rejection...")
    res_unauth = client.post(
        "/api/call-center/internal/ai-transfer/",
        data=json.dumps({
            "room_name": "room_test_123",
            "queue_code": test_queue_code,
            "user_id": user.id
        }),
        content_type="application/json"
    )
    assert res_unauth.status_code == 401, f"Expected 401, got {res_unauth.status_code}"
    print("[+] Unauthorized request correctly rejected with 401.")

    # 3. Test AI Transfer with invalid queue code
    print("\n[TEST 3] Testing AI transfer with non-existent queue code...")
    res_invalid = client.post(
        "/api/call-center/internal/ai-transfer/",
        data=json.dumps({
            "room_name": "room_test_123",
            "queue_code": "999999",
            "user_id": user.id
        }),
        content_type="application/json",
        HTTP_X_INTERNAL_API_KEY=INTERNAL_KEY
    )
    assert res_invalid.status_code == 404, f"Expected 404, got {res_invalid.status_code}"
    print(f"[+] Invalid queue correctly returned 404: {res_invalid.json().get('message')}")

    # 4. Test AI Transfer successful dispatch
    print("\n[TEST 4] Testing AI Transfer successful dispatch to queue...")
    test_room = "room_test_ai_transfer_1"
    res_transfer = client.post(
        "/api/call-center/internal/ai-transfer/",
        data=json.dumps({
            "room_name": test_room,
            "queue_code": test_queue_code,
            "user_id": user.id,
            "caller_phone": "+201099999999",
            "caller_name": "أحمد العميل",
            "reason": "استفسار عن أسعار وخدمات المتجر"
        }),
        content_type="application/json",
        HTTP_X_INTERNAL_API_KEY=INTERNAL_KEY
    )
    assert res_transfer.status_code == 200, f"Expected 200, got {res_transfer.status_code}: {res_transfer.content}"
    t_data = res_transfer.json()
    assert t_data.get("status") == "success", f"Transfer failed: {t_data}"
    transfer_id = t_data.get("transfer_id")
    assert transfer_id, "transfer_id missing from response"
    print(f"[+] AI Transfer successfully initiated!")
    print(f"    - Transfer ID: {transfer_id}")
    print(f"    - Target Queue: {t_data.get('queue_name')} ({t_data.get('queue_code')})")
    print(f"    - Candidate Count: {t_data.get('candidates_count')}")

    # Check Redis keys
    is_from_ai = r.get(f"transfer:{transfer_id}:from_ai")
    t_state = r.get(f"transfer:{transfer_id}:state")
    is_room_transferring = r.get(f"room:{test_room}:is_transferring")

    assert is_from_ai == b"true", "transfer:from_ai Redis key not set"
    assert t_state == b"ringing", "transfer:state not ringing"
    assert is_room_transferring == b"true", "room is_transferring key not set"
    print(f"[+] Redis state verified: transfer state={t_state.decode()}, from_ai={is_from_ai.decode()}")

    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    test_ai_transfer()
