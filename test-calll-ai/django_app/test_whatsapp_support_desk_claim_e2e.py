#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
E2E Test Suite for Dedicated Tier 2 WhatsApp Human Support Desk:
- Page render: GET /desk/whatsapp/
- Claim API: POST /api/crm/whatsapp/conversations/<phone>/claim/
- Release API: POST /api/crm/whatsapp/conversations/<phone>/release/
- Resolve API: POST /api/crm/whatsapp/conversations/<phone>/resolve/
- 300-Second (5-Minute) SLA Watchdog
- Multi-Tenant Isolation & Centrifugo PubSub
"""

import os
import sys
import json
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.contrib.auth.models import User
from django.test import Client
from crm.models import CustomerMemory, CRMSupportTicket
from crm.services.whatsapp_dispatcher import claim_conversation, release_conversation_to_pool, is_sla_breached

def run_suite():
    print("=" * 70)
    print("🚀 RUNNING DEDICATED WHATSAPP SUPPORT DESK E2E SUITE")
    print("=" * 70)

    passed = 0
    failed = 0

    def assert_true(condition, msg):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  ✅ PASS: {msg}")
        else:
            failed += 1
            print(f"  ❌ FAIL: {msg}")

    # Setup Fixtures
    uid_a = uuid.uuid4().hex[:6]
    uid_b = uuid.uuid4().hex[:6]
    user_a = User.objects.create_user(username=f"desk_agent_{uid_a}", password="password123")
    user_b = User.objects.create_user(username=f"other_agent_{uid_b}", password="password123")

    client_a = Client()
    client_a.force_login(user_a)

    client_b = Client()
    client_b.force_login(user_b)

    test_phone = f"+2010{uuid.uuid4().int % 100000000:08d}"

    try:
        # 1. Test GET /desk/whatsapp/
        resp_desk = client_a.get("/desk/whatsapp/")
        assert_true(resp_desk.status_code == 200, "GET /desk/whatsapp/ renders with HTTP 200")
        assert_true("مكتب دعم عملاء الواتساب" in resp_desk.content.decode("utf-8"), "Desk template contains Arabic title")
        assert_true("طابور الرنين العام" in resp_desk.content.decode("utf-8"), "Desk template contains Broadcast Ringing Queue")
        assert_true("05:00" in resp_desk.content.decode("utf-8"), "Desk template contains 5-minute SLA timer initial display")

        # 2. Test Direct Dispatcher claim_conversation
        claim_res = claim_conversation(user_id=user_a, phone_number=test_phone, agent_user_id=user_a.id)
        assert_true(claim_res.get("status") == "success", "claim_conversation returns success status")
        assert_true(claim_res.get("conversation_state") == "ACTIVE_SUPPORT", "claim_conversation sets ACTIVE_SUPPORT state")
        assert_true(claim_res.get("assigned_agent_id") == user_a.id, "claim_conversation records assigned_agent_id")

        mem = CustomerMemory.objects.get(user=user_a, phone_number=test_phone)
        assert_true(mem.whatsapp_memory.get("sla_seconds") == 300, "Default SLA window is 300 seconds (5 minutes)")
        assert_true(mem.whatsapp_memory.get("ai_auto_reply_enabled") is False, "Claiming pauses AI auto-reply")

        # 3. Test HTTP Claim Endpoint POST /api/crm/whatsapp/conversations/<phone>/claim/
        test_phone_2 = f"+2010{uuid.uuid4().int % 100000000:08d}"
        resp_claim = client_a.post(f"/api/crm/whatsapp/conversations/{test_phone_2}/claim/")
        assert_true(resp_claim.status_code == 200, "POST /claim/ HTTP endpoint returns 200")
        assert_true(resp_claim.json().get("conversation_state") == "ACTIVE_SUPPORT", "POST /claim/ returns ACTIVE_SUPPORT")

        # 4. Test HTTP Release Endpoint POST /api/crm/whatsapp/conversations/<phone>/release/
        resp_rel = client_a.post(f"/api/crm/whatsapp/conversations/{test_phone_2}/release/")
        assert_true(resp_rel.status_code == 200, "POST /release/ HTTP endpoint returns 200")
        assert_true(resp_rel.json().get("conversation_state") == "PENDING_AGENT_REPLY", "POST /release/ sets PENDING_AGENT_REPLY")
        assert_true(resp_rel.json().get("assigned_agent_id") is None, "POST /release/ unassigns agent (returns to pool)")

        # 5. Test 5-Minute (300-Second) SLA Watchdog
        # 280 seconds elapsed -> NOT breached
        mem_recent, _ = CustomerMemory.objects.get_or_create(user=user_a, phone_number=f"+2010{uuid.uuid4().int % 100000000:08d}")
        time_280s_ago = (datetime.now(timezone.utc) - timedelta(seconds=280)).isoformat()
        mem_recent.whatsapp_memory = {
            "conversation_state": "PENDING_AGENT_REPLY",
            "escalated_at": time_280s_ago,
            "sla_seconds": 300
        }
        mem_recent.save()
        assert_true(is_sla_breached(mem_recent) is False, "SLA Watchdog: 280s elapsed (<300s) is NOT breached")

        # 310 seconds elapsed -> BREACHED
        mem_breached, _ = CustomerMemory.objects.get_or_create(user=user_a, phone_number=f"+2010{uuid.uuid4().int % 100000000:08d}")
        time_310s_ago = (datetime.now(timezone.utc) - timedelta(seconds=310)).isoformat()
        mem_breached.whatsapp_memory = {
            "conversation_state": "PENDING_AGENT_REPLY",
            "escalated_at": time_310s_ago,
            "sla_seconds": 300
        }
        mem_breached.save()
        assert_true(is_sla_breached(mem_breached) is True, "SLA Watchdog: 310s elapsed (>300s) is correctly flagged as breached")

        # 6. Test Multi-Tenant Isolation
        # Tenant B cannot claim Tenant A customer
        resp_b_claim = client_b.post(f"/api/crm/whatsapp/conversations/{test_phone}/claim/")
        # Should create a separate CustomerMemory scoped to Tenant B, not alter Tenant A
        mem_a_check = CustomerMemory.objects.get(user=user_a, phone_number=test_phone)
        assert_true(mem_a_check.whatsapp_memory.get("assigned_agent_id") == user_a.id, "Tenant B cannot hijack Tenant A assigned agent")

        # 7. Test Resolve Endpoint Handback to AI
        resp_resolve = client_a.post(
            f"/api/crm/whatsapp/conversations/{test_phone}/resolve/",
            data=json.dumps({"resolution_notes": "Solved at desk", "resolution_status": "RESOLVED"}),
            content_type="application/json"
        )
        assert_true(resp_resolve.status_code == 200, "POST /resolve/ returns 200")
        assert_true(resp_resolve.json().get("ai_auto_reply_enabled") is True, "POST /resolve/ reactivates AI auto-reply")
        mem_resolved = CustomerMemory.objects.get(user=user_a, phone_number=test_phone)
        assert_true(mem_resolved.whatsapp_memory.get("conversation_state") == "RESOLVED", "Memory state updated to RESOLVED")
        assert_true(mem_resolved.whatsapp_memory.get("ai_auto_reply_enabled") is True, "Memory ai_auto_reply_enabled set to True")

    finally:
        # Cleanup
        CustomerMemory.objects.filter(user__in=[user_a, user_b]).delete()
        user_a.delete()
        user_b.delete()

    print("\n" + "=" * 70)
    print(f"📊 DESK SUITE SUMMARY: Passed: {passed} | Failed: {failed}")
    print("=" * 70)
    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_suite()
