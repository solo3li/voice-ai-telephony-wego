import os
import sys
import json
import uuid
import django
from decimal import Decimal
from unittest.mock import patch, MagicMock

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from django.test import RequestFactory
from django.conf import settings

from developer.models import UserApiKey
from partners.models import PartnerProfile, PartnerClientRelationship
from telephony.models import OutboundSIPTrunk, InboundPBXTrunk
from agents.models import AgentProfile
from crm.models import CallSession
from billing.models import BillingConfig, UserWallet
from developer.views import api_user_call_dial, api_user_openapi_spec
from partners.views import api_partner_client_call_dial, api_partner_openapi_spec
from telephony.views import trigger_ai_outbound_call

def run_tests():
    print("=" * 70)
    print("STARTING OUTBOUND AI DIALING END-TO-END VERIFICATION SUITE")
    print("=" * 70)

    rf = RequestFactory()

    # Setup User & Partner Test Fixtures
    admin_user, _ = User.objects.get_or_create(username='admin', defaults={'is_superuser': True, 'email': 'admin@test.com'})
    user_key, _ = UserApiKey.objects.get_or_create(user=admin_user, is_active=True, defaults={'name': 'E2E Test Key'})

    partner_user, _ = User.objects.get_or_create(username='test_partner_dialer', defaults={'email': 'partner_dialer@test.com'})
    partner_profile, _ = PartnerProfile.objects.get_or_create(
        user=partner_user,
        defaults={
            'company_name': 'Dialer Telecom Partner',
            'status': 'approved',
            'custom_rate_per_minute': Decimal('0.03'),
            'webhook_url': 'http://mock-store:8002/webhook-receiver',
            'webhook_secret': 'partner_secret_test_123',
        }
    )
    if partner_profile.status != 'approved':
        partner_profile.status = 'approved'
        partner_profile.save(update_fields=['status'])

    # Ensure partner wallet has funds
    p_wallet, _ = UserWallet.objects.get_or_create(user=partner_user, defaults={'balance': Decimal('100.00'), 'currency': 'USD'})
    if p_wallet.balance < Decimal('10.00'):
        p_wallet.balance = Decimal('100.00')
        p_wallet.save(update_fields=['balance'])

    # Ensure admin user wallet has funds
    u_wallet, _ = UserWallet.objects.get_or_create(user=admin_user, defaults={'balance': Decimal('50.00'), 'currency': 'USD'})
    if u_wallet.balance < Decimal('5.00'):
        u_wallet.balance = Decimal('50.00')
        u_wallet.save(update_fields=['balance'])

    # Sub-client user
    subclient_user, _ = User.objects.get_or_create(username='dial_subclient_1', defaults={'email': 'client1@test.com'})
    client_rel, _ = PartnerClientRelationship.objects.get_or_create(
        partner=partner_profile,
        client=subclient_user,
        defaults={
            'external_reference': 'EXT_DIAL_001',
            'spending_cap': Decimal('50.00'),
            'total_spent': Decimal('0.00'),
            'is_active': True
        }
    )

    # Ensure outbound trunks exist with LiveKit trunk IDs
    admin_trunk, _ = OutboundSIPTrunk.objects.get_or_create(
        user=admin_user,
        defaults={
            'name': 'Admin Outbound Trunk',
            'sip_host': 'sip.telnyx.com',
            'caller_id': '+201000000001',
            'livekit_outbound_trunk_id': 'TR_ADMIN_E2E_01',
            'is_active': True,
            'is_default': True
        }
    )
    if not admin_trunk.livekit_outbound_trunk_id:
        admin_trunk.livekit_outbound_trunk_id = 'TR_ADMIN_E2E_01'
        admin_trunk.save(update_fields=['livekit_outbound_trunk_id'])

    partner_trunk, _ = OutboundSIPTrunk.objects.get_or_create(
        user=partner_user,
        defaults={
            'name': 'Partner Telnyx Trunk',
            'sip_host': 'sip.telnyx.com',
            'caller_id': '+966112233445',
            'livekit_outbound_trunk_id': 'TR_PARTNER_E2E_01',
            'is_active': True,
            'is_default': True
        }
    )
    if not partner_trunk.livekit_outbound_trunk_id:
        partner_trunk.livekit_outbound_trunk_id = 'TR_PARTNER_E2E_01'
        partner_trunk.save(update_fields=['livekit_outbound_trunk_id'])

    # Also test PBX trunk with extension dialing
    admin_pbx, _ = InboundPBXTrunk.objects.get_or_create(
        user=admin_user,
        defaults={
            'name': 'Issabel Main PBX',
            'auth_mode': 'ip',
            'inbound_numbers': '101,102',
            'enable_outbound': True,
            'livekit_outbound_trunk_id': 'TR_PBX_E2E_01',
            'is_active': True
        }
    )
    if not admin_pbx.livekit_outbound_trunk_id:
        admin_pbx.livekit_outbound_trunk_id = 'TR_PBX_E2E_01'
        admin_pbx.enable_outbound = True
        admin_pbx.save(update_fields=['livekit_outbound_trunk_id', 'enable_outbound'])

    print("\n[OK] Test environment & database fixtures prepared successfully.")

    # =========================================================================
    # TEST 1: User Developer API: POST /api/v1/calls/dial/
    # =========================================================================
    print("\n--- TEST 1: User Developer API (POST /api/v1/calls/dial/) ---")

    # 1.1 Authentication check
    req = rf.post('/api/v1/calls/dial/', data=json.dumps({"phone_number": "+201012345678"}), content_type='application/json')
    resp = api_user_call_dial(req)
    assert resp.status_code == 401, f"Expected 401 without API key, got {resp.status_code}"
    print("  [PASS] 1.1: Unauthenticated request correctly rejected with 401.")

    # 1.2 Validation check: missing phone
    req = rf.post('/api/v1/calls/dial/', data=json.dumps({}), content_type='application/json', HTTP_X_API_KEY=user_key.key)
    resp = api_user_call_dial(req)
    assert resp.status_code == 400, f"Expected 400 for missing phone, got {resp.status_code}"
    print("  [PASS] 1.2: Missing phone_number correctly rejected with 400.")

    # 1.3 Successful Outbound Call to External E.164 Number
    with patch('telephony.services._async_dial_sip_participant') as mock_dial:
        mock_dial.return_value = MagicMock(participant_id="PA_E2E_USER_EXT")

        req = rf.post(
            '/api/v1/calls/dial/',
            data=json.dumps({
                "phone_number": "01098765432",
                "call_goal": "متابعة تأكيد حجز العميل للخدمة رقم 8801",
                "gateway_type": "auto"
            }),
            content_type='application/json',
            HTTP_X_API_KEY=user_key.key
        )
        resp = api_user_call_dial(req)
        assert resp.status_code == 201, f"Expected 201 Created, got {resp.status_code}: {resp.content}"
        body = json.loads(resp.content.decode('utf-8'))
        assert body['status'] == 'success'
        assert body['destination_phone'] == '+201098765432'
        assert 'call_id' in body
        assert 'session_id' in body
        session = CallSession.objects.get(id=body['session_id'])
        assert session.direction == 'outbound_ai'
        assert session.destination_phone == '+201098765432'
        assert '8801' in session.call_goal
        mock_dial.assert_called_once()
        print(f"  [PASS] 1.3: User API dial initiated successfully (Room: {body['call_id']}, Session: {body['session_id']}).")

    # 1.4 Successful Outbound Call to Internal PBX Extension (e.g. 101)
    with patch('telephony.services._async_dial_sip_participant') as mock_dial:
        mock_dial.return_value = MagicMock(participant_id="PA_E2E_USER_PBX")

        req = rf.post(
            '/api/v1/calls/dial/',
            data=json.dumps({
                "phone_number": "101",
                "call_goal": "تنبيه موظف الدعم بشأن تذكرة طارئة",
                "gateway_type": "pbx",
                "gateway_id": admin_pbx.id
            }),
            content_type='application/json',
            HTTP_X_API_KEY=user_key.key
        )
        resp = api_user_call_dial(req)
        assert resp.status_code == 201, f"Expected 201 Created for PBX extension, got {resp.status_code}: {resp.content}"
        body = json.loads(resp.content.decode('utf-8'))
        assert body['status'] == 'success'
        assert body['destination_phone'] == '101'
        print(f"  [PASS] 1.4: Internal PBX extension dialing (101) verified successfully.")

    # =========================================================================
    # TEST 2: Partner Headless SaaS API: POST /api/partner/v1/clients/{id}/calls/dial/
    # =========================================================================
    print("\n--- TEST 2: Partner Headless API (POST /api/partner/v1/clients/<client_id>/calls/dial/) ---")

    # 2.1 Authentication check
    req = rf.post(f'/api/partner/v1/clients/{subclient_user.id}/calls/dial/', data=json.dumps({"phone_number": "+966551122334"}), content_type='application/json')
    resp = api_partner_client_call_dial(req, client_id=subclient_user.id)
    assert resp.status_code == 401, f"Expected 401 without Partner Key, got {resp.status_code}"
    print("  [PASS] 2.1: Missing X-Partner-Key rejected with 401.")

    # 2.2 Client Spending Cap Enforcement
    client_rel.spending_cap = Decimal('0.01')
    client_rel.total_spent = Decimal('0.01')
    client_rel.save(update_fields=['spending_cap', 'total_spent'])

    req = rf.post(
        f'/api/partner/v1/clients/{subclient_user.id}/calls/dial/',
        data=json.dumps({"phone_number": "+966551122334"}),
        content_type='application/json',
        HTTP_X_PARTNER_KEY=partner_profile.api_key
    )
    resp = api_partner_client_call_dial(req, client_id=subclient_user.id)
    assert resp.status_code == 403, f"Expected 403 Cap Exceeded, got {resp.status_code}: {resp.content}"
    cap_body = json.loads(resp.content.decode('utf-8'))
    assert cap_body.get('code') == 'CAP_EXCEEDED'
    print("  [PASS] 2.2: Sub-client spending cap enforcement verified (403 CAP_EXCEEDED).")

    # Reset cap for successful dial
    client_rel.spending_cap = Decimal('100.00')
    client_rel.total_spent = Decimal('0.00')
    client_rel.save(update_fields=['spending_cap', 'total_spent'])

    # 2.3 Successful Outbound Call for Sub-Client (Inheriting partner's trunk)
    with patch('telephony.services._async_dial_sip_participant') as mock_dial, \
         patch('partners.views.dispatch_partner_webhook') as mock_webhook:
        mock_dial.return_value = MagicMock(participant_id="PA_E2E_PARTNER_EXT")

        req = rf.post(
            f'/api/partner/v1/clients/{subclient_user.id}/calls/dial/',
            data=json.dumps({
                "phone_number": "+966551122334",
                "call_goal": "الاتصال بالعميل لتأكيد تفاصيل الشحنة والتوصيل",
                "gateway_type": "auto"
            }),
            content_type='application/json',
            HTTP_X_PARTNER_KEY=partner_profile.api_key
        )
        resp = api_partner_client_call_dial(req, client_id=subclient_user.id)
        assert resp.status_code == 201, f"Expected 201 Created for partner sub-client, got {resp.status_code}: {resp.content}"
        body = json.loads(resp.content.decode('utf-8'))
        assert body['status'] == 'success'
        assert body['client_id'] == subclient_user.id
        assert body['destination_phone'] == '+966551122334'
        assert 'session_id' in body
        
        # Verify webhook dispatch
        mock_webhook.assert_called_once()
        wh_call_args = mock_webhook.call_args[0]
        assert wh_call_args[1] == 'call.outbound_initiated'
        assert wh_call_args[2]['client_id'] == subclient_user.id
        assert wh_call_args[2]['destination_phone'] == '+966551122334'
        print(f"  [PASS] 2.3: Partner sub-client dial successful & 'call.outbound_initiated' webhook dispatched.")

    # =========================================================================
    # TEST 3: Web UI Telephony View: trigger_ai_outbound_call
    # =========================================================================
    print("\n--- TEST 3: Web UI Telephony View Delegation (trigger_ai_outbound_call) ---")
    with patch('telephony.services._async_dial_sip_participant') as mock_dial:
        mock_dial.return_value = MagicMock(participant_id="PA_E2E_UI")
        ui_req = rf.post(
            '/api/telephony/ai-call/',
            data=json.dumps({
                "phone_number": "01234567890",
                "call_goal": "استطلاع رضا العميل عن الخدمة"
            }),
            content_type='application/json'
        )
        ui_req.user = admin_user
        ui_resp = trigger_ai_outbound_call(ui_req)
        assert ui_resp.status_code in (200, 201), f"Expected 200/201 from UI trigger, got {ui_resp.status_code}: {ui_resp.content}"
        ui_body = json.loads(ui_resp.content.decode('utf-8'))
        assert ui_body['status'] == 'success'
        assert ui_body['destination_phone'] == '+201234567890'
        print(f"  [PASS] 3.1: Web UI trigger_ai_outbound_call seamlessly delegated to services.py.")

    # =========================================================================
    # TEST 4: Bilingual OpenAPI Specs
    # =========================================================================
    print("\n--- TEST 4: Bilingual OpenAPI 3.1 Specification Verification ---")
    
    # 4.1 User Developer OpenAPI Spec (Arabic & English)
    req_ar = rf.get('/api/v1/docs/openapi.json?lang=ar')
    resp_ar = api_user_openapi_spec(req_ar)
    spec_ar = json.loads(resp_ar.content.decode('utf-8'))
    assert '/calls/dial/' in spec_ar['paths'], "User OpenAPI spec missing /calls/dial/"
    assert 'صادرة' in spec_ar['paths']['/calls/dial/']['post']['summary']
    print("  [PASS] 4.1: User OpenAPI Arabic spec contains /calls/dial/ with Arabic text.")

    req_en = rf.get('/api/v1/docs/openapi.json?lang=en')
    resp_en = api_user_openapi_spec(req_en)
    spec_en = json.loads(resp_en.content.decode('utf-8'))
    assert '/calls/dial/' in spec_en['paths'], "User OpenAPI spec missing /calls/dial/ in EN"
    assert 'Outbound' in spec_en['paths']['/calls/dial/']['post']['summary']
    print("  [PASS] 4.2: User OpenAPI English spec contains /calls/dial/ with English text.")

    # 4.2 Partner OpenAPI Spec (Arabic & English)
    p_req_ar = rf.get('/api/partner/v1/docs/openapi.json?lang=ar')
    p_resp_ar = api_partner_openapi_spec(p_req_ar)
    p_spec_ar = json.loads(p_resp_ar.content.decode('utf-8'))
    assert '/clients/{client_id}/calls/dial/' in p_spec_ar['paths'], "Partner OpenAPI spec missing /clients/{client_id}/calls/dial/"
    assert 'صادرة' in p_spec_ar['paths']['/clients/{client_id}/calls/dial/']['post']['summary']
    print("  [PASS] 4.3: Partner OpenAPI Arabic spec contains /clients/{client_id}/calls/dial/.")

    p_req_en = rf.get('/api/partner/v1/docs/openapi.json?lang=en')
    p_resp_en = api_partner_openapi_spec(p_req_en)
    p_spec_en = json.loads(p_resp_en.content.decode('utf-8'))
    assert '/clients/{client_id}/calls/dial/' in p_spec_en['paths'], "Partner OpenAPI spec missing /clients/{client_id}/calls/dial/ in EN"
    assert 'Outbound' in p_spec_en['paths']['/clients/{client_id}/calls/dial/']['post']['summary']
    print("  [PASS] 4.4: Partner OpenAPI English spec contains /clients/{client_id}/calls/dial/ in English.")

    # =========================================================================
    # TEST 5: Web UI Template Checks (room.html)
    # =========================================================================
    print("\n--- TEST 5: Web UI Template Integrity Checks ---")
    room_path = os.path.join(settings.BASE_DIR, 'voice_assistant', 'templates', 'voice_assistant', 'room.html')
    with open(room_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    assert 'btn_outbound_ai_call' in html_content, "Missing btn_outbound_ai_call i18n attribute in room.html"
    assert 'openNewAICallModal()' in html_content, "Missing openNewAICallModal() trigger in room.html"
    assert 'dev-curl-dial-sample' in html_content, "Missing dev-curl-dial-sample snippet in room.html"
    assert '/calls/dial/' in html_content, "Missing /calls/dial/ reference in room.html"
    print("  [PASS] 5.1: room.html contains Outbound AI Call action button, cURL sample, and translations.")

    print("\n" + "=" * 70)
    print("ALL END-TO-END TESTS PASSED SUCCESSFULLY! (100% VERIFIED)")
    print("=" * 70)

if __name__ == '__main__':
    run_tests()
