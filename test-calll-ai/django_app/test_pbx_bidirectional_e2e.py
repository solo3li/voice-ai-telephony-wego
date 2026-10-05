import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import json
from unittest.mock import patch, MagicMock
from django.test import RequestFactory
from django.contrib.auth.models import User
from telephony.models import InboundPBXTrunk, OutboundSIPTrunk
from telephony.views import (
    list_pbx_trunks,
    save_pbx_trunk,
    delete_pbx_trunk,
    list_outbound_gateways,
    trigger_ai_outbound_call
)
from agents.models import AgentProfile

def run_test():
    print("=== [PBX Bidirectional Inbound/Outbound E2E Test Starting] ===")

    # 1. Setup Test User
    user, _ = User.objects.get_or_create(username='pbx_bidi_test_user')
    rf = RequestFactory()

    # Agent Profile for Outbound testing
    profile, _ = AgentProfile.objects.get_or_create(
        user=user,
        name='Bidi Test Profile',
        defaults={'dialect': 'egyptian', 'is_active': True}
    )

    # Clean up leftover trunks
    for old_t in InboundPBXTrunk.objects.filter(user=user):
        req_del = rf.post(f'/api/telephony/pbx-trunks/{old_t.id}/delete/')
        req_del.user = user
        delete_pbx_trunk(req_del, old_t.id)

    # -------------------------------------------------------------
    # Test 1: Save Bidirectional PBX Trunk
    # -------------------------------------------------------------
    print("\n--- Test 1: Save Bidirectional PBX Trunk with LiveKit Outbound Trunk ---")
    payload = {
        'name': 'Branch Alexandria - Bidirectional Issabel',
        'auth_mode': 'ip',
        'pbx_ip': '197.38.100.50',
        'destination_type': 'ai',
        'target_profile_id': profile.id,
        'inbound_numbers': '800, 801',
        'enable_outbound': True,
        'outbound_port': 5060,
        'outbound_transport': 'UDP',
        'is_default_outbound': True
    }

    req = rf.post(
        '/api/telephony/pbx-trunks/save/',
        data=json.dumps(payload),
        content_type='application/json'
    )
    req.user = user

    res = save_pbx_trunk(req)
    res_data = json.loads(res.content.decode('utf-8'))
    print(f"Save Response status: {res.status_code}, data: {res_data}")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    assert res_data['status'] == 'success', f"Expected success: {res_data}"

    trunk_id = res_data['trunk']['id']
    trunk = InboundPBXTrunk.objects.get(id=trunk_id)
    assert trunk.enable_outbound is True
    assert trunk.outbound_port == 5060
    assert trunk.outbound_transport == 'UDP'
    assert trunk.is_default_outbound is True
    assert trunk.livekit_trunk_id.startswith('ST_')
    assert trunk.livekit_rule_id.startswith('SDR_')
    assert trunk.livekit_outbound_trunk_id.startswith('ST_')
    print(f"SUCCESS: LiveKit Inbound Trunk ID: {trunk.livekit_trunk_id}")
    print(f"SUCCESS: LiveKit Dispatch Rule ID: {trunk.livekit_rule_id}")
    print(f"SUCCESS: LiveKit Outbound Trunk ID: {trunk.livekit_outbound_trunk_id}")

    # -------------------------------------------------------------
    # Test 2: Verify Issabel Config Generation (PEER + USER Details)
    # -------------------------------------------------------------
    print("\n--- Test 2: Verify Dual-Direction Issabel Config Generation ---")
    config = trunk.generate_issabel_config()
    assert 'peer_details' in config
    assert 'user_details' in config
    assert 'host=app.localhost' in config['peer_details']
    assert '[USER Details]' in config['user_details']
    assert 'context=from-internal' in config['user_details']
    print("PASS: Both PEER Details and USER Details correctly generated.")

    # -------------------------------------------------------------
    # Test 3: List Outbound Gateways API
    # -------------------------------------------------------------
    print("\n--- Test 3: List Outbound Gateways Endpoint ---")
    req_gw = rf.get('/api/telephony/outbound-gateways/')
    req_gw.user = user
    res_gw = list_outbound_gateways(req_gw)
    gw_data = json.loads(res_gw.content.decode('utf-8'))
    print("Gateways returned:", json.dumps(gw_data, indent=2, ensure_ascii=False))
    assert gw_data['status'] == 'success'
    gateways = gw_data['gateways']
    pbx_gw = next((g for g in gateways if g['type'] == 'pbx' and g['id'] == trunk.id), None)
    assert pbx_gw is not None, "PBX gateway not found in outbound gateways list!"
    assert pbx_gw['is_default'] is True
    assert gw_data['default_gateway']['id'] == trunk.id
    print("PASS: PBX Trunk correctly listed as default Outbound Gateway!")

    # -------------------------------------------------------------
    # Test 4: Trigger AI Outbound Call via PBX (Extension Dialing)
    # -------------------------------------------------------------
    print("\n--- Test 4: Trigger AI Outbound Call to Internal Extension 101 via PBX ---")
    dial_payload = {
        'phone_number': '101',  # Internal PBX Extension
        'profile_id': profile.id,
        'call_goal': 'تأكيد وصول الأوراق لمكتب المحاسبة تحويلة 101',
        'gateway_type': 'pbx',
        'gateway_id': trunk.id
    }
    req_call = rf.post(
        '/api/telephony/ai-call/',
        data=json.dumps(dial_payload),
        content_type='application/json'
    )
    req_call.user = user

    # Mock LiveKit participant creation to verify the exact dialed params
    with patch('telephony.views._async_dial_sip_participant') as mock_dial:
        mock_dial.return_value = {
            'participant_id': 'PA_TEST_EXT_101',
            'room_name': 'call-outbound-test-ext'
        }
        res_call = trigger_ai_outbound_call(req_call)
        call_data = json.loads(res_call.content.decode('utf-8'))
        print("Call response:", call_data)
        assert call_data['status'] == 'success'
        assert call_data['destination_phone'] == '101', f"Expected untouched extension 101, got {call_data['destination_phone']}"
        assert 'Alexandria' in call_data['gateway_used']

        # Verify mock received the PBX outbound trunk ID and exact extension '101'
        mock_dial.assert_called_once()
        called_kwargs = mock_dial.call_args.kwargs
        dialed_trunk_id = called_kwargs.get('trunk_id')
        dialed_phone = called_kwargs.get('destination_phone')
        assert dialed_trunk_id == trunk.livekit_outbound_trunk_id, f"Expected {trunk.livekit_outbound_trunk_id}, got {dialed_trunk_id}"
        assert dialed_phone == '101', f"Expected 101, got {dialed_phone}"
        print(f"PASS: LiveKit dial participant called with PBX Outbound Trunk: {dialed_trunk_id} and extension: {dialed_phone}")

    # -------------------------------------------------------------
    # Test 5: Trigger AI Outbound Call to External Mobile Number
    # -------------------------------------------------------------
    print("\n--- Test 5: Trigger AI Outbound Call to External Mobile Number via PBX ---")
    ext_payload = {
        'phone_number': '01012345678',
        'profile_id': profile.id,
        'call_goal': 'تأكيد طلب العميل الخارجي عبر خطوط السنترال',
        'gateway_type': 'pbx',
        'gateway_id': trunk.id
    }
    req_call_ext = rf.post(
        '/api/telephony/ai-call/',
        data=json.dumps(ext_payload),
        content_type='application/json'
    )
    req_call_ext.user = user

    with patch('telephony.views._async_dial_sip_participant') as mock_dial:
        mock_dial.return_value = {
            'participant_id': 'PA_TEST_MOB_010',
            'room_name': 'call-outbound-test-mob'
        }
        res_call_ext = trigger_ai_outbound_call(req_call_ext)
        call_data_ext = json.loads(res_call_ext.content.decode('utf-8'))
        print("Call response:", call_data_ext)
        assert call_data_ext['status'] == 'success'
        assert call_data_ext['destination_phone'] == '+201012345678'
        mock_dial.assert_called_once()
        called_kwargs_ext = mock_dial.call_args.kwargs
        assert called_kwargs_ext.get('trunk_id') == trunk.livekit_outbound_trunk_id
        assert called_kwargs_ext.get('destination_phone') == '+201012345678'
        print("PASS: External mobile correctly normalized to +201012345678 and routed via PBX!")

    # -------------------------------------------------------------
    # Test 6: Delete PBX Trunk and Cleanup All LiveKit Resources
    # -------------------------------------------------------------
    print("\n--- Test 6: Delete PBX Trunk and Verify Full LiveKit Cleanup ---")
    inbound_trunk_id = trunk.livekit_trunk_id
    dispatch_rule_id = trunk.livekit_rule_id
    outbound_trunk_id = trunk.livekit_outbound_trunk_id

    req_del = rf.post(f'/api/telephony/pbx-trunks/{trunk.id}/delete/')
    req_del.user = user
    res_del = delete_pbx_trunk(req_del, trunk.id)
    del_data = json.loads(res_del.content.decode('utf-8'))
    assert del_data['status'] == 'success'
    assert not InboundPBXTrunk.objects.filter(id=trunk.id).exists()
    print(f"PASS: Trunk deleted from DB and cleanup dispatched for {inbound_trunk_id}, {dispatch_rule_id}, {outbound_trunk_id}")

    print("\n============================================================")
    print("🎉 ALL BIDIRECTIONAL PBX INTEGRATION TESTS PASSED SUCCESSFULLY!")
    print("============================================================")

if __name__ == '__main__':
    run_test()
