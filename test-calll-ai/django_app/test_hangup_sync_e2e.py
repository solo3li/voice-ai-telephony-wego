import os
import sys
import json
import time
import uuid
import django
import redis
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from django.test import RequestFactory
from django.contrib.auth.models import User
from call_center.models import EmployeeProfile, CallQueue, EmployeeCallLog
from call_center.views import api_hangup_call, api_internal_ai_transfer, generate_employee_jwt

def run_tests():
    print("==================================================")
    print("STARTING BIDIRECTIONAL HANGUP SYNCHRONIZATION TEST")
    print("==================================================")

    factory = RequestFactory()
    r = redis.Redis.from_url(settings.REDIS_URL)

    # 1. Setup Test Employee
    emp = EmployeeProfile.objects.filter(is_active=True).first()
    if not emp:
        print("[-] No active employee found!")
        return False
    print(f"[+] Using test employee: {emp.display_name} (id={emp.id}, ext={emp.extension})")

    # -------------------------------------------------------------------------
    # TEST 1: Customer hangs up from web widget (Anonymous/Customer -> Employee)
    # -------------------------------------------------------------------------
    print("\n--- TEST 1: Customer hangs up from web widget ---")
    room_1 = f"room_test_cust_hangup_{uuid.uuid4().hex[:6]}"
    
    # Simulate employee being connected with caller in room_1
    emp.status = "busy"
    emp.save(update_fields=['status'])
    
    # Create an open call log for this room
    log_1 = EmployeeCallLog.objects.create(
        employee=emp,
        other_party="العميل فيصل",
        extension="Web",
        room_name=room_1,
        call_type="inbound"
    )
    r.set(f"room:{room_1}:is_transferring", "true", ex=60) # Simulate residual transfer flag

    # Customer sends POST /api/call-center/calls/hangup/ with no auth headers
    payload = json.dumps({"room_name": room_1}).encode('utf-8')
    req = factory.post('/api/call-center/calls/hangup/', data=payload, content_type='application/json')
    req.user = type('AnonymousUser', (), {'is_authenticated': False})()

    resp = api_hangup_call(req)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.content}"
    data = json.loads(resp.content)
    assert data.get('status') == 'success', f"Expected success, got {data}"

    # Verify DB state
    emp.refresh_from_db()
    assert emp.status == 'ready', f"Expected employee status 'ready', got '{emp.status}'"
    
    log_1.refresh_from_db()
    assert log_1.ended_at is not None, "Expected call log to have ended_at set"
    
    # Verify Redis keys cleared
    assert not r.exists(f"room:{room_1}:is_transferring"), "is_transferring should be deleted"
    print("✅ TEST 1 PASSED: Web customer hangup successfully ended employee call, marked log, and reset status to 'ready'.")

    # -------------------------------------------------------------------------
    # TEST 2: Employee hangs up from app (Employee -> Web Customer)
    # -------------------------------------------------------------------------
    print("\n--- TEST 2: Employee hangs up from employee app ---")
    room_2 = f"room_test_emp_hangup_{uuid.uuid4().hex[:6]}"
    
    emp.status = "busy"
    emp.save(update_fields=['status'])
    
    log_2 = EmployeeCallLog.objects.create(
        employee=emp,
        other_party="العميل أحمد",
        extension="Web",
        room_name=room_2,
        call_type="inbound"
    )
    r.set(f"room:{room_2}:is_transferring", "true", ex=60)

    # Employee sends POST /api/call-center/calls/hangup/ with employee token
    token = generate_employee_jwt(emp)
    payload = json.dumps({"room_name": room_2}).encode('utf-8')
    req = factory.post(
        '/api/call-center/calls/hangup/',
        data=payload,
        content_type='application/json',
        HTTP_AUTHORIZATION=f"Bearer {token}"
    )
    req.user = type('AnonymousUser', (), {'is_authenticated': False})()

    resp = api_hangup_call(req)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.content}"
    data = json.loads(resp.content)
    assert data.get('status') == 'success', f"Expected success, got {data}"

    emp.refresh_from_db()
    assert emp.status == 'ready', f"Expected employee status 'ready', got '{emp.status}'"
    
    log_2.refresh_from_db()
    assert log_2.ended_at is not None, "Expected call log to have ended_at set"
    
    assert not r.exists(f"room:{room_2}:is_transferring"), "is_transferring should be deleted"
    print("✅ TEST 2 PASSED: Employee hangup successfully broadcasted, closed call log, reset status, and cleared transfer keys.")

    # -------------------------------------------------------------------------
    # TEST 3: Caller cancels/hangs up while ringing in queue (Transfer Cancel)
    # -------------------------------------------------------------------------
    print("\n--- TEST 3: Caller hangs up while call is ringing in queue ---")
    room_3 = f"room_test_queue_cancel_{uuid.uuid4().hex[:6]}"
    tr_id = f"tr_{uuid.uuid4().hex[:8]}"

    # Setup simulated queue transfer state in Redis
    r.set(f"room:{room_3}:is_transferring", "true", ex=120)
    r.set(f"room:{room_3}:transfer_id", tr_id, ex=300)
    r.set(f"transfer:{tr_id}:state", "ringing", ex=300)
    r.set(f"transfer:{tr_id}:current_candidate", emp.id, ex=60)

    payload = json.dumps({"room_name": room_3}).encode('utf-8')
    req = factory.post('/api/call-center/calls/hangup/', data=payload, content_type='application/json')
    req.user = type('AnonymousUser', (), {'is_authenticated': False})()

    resp = api_hangup_call(req)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.content}"

    # Verify transfer state changed to cancelled in Redis
    tr_state = r.get(f"transfer:{tr_id}:state")
    assert tr_state == b"cancelled", f"Expected transfer state 'cancelled', got {tr_state}"
    assert not r.exists(f"room:{room_3}:is_transferring"), "is_transferring should be deleted"
    assert not r.exists(f"room:{room_3}:transfer_id"), "transfer_id should be deleted"

    print("✅ TEST 3 PASSED: Hanging up while ringing cancelled queue transfer and dismissed candidate.")

    print("\n==================================================")
    print("ALL BIDIRECTIONAL HANGUP SYNCHRONIZATION TESTS PASSED!")
    print("==================================================")
    return True

if __name__ == '__main__':
    ok = run_tests()
    sys.exit(0 if ok else 1)
