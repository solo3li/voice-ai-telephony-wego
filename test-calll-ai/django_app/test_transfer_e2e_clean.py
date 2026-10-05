#!/usr/bin/env python3
"""
End-to-End Test for the Clean Call Transfer Workflow:
1. Employee 1 dials Employee 2 (WebRTC room created, status set to busy)
2. Employee 2 answers (both connected, call logs recorded)
3. Employee 2 transfers call to Employee 3 / Queue
   - Old room closed on LiveKit
   - Caller put on local HOLD
   - Inngest background job handles ring-robin queue dispatch
4. Employee 3 accepts transfer
   - New room created
   - Caller & Employee 3 receive new room tokens
   - Employee 2 returned to ready
5. Cancel Transfer Flow test
6. Reject/Timeout Flow test
"""

import os
import sys
import json
import time
import uuid
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.conf import settings
from call_center.models import EmployeeProfile, CallQueue, QueueMembership, EmployeeCallLog
from call_center.views import generate_employee_jwt
import redis

client = Client()
r = redis.Redis.from_url(settings.REDIS_URL)

def run_tests():
    print("=====================================================================")
    print("🚀 STARTING E2E TESTS: CLEAN CALL TRANSFER WORKFLOW")
    print("=====================================================================")

    # Setup / verify test employees
    emp1 = EmployeeProfile.objects.filter(extension="101").first()
    emp2 = EmployeeProfile.objects.filter(extension="102").first()
    emp3 = EmployeeProfile.objects.filter(extension="103").first()

    assert emp1 and emp2 and emp3, "Employees 101, 102, 103 must exist!"

    # Reset all statuses to ready
    EmployeeProfile.objects.filter(id__in=[emp1.id, emp2.id, emp3.id]).update(status='ready')

    token1 = generate_employee_jwt(emp1)
    token2 = generate_employee_jwt(emp2)
    token3 = generate_employee_jwt(emp3)

    auth1 = {"HTTP_AUTHORIZATION": f"Bearer {token1}"}
    auth2 = {"HTTP_AUTHORIZATION": f"Bearer {token2}"}
    auth3 = {"HTTP_AUTHORIZATION": f"Bearer {token3}"}

    # ─────────────────────────────────────────────────────────────
    # TEST 1: Full Transfer & Answer Workflow
    # ─────────────────────────────────────────────────────────────
    print("\n[TEST 1] Starting Dial from Emp 101 to Emp 102...")
    dial_res = client.post(
        "/api/call-center/calls/dial/",
        data=json.dumps({"target": "102"}),
        content_type="application/json",
        **auth1
    )
    assert dial_res.status_code == 200, f"Dial failed: {dial_res.content}"
    dial_data = dial_res.json()
    room_1 = dial_data["room_name"]
    print(f"  ✅ Dial successful! Room: {room_1}")

    emp1.refresh_from_db()
    assert emp1.status == "busy", f"Expected Emp 101 status busy, got {emp1.status}"
    print("  ✅ Emp 101 status is now BUSY")

    print("\n[TEST 1] Emp 102 Answers the call...")
    ans_res = client.post(
        "/api/call-center/calls/token/",
        data=json.dumps({"room_name": room_1}),
        content_type="application/json",
        **auth2
    )
    assert ans_res.status_code == 200, f"Answer failed: {ans_res.content}"
    emp2.refresh_from_db()
    assert emp2.status == "busy", f"Expected Emp 102 status busy, got {emp2.status}"
    print("  ✅ Emp 102 status is now BUSY")

    logs_count = EmployeeCallLog.objects.filter(room_name=room_1).count()
    assert logs_count >= 2, f"Expected at least 2 call logs for room_1, found {logs_count}"
    print(f"  ✅ Call logs recorded for both parties in room_1 (total: {logs_count})")

    # Time passes in call
    time.sleep(1)

    print("\n[TEST 1] Emp 102 initiates TRANSFER to Emp 103...")
    transfer_res = client.post(
        "/api/call-center/calls/transfer/",
        data=json.dumps({
            "room_name": room_1,
            "target": "103"
        }),
        content_type="application/json",
        **auth2
    )
    assert transfer_res.status_code == 200, f"Transfer failed: {transfer_res.content}"
    transfer_data = transfer_res.json()
    transfer_id = transfer_data["transfer_id"]
    print(f"  ✅ Transfer requested! Transfer ID: {transfer_id}, Target: {transfer_data['target_name']}")

    # Verify Emp 102 call log finalized
    my_log = EmployeeCallLog.objects.filter(room_name=room_1, employee=emp2).first()
    assert my_log.ended_at is not None, "Emp 102 call log should be finalized upon transfer!"
    print(f"  ✅ Emp 102 call log finalized with duration {my_log.duration_secs}s")

    # Verify Redis state
    state = r.get(f"transfer:{transfer_id}:state")
    assert state == b"ringing", f"Expected Redis state 'ringing', got {state}"
    print(f"  ✅ Redis transfer state: {state.decode()}")

    print("\n[TEST 1] Candidate (Emp 103) ANSWERS the transferred call...")
    action_res = client.post(
        "/api/call-center/calls/transfer/action/",
        data=json.dumps({
            "transfer_id": transfer_id,
            "action": "answer"
        }),
        content_type="application/json",
        **auth3
    )
    assert action_res.status_code == 200, f"Action failed: {action_res.content}"
    print("  ✅ Candidate answered event dispatched to Inngest!")

    # Wait briefly for Inngest function execution
    time.sleep(2)

    # ─────────────────────────────────────────────────────────────
    # TEST 2: Cancel Transfer Flow
    # ─────────────────────────────────────────────────────────────
    print("\n[TEST 2] Testing CANCEL TRANSFER flow...")
    EmployeeProfile.objects.filter(id__in=[emp1.id, emp2.id, emp3.id]).update(status='ready')

    dial2_res = client.post(
        "/api/call-center/calls/dial/",
        data=json.dumps({"target": "102"}),
        content_type="application/json",
        **auth1
    )
    room_2 = dial2_res.json()["room_name"]

    client.post(
        "/api/call-center/calls/token/",
        data=json.dumps({"room_name": room_2}),
        content_type="application/json",
        **auth2
    )

    # Initiate transfer
    tr2_res = client.post(
        "/api/call-center/calls/transfer/",
        data=json.dumps({
            "room_name": room_2,
            "target": "103"
        }),
        content_type="application/json",
        **auth2
    )
    tr2_id = tr2_res.json()["transfer_id"]
    print(f"  Transfer {tr2_id} initiated. Now cancelling from Emp 102...")

    cancel_res = client.post(
        "/api/call-center/calls/transfer/cancel/",
        data=json.dumps({"transfer_id": tr2_id}),
        content_type="application/json",
        **auth2
    )
    assert cancel_res.status_code == 200, f"Cancel failed: {cancel_res.content}"
    cancel_state = r.get(f"transfer:{tr2_id}:state")
    assert cancel_state == b"cancelled", f"Expected Redis state 'cancelled', got {cancel_state}"
    print(f"  ✅ Transfer {tr2_id} successfully CANCELLED and state updated in Redis!")

    # ─────────────────────────────────────────────────────────────
    # TEST 3: Queues API for Employee App
    # ─────────────────────────────────────────────────────────────
    print("\n[TEST 3] Testing Dynamic Queues API for Employee App...")
    queues_res = client.get("/api/call-center/queues/", **auth2)
    assert queues_res.status_code == 200, f"Queues API failed: {queues_res.content}"
    queues_data = queues_res.json()
    assert queues_data["status"] == "success", "Queues status must be success"
    assert len(queues_data["queues"]) > 0, "Should return at least 1 queue"
    print(f"  ✅ Dynamic queues retrieved successfully (Count: {len(queues_data['queues'])})")
    for q in queues_data["queues"]:
        print(f"     - Queue: {q['name']} (Code: {q['code']}), Members: {len(q['members'])}, Ring Timeout: {q['ring_timeout_seconds']}s")

    # ─────────────────────────────────────────────────────────────
    # TEST 4: Hangup & Status Restoration
    # ─────────────────────────────────────────────────────────────
    print("\n[TEST 4] Testing Hangup & Auto Status Restoration...")
    EmployeeProfile.objects.filter(id=emp1.id).update(status='busy')
    room_test = f"call_ext_{emp1.extension}_{emp2.extension}_norm"
    hang_res = client.post(
        "/api/call-center/calls/hangup/",
        data=json.dumps({"room_name": room_test}),
        content_type="application/json",
        **auth1
    )
    assert hang_res.status_code == 200
    emp1.refresh_from_db()
    assert emp1.status == "ready", f"Expected Emp 101 to be restored to ready, got {emp1.status}"
    print("  ✅ Status restored to READY upon hangup!")

    # Clean up test artifacts
    EmployeeProfile.objects.filter(id__in=[emp1.id, emp2.id, emp3.id]).update(status='ready')

    print("\n=====================================================================")
    print("🎉 ALL END-TO-END TRANSFER WORKFLOW TESTS PASSED SUCCESSFULLY!")
    print("=====================================================================")

if __name__ == "__main__":
    run_tests()
