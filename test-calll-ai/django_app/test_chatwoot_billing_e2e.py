# SPDX-License-Identifier: Apache-2.0
import os
import sys
import json
from decimal import Decimal
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from billing.models import BillingConfig, UserWallet, BillingTransaction
from partners.models import PartnerProfile, PartnerClientRelationship
from voice_assistant.models import TenantChatwootConfig


def run_tests():
    print("==================================================================")
    print("STARTING COMPREHENSIVE CHATWOOT MESSAGE BILLING E2E TEST SUITE")
    print("==================================================================")
    client = Client()

    # 0. Setup global billing configuration
    config = BillingConfig.get_config()
    config.cost_per_1k_chars = Decimal('0.0100')
    config.min_chars_per_message = 50
    config.media_equivalent_chars = 500
    config.save()
    print(f"[*] Config: rate={config.cost_per_1k_chars}/1k chars, min_chars={config.min_chars_per_message}, media_equiv={config.media_equivalent_chars}")

    # Create distinct test tenant user
    tenant_user, _ = User.objects.get_or_create(username='cw_billing_tenant_test')
    tenant_user.email = 'cw_tenant@test.local'
    tenant_user.save()

    tenant_wallet, _ = UserWallet.objects.get_or_create(
        user=tenant_user,
        defaults={
            'balance': Decimal('10.0000'),
            'currency': 'USD',
            'total_deposited': Decimal('10.0000'),
            'total_spent': Decimal('0.0000')
        }
    )
    tenant_wallet.balance = Decimal('10.0000')
    tenant_wallet.total_spent = Decimal('0.0000')
    tenant_wallet.save()

    tenant_cw_cfg, _ = TenantChatwootConfig.objects.get_or_create(
        user=tenant_user,
        defaults={'account_id': 8801, 'chatwoot_user_id': 8801, 'assistant_id': 1, 'is_provisioned': True}
    )
    tenant_cw_cfg.account_id = 8801
    tenant_cw_cfg.save()

    # Clean existing test transactions
    BillingTransaction.objects.filter(chatwoot_message_id__in=list(range(8001, 8025))).delete()

    # ------------------------------------------------------------------
    # Test 1: Text message billing with minimum character threshold (< 50 chars)
    # ------------------------------------------------------------------
    print("\n--- Test 1: Short text message (under min threshold) ---")
    initial_bal = tenant_wallet.balance
    short_content = "Hello there!"  # 12 chars
    payload_t1 = {
        "event": "message_created",
        "id": 8001,
        "message_type": "outgoing",
        "private": False,
        "content": short_content,
        "account": {"id": 8801},
        "inbox": {"id": 1, "name": "WhatsApp"}
    }
    resp = client.post('/api/billing/chatwoot/webhook/', data=json.dumps(payload_t1), content_type='application/json')
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.content}"
    data = resp.json()
    assert data["status"] == "success", f"Expected success, got {data}"
    assert data["actual_characters"] == len(short_content) == 12
    assert data["billed_characters"] == 50, f"Expected 50 billed chars, got {data['billed_characters']}"
    expected_cost = round((Decimal('50') / Decimal('1000')) * Decimal('0.0100'), 4)  # 0.0005
    assert Decimal(str(data["cost"])) == expected_cost, f"Expected cost {expected_cost}, got {data['cost']}"

    tenant_wallet.refresh_from_db()
    expected_bal = initial_bal - expected_cost
    assert tenant_wallet.balance == expected_bal, f"Expected wallet balance {expected_bal}, got {tenant_wallet.balance}"
    assert tenant_wallet.total_spent == expected_cost

    tx = BillingTransaction.objects.get(chatwoot_message_id=8001)
    assert tx.transaction_type == 'message_deduction'
    assert tx.amount == -expected_cost
    assert tx.actual_characters == 12
    assert tx.billed_characters == 50
    assert tx.inbox_name == "WhatsApp"
    print(f" [PASS] Test 1 passed: 12 chars billed at minimum 50 threshold -> cost {expected_cost}$, wallet balance {tenant_wallet.balance}$")

    # ------------------------------------------------------------------
    # Test 2: Long text message billing (> 50 chars threshold)
    # ------------------------------------------------------------------
    print("\n--- Test 2: Long text message (> 50 chars) ---")
    initial_bal = tenant_wallet.balance
    long_content = "A" * 1500  # 1500 chars
    payload_t2 = {
        "event": "message_created",
        "id": 8002,
        "message_type": "outgoing",
        "private": False,
        "content": long_content,
        "account": {"id": 8801},
        "inbox": {"id": 2, "name": "Website LiveChat"}
    }
    resp = client.post('/api/billing/chatwoot/webhook/', data=json.dumps(payload_t2), content_type='application/json')
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["actual_characters"] == 1500
    assert data["billed_characters"] == 1500
    expected_cost_t2 = round((Decimal('1500') / Decimal('1000')) * Decimal('0.0100'), 4)  # 0.0150
    assert Decimal(str(data["cost"])) == expected_cost_t2

    tenant_wallet.refresh_from_db()
    assert tenant_wallet.balance == initial_bal - expected_cost_t2
    tx2 = BillingTransaction.objects.get(chatwoot_message_id=8002)
    assert tx2.actual_characters == 1500
    assert tx2.billed_characters == 1500
    assert tx2.amount == -expected_cost_t2
    print(f" [PASS] Test 2 passed: 1500 chars billed exactly at 1500 -> cost {expected_cost_t2}$, wallet balance {tenant_wallet.balance}$")

    # ------------------------------------------------------------------
    # Test 3: Media attachment character equivalency billing (no text)
    # ------------------------------------------------------------------
    print("\n--- Test 3: Media attachment character equivalency (empty content + attachments) ---")
    initial_bal = tenant_wallet.balance
    payload_t3 = {
        "event": "message_created",
        "id": 8003,
        "message_type": "outgoing",
        "private": False,
        "content": "",
        "attachments": [{"id": 99, "file_type": "image", "data_url": "https://example.com/cat.jpg"}],
        "account": {"id": 8801},
        "inbox": {"id": 1, "name": "WhatsApp"}
    }
    resp = client.post('/api/billing/chatwoot/webhook/', data=json.dumps(payload_t3), content_type='application/json')
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["actual_characters"] == 500  # media_equivalent_chars
    assert data["billed_characters"] == 500
    expected_cost_t3 = round((Decimal('500') / Decimal('1000')) * Decimal('0.0100'), 4)  # 0.0050
    assert Decimal(str(data["cost"])) == expected_cost_t3

    tenant_wallet.refresh_from_db()
    assert tenant_wallet.balance == initial_bal - expected_cost_t3
    tx3 = BillingTransaction.objects.get(chatwoot_message_id=8003)
    assert tx3.actual_characters == 500
    assert tx3.billed_characters == 500
    print(f" [PASS] Test 3 passed: Media attachment equivalent to 500 chars -> cost {expected_cost_t3}$, wallet balance {tenant_wallet.balance}$")

    # ------------------------------------------------------------------
    # Test 4: Idempotency (duplicate webhook ignored)
    # ------------------------------------------------------------------
    print("\n--- Test 4: Idempotency (replay webhook with message ID 8001) ---")
    bal_before_dup = tenant_wallet.balance
    tx_count_before = BillingTransaction.objects.count()
    resp_dup = client.post('/api/billing/chatwoot/webhook/', data=json.dumps(payload_t1), content_type='application/json')
    assert resp_dup.status_code == 200
    data_dup = resp_dup.json()
    assert data_dup["status"] == "ignored"
    assert data_dup["reason"] == "already_billed"
    assert data_dup["chatwoot_message_id"] == 8001

    tenant_wallet.refresh_from_db()
    assert tenant_wallet.balance == bal_before_dup, "Balance must not change on duplicate webhook"
    assert BillingTransaction.objects.count() == tx_count_before, "No new transaction should be created"
    print(" [PASS] Test 4 passed: Duplicate webhook ignored, wallet balance and transaction count unchanged")

    # ------------------------------------------------------------------
    # Test 5: Partner SaaS custom rate deduction & relationship tracking
    # ------------------------------------------------------------------
    print("\n--- Test 5: Partner SaaS custom rate deduction ---")
    partner_user, _ = User.objects.get_or_create(username='partner_company_test')
    partner_user.email = 'partner@saas.local'
    partner_user.save()

    partner_profile, _ = PartnerProfile.objects.get_or_create(
        user=partner_user,
        defaults={
            'company_name': 'OmniPartner Ltd',
            'status': 'approved',
            'custom_rate_per_minute': Decimal('0.0300'),
            'custom_rate_per_1k_chars': Decimal('0.0070'),  # 0.0070 wholesale rate
        }
    )
    partner_profile.status = 'approved'
    partner_profile.custom_rate_per_1k_chars = Decimal('0.0070')
    partner_profile.save()

    partner_wallet, _ = UserWallet.objects.get_or_create(
        user=partner_user,
        defaults={'balance': Decimal('20.0000'), 'currency': 'USD', 'total_deposited': Decimal('20.0000')}
    )
    partner_wallet.balance = Decimal('20.0000')
    partner_wallet.total_spent = Decimal('0.0000')
    partner_wallet.save()

    # Sub-client user
    subclient_user, _ = User.objects.get_or_create(username='subclient_tenant_test')
    subclient_user.email = 'client1@partner-saas.com'
    subclient_user.save()

    subclient_cw, _ = TenantChatwootConfig.objects.get_or_create(
        user=subclient_user,
        defaults={'account_id': 8802, 'chatwoot_user_id': 8802, 'assistant_id': 2, 'is_provisioned': True}
    )
    subclient_cw.account_id = 8802
    subclient_cw.save()

    rel, _ = PartnerClientRelationship.objects.get_or_create(
        partner=partner_profile,
        client=subclient_user,
        defaults={'external_reference': 'ext_cust_777'}
    )
    rel.total_spent = Decimal('0.0000')
    rel.total_messages = 0
    rel.total_message_chars = 0
    rel.save()

    # Send outgoing message from sub-client (200 characters)
    subclient_content = "M" * 200
    payload_t5 = {
        "event": "message_created",
        "id": 8005,
        "message_type": "outgoing",
        "private": False,
        "content": subclient_content,
        "account": {"id": 8802},
        "inbox": {"id": 5, "name": "Partner Telegram Bot"}
    }
    resp5 = client.post('/api/billing/chatwoot/webhook/', data=json.dumps(payload_t5), content_type='application/json')
    assert resp5.status_code == 200
    data5 = resp5.json()
    assert data5["status"] == "success"
    assert data5["billed_characters"] == 200
    assert data5["rate_applied"] == 0.0070
    expected_cost_t5 = round((Decimal('200') / Decimal('1000')) * Decimal('0.0070'), 4)  # 0.0014
    assert Decimal(str(data5["cost"])) == expected_cost_t5

    # Verify Partner wallet deducted
    partner_wallet.refresh_from_db()
    assert partner_wallet.balance == Decimal('20.0000') - expected_cost_t5
    assert partner_wallet.total_spent == expected_cost_t5

    # Verify sub-client relationship stats updated
    rel.refresh_from_db()
    assert rel.total_messages == 1
    assert rel.total_message_chars == 200
    assert rel.total_spent == expected_cost_t5

    # Verify Transaction created under Partner wallet
    tx5 = BillingTransaction.objects.get(chatwoot_message_id=8005)
    assert tx5.wallet == partner_wallet
    assert tx5.amount == -expected_cost_t5
    assert tx5.rate_applied == Decimal('0.0070')
    assert "subclient_tenant_test" in tx5.description
    print(f" [PASS] Test 5 passed: Sub-client message billed to Partner wallet at wholesale rate {tx5.rate_applied}$, rel.total_messages={rel.total_messages}, rel.total_message_chars={rel.total_message_chars}")

    # ------------------------------------------------------------------
    # Test 6: Zero / Insufficient balance safety
    # ------------------------------------------------------------------
    print("\n--- Test 6: Zero / Insufficient balance safety ---")
    poor_user, _ = User.objects.get_or_create(username='poor_tenant_test')
    poor_cw, _ = TenantChatwootConfig.objects.get_or_create(
        user=poor_user,
        defaults={'account_id': 8803, 'is_provisioned': True}
    )
    poor_cw.account_id = 8803
    poor_cw.save()

    poor_wallet, _ = UserWallet.objects.get_or_create(
        user=poor_user,
        defaults={'balance': Decimal('0.0000'), 'currency': 'USD', 'total_deposited': Decimal('0.0000')}
    )
    # Set exact zero balance
    poor_wallet.balance = Decimal('0.0000')
    poor_wallet.total_spent = Decimal('0.0000')
    poor_wallet.save()

    payload_t6 = {
        "event": "message_created",
        "id": 8006,
        "message_type": "outgoing",
        "private": False,
        "content": "Message from user with 0 balance",
        "account": {"id": 8803},
        "inbox": {"id": 1, "name": "Web Chat"}
    }
    # Must NOT crash or raise 500 / IntegrityError
    resp6 = client.post('/api/billing/chatwoot/webhook/', data=json.dumps(payload_t6), content_type='application/json')
    assert resp6.status_code == 200, f"Expected 200, got {resp6.status_code}: {resp6.content}"
    data6 = resp6.json()
    assert data6["status"] == "insufficient_balance"
    assert data6["deducted"] == 0.0
    assert data6["balance_after"] == 0.0

    poor_wallet.refresh_from_db()
    assert poor_wallet.balance == Decimal('0.0000'), "Balance must remain non-negative (0.0000)"

    tx6 = BillingTransaction.objects.get(chatwoot_message_id=8006)
    assert tx6.amount == Decimal('0.0000')
    assert tx6.balance_after == Decimal('0.0000')
    assert "رصيد غير كافٍ" in tx6.description
    print(" [PASS] Test 6 passed: Zero balance handled gracefully without crash, balance remains non-negative (0.0000$)")

    # ------------------------------------------------------------------
    # Test 7: Direction & Privacy ignore filters
    # ------------------------------------------------------------------
    print("\n--- Test 7: Incoming message & private note filters ---")
    # 7.1 Incoming message
    p_incoming = {
        "event": "message_created",
        "id": 8007,
        "message_type": "incoming",
        "private": False,
        "content": "Customer message to company",
        "account": {"id": 8801}
    }
    resp7_1 = client.post('/api/billing/chatwoot/webhook/', data=json.dumps(p_incoming), content_type='application/json')
    assert resp7_1.status_code == 200
    assert resp7_1.json()["status"] == "ignored"
    assert not BillingTransaction.objects.filter(chatwoot_message_id=8007).exists()

    # 7.2 Private note
    p_private = {
        "event": "message_created",
        "id": 8008,
        "message_type": "outgoing",
        "private": True,
        "content": "Internal agent note: customer needs VIP follow up",
        "account": {"id": 8801}
    }
    resp7_2 = client.post('/api/billing/chatwoot/webhook/', data=json.dumps(p_private), content_type='application/json')
    assert resp7_2.status_code == 200
    assert resp7_2.json()["status"] == "ignored"
    assert not BillingTransaction.objects.filter(chatwoot_message_id=8008).exists()

    # 7.3 Other events (e.g. conversation_status_changed)
    p_conv = {
        "event": "conversation_status_changed",
        "id": 8009,
        "account": {"id": 8801}
    }
    resp7_3 = client.post('/api/billing/chatwoot/webhook/', data=json.dumps(p_conv), content_type='application/json')
    assert resp7_3.status_code == 200
    assert resp7_3.json()["status"] == "ignored"
    print(" [PASS] Test 7 passed: Incoming, private notes, and non-message_created events safely ignored")

    # ------------------------------------------------------------------
    # Test 8: Missing inbox in payload handled safely without NotNullViolation
    # ------------------------------------------------------------------
    print("\n--- Test 8: Missing inbox in payload (DB not-null safety) ---")
    payload_t8 = {
        "event": "message_created",
        "id": 8010,
        "message_type": "outgoing",
        "private": False,
        "content": "Message without inbox metadata",
        "account": {"id": 8801}
    }
    resp8 = client.post('/api/billing/chatwoot/webhook/', data=json.dumps(payload_t8), content_type='application/json')
    assert resp8.status_code == 200, f"Expected 200, got {resp8.status_code}: {resp8.content}"
    data8 = resp8.json()
    assert data8["status"] == "success"
    tx8 = BillingTransaction.objects.get(chatwoot_message_id=8010)
    assert tx8.inbox_name == "", f"Expected empty string inbox_name, got {repr(tx8.inbox_name)}"
    print(" [PASS] Test 8 passed: Missing inbox gracefully saved with empty string, no DB NotNullViolation")

    # ------------------------------------------------------------------
    # Test 9: Flat account_id format support
    # ------------------------------------------------------------------
    print("\n--- Test 9: Flat account_id format support ---")
    payload_t9 = {
        "event": "message_created",
        "id": 8011,
        "message_type": "outgoing",
        "private": False,
        "content": "Message with flat account_id key",
        "account_id": 8801
    }
    resp9 = client.post('/api/billing/chatwoot/webhook/', data=json.dumps(payload_t9), content_type='application/json')
    assert resp9.status_code == 200, f"Expected 200, got {resp9.status_code}: {resp9.content}"
    data9 = resp9.json()
    assert data9["status"] == "success"
    assert BillingTransaction.objects.filter(chatwoot_message_id=8011).exists()
    print(" [PASS] Test 9 passed: Flat account_id key resolved correctly")

    # ------------------------------------------------------------------
    # Test 10: Multi-threaded concurrent webhook idempotency
    # ------------------------------------------------------------------
    print("\n--- Test 10: Multi-threaded concurrent webhook idempotency ---")
    import threading
    concurrent_results = []
    concurrent_errors = []

    def dispatch_concurrent():
        c = Client()
        p = {
            "event": "message_created",
            "id": 8012,
            "message_type": "outgoing",
            "private": False,
            "content": "Concurrent idempotency test payload",
            "account": {"id": 8801},
            "inbox": {"id": 1, "name": "LiveChat"}
        }
        try:
            r = c.post('/api/billing/chatwoot/webhook/', data=json.dumps(p), content_type='application/json')
            concurrent_results.append((r.status_code, r.json()))
        except Exception as e:
            concurrent_errors.append(str(e))

    threads = [threading.Thread(target=dispatch_concurrent) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(concurrent_errors) == 0, f"Expected 0 thread errors, got {concurrent_errors}"
    assert len(concurrent_results) == 3, f"Expected 3 responses, got {len(concurrent_results)}"
    tx_count_t10 = BillingTransaction.objects.filter(chatwoot_message_id=8012).count()
    assert tx_count_t10 == 1, f"Expected exactly 1 transaction created, got {tx_count_t10}"
    statuses_t10 = [res[1].get('status') for res in concurrent_results]
    assert statuses_t10.count('success') == 1, f"Expected exactly 1 success, got {statuses_t10}"
    assert statuses_t10.count('ignored') == 2, f"Expected 2 ignored, got {statuses_t10}"
    print(f" [PASS] Test 10 passed: 3 concurrent requests resulted in exactly 1 transaction and 2 idempotency catches")

    # ------------------------------------------------------------------
    # Test 11: Micro-transaction precision in to_dict()
    # ------------------------------------------------------------------
    print("\n--- Test 11: Micro-transaction precision formatting in to_dict() ---")
    tx1 = BillingTransaction.objects.get(chatwoot_message_id=8001)
    dict1 = tx1.to_dict()
    assert "-0.0005" in dict1["amount_formatted"], f"Expected -0.0005 in amount_formatted, got {dict1['amount_formatted']}"
    assert "9.9995" in dict1["balance_after_formatted"], f"Expected 9.9995 in balance_after_formatted, got {dict1['balance_after_formatted']}"
    print(f" [PASS] Test 11 passed: Micro-transaction displays {dict1['amount_formatted']} and {dict1['balance_after_formatted']} with 4 decimal places")

    print("\n==================================================================")
    print("ALL 11 E2E TEST SCENARIOS PASSED WITH 100% SUCCESS!")
    print("==================================================================")


if __name__ == '__main__':
    run_tests()
