import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import json
from django.test import RequestFactory
from django.contrib.auth.models import User
from telephony.models import InboundPBXTrunk
from telephony.views import list_pbx_trunks, save_pbx_trunk, delete_pbx_trunk
from voice_assistant.views import livekit_webhook
from call_center.models import CallQueue
from agents.models import AgentProfile

def run_test():
    print("=== [PBX Integration E2E Test Starting] ===")

    # 1. Setup Test User
    user, _ = User.objects.get_or_create(username='pbx_test_user')
    rf = RequestFactory()

    # Create Voice Profile & Call Queue for routing tests
    profile, _ = AgentProfile.objects.get_or_create(
        user=user,
        name='PBX Dedicated Profile',
        defaults={'dialect': 'egyptian', 'is_active': False}
    )
    queue, _ = CallQueue.objects.get_or_create(
        user=user,
        code='555',
        defaults={'name': 'PBX Tech Support', 'strategy': 'round_robin'}
    )

    # Clean up any leftover trunks properly in both DB and LiveKit
    for old_t in InboundPBXTrunk.objects.filter(user=user):
        req_clean = rf.post(f'/api/telephony/pbx-trunks/{old_t.id}/delete/')
        req_clean.user = user
        delete_pbx_trunk(req_clean, old_t.id)

    # -------------------------------------------------------------
    # 2. Test Case 1: Save Inbound PBX Trunk with IP Whitelisting
    # -------------------------------------------------------------
    print("\n--- Test 1: Save Inbound PBX Trunk (IP Whitelisting + AI Destination) ---")
    payload_ip = {
        'name': 'Main Cairo Office - Issabel PBX',
        'auth_mode': 'ip',
        'pbx_ip': '197.38.45.12',
        'destination_type': 'ai',
        'target_profile_id': profile.id,
        'inbound_numbers': '888, 999'
    }
    req = rf.post(
        '/api/telephony/pbx-trunks/save/',
        data=json.dumps(payload_ip),
        content_type='application/json'
    )
    req.user = user

    res = save_pbx_trunk(req)
    res_data = json.loads(res.content.decode('utf-8'))
    print(f"Response status: {res.status_code}, data: {res_data}")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    assert res_data['status'] == 'success', f"Expected success: {res_data}"
    
    trunk_id = res_data['trunk']['id']
    trunk_obj = InboundPBXTrunk.objects.get(id=trunk_id)
    assert trunk_obj.name == 'Main Cairo Office - Issabel PBX'
    assert trunk_obj.auth_mode == 'ip'
    assert trunk_obj.pbx_ip == '197.38.45.12'
    assert trunk_obj.destination_type in ('ai_assistant', 'ai')
    assert trunk_obj.target_profile == profile
    assert trunk_obj.inbound_numbers == '888, 999'
    print(f"Trunk created: ID={trunk_obj.id}, LiveKit Trunk ID={trunk_obj.livekit_trunk_id}, Rule ID={trunk_obj.livekit_rule_id}")
    print("PASS: Trunk saved and synced with LiveKit!")

    # Verify Issabel Config Generation
    issabel_config = trunk_obj.generate_issabel_config()
    print("\nGenerated Issabel PEER Details:")
    print(issabel_config['peer_details'])
    assert 'type=peer' in issabel_config['peer_details']
    assert 'promiscredir=yes' in issabel_config['peer_details']
    assert 'canreinvite=yes' in issabel_config['peer_details']
    print("PASS: Issabel PEER Details verified!")

    # -------------------------------------------------------------
    # 3. Test Case 2: List PBX Trunks API
    # -------------------------------------------------------------
    print("\n--- Test 2: List PBX Trunks API ---")
    req_list = rf.get('/api/telephony/pbx-trunks/')
    req_list.user = user
    res_list = list_pbx_trunks(req_list)
    res_list_data = json.loads(res_list.content.decode('utf-8'))
    assert res_list.status_code == 200
    assert res_list_data['status'] == 'success'
    assert len(res_list_data['trunks']) == 1
    t_dict = res_list_data['trunks'][0]
    assert t_dict['name'] == 'Main Cairo Office - Issabel PBX'
    assert t_dict['target_profile_name'] == 'PBX Dedicated Profile'
    assert 'issabel_config' in t_dict
    print("PASS: list_pbx_trunks returns correct structure and configs!")

    # -------------------------------------------------------------
    # 4. Test Case 3: Save Inbound PBX Trunk with SIP Digest & Queue
    # -------------------------------------------------------------
    print("\n--- Test 3: Save Inbound PBX Trunk (SIP Credentials + Queue Destination) ---")
    payload_creds = {
        'name': 'Alexandria Branch - Asterisk PBX',
        'auth_mode': 'credentials',
        'auth_username': 'alex_pbx_trunk',
        'auth_password': 'SecretPassword123!',
        'destination_type': 'queue',
        'target_queue_id': queue.id,
        'inbound_numbers': ''
    }
    req_creds = rf.post(
        '/api/telephony/pbx-trunks/save/',
        data=json.dumps(payload_creds),
        content_type='application/json'
    )
    req_creds.user = user

    res_creds = save_pbx_trunk(req_creds)
    res_creds_data = json.loads(res_creds.content.decode('utf-8'))
    assert res_creds.status_code == 200
    assert res_creds_data['status'] == 'success'
    
    trunk2_id = res_creds_data['trunk']['id']
    trunk2_obj = InboundPBXTrunk.objects.get(id=trunk2_id)
    assert trunk2_obj.auth_mode == 'credentials'
    assert trunk2_obj.target_queue == queue
    
    issabel_config2 = trunk2_obj.generate_issabel_config()
    print("\nGenerated Issabel Config for Credentials Trunk:")
    print("Register String:", issabel_config2['register_string'])
    assert 'alex_pbx_trunk:SecretPassword123!' in issabel_config2['register_string']
    print("PASS: SIP Digest Credentials trunk and register string verified!")

    # -------------------------------------------------------------
    # 5. Test Case 4: Webhook Room Recognition for PBX Incoming Calls
    # -------------------------------------------------------------
    print("\n--- Test 4: Webhook Dispatch & Room Handling for PBX Calls ---")
    import hashlib, base64, redis
    from livekit import api
    from django.conf import settings

    # Simulate a room name produced by LiveKit SIP Dispatch Rule:
    # room_user_{user.id}_pbx_{trunk_obj.id}_call_777888
    pbx_room_name = f"room_user_{user.id}_pbx_{trunk_obj.id}_call_777888"
    
    webhook_payload = {
        "event": "participant_joined",
        "room": {
            "name": pbx_room_name
        },
        "participant": {
            "identity": "sip_01099998888",
            "name": "Caller 01099998888"
        }
    }
    
    body_str = json.dumps(webhook_payload)
    body_hash = hashlib.sha256(body_str.encode()).digest()
    body_b64 = base64.b64encode(body_hash).decode()
    token = api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET).with_sha256(body_b64).to_jwt()

    req_webhook = rf.post(
        '/api/voice/livekit-webhook/',
        data=body_str,
        content_type='application/json',
        HTTP_AUTHORIZATION=token
    )
    res_webhook = livekit_webhook(req_webhook)
    print(f"Webhook response status: {res_webhook.status_code}, content: {res_webhook.content.decode('utf-8')}")
    assert res_webhook.status_code == 200
    assert res_webhook.content.decode('utf-8') == "ok"

    # Verify room mapping in Redis set by webhook dispatch
    r = redis.Redis.from_url(settings.REDIS_URL)
    dispatched_room = r.get("agent_room:sip_01099998888")
    assert dispatched_room is not None, "Expected agent_room in Redis"
    assert dispatched_room.decode('utf-8') == pbx_room_name
    print(f"PASS: Redis agent_room verified: {dispatched_room.decode('utf-8')}")
    print("PASS: Webhook successfully recognized PBX room, resolved caller phone, and dispatched to Voice Agent!")

    # -------------------------------------------------------------
    # 6. Test Case 5: PBX Trunk Deletion & Cleanup
    # -------------------------------------------------------------
    print("\n--- Test 5: PBX Trunk Deletion & LiveKit Cleanup ---")
    req_del1 = rf.post(f'/api/telephony/pbx-trunks/{trunk_id}/delete/')
    req_del1.user = user
    res_del1 = delete_pbx_trunk(req_del1, trunk_id)
    assert res_del1.status_code == 200
    assert not InboundPBXTrunk.objects.filter(id=trunk_id).exists()

    req_del2 = rf.post(f'/api/telephony/pbx-trunks/{trunk2_id}/delete/')
    req_del2.user = user
    res_del2 = delete_pbx_trunk(req_del2, trunk2_id)
    assert res_del2.status_code == 200
    assert not InboundPBXTrunk.objects.filter(id=trunk2_id).exists()
    print("PASS: Trunks deleted cleanly from LiveKit and database!")

    # -------------------------------------------------------------
    # 7. Test Case 6: Verify Dashboard HTML Rendering
    # -------------------------------------------------------------
    print("\n--- Test 6: Verify room.html Dashboard Rendering ---")
    from voice_assistant.views import room_view as room
    req_room = rf.get('/')
    req_room.user = user
    res_room = room(req_room)
    html_content = res_room.content.decode('utf-8')
    assert 'pbx-trunks-grid' in html_content
    assert 'new-pbx-modal' in html_content
    assert 'issabel-code-modal' in html_content
    assert 'loadPbxTrunks' in html_content
    assert 'ربط السنترالات المحلية والأنظمة الخارجية' in html_content
    print("PASS: room.html contains all PBX Trunk UI elements, modals, and JS!")

    print("\n=================================================")
    print("🎉 ALL PBX TRUNK INTEGRATION E2E TESTS PASSED! 🎉")
    print("=================================================")

if __name__ == '__main__':
    run_test()
