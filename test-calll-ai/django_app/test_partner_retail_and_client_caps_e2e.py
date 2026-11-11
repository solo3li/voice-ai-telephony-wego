# SPDX-License-Identifier: Apache-2.0
import os
import sys
import json
from decimal import Decimal
import django
from unittest.mock import patch

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from billing.models import BillingConfig, UserWallet, BillingTransaction
from partners.models import PartnerProfile, PartnerClientRelationship, PartnerSaaSProfile
from voice_assistant.models import TenantChatwootConfig


def run_tests():
    print("==================================================================")
    print("STARTING PARTNER RETAIL MARKUP & CLIENT CAPS COMPREHENSIVE E2E SUITE")
    print("==================================================================")
    client = Client()

    # 0. Global Billing Config setup
    config = BillingConfig.get_config()
    config.cost_per_1k_chars = Decimal('0.0100')
    config.min_chars_per_message = 50
    config.media_equivalent_chars = 500
    config.save()

    # 1. Setup Test Partner
    partner_user, _ = User.objects.get_or_create(username='test_partner_caps_admin')
    partner_user.email = 'partner_caps@test.local'
    partner_user.set_password('PartnerPass123!')
    partner_user.save()

    partner_profile, _ = PartnerProfile.objects.get_or_create(
        user=partner_user,
        defaults={
            'company_name': 'CloudReseller Corp',
            'status': 'approved',
            'custom_rate_per_minute': Decimal('0.0300'),
            'custom_rate_per_1k_chars': Decimal('0.0070'),
            'retail_rate_per_minute': Decimal('0.0500'),
            'retail_rate_per_1k_chars': Decimal('0.0150'),
            'webhook_url': 'https://partner-saas.com/webhooks/voice/'
        }
    )
    partner_profile.status = 'approved'
    partner_profile.custom_rate_per_minute = Decimal('0.0300')
    partner_profile.custom_rate_per_1k_chars = Decimal('0.0070')
    partner_profile.retail_rate_per_minute = Decimal('0.0500')
    partner_profile.retail_rate_per_1k_chars = Decimal('0.0150')
    partner_profile.save()

    partner_wallet, _ = UserWallet.objects.get_or_create(
        user=partner_user,
        defaults={'balance': Decimal('100.0000'), 'currency': 'USD', 'total_deposited': Decimal('100.0000')}
    )
    partner_wallet.balance = Decimal('100.0000')
    partner_wallet.total_spent = Decimal('0.0000')
    partner_wallet.save()

    partner_key = partner_profile.api_key
    auth_headers = {'HTTP_X_PARTNER_KEY': partner_key}

    # Clean old test transactions & previous test client
    BillingTransaction.objects.filter(chatwoot_message_id__in=list(range(9100, 9150))).delete()
    for old_r in PartnerClientRelationship.objects.filter(external_reference='client_quota_e2e_01'):
        u = old_r.client
        old_r.delete()
        if u:
            u.delete()

    # ------------------------------------------------------------------
    # Test 1: Partner Retail Markup Pricing via API (GET & POST /settings/)
    # ------------------------------------------------------------------
    print("\n--- Test 1: Partner Retail Markup Pricing via Settings API ---")
    get_res = client.get('/api/partner/v1/settings/', **auth_headers)
    assert get_res.status_code == 200, f"Expected 200, got {get_res.status_code}: {get_res.content}"
    get_data = get_res.json()
    assert get_data['status'] == 'success'
    assert 'retail_rate_per_minute' in get_data['settings']
    assert 'retail_rate_per_1k_chars' in get_data['settings']
    assert get_data['settings']['retail_rate_per_minute'] == 0.05
    assert get_data['settings']['retail_rate_per_1k_chars'] == 0.015

    # Update retail markup rates via POST
    update_payload = {
        'retail_rate_per_minute': 0.0600,
        'retail_rate_per_1k_chars': 0.0200,
    }
    post_res = client.post(
        '/api/partner/v1/settings/',
        data=json.dumps(update_payload),
        content_type='application/json',
        **auth_headers
    )
    assert post_res.status_code == 200, f"Expected 200, got {post_res.status_code}: {post_res.content}"
    post_data = post_res.json()
    assert post_data['status'] == 'success'
    assert post_data['settings']['retail_rate_per_minute'] == 0.06
    assert post_data['settings']['retail_rate_per_1k_chars'] == 0.02

    partner_profile.refresh_from_db()
    assert partner_profile.retail_rate_per_minute == Decimal('0.0600')
    assert partner_profile.retail_rate_per_1k_chars == Decimal('0.0200')
    p_dict = partner_profile.to_dict()
    assert p_dict['retail_rate_per_minute'] == 0.06
    assert p_dict['retail_rate_per_1k_chars'] == 0.02
    print(" [PASS] Test 1 passed: Retail markup rates read and updated successfully via API.")

    # ------------------------------------------------------------------
    # Test 2: Onboard Sub-Client with message_cap and message_char_cap
    # ------------------------------------------------------------------
    print("\n--- Test 2: Onboard Sub-Client with Message & Character Caps ---")
    reg_payload = {
        'external_reference': 'client_quota_e2e_01',
        'name': 'Alpha Store Quota Test',
        'email': 'alpha_quota@partner-subclient.local',
        'spending_cap': 10.00,
        'minute_cap': 100,
        'message_cap': 2,
        'message_char_cap': 300
    }
    reg_res = client.post(
        '/api/partner/v1/clients/register/',
        data=json.dumps(reg_payload),
        content_type='application/json',
        **auth_headers
    )
    assert reg_res.status_code == 201, f"Expected 201, got {reg_res.status_code}: {reg_res.content}"
    reg_data = reg_res.json()
    assert reg_data['status'] == 'success'
    subclient_id = reg_data['client_id']

    subclient_rel = PartnerClientRelationship.objects.get(client_id=subclient_id, partner=partner_profile)
    assert subclient_rel.message_cap == 2
    assert subclient_rel.message_char_cap == 300
    assert subclient_rel.spending_cap == Decimal('10.00')

    rel_dict = subclient_rel.to_dict()
    assert rel_dict['message_cap'] == 2
    assert rel_dict['message_char_cap'] == 300
    assert 'retail_revenue' in rel_dict
    assert 'estimated_profit' in rel_dict
    print(f" [PASS] Test 2 passed: Sub-client #{subclient_id} onboarded with message_cap=2, message_char_cap=300.")

    # ------------------------------------------------------------------
    # Test 3: Updating and Fetching Quotas via /quota/ and /cap/
    # ------------------------------------------------------------------
    print("\n--- Test 3: Quota API Endpoints (/clients/<id>/quota/) ---")
    # GET quota
    quota_get_res = client.get(f'/api/partner/v1/clients/{subclient_id}/quota/', **auth_headers)
    assert quota_get_res.status_code == 200
    assert quota_get_res.json()['client']['message_cap'] == 2

    # POST quota update
    quota_update_payload = {
        'message_cap': 3,
        'message_char_cap': 500,
        'spending_cap': 15.00
    }
    quota_post_res = client.post(
        f'/api/partner/v1/clients/{subclient_id}/quota/',
        data=json.dumps(quota_update_payload),
        content_type='application/json',
        **auth_headers
    )
    assert quota_post_res.status_code == 200
    updated_client_data = quota_post_res.json()['client']
    assert updated_client_data['message_cap'] == 3
    assert updated_client_data['message_char_cap'] == 500
    assert updated_client_data['spending_cap'] == 15.0

    subclient_rel.refresh_from_db()
    assert subclient_rel.message_cap == 3
    assert subclient_rel.message_char_cap == 500
    print(" [PASS] Test 3 passed: Quotas updated and read via /clients/<id>/quota/ endpoint.")

    # ------------------------------------------------------------------
    # Test 4: Sending Message Below Cap (Billed Normally + Retail Profit Tracking)
    # ------------------------------------------------------------------
    print("\n--- Test 4: Sending Messages Below Cap (Normal Billing & Profit) ---")
    subclient_user = subclient_rel.client
    cw_cfg, _ = TenantChatwootConfig.objects.get_or_create(
        user=subclient_user,
        defaults={'account_id': 9901, 'chatwoot_user_id': 9901, 'assistant_id': 10, 'is_provisioned': True}
    )
    cw_cfg.account_id = 9901
    cw_cfg.save()

    # Reset relationship usage counters
    subclient_rel.total_messages = 0
    subclient_rel.total_message_chars = 0
    subclient_rel.total_spent = Decimal('0.0000')
    subclient_rel.save()

    # Message 1: 100 characters (< 300 char cap, message count 1 <= 3)
    content_msg1 = "A" * 100
    payload_msg1 = {
        "event": "message_created",
        "id": 9101,
        "message_type": "outgoing",
        "private": False,
        "content": content_msg1,
        "account": {"id": 9901},
        "inbox": {"id": 1, "name": "WhatsApp"}
    }
    wh_res1 = client.post('/api/billing/chatwoot/webhook/', data=json.dumps(payload_msg1), content_type='application/json')
    assert wh_res1.status_code == 200
    assert wh_res1.json()['status'] == 'success'

    subclient_rel.refresh_from_db()
    assert subclient_rel.total_messages == 1
    assert subclient_rel.total_message_chars == 100
    # wholesale cost = (100 / 1000) * 0.0070 = 0.0007
    expected_cost = Decimal('0.0007')
    assert subclient_rel.total_spent == expected_cost
    # retail revenue = (100 / 1000) * 0.0200 = 0.0020
    assert subclient_rel.retail_revenue == Decimal('0.0020')
    # estimated profit = 0.0020 - 0.0007 = 0.0013
    assert subclient_rel.estimated_profit == Decimal('0.0013')
    print(f" [PASS] Test 4 passed: Message 1 billed normally. Spent={subclient_rel.total_spent}$, Revenue={subclient_rel.retail_revenue}$, Profit={subclient_rel.estimated_profit}$.")

    # ------------------------------------------------------------------
    # Test 5: Enforcing message_cap (Limit Exceeded)
    # ------------------------------------------------------------------
    print("\n--- Test 5: Enforcing message_cap (Message Limit Exceeded) ---")
    # Set cap to 1 (already at 1, so 2nd message exceeds)
    subclient_rel.message_cap = 1
    subclient_rel.save()

    dispatched_events = []
    def mock_dispatch(partner, event, data):
        dispatched_events.append((event, data))

    with patch('partners.services.webhook.dispatch_partner_webhook', side_effect=mock_dispatch):
        payload_msg2 = {
            "event": "message_created",
            "id": 9102,
            "message_type": "outgoing",
            "private": False,
            "content": "A" * 50,
            "account": {"id": 9901},
            "inbox": {"id": 1, "name": "WhatsApp"}
        }
        wh_res2 = client.post('/api/billing/chatwoot/webhook/', data=json.dumps(payload_msg2), content_type='application/json')
        assert wh_res2.status_code == 200
        wh_data2 = wh_res2.json()
        assert wh_data2['status'] == 'blocked', f"Expected blocked status, got {wh_data2}"
        assert wh_data2['reason'] == 'client_cap_exceeded'
        assert wh_data2['client_id'] == subclient_user.id
        assert wh_data2['cap_type'] == 'message_cap'

        # Verify partner webhook was dispatched with client.cap_exceeded
        assert len(dispatched_events) == 1
        event_name, event_data = dispatched_events[0]
        assert event_name == "client.cap_exceeded"
        assert event_data["client_id"] == subclient_user.id
        assert event_data["cap_type"] == "message_cap"

    # Verify no database transaction was created and counters were NOT incremented
    assert not BillingTransaction.objects.filter(chatwoot_message_id=9102).exists()
    subclient_rel.refresh_from_db()
    assert subclient_rel.total_messages == 1
    assert subclient_rel.total_spent == expected_cost
    print(" [PASS] Test 5 passed: Message 2 blocked due to message_cap exceeded; webhook client.cap_exceeded dispatched.")

    # ------------------------------------------------------------------
    # Test 6: Enforcing message_char_cap (Character Limit Exceeded)
    # ------------------------------------------------------------------
    print("\n--- Test 6: Enforcing message_char_cap (Character Limit Exceeded) ---")
    # Allow 10 messages, but set char cap to 150 (currently at 100 chars)
    subclient_rel.message_cap = 10
    subclient_rel.message_char_cap = 150
    subclient_rel.save()

    dispatched_events.clear()
    with patch('partners.services.webhook.dispatch_partner_webhook', side_effect=mock_dispatch):
        # Sending 80 chars -> 100 + 80 = 180 > 150
        payload_msg3 = {
            "event": "message_created",
            "id": 9103,
            "message_type": "outgoing",
            "private": False,
            "content": "B" * 80,
            "account": {"id": 9901},
            "inbox": {"id": 1, "name": "WhatsApp"}
        }
        wh_res3 = client.post('/api/billing/chatwoot/webhook/', data=json.dumps(payload_msg3), content_type='application/json')
        assert wh_res3.status_code == 200
        wh_data3 = wh_res3.json()
        assert wh_data3['status'] == 'blocked'
        assert wh_data3['reason'] == 'client_cap_exceeded'
        assert wh_data3['cap_type'] == 'message_char_cap'

        assert len(dispatched_events) == 1
        assert dispatched_events[0][0] == "client.cap_exceeded"
        assert dispatched_events[0][1]["cap_type"] == "message_char_cap"

    subclient_rel.refresh_from_db()
    assert subclient_rel.total_messages == 1
    assert subclient_rel.total_message_chars == 100
    print(" [PASS] Test 6 passed: Message 3 blocked due to message_char_cap exceeded; no charge incurred.")

    # ------------------------------------------------------------------
    # Test 7: Enforcing spending_cap on Messages
    # ------------------------------------------------------------------
    print("\n--- Test 7: Enforcing spending_cap on Messages ---")
    # Reset char cap to None, but set spending cap to exactly 0.0010 (spent=0.0007, next=0.0007 -> 0.0014 > 0.0010)
    subclient_rel.message_char_cap = None
    subclient_rel.spending_cap = Decimal('0.0010')
    subclient_rel.save()

    dispatched_events.clear()
    with patch('partners.services.webhook.dispatch_partner_webhook', side_effect=mock_dispatch):
        payload_msg4 = {
            "event": "message_created",
            "id": 9104,
            "message_type": "outgoing",
            "private": False,
            "content": "C" * 100,
            "account": {"id": 9901},
            "inbox": {"id": 1, "name": "WhatsApp"}
        }
        wh_res4 = client.post('/api/billing/chatwoot/webhook/', data=json.dumps(payload_msg4), content_type='application/json')
        assert wh_res4.status_code == 200
        wh_data4 = wh_res4.json()
        assert wh_data4['status'] == 'blocked'
        assert wh_data4['reason'] == 'client_cap_exceeded'
        assert wh_data4['cap_type'] == 'spending_cap'
        assert len(dispatched_events) == 1
        assert dispatched_events[0][1]["cap_type"] == "spending_cap"
    print(" [PASS] Test 7 passed: Message 4 blocked due to spending_cap exceeded.")

    # ------------------------------------------------------------------
    # Test 8: Method & Model Edge Cases (is_message_cap_exceeded, PartnerSaaSProfile alias)
    # ------------------------------------------------------------------
    print("\n--- Test 8: Model Unit & Method Tests ---")
    assert PartnerSaaSProfile is PartnerProfile
    test_rel = PartnerClientRelationship(
        partner=partner_profile,
        total_spent=Decimal('5.0000'),
        spending_cap=Decimal('5.0000'),
        total_messages=10,
        message_cap=10,
        total_message_chars=1000,
        message_char_cap=1000
    )
    # Spending cap boundary: spent 5.0, cap 5.0 -> next cost 0.0001 exceeds!
    assert test_rel.is_message_cap_exceeded(next_chars=10, next_cost=Decimal('0.0001')) is True
    assert test_rel.get_exceeded_message_cap_type(next_chars=10, next_cost=Decimal('0.0001')) == 'spending_cap'

    # When spending cap is not exceeded, but message cap is (10 + 1 > 10)
    test_rel.spending_cap = Decimal('10.0000')
    assert test_rel.is_message_cap_exceeded(next_chars=10, next_cost=Decimal('0.0000')) is True
    assert test_rel.get_exceeded_message_cap_type(next_chars=10, next_cost=Decimal('0.0000')) == 'message_cap'

    # When message cap is relaxed, but message_char_cap exceeded
    test_rel.message_cap = 20
    assert test_rel.is_message_cap_exceeded(next_chars=5, next_cost=Decimal('0.0000')) is True
    assert test_rel.get_exceeded_message_cap_type(next_chars=5, next_cost=Decimal('0.0000')) == 'message_char_cap'

    # When all relaxed -> False
    test_rel.message_char_cap = 2000
    assert test_rel.is_message_cap_exceeded(next_chars=5, next_cost=Decimal('0.0000')) is False
    assert test_rel.get_exceeded_message_cap_type(next_chars=5, next_cost=Decimal('0.0000')) is None
    print(" [PASS] Test 8 passed: is_message_cap_exceeded boundary checks and PartnerSaaSProfile alias verified.")

    # ------------------------------------------------------------------
    # Test 9: Partner Dashboard KPIs (Retail Revenue & Estimated Profit)
    # ------------------------------------------------------------------
    print("\n--- Test 9: Partner Dashboard KPIs & Client Consumption ---")
    client.force_login(partner_user)
    dash_res = client.get('/api/partner/v1/dashboard/')
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    assert dash_data['status'] == 'success'
    kpis = dash_data['kpis']
    assert 'retail_rate_per_minute' in kpis
    assert 'retail_rate_per_1k_chars' in kpis
    assert 'total_retail_revenue' in kpis
    assert 'total_estimated_profit' in kpis
    assert kpis['retail_rate_per_minute'] == 0.06
    assert kpis['retail_rate_per_1k_chars'] == 0.02

    # Check client entry in dashboard
    matching_clients = [c for c in dash_data['clients'] if c['client_id'] == subclient_id]
    assert len(matching_clients) == 1
    c_item = matching_clients[0]
    assert 'message_cap' in c_item
    assert 'message_char_cap' in c_item
    assert 'retail_revenue' in c_item
    assert 'estimated_profit' in c_item
    print(f" [PASS] Test 9 passed: Dashboard reflects retail rates, profit KPIs, and sub-client consumption.")

    # ------------------------------------------------------------------
    # Test 10: Non-numeric External Reference Lookup & Safe 404 Handling
    # ------------------------------------------------------------------
    print("\n--- Test 10: String External Reference Lookup & Safe 404 Handling ---")
    ext_lookup_res = client.get('/api/partner/v1/clients/cap/?client_id=client_quota_e2e_01', **auth_headers)
    assert ext_lookup_res.status_code == 200, f"Expected 200 for external_ref lookup, got {ext_lookup_res.status_code}: {ext_lookup_res.content}"
    assert ext_lookup_res.json()['client']['external_reference'] == 'client_quota_e2e_01'

    # Non-existent string ID must return 404 cleanly, never 500 ValueError
    not_found_res = client.get('/api/partner/v1/clients/cap/?client_id=completely_unknown_ref_xyz', **auth_headers)
    assert not_found_res.status_code == 404
    assert not_found_res.json()['status'] == 'error'
    print(" [PASS] Test 10 passed: String external reference lookup succeeded and unknown reference returned 404 cleanly.")

    # ------------------------------------------------------------------
    # Test 11: Validation on Invalid Cap and Retail Rate Inputs (400 Bad Request)
    # ------------------------------------------------------------------
    print("\n--- Test 11: Validation on Invalid Cap and Retail Rate Inputs ---")
    # Negative retail rate
    neg_rate_res = client.post(
        '/api/partner/v1/settings/',
        data=json.dumps({'retail_rate_per_minute': -0.05}),
        content_type='application/json',
        **auth_headers
    )
    assert neg_rate_res.status_code == 400
    assert neg_rate_res.json()['status'] == 'error'

    # Non-numeric retail rate string
    bad_rate_res = client.post(
        '/api/partner/v1/settings/',
        data=json.dumps({'retail_rate_per_1k_chars': 'not-a-decimal'}),
        content_type='application/json',
        **auth_headers
    )
    assert bad_rate_res.status_code == 400
    assert bad_rate_res.json()['status'] == 'error'

    # Negative message cap
    neg_cap_res = client.post(
        f'/api/partner/v1/clients/{subclient_id}/quota/',
        data=json.dumps({'message_cap': -5}),
        content_type='application/json',
        **auth_headers
    )
    assert neg_cap_res.status_code == 400
    assert neg_cap_res.json()['status'] == 'error'

    # Negative spending cap
    neg_spend_res = client.post(
        f'/api/partner/v1/clients/{subclient_id}/quota/',
        data=json.dumps({'spending_cap': -10.00}),
        content_type='application/json',
        **auth_headers
    )
    assert neg_spend_res.status_code == 400
    assert neg_spend_res.json()['status'] == 'error'
    print(" [PASS] Test 11 passed: Invalid and negative cap/retail inputs rejected with 400 Bad Request.")

    # ------------------------------------------------------------------
    # Test 12: Atomic Lock Re-check Dispatches Webhook on Concurrency Race
    # ------------------------------------------------------------------
    print("\n--- Test 12: Atomic Lock Re-check Webhook Dispatch on Concurrency Race ---")
    # Reset subclient rel for clean concurrency race check
    subclient_rel.refresh_from_db()
    subclient_rel.total_messages = 0
    subclient_rel.total_message_chars = 0
    subclient_rel.total_spent = Decimal('0.0000')
    subclient_rel.spending_cap = None
    subclient_rel.message_char_cap = None
    subclient_rel.message_cap = 2  # Allows 2 messages
    subclient_rel.save()

    dispatched_events.clear()
    original_select_for_update = PartnerClientRelationship.objects.select_for_update

    # We simulate a race: pre-check evaluates when total_messages=1 (passes),
    # but another thread increments total_messages to 2 right before lock is acquired.
    race_simulated = {'fired': False}
    from django.db.models.query import QuerySet

    def mock_select_for_update(*args, **kwargs):
        qs = original_select_for_update(*args, **kwargs)
        if not race_simulated['fired']:
            # Sneak in an update in DB before this request locks
            PartnerClientRelationship.objects.filter(id=subclient_rel.id).update(total_messages=2)
            race_simulated['fired'] = True
        return qs

    with patch('partners.services.webhook.dispatch_partner_webhook', side_effect=mock_dispatch):
        with patch.object(PartnerClientRelationship.objects, 'select_for_update', side_effect=mock_select_for_update):
            payload_race = {
                "event": "message_created",
                "id": 9120,
                "message_type": "outgoing",
                "private": False,
                "content": "Concurrent message test",
                "account": {"id": 9901},
                "inbox": {"id": 1, "name": "WhatsApp"}
            }
            res_race = client.post('/api/billing/chatwoot/webhook/', data=json.dumps(payload_race), content_type='application/json')
            assert res_race.status_code == 200
            race_json = res_race.json()
            assert race_json['status'] == 'blocked'
            assert race_json['reason'] == 'client_cap_exceeded'
            assert race_json['cap_type'] == 'message_cap'

            # Crucial assertion: Webhook MUST be dispatched even when caught under lock re-check!
            assert len(dispatched_events) == 1, f"Expected 1 dispatched event, got {len(dispatched_events)}"
            assert dispatched_events[0][0] == "client.cap_exceeded"
            assert dispatched_events[0][1]["cap_type"] == "message_cap"
            assert dispatched_events[0][1]["chatwoot_message_id"] == 9120
    print(" [PASS] Test 12 passed: Lock re-check under race condition successfully blocked message and dispatched client.cap_exceeded webhook.")

    # ------------------------------------------------------------------
    # Test 13: 6-Language I18N Keys Completeness Check
    # ------------------------------------------------------------------
    print("\n--- Test 13: 6-Language I18N Keys Completeness Check ---")
    import re
    common_js_path = os.path.join(os.path.dirname(__file__), 'static', 'js', 'common.js')
    with open(common_js_path, 'r', encoding='utf-8') as f:
        js_content = f.read()

    m_i18n = re.search(r'const APP_I18N = (\{.*?\n\};)', js_content, re.DOTALL)
    assert m_i18n, "APP_I18N not found in common.js!"
    i18n_dict = json.loads(m_i18n.group(1).rstrip(';'))

    required_partner_keys = [
        'partner_kpi_retail_rate', 'partner_kpi_revenue', 'partner_kpi_profit',
        'partner_retail_min_rate_label', 'partner_retail_char_rate_label',
        'partner_th_messages', 'partner_th_cost_profit',
        'partner_cap_messages_label', 'partner_cap_message_chars_label'
    ]
    for lang in ['ar', 'en', 'tr', 'fr', 'de', 'es']:
        assert lang in i18n_dict, f"Language '{lang}' missing in APP_I18N!"
        for r_key in required_partner_keys:
            val = i18n_dict[lang].get(r_key)
            assert val and isinstance(val, str), f"Missing key '{r_key}' in language '{lang}'!"
    print(" [PASS] Test 13 passed: All 9 partner UI and quota translation keys verified in 6 languages.")

    print("\n==================================================================")
    print("ALL 13 PARTNER RETAIL MARKUP & CONSUMPTION CAP SCENARIOS PASSED 100%!")
    print("==================================================================")


if __name__ == '__main__':
    run_tests()

