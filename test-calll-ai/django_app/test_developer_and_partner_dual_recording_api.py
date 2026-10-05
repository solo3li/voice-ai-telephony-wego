"""
Comprehensive E2E Test for Developer API & Partner API:
Verifies that CallSession endpoints in Developer API and Partner API
correctly expose dual recordings (AI + transferred employee) and transfer metadata.
"""
import os
import sys
import json
import time
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from crm.models import CallSession
from developer.models import UserApiKey
from partners.models import PartnerProfile, PartnerClientRelationship
from developer.serializers import CallSessionSerializer
from partners.serializers import PartnerClientCallSessionSerializer


def test_apis():
    print("\n=======================================================")
    print("🚀 TESTING DEVELOPER & PARTNER APIS FOR DUAL RECORDING")
    print("=======================================================\n")

    client = Client()
    user = User.objects.filter(is_superuser=True).first() or User.objects.first()
    assert user is not None, "A valid Django user is required."

    # 1. Setup Developer API Key
    dev_key_obj = UserApiKey.objects.filter(user=user, is_active=True).first()
    if not dev_key_obj:
        dev_key_obj = UserApiKey.generate_for_user(user, "Test Key")
    api_key = dev_key_obj.key
    print(f"✅ Developer API Key ready: {api_key[:12]}...")

    # 2. Setup Partner Profile & Client Relation
    partner = PartnerProfile.objects.filter(status='approved').first()
    if not partner:
        partner_user, _ = User.objects.get_or_create(username="test_partner_admin")
        partner = PartnerProfile.objects.create(
            user=partner_user,
            company_name="Test Partner SaaS",
            status='approved',
            api_key=f"sk_live_prt_{secrets_token()}"
        )
    partner_key = partner.api_key
    print(f"✅ Partner API Key ready: {partner_key[:12]}... (Company: {partner.company_name})")

    # Ensure client relation
    rel = PartnerClientRelationship.objects.filter(partner=partner, client=user).first()
    if not rel:
        rel = PartnerClientRelationship.objects.create(
            partner=partner,
            client=user,
            external_reference="cli_ext_test_99"
        )
    client_id = user.id

    # 3. Create a CallSession with dual recordings and transfer data
    room_name = f"dev_api_test_room_{int(time.time())}"
    ai_rec = f"/api/calls/recordings/recordings/{room_name}_ai.mp3"
    trans_rec = f"/media/recordings/{int(time.time())}.wav"
    session = CallSession.objects.create(
        user=user,
        room_name=room_name,
        direction='inbound',
        caller_phone='+201099887766',
        destination_phone='999',
        duration_seconds=120,
        billed_minutes=2,
        recording_url=ai_rec,
        transferred_recording_url=trans_rec,
        transferred_to_extension='خالد سعيد (109)',
        caller_extension='101',
        is_internal_test=False,
        summary='تم تحويل العميل إلى خالد سعيد (109) واستمرت محادثة الموظف 60 ثانية.'
    )
    print(f"✅ Created test CallSession #{session.id} ({room_name}) with dual recordings.")

    # ----------------------------------------------------
    # TEST DEVELOPER API: /api/v1/calls/
    # ----------------------------------------------------
    print("\n--- [1] Testing Developer API Endpoints ---")
    headers = {"HTTP_X_API_KEY": api_key}
    
    # 1.1 List Calls
    res_list = client.get(f'/api/v1/calls/?search={room_name}', **headers)
    assert res_list.status_code == 200, f"Expected 200, got {res_list.status_code}: {res_list.content}"
    data_list = res_list.json()
    assert data_list["status"] == "success"
    matched_call = next((c for c in data_list["calls"] if c["call_id"] == room_name), None)
    assert matched_call is not None, "CallSession must be found in Developer calls list."
    
    assert ai_rec in matched_call["recording_url"], "AI recording URL mismatch"
    assert trans_rec in matched_call["transferred_recording_url"], "Transferred recording URL mismatch"
    assert matched_call["transferred_to_extension"] == 'خالد سعيد (109)'
    assert matched_call["is_transferred"] is True
    assert matched_call["caller_extension"] == '101'
    assert matched_call["is_internal_test"] is False
    print("  ✅ GET /api/v1/calls/ correctly returned dual recordings and transfer metadata.")

    # 1.2 Call Detail
    res_detail = client.get(f'/api/v1/calls/{room_name}/', **headers)
    assert res_detail.status_code == 200, f"Expected 200, got {res_detail.status_code}"
    data_detail = res_detail.json()
    assert data_detail["status"] == "success"
    c_detail = data_detail["call"]
    assert ai_rec in c_detail["recording_url"]
    assert trans_rec in c_detail["transferred_recording_url"]
    assert c_detail["transferred_to_extension"] == 'خالد سعيد (109)'
    assert c_detail["is_transferred"] is True
    print("  ✅ GET /api/v1/calls/<call_id>/ correctly returned dual recordings and transfer metadata.")

    # 1.3 Developer Serializer Validation
    ser = CallSessionSerializer(data={
        "call_id": room_name,
        "from_number": "+201099887766",
        "to_number": "999",
        "status": "completed",
        "duration": 120,
        "started_at": "2026-10-06T00:00:00Z",
        "recording_url": "https://example.com/ai.mp3",
        "transferred_recording_url": "https://example.com/human.wav",
        "transferred_to_extension": "109",
        "is_transferred": True,
        "caller_extension": "101",
        "is_internal_test": False,
        "summary": "Transfer test"
    })
    assert ser.is_valid(), f"CallSessionSerializer errors: {ser.errors}"
    print("  ✅ CallSessionSerializer validated dual recordings and transfer fields successfully.")

    # 1.4 Developer OpenAPI Spec
    res_spec = client.get('/api/v1/docs/openapi.json')
    assert res_spec.status_code == 200
    spec_json = res_spec.json()
    assert "transferred_recording_url" in json.dumps(spec_json)
    print("  ✅ Developer OpenAPI spec contains 'transferred_recording_url'.")

    # ----------------------------------------------------
    # TEST PARTNER API: /api/partner/v1/clients/<client_id>/calls/
    # ----------------------------------------------------
    print("\n--- [2] Testing Partner API Endpoints ---")
    partner_headers = {"HTTP_X_PARTNER_KEY": partner_key}

    # 2.1 List Partner Client Calls
    res_p_list = client.get(f'/api/partner/v1/clients/{client_id}/calls/', **partner_headers)
    assert res_p_list.status_code == 200, f"Expected 200, got {res_p_list.status_code}: {res_p_list.content}"
    data_p_list = res_p_list.json()
    assert data_p_list["status"] == "success"
    p_matched_call = next((c for c in data_p_list["calls"] if c["call_id"] == room_name), None)
    assert p_matched_call is not None, "CallSession must be found in Partner client calls list."
    assert ai_rec in p_matched_call["recording_url"]
    assert trans_rec in p_matched_call["transferred_recording_url"]
    assert p_matched_call["transferred_to_extension"] == 'خالد سعيد (109)'
    assert p_matched_call["is_transferred"] is True
    print("  ✅ GET /api/partner/v1/clients/<id>/calls/ correctly returned dual recordings and transfer metadata.")

    # 2.2 Partner Client Call Detail
    res_p_detail = client.get(f'/api/partner/v1/clients/{client_id}/calls/{room_name}/', **partner_headers)
    assert res_p_detail.status_code == 200, f"Expected 200, got {res_p_detail.status_code}"
    data_p_detail = res_p_detail.json()
    assert data_p_detail["status"] == "success"
    p_c_detail = data_p_detail["call"]
    assert ai_rec in p_c_detail["recording_url"]
    assert trans_rec in p_c_detail["transferred_recording_url"]
    assert p_c_detail["transferred_to_extension"] == 'خالد سعيد (109)'
    assert p_c_detail["is_transferred"] is True
    print("  ✅ GET /api/partner/v1/clients/<id>/calls/<call_id>/ correctly returned dual recordings and transfer metadata.")

    # 2.3 Partner Serializer Validation
    p_ser = PartnerClientCallSessionSerializer(data={
        "call_id": room_name,
        "from_number": "+201099887766",
        "to_number": "999",
        "status": "completed",
        "duration": 120,
        "started_at": "2026-10-06T00:00:00Z",
        "recording_url": "https://example.com/ai.mp3",
        "transferred_recording_url": "https://example.com/human.wav",
        "transferred_to_extension": "109",
        "is_transferred": True,
        "caller_extension": "101",
        "is_internal_test": False,
        "summary": "Transfer test"
    })
    assert p_ser.is_valid(), f"PartnerClientCallSessionSerializer errors: {p_ser.errors}"
    print("  ✅ PartnerClientCallSessionSerializer validated dual recordings and transfer fields successfully.")

    # 2.4 Partner OpenAPI Spec
    res_p_spec = client.get('/api/partner/v1/docs/openapi.json')
    assert res_p_spec.status_code == 200
    p_spec_json = res_p_spec.json()
    assert "transferred_recording_url" in json.dumps(p_spec_json)
    print("  ✅ Partner OpenAPI spec contains 'transferred_recording_url'.")

    # Cleanup test session
    session.delete()
    print("\n🎉 ALL DEVELOPER & PARTNER API TESTS PASSED SUCCESSFULLY!\n")


def secrets_token():
    import secrets
    return secrets.token_hex(16)


if __name__ == '__main__':
    test_apis()
