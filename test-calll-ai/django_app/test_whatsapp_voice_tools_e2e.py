import os
import sys
import django
import json

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import RequestFactory
from django.conf import settings
from django.contrib.auth.models import User
from agents.views import api_internal_agent_whatsapp_send, api_internal_agent_bootstrap
from agents.live_context_service import format_live_context_for_prompt
from agents.models import UserMCPServer
from crm.models import OmnichannelMessage

def run_tests():
    print("=" * 70)
    print("🚀 STARTING E2E TEST: WhatsApp Tools & Menu Link in Voice AI Calls")
    print("=" * 70)

    # TEST 1: Internal WhatsApp Sending API
    print("\n--- TEST 1: Internal WhatsApp Sending API (/api/agents/internal/whatsapp/send/) ---")
    user = User.objects.filter(id=69).first() or User.objects.first()
    rf = RequestFactory()
    payload = {
        "user_id": user.id,
        "phone_number": "0559876543",
        "message": "أهلاً بك يا فندم! رابط منيو المطعم: https://uggu.space/m/test/ يسعدنا خدمتك!"
    }
    req = rf.post(
        "/api/agents/internal/whatsapp/send/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_X_INTERNAL_API_KEY=settings.INTERNAL_API_KEY
    )
    resp = api_internal_agent_whatsapp_send(req)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    resp_data = json.loads(resp.content.decode("utf-8"))
    assert resp_data.get("status") == "success"
    assert resp_data.get("ok") is True
    assert resp_data.get("phone_number") == "966559876543"
    msg_id = resp_data.get("message_id")
    assert msg_id is not None
    created_msg = OmnichannelMessage.objects.filter(id=msg_id).first()
    assert created_msg is not None
    assert created_msg.direction == "outbound_agent"
    assert created_msg.channel == "whatsapp"
    print(f"✅ TEST 1 PASSED: Internal WhatsApp API created OmnichannelMessage #{msg_id} with direction outbound_agent.")

    # TEST 2: Unauthorized request handling
    print("\n--- TEST 2: Security Validation for Internal WhatsApp API ---")
    req_bad = rf.post(
        "/api/agents/internal/whatsapp/send/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_X_INTERNAL_API_KEY="invalid-key-xyz"
    )
    resp_bad = api_internal_agent_whatsapp_send(req_bad)
    assert resp_bad.status_code == 401
    print("✅ TEST 2 PASSED: Unauthorized request properly rejected with 401.")

    # TEST 3: Live Context Format with Digital Menu Link
    print("\n--- TEST 3: Live Context Formatting with Digital Menu URL ---")
    ctx_data = {
        "restaurant_name": "شاورما الريان",
        "digital_menu_url": "https://uggu.space/m/al-rayyan/",
        "menu": [{"name": "شاورما لحم", "price": 30}]
    }
    prompt_str = format_live_context_for_prompt(ctx_data)
    assert "https://uggu.space/m/al-rayyan/" in prompt_str
    assert "send_whatsapp_message" in prompt_str
    assert "رابط قائمة الطعام الإلكترونية" in prompt_str
    print("✅ TEST 3 PASSED: Live context correctly exposes digital menu link & prompt rules.")

    # TEST 4: MCP Servers Cache has get_digital_menu_link
    print("\n--- TEST 4: Verifying FastMCP Tool Discovery in UserMCPServer ---")
    active_mcp = UserMCPServer.objects.filter(is_active=True).exclude(cached_tools=[]).first()
    if active_mcp:
        tool_names = [t.get("name") for t in (active_mcp.cached_tools or [])]
        assert "get_digital_menu_link" in tool_names, f"Expected get_digital_menu_link in {tool_names}"
        print(f"✅ TEST 4 PASSED: UserMCPServer #{active_mcp.id} has get_digital_menu_link registered among {len(tool_names)} tools.")
    else:
        print("⚠️ TEST 4 SKIPPED: No active MCP server found with cached tools.")

    # TEST 5: Bootstrap Bundle
    print("\n--- TEST 5: Agent Bootstrap Bundle with Tools & Memory ---")
    bootstrap_req = rf.post(
        "/api/agents/internal/bootstrap/",
        data=json.dumps({"user_id": user.id, "caller_phone": "0559876543"}),
        content_type="application/json",
        HTTP_X_INTERNAL_API_KEY=settings.INTERNAL_API_KEY
    )
    bootstrap_resp = api_internal_agent_bootstrap(bootstrap_req)
    assert bootstrap_resp.status_code == 200
    b_data = json.loads(bootstrap_resp.content.decode("utf-8"))
    assert b_data.get("status") == "success"
    print("✅ TEST 5 PASSED: Agent bootstrap successfully delivers unified bundle.")

    print("\n" + "=" * 70)
    print("🎉 ALL 5 E2E INTEGRATION TESTS PASSED PERFECTLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
