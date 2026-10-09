#!/usr/bin/env python3
"""
Comprehensive End-to-End Test Suite for Digital Coworker & Omnichannel Integration.
Tests all stages end-to-end via scripts without any browser interaction:
  1. ForwardAuth & Session Bridge (/api/auth/verify-session/, /api/auth/trinity-sso/)
  2. Dual-Mode Tenant Switching (call_center_only vs digital_coworker)
  3. Phone-First Identity Resolution (E.164 anchor across Voice & WhatsApp)
  4. Call Completion & Trinity Event Bridge (Redis queue + event dispatch)
  5. Conditional Approval Gates & Decision Execution (Inline Telegram callback & Auto-discount)
  6. Unified Coworker Tool Dispatcher (MCP / Trinity Tool Execution)
  7. Regression & Zero-Breaking-Changes Check (Call Center, Telephony, CRM)
"""
import os
import sys
import json
import time
import requests
import redis
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client
from agents.models import DigitalCoworkerConfig, AgentProfile
from crm.models import CustomerMemory, CustomerChannelIdentifier, ApprovalRequest, OmnichannelMessage, CallSession


BASE_URL = "http://127.0.0.1:8000"
INTERNAL_API_KEY = getattr(settings, 'INTERNAL_API_KEY', 'voice_internal_secret_key_2026')
TEST_USERNAME = "e2e_coworker_tester"
TEST_PASSWORD = "StrongCoworkerPass123!"
TEST_PHONE = "+201011223344"

# Color formatting for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

passed_tests = 0
failed_tests = 0


def log_step(title):
    print(f"\n{BLUE}{BOLD}▶ [STAGE] {title}{RESET}")


def assert_test(condition, message):
    global passed_tests, failed_tests
    if condition:
        print(f"  {GREEN}✔ PASSED:{RESET} {message}")
        passed_tests += 1
    else:
        print(f"  {RED}✘ FAILED:{RESET} {message}")
        failed_tests += 1
        raise AssertionError(message)


def run_all_stages():
    global passed_tests, failed_tests
    print(f"{BOLD}{YELLOW}========================================================================")
    print("  STARTING END-TO-END AUTOMATED VERIFICATION SUITE")
    print(f"  Target: Voice AI Telephony -> Autonomous Digital Coworker Engine")
    print(f"========================================================================{RESET}")

    # Step 0: Ensure Test User exists
    log_step("0. Setup Test Tenant & User")
    user, created = User.objects.get_or_create(username=TEST_USERNAME, defaults={"email": "coworker@test.ai"})
    user.set_password(TEST_PASSWORD)
    user.save()
    assert_test(user is not None and user.id > 0, f"Test user '{TEST_USERNAME}' (ID: {user.id}) ready.")

    session = requests.Session()
    # Create valid authenticated session for test user
    from django.contrib.sessions.backends.db import SessionStore
    store = SessionStore()
    store['_auth_user_id'] = str(user.id)
    store['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
    store['_auth_user_hash'] = user.get_session_auth_hash()
    store.save()
    session.cookies.set('sessionid', store.session_key)
    assert_test(session.cookies.get('sessionid') is not None, f"Authenticated successfully; sessionid '{store.session_key[:8]}...' acquired.")

    # ---------------------------------------------------------------------------------------------------
    # STAGE 1: ForwardAuth & Session Bridge
    # ---------------------------------------------------------------------------------------------------
    log_step("1. ForwardAuth & Session Bridge (/api/auth/verify-session/ & /api/auth/trinity-sso/)")
    
    # Unauthenticated request
    unauth_resp = requests.get(f"{BASE_URL}/api/auth/verify-session/")
    assert_test(unauth_resp.status_code == 401, f"Unauthenticated request returns 401 Unauthorized (got {unauth_resp.status_code})")
    assert_test(unauth_resp.json().get("authenticated") is False, "Unauthenticated response payload has authenticated: false")

    # Authenticated request with session cookie
    auth_resp = session.get(f"{BASE_URL}/api/auth/verify-session/")
    assert_test(auth_resp.status_code == 200, f"Authenticated request returns 200 OK (got {auth_resp.status_code})")
    auth_data = auth_resp.json()
    assert_test(auth_data.get("authenticated") is True, "Response contains authenticated: true")
    assert_test(auth_data.get("user", {}).get("username") == TEST_USERNAME, f"Response user matches {TEST_USERNAME}")
    
    # Verify Traefik ForwardAuth injected response headers
    assert_test(auth_resp.headers.get("X-Forwarded-User") == TEST_USERNAME, "ForwardAuth header X-Forwarded-User injected properly")
    assert_test(auth_resp.headers.get("X-User-Id") == str(user.id), "ForwardAuth header X-User-Id matches tenant user id")
    assert_test(auth_resp.headers.get("X-Service-Mode") is not None, "ForwardAuth header X-Service-Mode present")

    # Trinity SSO Token Exchange
    sso_resp = session.get(f"{BASE_URL}/api/auth/trinity-sso/")
    assert_test(sso_resp.status_code == 200, "SSO endpoint returns 200 OK")
    sso_data = sso_resp.json()
    assert_test(sso_data.get("status") == "success" and sso_data.get("user_id") == user.id, "SSO token payload matches user")

    # ---------------------------------------------------------------------------------------------------
    # STAGE 2: Dual-Mode Tenant Switching & Configuration
    # ---------------------------------------------------------------------------------------------------
    log_step("2. Dual-Mode Tenant Switching (call_center_only vs digital_coworker)")

    # 2.1 Switch to Classic Call Center Mode
    mode_cc_payload = {"service_mode": "call_center_only", "is_active": True}
    res_cc = session.post(f"{BASE_URL}/api/crm/coworker/config/", json=mode_cc_payload)
    assert_test(res_cc.status_code == 200, "Switched tenant mode to 'call_center_only'")
    assert_test(res_cc.json().get("config", {}).get("service_mode") == "call_center_only", "Config confirmed service_mode: call_center_only")

    # 2.2 Switch to Autonomous Digital Coworker Mode with complete configuration
    mode_dc_payload = {
        "service_mode": "digital_coworker",
        "coworker_name": "سارة - الموظف الرقمي الذكي",
        "coworker_role": "مساعد المبيعات وخدمة العملاء الذكي",
        "autonomy_level": "hybrid_supervised",
        "whatsapp_mode": "meta_cloud",
        "telegram_bot_token": "test_bot_token_12345",
        "telegram_manager_chat_id": "987654321",
        "auto_call_followup_enabled": True,
        "auto_whatsapp_followup_enabled": True,
        "proactive_actions_enabled": True,
        "custom_instructions": "أنت موظف ذكي مستقل للشركة، تتعامل بلباقة وسرعة وتطلب الموافقة عند الخصومات.",
        "is_active": True,
        "max_budget_per_day": 75.50,
        "daily_calls_limit": 250,
        "whatsapp_phone_number_id": "phone_id_998877",
        "email_followups_enabled": True
    }
    res_dc = session.post(f"{BASE_URL}/api/crm/coworker/config/", json=mode_dc_payload)
    assert_test(res_dc.status_code == 200, "Switched tenant mode to 'digital_coworker'")
    dc_cfg = res_dc.json().get("config", {})
    assert_test(dc_cfg.get("service_mode") == "digital_coworker", "Verified service_mode: digital_coworker")
    assert_test(dc_cfg.get("coworker_name") == "سارة - الموظف الرقمي الذكي", "Verified coworker_name updated")
    assert_test(dc_cfg.get("auto_call_followup_enabled") is True, "Verified auto_call_followup_enabled is True")
    assert_test(dc_cfg.get("custom_instructions") == mode_dc_payload["custom_instructions"], "Verified custom_instructions persisted to DB")
    assert_test(dc_cfg.get("proactive_actions_enabled") is True, "Verified proactive_actions_enabled is True")
    assert_test(dc_cfg.get("auto_whatsapp_followup_enabled") is True, "Verified auto_whatsapp_followup_enabled is True")
    assert_test(dc_cfg.get("is_active") is True, "Verified is_active is True")
    assert_test(dc_cfg.get("max_budget_per_day") == 75.5, "Verified max_budget_per_day updated to 75.5")
    assert_test(dc_cfg.get("daily_calls_limit") == 250, "Verified daily_calls_limit updated to 250")
    assert_test(dc_cfg.get("whatsapp_phone_number_id") == "phone_id_998877", "Verified whatsapp_phone_number_id persisted and returned")

    # ---------------------------------------------------------------------------------------------------
    # STAGE 3: Phone-First Identity Resolution (Voice & WhatsApp Anchor)
    # ---------------------------------------------------------------------------------------------------
    log_step("3. Phone-First Identity Resolution (E.164 Anchor across Voice & WhatsApp)")

    # Send outbound WhatsApp message to anchor phone
    wa_payload = {
        "recipient_phone": TEST_PHONE,
        "message": "أهلاً بك يا فندم! نسعد بخدمتك ومتابعة طلبك."
    }
    wa_resp = session.post(f"{BASE_URL}/api/crm/whatsapp/send/", json=wa_payload)
    assert_test(wa_resp.status_code == 200, f"WhatsApp send API returns 200 (got {wa_resp.status_code})")
    assert_test(wa_resp.json().get("status") == "success", "WhatsApp message delivered / recorded")

    # Verify CustomerMemory was automatically created or linked
    cust_mem = CustomerMemory.objects.filter(user=user, phone_number=TEST_PHONE).first()
    assert_test(cust_mem is not None, f"CustomerMemory automatically created for anchor {TEST_PHONE}")

    # Verify CustomerChannelIdentifier links WhatsApp channel to same memory
    chan_link = CustomerChannelIdentifier.objects.filter(customer_memory=cust_mem, channel='whatsapp').first()
    assert_test(chan_link is not None, "CustomerChannelIdentifier correctly mapped WhatsApp to CustomerMemory")

    # Verify OmnichannelMessage audit trail has recorded the message
    omni_msg = OmnichannelMessage.objects.filter(user=user, channel='whatsapp', recipient=TEST_PHONE).first()
    assert_test(omni_msg is not None, "OmnichannelMessage audit log recorded outbound WhatsApp communication")

    # ---------------------------------------------------------------------------------------------------
    # STAGE 4: Call Completion & Trinity Event Bridge
    # ---------------------------------------------------------------------------------------------------
    log_step("4. Call Completion & Trinity Post-Call Event Bridge")

    # Prepare Redis subscriber to verify real-time event publishing
    r = redis.Redis.from_url(settings.REDIS_URL)
    pubsub = r.pubsub()
    pubsub.subscribe("trinity:events")
    # Flush queue for clean test
    r.delete("trinity:event_queue")

    test_room = f"room-test-coworker-{int(time.time())}"
    call_complete_payload = {
        "user_id": user.id,
        "room_name": test_room,
        "caller_phone": TEST_PHONE,
        "destination_phone": TEST_PHONE,
        "duration_seconds": 125,
        "summary": "تحدث العميل عن رغبته في شراء الباقة وطلب خصم خاص بنسبة 15% على الفاتورة.",
        "transcript_text": "العميل: هل لديكم خصم إضافي؟ الموظف: سأعرض الأمر على الإدارة فوراً.",
        "direction": "inbound"
    }

    # Internal API call with secret key
    complete_resp = requests.post(
        f"{BASE_URL}/api/crm/internal/complete-call/",
        headers={"X-Internal-API-Key": INTERNAL_API_KEY, "Content-Type": "application/json"},
        json=call_complete_payload
    )
    assert_test(complete_resp.status_code == 200, f"Internal complete-call returned 200 OK (got {complete_resp.status_code})")
    assert_test(complete_resp.json().get("status") == "success", "Call completion marked success")

    # Verify CallSession is persisted
    call_sess = CallSession.objects.filter(room_name=test_room).first()
    assert_test(call_sess is not None, f"CallSession #{call_sess.id} created with room {test_room}")
    assert_test(call_sess.duration_seconds == 125, "Call duration persisted accurately")

    # Verify Trinity Redis Event Queue received the event
    queued_event_bytes = r.lpop("trinity:event_queue")
    assert_test(queued_event_bytes is not None, "Trinity Event Queue ('trinity:event_queue') received call.completed event")
    if queued_event_bytes:
        event_dict = json.loads(queued_event_bytes.decode('utf-8'))
        assert_test(event_dict.get("event") == "call.completed", "Event type is 'call.completed'")
        assert_test(event_dict.get("phone_number") == TEST_PHONE, f"Event phone_number matches {TEST_PHONE}")
        assert_test(event_dict.get("service_mode") == "digital_coworker", "Event service_mode reflects digital_coworker")

    # Verify sensitive trigger keyword 'خصم' automatically spawned an ApprovalRequest
    pending_appr = ApprovalRequest.objects.filter(user=user, customer_memory=cust_mem, status='pending').order_by('-id').first()
    assert_test(pending_appr is not None, f"Approval Gate automatically triggered! Created ApprovalRequest #{pending_appr.id}")
    assert_test(pending_appr.action_type == "post_call_discount_review", "Approval action_type is 'post_call_discount_review'")

    # ---------------------------------------------------------------------------------------------------
    # STAGE 5: Conditional Approval Gate & Telegram Webhook Decision
    # ---------------------------------------------------------------------------------------------------
    log_step("5. Conditional Approval Gate & Telegram Inline Decision Execution")

    # 5.1 Query pending approvals list via REST API
    approvals_resp = session.get(f"{BASE_URL}/api/crm/coworker/approvals/?status=pending")
    assert_test(approvals_resp.status_code == 200, "Approvals list API returned 200 OK")
    appr_list = approvals_resp.json().get("approvals", [])
    assert_test(any(a["id"] == pending_appr.id for a in appr_list), f"Approval #{pending_appr.id} present in pending list")

    # 5.2 Simulate Telegram Inline Button Click Callback
    # Callback data format: "appr:<approval_id>"
    telegram_update_payload = {
        "update_id": 999111,
        "callback_query": {
            "id": "cb_query_12345",
            "from": {"id": 987654321, "first_name": "سيد المدير"},
            "data": f"appr:{pending_appr.id}"
        }
    }
    tg_res = requests.post(
        f"{BASE_URL}/api/crm/telegram/webhook/",
        json=telegram_update_payload
    )
    assert_test(tg_res.status_code == 200, "Telegram Webhook received callback and returned 200 OK")
    assert_test(tg_res.json().get("status") == "ok", "Telegram callback handled successfully")

    # Refresh approval from DB
    pending_appr.refresh_from_db()
    assert_test(pending_appr.status == 'executed', f"Approval #{pending_appr.id} transitioned to 'executed' (got {pending_appr.status})")
    assert_test(pending_appr.execution_result.get("whatsapp_sent") is True, "Automated action executed: WhatsApp discount code sent to customer")
    promo_code = pending_appr.execution_result.get("promo_code")
    assert_test(promo_code is not None and "DISC-" in promo_code, f"Promo code generated: {promo_code}")

    # Verify customer received discount message on WhatsApp audit log
    disc_msg = OmnichannelMessage.objects.filter(
        user=user,
        channel='whatsapp',
        recipient=TEST_PHONE,
        content__icontains=promo_code
    ).first()
    assert_test(disc_msg is not None, "Omnichannel audit log confirms customer received discount coupon via WhatsApp")

    # ---------------------------------------------------------------------------------------------------
    # STAGE 6: Unified Coworker Tool Dispatcher (FastMCP / Trinity Tool Calling)
    # ---------------------------------------------------------------------------------------------------
    log_step("6. Unified Tool Dispatcher (FastMCP / Trinity Call-as-a-Tool)")

    # 6.1 Tool: lookup_customer
    lookup_payload = {
        "tool_name": "lookup_customer",
        "params": {"phone": TEST_PHONE}
    }
    tool_lookup_res = session.post(f"{BASE_URL}/api/crm/coworker/tool/execute/", json=lookup_payload)
    assert_test(tool_lookup_res.status_code == 200, "Tool 'lookup_customer' executed successfully")
    tool_lookup_data = tool_lookup_res.json()
    assert_test(tool_lookup_data.get("customer") is not None, "Customer details returned by lookup tool")
    assert_test(len(tool_lookup_data.get("recent_messages", [])) > 0, "Omnichannel message history returned by lookup tool")

    # 6.2 Tool: send_whatsapp
    tool_wa_payload = {
        "tool_name": "send_whatsapp",
        "params": {
            "destination_phone": TEST_PHONE,
            "message": "تم تأكيد طلبك بنجاح من الموظف الذكي."
        }
    }
    tool_wa_res = session.post(f"{BASE_URL}/api/crm/coworker/tool/execute/", json=tool_wa_payload)
    assert_test(tool_wa_res.status_code == 200 and tool_wa_res.json().get("status") == "success", "Tool 'send_whatsapp' executed successfully")

    # 6.3 Tool: send_email
    tool_email_payload = {
        "tool_name": "send_email",
        "params": {
            "recipient_email": "client@example.com",
            "subject": "ملخص متابعة من الموظف الذكي",
            "body": "نشكركم على التواصل معنا ويسعدنا تقديم العرض المرفق."
        }
    }
    tool_email_res = session.post(f"{BASE_URL}/api/crm/coworker/tool/execute/", json=tool_email_payload)
    assert_test(tool_email_res.status_code == 200 and tool_email_res.json().get("status") == "success", "Tool 'send_email' executed successfully")
    email_logged = OmnichannelMessage.objects.filter(user=user, channel='email', recipient='client@example.com').first()
    assert_test(email_logged is not None, "Email follow-up logged in Omnichannel audit trail")

    # 6.4 Omnichannel Timeline Retrieval
    timeline_res = session.get(f"{BASE_URL}/api/crm/omnichannel/messages/?phone={TEST_PHONE}")
    assert_test(timeline_res.status_code == 200, "Omnichannel timeline endpoint returned 200 OK")
    all_msgs = timeline_res.json().get("messages", [])
    assert_test(len(all_msgs) >= 3, f"Unified timeline has {len(all_msgs)} chronological cross-channel events")

    # ---------------------------------------------------------------------------------------------------
    # STAGE 7: Regression Check (Call Center, Telephony, CRM APIs)
    # ---------------------------------------------------------------------------------------------------
    log_step("7. Regression Check - Verifying Zero Breaking Changes on Existing Call Center")

    # 7.1 Telephony Outbound Gateways
    gw_res = session.get(f"{BASE_URL}/api/telephony/outbound-gateways/")
    assert_test(gw_res.status_code == 200, f"Existing API /api/telephony/outbound-gateways/ returns 200 OK (got {gw_res.status_code})")

    # 7.2 CRM Customers List
    crm_cust_res = session.get(f"{BASE_URL}/api/crm/customers/")
    assert_test(crm_cust_res.status_code == 200, f"Existing API /api/crm/customers/ returns 200 OK (got {crm_cust_res.status_code})")

    # 7.3 CRM Calls History (CDR)
    calls_res = session.get(f"{BASE_URL}/api/crm/calls/")
    assert_test(calls_res.status_code == 200, f"Existing API /api/crm/calls/ returns 200 OK (got {calls_res.status_code})")

    # 7.4 Agent Profiles API
    profiles_res = session.get(f"{BASE_URL}/api/agents/profiles/")
    assert_test(profiles_res.status_code == 200, f"Existing API /api/agents/profiles/ returns 200 OK (got {profiles_res.status_code})")

    # 7.5 Digital Coworker Dashboard Web Page
    coworker_ui_res = session.get(f"{BASE_URL}/coworker/")
    assert_test(coworker_ui_res.status_code == 200, f"Digital Coworker Dashboard page /coworker/ returns 200 OK (got {coworker_ui_res.status_code})")
    assert_test("الموظف الرقمي الذكي" in coworker_ui_res.text, "Verified Coworker Dashboard page HTML rendered with Arabic title")

    # 7.6 Django Admin Registry Verification
    from django.contrib import admin
    assert_test(DigitalCoworkerConfig in admin.site._registry, "Verified DigitalCoworkerConfig registered in Django Admin site")
    assert_test(ApprovalRequest in admin.site._registry, "Verified ApprovalRequest registered in Django Admin site")
    assert_test(CustomerChannelIdentifier in admin.site._registry, "Verified CustomerChannelIdentifier registered in Django Admin site")
    assert_test(OmnichannelMessage in admin.site._registry, "Verified OmnichannelMessage registered in Django Admin site")

    # ---------------------------------------------------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------------------------------------------------
    print(f"\n{BOLD}{GREEN}========================================================================")
    print(f"  ALL END-TO-END TESTS COMPLETED SUCCESSFULLY! ")
    print(f"  Passed Tests: {passed_tests} | Failed Tests: {failed_tests}")
    print(f"========================================================================{RESET}\n")


if __name__ == '__main__':
    try:
        run_all_stages()
    except AssertionError as ae:
        print(f"\n{RED}{BOLD}TEST RUN TERMINATED ON FAILURE: {ae}{RESET}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n{RED}{BOLD}UNEXPECTED EXCEPTION: {e}{RESET}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
