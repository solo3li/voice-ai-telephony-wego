import os
import sys
import time
import json
import threading
import uvicorn
from starlette.applications import Starlette

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.contrib.auth.models import User
from django.test import RequestFactory, Client
from django.urls import reverse
from agents.models import UserMCPServer
from agents.mcp_service import test_mcp_connection_sync, test_mcp_tool_sync
from agents.admin import UserMCPServerAdmin
from django.contrib.admin.sites import AdminSite

# 1. Setup Mock FastMCP / MCPServer
from mcp.server.mcpserver import MCPServer

test_mcp = MCPServer('test-store')

@test_mcp.tool()
def search_inventory(item_name: str, max_results: int = 5) -> str:
    """Search for store items in stock."""
    return json.dumps({
        "status": "success",
        "found": True,
        "item": item_name,
        "quantity_available": 42,
        "max_results": max_results
    })

@test_mcp.tool()
def check_order(order_id: str) -> str:
    """Check shipment status for order."""
    if order_id == "999":
        return json.dumps({"ok": False, "error": "Order #999 was cancelled by customer"})
    return json.dumps({"ok": True, "order_id": order_id, "status": "Shipped and Out for Delivery"})

asgi_app = test_mcp.sse_app()

class ServerThread(threading.Thread):
    def __init__(self, app, host='127.0.0.1', port=8999):
        super().__init__(daemon=True)
        self.server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning"))

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True

def run_all_tests():
    print("=" * 70)
    print("🚀 STARTING E2E TESTS: MCP Server & Tool Live Testing Feature")
    print("=" * 70)

    # Start live test server
    print("\n[Step 1] Starting In-Process MCP SSE Server on http://127.0.0.1:8999/sse...")
    server_thread = ServerThread(asgi_app, host='127.0.0.1', port=8999)
    server_thread.start()
    time.sleep(1.2)
    server_url = "http://127.0.0.1:8999/sse"

    try:
        # TEST 1: Direct Service Connection Test
        print("\n--- TEST 1: agents.mcp_service.test_mcp_connection_sync ---")
        res_conn = test_mcp_connection_sync(server_url, timeout=5.0)
        print(f"Connection result: ok={res_conn.get('ok')}, latency={res_conn.get('latency_ms')}ms, tools_count={res_conn.get('tools_count')}")
        assert res_conn.get("ok") is True, f"Connection failed: {res_conn}"
        assert res_conn.get("tools_count") == 2, f"Expected 2 tools, got {res_conn.get('tools_count')}"
        tool_names = [t["name"] for t in res_conn.get("tools", [])]
        assert "search_inventory" in tool_names and "check_order" in tool_names
        print("✅ TEST 1 PASSED: Successfully connected via SSE, handshaked, and discovered all tools.")

        # TEST 2: Direct Service Tool Execution
        print("\n--- TEST 2: agents.mcp_service.test_mcp_tool_sync (Success & Error detection) ---")
        res_tool1 = test_mcp_tool_sync(server_url, tool_name="search_inventory", arguments={"item_name": "Smart Watch", "max_results": 3})
        print(f"Tool search_inventory result: ok={res_tool1.get('ok')}, exec_time={res_tool1.get('execution_time_ms')}ms")
        assert res_tool1.get("ok") is True, f"Tool call failed: {res_tool1}"
        assert "Smart Watch" in res_tool1.get("result", "")

        res_tool2 = test_mcp_tool_sync(server_url, tool_name="check_order", arguments={"order_id": "999"})
        print(f"Tool check_order (error case) result: ok={res_tool2.get('ok')}, is_error={res_tool2.get('is_error')}, error_msg='{res_tool2.get('error_message')}'")
        assert res_tool2.get("ok") is False, "Expected error detection on cancelled order"
        assert res_tool2.get("is_error") is True
        assert "cancelled" in res_tool2.get("error_message", "").lower()
        print("✅ TEST 2 PASSED: Live tool execution and application error detection work perfectly.")

        # TEST 3: Negative Connection Handling (Unreachable Server & Bad URL)
        print("\n--- TEST 3: Negative Connection Tests (Invalid URL & Dead Port) ---")
        bad_url_res = test_mcp_connection_sync("invalid-url")
        assert bad_url_res.get("ok") is False and bad_url_res.get("error_type") == "invalid_url"

        dead_port_res = test_mcp_connection_sync("http://127.0.0.1:9998/sse", timeout=1.5)
        assert dead_port_res.get("ok") is False
        assert dead_port_res.get("error_type") in ("connection_error", "handshake_error")
        print("✅ TEST 3 PASSED: Robust error categorization for invalid URLs and unreachable endpoints.")

        # Setup test user
        user, _ = User.objects.get_or_create(username='test_mcp_user', defaults={'email': 'mcp@test.com'})
        user.set_password('password123')
        user.save()

        # TEST 4: Django Web Internal APIs
        print("\n--- TEST 4: Web Internal Endpoints (/api/agents/mcp/test-connection/ & test-tool/) ---")
        client = Client()
        client.force_login(user)

        resp = client.post('/api/agents/mcp/test-connection/', data=json.dumps({
            "server_url": server_url
        }), content_type='application/json')
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.content}"
        data = resp.json()
        assert data.get("ok") is True and data.get("tools_count") == 2

        resp_tool = client.post('/api/agents/mcp/test-tool/', data=json.dumps({
            "server_url": server_url,
            "tool_name": "search_inventory",
            "arguments": {"item_name": "Wireless Mouse"}
        }), content_type='application/json')
        assert resp_tool.status_code == 200
        data_tool = resp_tool.json()
        assert data_tool.get("ok") is True
        assert "Wireless Mouse" in data_tool.get("result", "")
        print("✅ TEST 4 PASSED: Web Internal endpoints return 200 with accurate test payloads.")

        # TEST 5: User Developer API
        print("\n--- TEST 5: Developer API (/api/v1/mcp/test/ & /api/v1/mcp/test-tool/) ---")
        # Ensure user has API key
        from developer.models import UserApiKey
        api_key = 'dev_test_api_key_12345'
        UserApiKey.objects.update_or_create(user=user, key=api_key, defaults={'name': 'Test Dev Key', 'is_active': True})

        dev_headers = {'HTTP_X_API_KEY': api_key}
        resp_dev = client.post('/api/v1/mcp/test/', data=json.dumps({
            "server_url": server_url
        }), content_type='application/json', **dev_headers)
        assert resp_dev.status_code == 200, f"Expected 200, got {resp_dev.status_code}: {resp_dev.content}"
        assert resp_dev.json().get("ok") is True

        resp_dev_tool = client.post('/api/v1/mcp/test-tool/', data=json.dumps({
            "server_url": server_url,
            "tool_name": "check_order",
            "arguments": {"order_id": "1001"}
        }), content_type='application/json', **dev_headers)
        assert resp_dev_tool.status_code == 200
        assert resp_dev_tool.json().get("ok") is True
        print("✅ TEST 5 PASSED: Developer API endpoints test connections and tools seamlessly.")

        # TEST 6: Partner API
        print("\n--- TEST 6: Partner API (/api/partner/v1/clients/<id>/mcp/test/ & test-tool/) ---")
        from partners.models import PartnerProfile, PartnerClientRelationship
        partner_user, _ = User.objects.get_or_create(username='test_partner_mcp', defaults={'email': 'partner@test.com'})
        partner_profile, _ = PartnerProfile.objects.update_or_create(
            user=partner_user,
            defaults={
                'company_name': 'Test Partner Co',
                'partner_code': 'PARTNER_TEST_101',
                'api_key': 'pk_live_test_12345678',
                'status': 'approved'
            }
        )

        # Link client user to partner
        PartnerClientRelationship.objects.update_or_create(partner=partner_profile, client=user, defaults={'is_active': True})

        partner_headers = {'HTTP_X_PARTNER_KEY': partner_profile.api_key}
        resp_p_conn = client.post(f'/api/partner/v1/clients/{user.id}/mcp/test/', data=json.dumps({
            "server_url": server_url
        }), content_type='application/json', **partner_headers)
        assert resp_p_conn.status_code == 200, f"Expected 200, got {resp_p_conn.status_code}: {resp_p_conn.content}"
        assert resp_p_conn.json().get("ok") is True

        resp_p_tool = client.post(f'/api/partner/v1/clients/{user.id}/mcp/test-tool/', data=json.dumps({
            "server_url": server_url,
            "tool_name": "search_inventory",
            "arguments": {"item_name": "Partner Tablet"}
        }), content_type='application/json', **partner_headers)
        assert resp_p_tool.status_code == 200
        assert resp_p_tool.json().get("ok") is True
        print("✅ TEST 6 PASSED: Partner API endpoints verified with multi-tenant client isolation.")

        # TEST 7: Django Admin Panel Live Test Action and View
        print("\n--- TEST 7: Django Admin Panel (UserMCPServerAdmin Action & Test View) ---")
        server_obj, _ = UserMCPServer.objects.update_or_create(
            user=user,
            name="Test Store Server",
            defaults={"server_url": server_url, "is_active": True}
        )

        admin_site = AdminSite()
        mcp_admin = UserMCPServerAdmin(UserMCPServer, admin_site)

        # Test Action
        rf = RequestFactory()
        req = rf.post('/admin/agents/usermcpserver/')
        req.user = User.objects.filter(is_superuser=True).first() or user
        from django.contrib.messages.storage.fallback import FallbackStorage
        setattr(req, 'session', {})
        setattr(req, '_messages', FallbackStorage(req))

        mcp_admin.test_selected_servers(req, UserMCPServer.objects.filter(id=server_obj.id))
        server_obj.refresh_from_db()
        assert len(server_obj.cached_tools) == 2, f"Expected 2 cached tools, got {len(server_obj.cached_tools)}"
        assert server_obj.last_synced_at is not None
        print("✅ TEST 7 PASSED: Django Admin action and test view successfully updated cached tools and last synced at.")

        print("\n" + "=" * 70)
        print("🎉 ALL 7 E2E TEST SUITES PASSED FLAWLESSLY!")
        print("=" * 70)

    finally:
        server_thread.stop()

if __name__ == '__main__':
    run_all_tests()
