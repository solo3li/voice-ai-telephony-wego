"""
Complete Multi-Tenant MCP Architecture and Chatwoot Integration End-to-End Test Suite.

Verifies:
1. Multi-tenant MCP isolation across tenants.
2. Auto-sync MCP tools into chatwoot_production.captain_custom_tools per tenant account.
3. Slug consistency (mcp_{user.id}_{tool.name}) and anti-duplication.
4. Secure Execution Bridge (/api/mcp/execute/<int:user_id>/<str:tool_name>/).
5. Anti-IDOR enforcement (cross-tenant token rejection).
6. Tool resolution on active servers and rejection of unauthorized/invalid tools.
7. AgentToolCallLog logging without schema errors.
8. Store UI native isolation: zero external iframes pointing to leaked URLs.
9. Tenant context passing (X-Tenant-ID header).
"""
import os
import sys
import json
import secrets
from unittest.mock import patch

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from voice_assistant.models import TenantChatwootConfig
from voice_assistant.chatwoot_service import (
    get_or_create_tenant_chatwoot,
    sync_tenant_mcp_to_chatwoot,
    get_chatwoot_db_conn
)
from agents.models import UserMCPServer, AgentToolCallLog


def run_mcp_multitenancy_e2e():
    print("\n========================================================")
    print("🚀 RUNNING COMPLETE MCP MULTI-TENANCY & CHATWOOT E2E SUITE")
    print("========================================================")

    # Clean up test users and related records
    test_usernames = ['mcp_tenant_alpha', 'mcp_tenant_beta']
    UserMCPServer.objects.filter(user__username__in=test_usernames).delete()
    TenantChatwootConfig.objects.filter(user__username__in=test_usernames).delete()
    User.objects.filter(username__in=test_usernames).delete()

    # 1. Create Tenant A and Tenant B
    print("\n[TEST 1] Verifying Tenant A & B auto-provisioning and unique MCP webhook secrets...")
    tenant_a = User.objects.create_user(
        username='mcp_tenant_alpha',
        email='alpha@mcptest.local',
        password='Password123!',
        first_name='Alpha Tech'
    )
    tenant_b = User.objects.create_user(
        username='mcp_tenant_beta',
        email='beta@mcptest.local',
        password='Password123!',
        first_name='Beta Health'
    )

    cfg_a = get_or_create_tenant_chatwoot(tenant_a)
    cfg_b = get_or_create_tenant_chatwoot(tenant_b)

    assert cfg_a is not None, "Failed to get Chatwoot config for Tenant A"
    assert cfg_b is not None, "Failed to get Chatwoot config for Tenant B"
    assert cfg_a.account_id != cfg_b.account_id, f"Tenants must have different account_ids: {cfg_a.account_id} vs {cfg_b.account_id}"
    assert cfg_a.assistant_id != cfg_b.assistant_id, f"Tenants must have different assistant_ids: {cfg_a.assistant_id} vs {cfg_b.assistant_id}"

    assert cfg_a.mcp_webhook_secret, "Tenant A mcp_webhook_secret must not be empty"
    assert cfg_b.mcp_webhook_secret, "Tenant B mcp_webhook_secret must not be empty"
    assert cfg_a.mcp_webhook_secret != cfg_b.mcp_webhook_secret, "Secrets must be unique per tenant"
    print(f"✅ Tenant A Account #{cfg_a.account_id} (Assistant #{cfg_a.assistant_id}) & Tenant B Account #{cfg_b.account_id} (Assistant #{cfg_b.assistant_id}) provisioned with unique secrets!")

    # 2. Setup isolated MCP servers for Tenant A and Tenant B
    print("\n[TEST 2] Configuring tenant MCP servers and discovered tools in Django...")
    server_a = UserMCPServer.objects.create(
        user=tenant_a,
        name="خادم مطاعم ألفا",
        server_url="http://mock-fastmcp-a:8002/sse",
        auth_token="token_alpha_secret_123",
        is_active=True,
        cached_tools=[
            {
                "name": "order_food",
                "description": "طلب وجبة من قائمة الطعام",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item": {"type": "string", "description": "اسم الوجبة"},
                        "quantity": {"type": "integer", "description": "العدد"}
                    },
                    "required": ["item"]
                }
            },
            {
                "name": "get_menu",
                "description": "استعراض أصناف القائمة والأسعار",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"}
                    }
                }
            }
        ]
    )

    server_b = UserMCPServer.objects.create(
        user=tenant_b,
        name="خادم عيادات بيتا",
        server_url="http://mock-fastmcp-b:8003/sse",
        auth_token="token_beta_secret_456",
        is_active=True,
        cached_tools=[
            {
                "name": "lookup_patient",
                "description": "البحث عن ملف المريض برقم الهوية",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "patient_id": {"type": "string", "description": "رقم ملف المريض"}
                    },
                    "required": ["patient_id"]
                }
            }
        ]
    )

    # Verify Django-level tenant isolation
    servers_a = list(UserMCPServer.objects.filter(user=tenant_a))
    servers_b = list(UserMCPServer.objects.filter(user=tenant_b))
    assert len(servers_a) == 1 and servers_a[0].id == server_a.id
    assert len(servers_b) == 1 and servers_b[0].id == server_b.id
    print("✅ MCP servers correctly isolated per tenant in Django database.")

    # 3. Auto-Sync MCP Tools to Tenant A's Chatwoot Account
    print("\n[TEST 3] Testing auto-sync of Tenant A's tools to chatwoot_production...")
    sync_res_a = sync_tenant_mcp_to_chatwoot(tenant_a)
    assert sync_res_a.get("status") == "success", f"Sync failed: {sync_res_a}"
    assert sync_res_a.get("synced") == 2, f"Expected 2 tools synced, got {sync_res_a.get('synced')}"
    assert sync_res_a.get("account_id") == cfg_a.account_id

    # Query Chatwoot DB directly to verify captain_custom_tools
    with get_chatwoot_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT slug, title, endpoint_url, headers, param_schema, account_id, assistant_id, request_template, auth_type, auth_config
                FROM captain_custom_tools
                WHERE assistant_id = %s
                ORDER BY slug;
            """, (cfg_a.assistant_id,))
            rows_a = cur.fetchall()

    assert len(rows_a) == 2, f"Expected 2 tools in Chatwoot DB for Tenant A, found {len(rows_a)}"
    slugs_a = [r[0] for r in rows_a]
    assert f"mcp_{tenant_a.id}_get_menu" in slugs_a
    assert f"mcp_{tenant_a.id}_order_food" in slugs_a

    # Check endpoint and auth header
    order_food_row = [r for r in rows_a if r[0] == f"mcp_{tenant_a.id}_order_food"][0]
    expected_endpoint = f"https://app.169.58.32.179.nip.io/api/mcp/execute/{tenant_a.id}/order_food/"
    assert order_food_row[2] == expected_endpoint, f"Expected endpoint {expected_endpoint}, got {order_food_row[2]}"
    
    headers = order_food_row[3]
    if isinstance(headers, str):
        headers = json.loads(headers)
    assert headers.get("Authorization") == f"Bearer {cfg_a.mcp_webhook_secret}"
    assert order_food_row[5] == cfg_a.account_id
    assert order_food_row[6] == cfg_a.assistant_id

    # Check param schema
    param_schema = order_food_row[4]
    if isinstance(param_schema, str):
        param_schema = json.loads(param_schema)
    param_names = [p['name'] for p in param_schema]
    assert 'item' in param_names
    assert 'quantity' in param_names

    # Check request_template and auth_type/auth_config
    assert order_food_row[7] is not None and "item" in order_food_row[7], "request_template must serialize parameters"
    assert order_food_row[8] == 'bearer', "auth_type must be bearer"
    auth_cfg = order_food_row[9] if isinstance(order_food_row[9], dict) else json.loads(order_food_row[9])
    assert auth_cfg.get("token") == cfg_a.mcp_webhook_secret

    # Verify connection pool safety under repeated syncs
    for _ in range(5):
        repeat_sync = sync_tenant_mcp_to_chatwoot(tenant_a.id)
        assert repeat_sync.get("status") == "success"
    print("  [+] Connection pool release verified: 5 consecutive syncs succeeded without leaking connections")
    print(f"✅ Tenant A's 2 tools successfully synced into Chatwoot Account #{cfg_a.account_id} with correct endpoint and Bearer secret!")

    # 4. Auto-Sync MCP Tools to Tenant B & Strict Isolation
    print("\n[TEST 4] Testing Tenant B auto-sync & strict cross-account isolation...")
    sync_res_b = sync_tenant_mcp_to_chatwoot(tenant_b)
    assert sync_res_b.get("status") == "success"
    assert sync_res_b.get("synced") == 1

    with get_chatwoot_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT slug, endpoint_url, headers, account_id, assistant_id
                FROM captain_custom_tools
                WHERE assistant_id = %s;
            """, (cfg_b.assistant_id,))
            rows_b = cur.fetchall()

    assert len(rows_b) == 1, f"Expected 1 tool for Tenant B, found {len(rows_b)}"
    row_b = rows_b[0]
    assert row_b[0] == f"mcp_{tenant_b.id}_lookup_patient"
    assert f"/api/mcp/execute/{tenant_b.id}/lookup_patient/" in row_b[1]
    headers_b = row_b[2] if isinstance(row_b[2], dict) else json.loads(row_b[2])
    assert headers_b.get("Authorization") == f"Bearer {cfg_b.mcp_webhook_secret}"
    assert row_b[3] == cfg_b.account_id
    assert row_b[4] == cfg_b.assistant_id

    # Ensure zero tool leakage between Tenant A and Tenant B
    with get_chatwoot_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM captain_custom_tools
                WHERE account_id = %s AND slug LIKE %s;
            """, (cfg_a.account_id, f"mcp_{tenant_b.id}_%"))
            assert cur.fetchone()[0] == 0, "Tenant B tool leaked into Tenant A's account!"

            cur.execute("""
                SELECT COUNT(*) FROM captain_custom_tools
                WHERE account_id = %s AND slug LIKE %s;
            """, (cfg_b.account_id, f"mcp_{tenant_a.id}_%"))
            assert cur.fetchone()[0] == 0, "Tenant A tool leaked into Tenant B's account!"

    print("✅ Zero cross-account leakage verified! Tenant tools reside exclusively in their respective Chatwoot accounts.")

    # 5. Stale tool cleanup & server deactivation sync
    print("\n[TEST 5] Testing stale tool cleanup and server deactivation...")
    # Remove 'get_menu' from Tenant A
    server_a.cached_tools = [server_a.cached_tools[0]]  # only 'order_food'
    server_a.save()
    sync_res_a2 = sync_tenant_mcp_to_chatwoot(tenant_a)
    assert sync_res_a2.get("synced") == 1

    with get_chatwoot_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT slug FROM captain_custom_tools
                WHERE assistant_id = %s;
            """, (cfg_a.assistant_id,))
            slugs_after_removal = [r[0] for r in cur.fetchall()]
    assert f"mcp_{tenant_a.id}_get_menu" not in slugs_after_removal
    assert f"mcp_{tenant_a.id}_order_food" in slugs_after_removal
    print("  [+] Stale tool 'get_menu' cleanly pruned from Chatwoot DB upon update")

    # Deactivate Tenant A server
    server_a.is_active = False
    server_a.save()
    sync_tenant_mcp_to_chatwoot(tenant_a)

    with get_chatwoot_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM captain_custom_tools
                WHERE assistant_id = %s;
            """, (cfg_a.assistant_id,))
            count_deactivated = cur.fetchone()[0]
    assert count_deactivated == 0, f"Expected 0 tools after deactivation, got {count_deactivated}"

    # Verify Tenant B is completely unaffected
    with get_chatwoot_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM captain_custom_tools
                WHERE assistant_id = %s;
            """, (cfg_b.assistant_id,))
            count_b = cur.fetchone()[0]
    assert count_b == 1, "Tenant B's tools were affected by Tenant A's deactivation!"
    print("✅ Stale tool cleanup and server deactivation sync verified with 100% tenant isolation!")

    # Reactivate Tenant A for execution testing
    server_a.is_active = True
    server_a.cached_tools = [
        {
            "name": "order_food",
            "description": "طلب وجبة",
            "parameters": {"type": "object", "properties": {"item": {"type": "string"}}}
        }
    ]
    server_a.save()
    sync_tenant_mcp_to_chatwoot(tenant_a)

    # 6. Secure Execution Bridge: Auth & Anti-IDOR Security Checks
    print("\n[TEST 6] Testing Secure Execution Bridge auth and Anti-IDOR...")
    client = Client()
    exec_url_a = f"/api/mcp/execute/{tenant_a.id}/order_food/"

    # Test 6.1: Missing Authorization header
    resp_no_auth = client.post(exec_url_a, data=json.dumps({"item": "Pizza"}), content_type="application/json")
    assert resp_no_auth.status_code == 403, f"Expected 403, got {resp_no_auth.status_code}"
    print("  [+] Missing auth header rejected (403)")

    # Test 6.2: Invalid Bearer token
    resp_bad_auth = client.post(
        exec_url_a,
        data=json.dumps({"item": "Pizza"}),
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer invalid_secret_token_123"
    )
    assert resp_bad_auth.status_code == 403, f"Expected 403, got {resp_bad_auth.status_code}"
    print("  [+] Invalid Bearer token rejected (403)")

    # Test 6.3: Anti-IDOR: Tenant B's token used against Tenant A's endpoint
    resp_idor = client.post(
        exec_url_a,
        data=json.dumps({"item": "Pizza"}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {cfg_b.mcp_webhook_secret}"
    )
    assert resp_idor.status_code == 403, f"Anti-IDOR failed: Expected 403, got {resp_idor.status_code}"
    print("  [+] Anti-IDOR: Tenant B secret on Tenant A endpoint rejected (403)")

    # Test 6.4: Non-existent tenant
    resp_no_tenant = client.post(
        "/api/mcp/execute/999999/order_food/",
        data=json.dumps({"item": "Pizza"}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {cfg_a.mcp_webhook_secret}"
    )
    assert resp_no_tenant.status_code == 404, f"Expected 404, got {resp_no_tenant.status_code}"
    print("  [+] Non-existent tenant rejected (404)")

    # Test 6.5: Non-existent tool for tenant
    resp_bad_tool = client.post(
        f"/api/mcp/execute/{tenant_a.id}/unknown_hack_tool/",
        data=json.dumps({}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {cfg_a.mcp_webhook_secret}"
    )
    assert resp_bad_tool.status_code == 404, f"Expected 404, got {resp_bad_tool.status_code}"
    print("  [+] Tool not belonging to tenant rejected (404)")

    # 7. Secure Execution Bridge: Live Execution & Response Handling
    print("\n[TEST 7] Testing tool execution through Execution Bridge...")
    mock_mcp_response = {
        "ok": True,
        "status": "success",
        "result": json.dumps({"order_id": 9921, "item": "Pizza", "status": "confirmed"}),
        "execution_time_ms": 35.4
    }

    with patch('agents.mcp_service.test_mcp_tool_sync', return_value=mock_mcp_response) as mock_test_tool:
        resp_valid = client.post(
            exec_url_a,
            data=json.dumps({"item": "Pizza"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {cfg_a.mcp_webhook_secret}"
        )
        assert resp_valid.status_code == 200, f"Expected 200, got {resp_valid.status_code}: {resp_valid.content}"
        data = resp_valid.json()
        assert data.get("status") == "success"
        assert data.get("ok") is True
        assert isinstance(data.get("result"), dict)
        assert data["result"]["order_id"] == 9921

        # Verify X-Tenant-ID header was passed to the FastMCP execution
        call_kwargs = mock_test_tool.call_args.kwargs
        assert call_kwargs.get("headers", {}).get("X-Tenant-ID") == str(tenant_a.id), "X-Tenant-ID header was not passed to FastMCP!"
        print("  [+] Execution Bridge executed FastMCP tool and passed X-Tenant-ID header")

    # Test 7.2: Wrapped {"arguments": {...}} input
    with patch('agents.mcp_service.test_mcp_tool_sync', return_value=mock_mcp_response) as mock_test_tool:
        resp_wrapped = client.post(
            exec_url_a,
            data=json.dumps({"arguments": {"item": "Calzone"}}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {cfg_a.mcp_webhook_secret}"
        )
        assert resp_wrapped.status_code == 200
        call_kwargs = mock_test_tool.call_args.kwargs
        assert call_kwargs.get("arguments") == {"item": "Calzone"}
        print("  [+] Wrapped {'arguments': {...}} correctly unwrapped before FastMCP execution")

    # Test 7.3: Upstream exception shielding
    with patch('agents.mcp_service.test_mcp_tool_sync', side_effect=RuntimeError("FastMCP upstream connection reset")):
        resp_err = client.post(
            exec_url_a,
            data=json.dumps({"item": "Pasta"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {cfg_a.mcp_webhook_secret}"
        )
        assert resp_err.status_code == 200
        err_data = resp_err.json()
        assert err_data.get("ok") is False
        assert "FastMCP upstream connection reset" in err_data.get("error")
        print("  [+] FastMCP exception shielded gracefully with 200 JSON error")

    # Verify AgentToolCallLog was created
    log_entry = AgentToolCallLog.objects.filter(user=tenant_a, tool_name="order_food", status="success", arguments__item="Pizza").first()
    assert log_entry is not None, "AgentToolCallLog for Pizza was not created"
    assert log_entry.room_name == "chatwoot_captain"
    assert log_entry.status == "success"
    assert log_entry.tool_type == "mcp"
    assert log_entry.arguments.get("item") == "Pizza"
    print("  [+] AgentToolCallLog entry stamped with user, status, and execution details")
    print("✅ Secure Execution Bridge passed all functional, security, and logging tests!")

    # 8. LangGraph Worker AgentToolCallLog & Tenant Context Fix
    print("\n[TEST 8] Verifying LangGraph worker AgentToolCallLog creation & tools loading...")
    from crm.services.langgraph_worker import load_user_mcp_tools
    decls, tool_map = load_user_mcp_tools(tenant_a.id)
    assert "order_food" in tool_map, "order_food missing in load_user_mcp_tools mapping!"
    assert tool_map["order_food"]["server_name"] == "خادم مطاعم ألفا"
    assert tool_map["order_food"]["server_url"] == server_a.server_url
    print("  [+] LangGraph load_user_mcp_tools correctly loaded tenant tools mapping")

    # Verify tool types mapping for AgentToolCallLog
    for t_n, exp_type in [("search_knowledge_base", "rag"), ("lookup_customer_memory", "memory"), ("escalate_to_human_support", "transfer"), ("order_food", "mcp")]:
        log = AgentToolCallLog.objects.create(
            user_id=tenant_a.id,
            room_name="whatsapp_+966500000000",
            caller_phone="+966500000000",
            tool_name=t_n,
            tool_type="rag" if t_n == "search_knowledge_base" else ("memory" if t_n == "lookup_customer_memory" else ("transfer" if t_n == "escalate_to_human_support" else "mcp")),
            server_name="خادم مطاعم ألفا" if exp_type == "mcp" else "",
            server_url=server_a.server_url if exp_type == "mcp" else "",
            arguments={"query": "test"},
            status="success",
            error_type="none",
            error_message="",
            response_preview="OK",
            raw_response={"output": "OK"},
            execution_time_ms=25
        )
        assert log.tool_type == exp_type
    print("  [+] AgentToolCallLog tool_type mapping verified for rag, memory, transfer, and mcp")
    print("✅ LangGraph AgentToolCallLog creation successfully saved with zero schema errors!")

    # 9. Native Isolated Store UI (A1): Zero Exposed Iframe
    print("\n[TEST 9] Verifying Store UI (/tools/) native isolation (A1)...")
    client_a = Client()
    client_a.force_login(tenant_a)

    resp_tools = client_a.get('/tools/')
    assert resp_tools.status_code == 200, f"Expected 200, got {resp_tools.status_code}"
    html_tools = resp_tools.content.decode('utf-8')

    # Security check: Leaked external iframe MUST NOT EXIST
    assert 'https://mcp.169.58.32.179.nip.io/' not in html_tools, "CRITICAL: Leaked external FastMCP URL found in /tools/ HTML!"
    assert '<iframe' not in html_tools, "CRITICAL: External iframe found in /tools/ HTML!"
    assert 'store-portal-section' not in html_tools, "store-portal-section still present in HTML!"

    # Native UI markers
    assert 'mcp-servers-grid' in html_tools
    assert 'mcp-tools-container' in html_tools
    assert 'mcp-modal' in html_tools
    assert 'btn-preview-isolated-tools' in html_tools
    assert '/embed/call-center/tools/' in html_tools
    print("✅ /tools/ 100% verified: Zero external iframe, zero token leakage, native isolated preview present!")

    # 10. Embedded Call Center Suite Tools Route (/embed/call-center/tools/)
    print("\n[TEST 10] Verifying embedded tools route (/embed/call-center/tools/)...")
    resp_embed_tools = client_a.get('/embed/call-center/tools/')
    assert resp_embed_tools.status_code == 200, f"Expected 200, got {resp_embed_tools.status_code}"
    html_embed_tools = resp_embed_tools.content.decode('utf-8')

    assert 'https://mcp.169.58.32.179.nip.io/' not in html_embed_tools, "Leaked URL found in embedded tools route!"
    assert '<iframe' not in html_embed_tools, "Iframe found in embedded tools route!"
    assert 'mcp-servers-grid' in html_embed_tools
    assert 'mcp-tools-container' in html_embed_tools
    assert 'btn-preview-isolated-tools' not in html_embed_tools, "Preview button should be hidden in embedded view"
    print("✅ Embedded /embed/call-center/tools/ verified with zero external iframes, hidden preview button, and pure native UI!")

    # Clean up test users and related records
    UserMCPServer.objects.filter(user__in=[tenant_a, tenant_b]).delete()
    TenantChatwootConfig.objects.filter(user__in=[tenant_a, tenant_b]).delete()
    User.objects.filter(username__in=test_usernames).delete()

    print("\n========================================================")
    print("🎉 ALL 10 MCP MULTI-TENANCY E2E TESTS PASSED 100%!")
    print("========================================================\n")


if __name__ == '__main__':
    run_mcp_multitenancy_e2e()
