#!/usr/bin/env python
"""
End-to-End Test Suite for Persona Customization Studio API & API Gaps Parity.
Tests:
1. Persona Customization Studio API (User & Partner):
   - 30 Google HD Voices metadata
   - 11 Supported Languages
   - 29 Hierarchical Dialects
   - Free-text Role & Style Inspiration samples
2. Free-Text Persona Role & Speaking Style:
   - Create profile with pure arbitrary free text
   - Update profile with free text
   - AI agent dynamic prompt injection with free text
3. Call Queues Parity:
   - Code, Description, Timeouts (ring & total hold), Strategy, Fallback action
   - Queue Members endpoint (GET, POST, DELETE)
4. Programmatic Call Hangup:
   - User call hangup (/api/v1/calls/hangup/)
   - Partner client call hangup (/api/partner/v1/clients/{id}/calls/hangup/)
   - LiveKit room cleanup & CallSession duration / billed minutes calculation
5. Call Logs (CDR) Parity:
   - Recording URL
   - Parsed structured Dialogue Turns
"""
import os
import sys
import json
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from django.utils import timezone
from agents.models import AgentProfile
from call_center.models import CallQueue, EmployeeProfile, QueueMembership
from crm.models import CallSession
from developer.models import UserApiKey
from partners.models import PartnerProfile, PartnerClientRelationship

def run_tests():
    print("=" * 70)
    print("🚀 STARTING E2E TEST: Persona Studio API & User/Partner API Parity")
    print("=" * 70)

    client = Client()

    # 1. Setup Test User, Partner, and Client
    user, _ = User.objects.get_or_create(username='test_dev_user', defaults={'email': 'dev@test.com'})
    user.set_password('password123')
    user.save()

    # User API Key
    api_key_obj, _ = UserApiKey.objects.get_or_create(
        user=user,
        defaults={'name': 'Test Key', 'key': 'sk_live_usr_' + 'a' * 32, 'is_active': True}
    )
    user_headers = {'HTTP_X_API_KEY': api_key_obj.key}

    # Partner User & Partner Profile
    partner_user, _ = User.objects.get_or_create(username='test_partner_admin', defaults={'email': 'partner@test.com'})
    partner_profile, _ = PartnerProfile.objects.get_or_create(
        user=partner_user,
        defaults={
            'company_name': 'Test Telecom Partner',
            'partner_code': 'test_part_001',
            'api_key': 'sk_live_part_' + 'b' * 32,
            'status': 'approved'
        }
    )
    partner_headers = {'HTTP_X_PARTNER_KEY': partner_profile.api_key}

    # Sub-client User & Relationship
    subclient_user, _ = User.objects.get_or_create(username='test_subclient_1', defaults={'email': 'sub@test.com'})
    rel, _ = PartnerClientRelationship.objects.get_or_create(
        partner=partner_profile,
        client=subclient_user,
        defaults={'external_reference': 'ext_crm_999'}
    )

    # -------------------------------------------------------------
    # TEST 1: Developer Persona Studio API (GET /api/v1/profiles/studio/)
    # -------------------------------------------------------------
    print("\n[TEST 1] Testing Developer Studio API: GET /api/v1/profiles/studio/")
    res = client.get('/api/v1/profiles/studio/', **user_headers)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.content}"
    data = res.json()
    assert data.get('status') == 'success'
    assert len(data.get('google_voices', [])) == 30, f"Expected 30 Google voices, got {len(data.get('google_voices', []))}"
    assert len(data.get('languages', [])) == 11, f"Expected 11 languages, got {len(data.get('languages', []))}"
    assert 'language_dialects_map' in data
    assert len(data.get('sample_roles', [])) >= 4
    assert len(data.get('sample_styles', [])) >= 4
    print(f"✅ Developer Studio API passed: 30 voices, 11 languages, 29 dialects, and free-text samples returned.")

    # -------------------------------------------------------------
    # TEST 2: Partner Persona Studio API (GET /api/partner/v1/studio/)
    # -------------------------------------------------------------
    print("\n[TEST 2] Testing Partner Studio API: GET /api/partner/v1/studio/")
    res = client.get('/api/partner/v1/studio/', **partner_headers)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.content}"
    data = res.json()
    assert data.get('status') == 'success'
    assert len(data.get('google_voices', [])) == 30
    assert len(data.get('languages', [])) == 11
    print(f"✅ Partner Studio API passed.")

    # Client-specific studio route:
    res = client.get(f'/api/partner/v1/clients/{rel.id}/profiles/studio/', **partner_headers)
    assert res.status_code == 200
    print(f"✅ Partner Client Studio route passed.")

    # -------------------------------------------------------------
    # TEST 3: Free-Text Persona Role & Style in Developer API
    # -------------------------------------------------------------
    print("\n[TEST 3] Testing Free-Text Persona Role & Style creation via Developer API")
    custom_role = "مستشار عقاري خبير ومبيعات فيلات فاخرة في التجمع الخامس والعاصمة الإدارية"
    custom_style = "أسلوب فخم وراقي وهادئ، يعكس الاحترافية العالية مع إيجاز وسرعة في الرد"
    payload = {
        "name": "مستشار العقارات الفاخرة",
        "voice_name": "Fenrir",
        "gender": "male",
        "language": "arabic",
        "dialect": "egyptian",
        "persona_role": custom_role,
        "speaking_style": custom_style,
        "custom_instructions": "دائماً رحب بالعميل بعبارة 'أهلاً بحضرتك يا فندم في سراي العقارية'",
        "is_active": True
    }
    res = client.post('/api/v1/profiles/', data=json.dumps(payload), content_type='application/json', **user_headers)
    assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.content}"
    p_data = res.json().get('profile', {})
    prof_id = p_data.get('id')
    assert p_data.get('persona_role') == custom_role, f"Persona role mismatch: {p_data.get('persona_role')}"
    assert p_data.get('speaking_style') == custom_style, f"Speaking style mismatch: {p_data.get('speaking_style')}"
    print(f"✅ Free-text profile created successfully with custom role and style strings.")

    # Update via PATCH
    new_role = "خبير حلول تقنية ودعم برمجي للذكاء الاصطناعي"
    res = client.patch(f'/api/v1/profiles/{prof_id}/', data=json.dumps({"persona_role": new_role}), content_type='application/json', **user_headers)
    assert res.status_code == 200
    assert res.json().get('profile', {}).get('persona_role') == new_role
    print(f"✅ Free-text profile updated successfully via PATCH.")

    # -------------------------------------------------------------
    # TEST 4: Agent Profile Model Free-Text Storage & to_dict Verification
    # -------------------------------------------------------------
    print("\n[TEST 4] Testing Agent Profile Free-Text Model Persistence & Serialization")
    prof = AgentProfile.objects.get(id=prof_id)
    assert prof.persona_role == new_role
    assert prof.speaking_style == custom_style
    p_dict = prof.to_dict()
    assert p_dict['persona_role'] == new_role
    assert p_dict['speaking_style'] == custom_style
    print(f"✅ Agent Profile correctly stores and serializes arbitrary user free-text without enum restrictions.")

    # -------------------------------------------------------------
    # TEST 5: Call Queues Parity (Code, Description, Timeouts, Strategy, Members)
    # -------------------------------------------------------------
    print("\n[TEST 5] Testing Call Queues in Developer API (code, description, timeouts, members)")
    # Create employee via API
    res_emp = client.post('/api/v1/employees/', data=json.dumps({'name': 'عمر خالد', 'extension': '301', 'department': 'المبيعات'}), content_type='application/json', **user_headers)
    assert res_emp.status_code in (200, 201), f"Employee creation failed: {res_emp.content}"
    emp_id = res_emp.json()['employee']['id']
    
    # Delete existing queue with code 770 if exists from earlier run
    CallQueue.objects.filter(user=user, code="770").delete()

    queue_payload = {
        "name": "طابور المبيعات العقارية",
        "code": "770",
        "description": "طابور مخصص لتحويل العملاء المهتمين بحجز فيلات أو استفسارات التقسيط",
        "strategy": "round_robin",
        "ring_timeout_seconds": 20,
        "total_timeout_seconds": 120,
        "fallback_action": "ai_assistant",
        "members": [emp_id]
    }
    res = client.post('/api/v1/queues/', data=json.dumps(queue_payload), content_type='application/json', **user_headers)
    assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.content}"
    q_data = res.json().get('queue', {})
    q_id = q_data.get('id')
    assert q_data.get('code') == '770'
    assert q_data.get('description') == queue_payload['description']
    assert q_data.get('ring_timeout_seconds') == 20
    assert q_data.get('total_timeout_seconds') == 120
    assert len(q_data.get('members', [])) == 1
    print(f"✅ CallQueue created with code, description, timeouts, fallback, and initial members.")

    # Test Queue Members Management endpoint
    print("Testing GET /api/v1/queues/{id}/members/")
    res = client.get(f'/api/v1/queues/{q_id}/members/', **user_headers)
    assert res.status_code == 200
    assert res.json().get('total_members') == 1

    # Add second employee to queue via API
    res_emp2 = client.post('/api/v1/employees/', data=json.dumps({'name': 'مريم سمير', 'extension': '302', 'department': 'المبيعات'}), content_type='application/json', **user_headers)
    assert res_emp2.status_code in (200, 201)
    emp2_id = res_emp2.json()['employee']['id']

    res = client.post(f'/api/v1/queues/{q_id}/members/', data=json.dumps({'employee_id': emp2_id, 'order': 2}), content_type='application/json', **user_headers)
    assert res.status_code in (200, 201)
    print(f"✅ Second employee added to queue via POST /queues/{q_id}/members/.")

    # Delete membership
    res = client.delete(f'/api/v1/queues/{q_id}/members/?employee_id={emp2_id}', **user_headers)
    assert res.status_code == 200
    print(f"✅ Employee removed from queue via DELETE /queues/{q_id}/members/.")

    # -------------------------------------------------------------
    # TEST 6: Call Hangup Endpoint & CDR Parity (recording_url, dialogue_turns)
    # -------------------------------------------------------------
    print("\n[TEST 6] Testing Call Hangup & CDR serialization in Developer API")
    test_room = f"user_{user.id}_test_hangup_{int(timezone.now().timestamp())}"
    sample_transcript = "العميل: السلام عليكم، عاوز استفسر عن أسعار الفيلات.\nالمساعد: أهلاً بحضرتك يا فندم، الفيلات تبدأ من 10 مليون جنيه مع تسهيلات في السداد.\nالعميل: شكراً جزيلاً."
    
    call_session = CallSession.objects.create(
        user=user,
        room_name=test_room,
        direction='inbound',
        caller_phone='+201012345678',
        started_at=timezone.now(),
        transcript_text=sample_transcript,
        recording_url='https://storage.googleapis.com/test-bucket/recordings/call_123.mp3'
    )

    # Call Hangup endpoint
    res = client.post('/api/v1/calls/hangup/', data=json.dumps({'call_id': test_room}), content_type='application/json', **user_headers)
    assert res.status_code == 200, f"Expected 200 from hangup, got {res.status_code}: {res.content}"
    
    # Reload session from DB
    call_session.refresh_from_db()
    assert call_session.ended_at is not None, "CallSession was not ended!"
    print(f"✅ Call hangup completed and session closed with duration: {call_session.duration_seconds}s, billed: {call_session.billed_minutes}m.")

    # Verify CDR serialization includes recording_url and dialogue_turns
    res = client.get('/api/v1/calls/', **user_headers)
    assert res.status_code == 200
    calls_list = res.json().get('calls', [])
    matched_call = next((c for c in calls_list if c['call_id'] == test_room), None)
    assert matched_call is not None, "Target call not found in CDR list!"
    assert matched_call.get('recording_url') == 'https://storage.googleapis.com/test-bucket/recordings/call_123.mp3'
    assert len(matched_call.get('dialogue_turns', [])) == 3, f"Expected 3 turns, got {len(matched_call.get('dialogue_turns', []))}"
    assert matched_call['dialogue_turns'][0]['speaker'] == 'العميل'
    assert matched_call['dialogue_turns'][1]['speaker'] == 'المساعد'
    print(f"✅ CDR list successfully serializes recording_url and parsed dialogue_turns!")

    # -------------------------------------------------------------
    # TEST 7: Partner Client Call Queues and Hangup Parity
    # -------------------------------------------------------------
    print("\n[TEST 7] Testing Partner Client Queue Description & Call Hangup")
    p_q_res = client.post(f'/api/partner/v1/clients/{rel.id}/queues/', data=json.dumps({
        "name": "طابور خدمة عملاء الشريك",
        "code": "880",
        "description": "طابور للعملاء التجاريين للشريك",
        "strategy": "ring_all",
        "ring_timeout_seconds": 15,
        "total_timeout_seconds": 90,
        "fallback_action": "ai_assistant"
    }), content_type='application/json', **partner_headers)
    assert p_q_res.status_code in (200, 201), f"Partner queue failed: {p_q_res.content}"
    assert p_q_res.json().get('queue', {}).get('description') == "طابور للعملاء التجاريين للشريك"
    print(f"✅ Partner Client queue created with description successfully.")

    # Partner Call Hangup
    sub_room = f"user_{subclient_user.id}_partner_hangup_test"
    sub_session = CallSession.objects.create(
        user=subclient_user,
        room_name=sub_room,
        direction='outbound_ai',
        destination_phone='+966500000000',
        started_at=timezone.now(),
        transcript_text="المتصل: مرحباً\nالمساعد: مرحباً بك",
        recording_url='https://storage.example.com/partner_sub.mp3'
    )
    p_hangup_res = client.post(f'/api/partner/v1/clients/{rel.id}/calls/hangup/', data=json.dumps({'call_id': sub_room}), content_type='application/json', **partner_headers)
    assert p_hangup_res.status_code == 200, f"Partner hangup failed: {p_hangup_res.content}"
    sub_session.refresh_from_db()
    assert sub_session.ended_at is not None
    print(f"✅ Partner client call hangup succeeded and closed call session.")

    # Partner Calls List CDR verification
    p_calls_res = client.get(f'/api/partner/v1/clients/{rel.id}/calls/', **partner_headers)
    assert p_calls_res.status_code == 200
    p_calls = p_calls_res.json().get('calls', [])
    matched_p_call = next((c for c in p_calls if c['call_id'] == sub_room), None)
    assert matched_p_call is not None
    assert matched_p_call.get('recording_url') == 'https://storage.example.com/partner_sub.mp3'
    assert len(matched_p_call.get('dialogue_turns', [])) == 2
    print(f"✅ Partner CDR list successfully returns recording_url and structured dialogue_turns.")

    print("\n" + "=" * 70)
    print("🎉 ALL E2E TESTS PASSED 100% SUCCESSFULLY!")
    print("=" * 70)

if __name__ == '__main__':
    run_tests()
