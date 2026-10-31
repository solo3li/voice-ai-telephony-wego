"""
End-to-End Test for Chatwoot Multi-Tenancy Isolation Architecture:
1. Superuser maps to Chatwoot Account 2.
2. Tenant A registers and accesses /chat/ -> auto-provisions Account A.
3. Tenant B registers and accesses /chat/ -> auto-provisions Account B (Account B != Account A).
4. SSO tokens redirect to /app/accounts/{account_a} and /app/accounts/{account_b} respectively without SuperAdmin fallback.
5. Inboxes created by Tenant A do not appear in Tenant B's channels list.
6. Anti-IDOR: Tenant B is rejected when attempting to update or delete Tenant A's inbox.
7. Employee of Tenant A shares Tenant A's account.
8. RAG document sync isolates to tenant's account_id and assistant_id.
"""
import os
import sys
import json
import urllib.parse
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from voice_assistant.models import TenantChatwootConfig, EmployeeProfile
from voice_assistant.chatwoot_service import (
    get_or_create_tenant_chatwoot,
    generate_chatwoot_sso_url,
    get_all_channels_detailed,
    create_channel_inbox,
    update_channel_inbox,
    delete_channel_inbox,
    get_chatwoot_db_conn
)
from knowledge.models import Document, DocumentChunk
from knowledge.services.chatwoot_sync import sync_document_to_chatwoot, delete_document_from_chatwoot


def run_chatwoot_multitenancy_e2e():
    print("\n========================================================")
    print("🚀 RUNNING COMPLETE CHATWOOT MULTI-TENANCY E2E TEST SUITE")
    print("========================================================")

    # Clean up test users if existing
    User.objects.filter(username__in=[
        'cw_test_admin',
        'cw_tenant_alpha',
        'cw_tenant_beta',
        'cw_emp_alpha'
    ]).delete()

    # 1. SuperAdmin / Superuser Preserves Account 2
    print("\n[TEST 1] Verifying Superuser / Platform Admin maps to Account 2...")
    admin_user = User.objects.create_superuser(
        username='cw_test_admin',
        email='superadmin_test@nexmedia.local',
        password='AdminPassword123!'
    )
    admin_cfg = get_or_create_tenant_chatwoot(admin_user)
    assert admin_cfg is not None, "Failed to get config for superadmin"
    assert admin_cfg.account_id == 2, f"Expected superadmin account_id 2, got {admin_cfg.account_id}"
    assert admin_cfg.chatwoot_user_id == 2, f"Expected superadmin cw user 2, got {admin_cfg.chatwoot_user_id}"

    admin_sso = generate_chatwoot_sso_url(user=admin_user)
    assert "/app/accounts/2" in admin_sso, f"Admin SSO URL should target /app/accounts/2, got: {admin_sso}"
    print(f"✅ SuperAdmin verified: Account ID = {admin_cfg.account_id}, CW User = {admin_cfg.chatwoot_user_id}")

    # 2. Tenant A auto-provisioning
    print("\n[TEST 2] Verifying Tenant A auto-provisioning upon registration / access...")
    tenant_a = User.objects.create_user(
        username='cw_tenant_alpha',
        email='alpha@company-alpha.com',
        password='PasswordAlpha123!',
        first_name='Alpha Corp'
    )
    client_a = Client()
    client_a.force_login(tenant_a)

    resp_a = client_a.get('/chat/')
    assert resp_a.status_code == 200, f"Expected 200 on /chat/, got {resp_a.status_code}"
    
    cfg_a = TenantChatwootConfig.objects.filter(user=tenant_a).first()
    assert cfg_a is not None, "TenantChatwootConfig was not created for Tenant A"
    assert cfg_a.is_provisioned is True, "Tenant A config is not marked provisioned"
    assert cfg_a.account_id != 2, f"Tenant A must not have Account 2! Got {cfg_a.account_id}"
    assert cfg_a.chatwoot_user_id is not None, "Tenant A chatwoot_user_id is None"
    assert cfg_a.assistant_id is not None, "Tenant A assistant_id is None"

    html_a = resp_a.content.decode('utf-8')
    account_a_id = cfg_a.account_id
    assert f"/app/accounts/{account_a_id}" in html_a, f"Expected /app/accounts/{account_a_id} in HTML, got:\n{html_a[:500]}"
    
    sso_api_a = client_a.get('/api/chat/sso-url/').json()
    assert sso_api_a.get('status') == 'success'
    assert f"/app/accounts/{account_a_id}" in sso_api_a['sso_url']
    print(f"✅ Tenant A auto-provisioned: Account #{account_a_id}, CW User #{cfg_a.chatwoot_user_id}, Assistant #{cfg_a.assistant_id}")

    # 3. Tenant B auto-provisioning (Strict isolation from Tenant A)
    print("\n[TEST 3] Verifying Tenant B auto-provisioning (Different Account ID)...")
    tenant_b = User.objects.create_user(
        username='cw_tenant_beta',
        email='beta@company-beta.com',
        password='PasswordBeta123!',
        first_name='Beta Industries'
    )
    client_b = Client()
    client_b.force_login(tenant_b)

    resp_b = client_b.get('/chat/')
    assert resp_b.status_code == 200, f"Expected 200 on /chat/, got {resp_b.status_code}"

    cfg_b = TenantChatwootConfig.objects.filter(user=tenant_b).first()
    assert cfg_b is not None, "TenantChatwootConfig was not created for Tenant B"
    assert cfg_b.is_provisioned is True, "Tenant B config is not marked provisioned"
    assert cfg_b.account_id != 2, f"Tenant B must not have Account 2! Got {cfg_b.account_id}"
    assert cfg_b.account_id != cfg_a.account_id, f"Tenant B ({cfg_b.account_id}) must differ from Tenant A ({cfg_a.account_id})"
    
    account_b_id = cfg_b.account_id
    html_b = resp_b.content.decode('utf-8')
    assert f"/app/accounts/{account_b_id}" in html_b, f"Expected /app/accounts/{account_b_id} in HTML, got:\n{html_b[:500]}"

    sso_api_b = client_b.get('/api/chat/sso-url/').json()
    assert sso_api_b.get('status') == 'success'
    assert f"/app/accounts/{account_b_id}" in sso_api_b['sso_url']
    print(f"✅ Tenant B auto-provisioned: Account #{account_b_id} != Tenant A Account #{account_a_id}")

    # 4. Inboxes isolation: Create channel in Tenant A, verify unseen in Tenant B
    print("\n[TEST 4] Verifying channel/inbox isolation across accounts...")
    create_payload = {
        "channel_type": "web_widget",
        "name": "Alpha Website Chat Widget",
        "website_url": "https://company-alpha.com",
        "widget_color": "#2563eb",
        "welcome_title": "Welcome to Alpha Corp",
        "enable_ai": True
    }
    resp_create = client_a.post(
        '/api/chat/channels/create/',
        data=json.dumps(create_payload),
        content_type='application/json'
    )
    assert resp_create.status_code == 200, f"Failed to create inbox for Tenant A: {resp_create.content}"
    create_data = resp_create.json()
    assert create_data.get('status') == 'success'
    inbox_a_id = create_data['data']['inbox_id']
    print(f"  [+] Created Inbox #{inbox_a_id} for Tenant A (Account #{account_a_id})")

    # Fetch channels for Tenant A
    resp_channels_a = client_a.get('/api/chat/channels/')
    channels_a_data = resp_channels_a.json()
    inbox_ids_a = [ch['id'] for ch in channels_a_data.get('channels', [])]
    assert inbox_a_id in inbox_ids_a, f"Inbox {inbox_a_id} should be visible to Tenant A"

    # Fetch channels for Tenant B
    resp_channels_b = client_b.get('/api/chat/channels/')
    channels_b_data = resp_channels_b.json()
    inbox_ids_b = [ch['id'] for ch in channels_b_data.get('channels', [])]
    assert inbox_a_id not in inbox_ids_b, f"LEAK DETECTED! Tenant A Inbox {inbox_a_id} appeared in Tenant B ({inbox_ids_b})"
    
    # Verify Evolution instances scoping (no leakage of other tenants' instances)
    evo_b = channels_b_data.get('evolution_instances', [])
    for inst in evo_b:
        name = inst.get('name', '')
        assert name.startswith(f"acc{account_b_id}_") or name == 'whatsapp_main', f"Leak in evolution_instances: {name} found in Tenant B"
    print(f"✅ Inbox isolation verified: Inbox #{inbox_a_id} visible in Tenant A, invisible in Tenant B! (Zero instance leakage)")

    # 5. Anti-IDOR Enforcement: Tenant B cannot update, delete, toggle, or view Tenant A / Admin resources
    print("\n[TEST 5] Testing Anti-IDOR enforcement on channels update & delete...")
    # Attempt update by Tenant B on Tenant A's inbox
    resp_idor_update = client_b.post(
        f'/api/chat/channels/{inbox_a_id}/update/',
        data=json.dumps({"name": "Hacked by Tenant B"}),
        content_type='application/json'
    )
    assert resp_idor_update.status_code in (400, 403), f"Expected 400 or 403 on IDOR update, got {resp_idor_update.status_code}"
    print(f"  [+] IDOR Update rejected ({resp_idor_update.status_code})")

    # Attempt delete by Tenant B on Tenant A's inbox
    resp_idor_delete = client_b.post(f'/api/chat/channels/{inbox_a_id}/delete/')
    assert resp_idor_delete.status_code in (400, 403), f"Expected 400 or 403 on IDOR delete, got {resp_idor_delete.status_code}"
    print(f"  [+] IDOR Delete rejected ({resp_idor_delete.status_code})")

    # Attempt AI toggle by Tenant B on Tenant A's inbox
    resp_idor_toggle = client_b.post(
        '/api/chat/channels/toggle-ai/',
        data=json.dumps({"inbox_id": inbox_a_id, "enable": False}),
        content_type='application/json'
    )
    assert resp_idor_toggle.status_code in (400, 403), f"Expected 400 or 403 on IDOR AI toggle, got {resp_idor_toggle.status_code}"
    print(f"  [+] IDOR AI toggle rejected ({resp_idor_toggle.status_code})")

    # Attempt QR code fetch of Superadmin's whatsapp_main by Tenant B
    resp_idor_qr = client_b.get('/api/chat/channels/whatsapp-qr/?instance_name=whatsapp_main')
    assert resp_idor_qr.status_code == 403, f"Expected 403 on IDOR QR on whatsapp_main, got {resp_idor_qr.status_code}"
    print(f"  [+] IDOR WhatsApp QR on whatsapp_main rejected (403)")
    print("✅ Anti-IDOR security checks fully passed!")

    # 6. Employee Mapping: Employee shares Tenant A's account and gets distinct Agent identity
    print("\n[TEST 6] Testing Employee of Tenant A mapping & distinct Agent identity...")
    emp_user = User.objects.create_user(
        username='cw_emp_alpha',
        email='agent1@company-alpha.com',
        password='AgentPassword123!',
        first_name='Agent 101'
    )
    emp_profile = EmployeeProfile.objects.create(
        user=emp_user,
        employer=tenant_a,
        extension='101',
        display_name='Agent One'
    )

    emp_cfg = get_or_create_tenant_chatwoot(emp_user)
    assert emp_cfg.account_id == account_a_id, f"Employee must map to employer's account {account_a_id}, got {emp_cfg.account_id}"

    client_emp = Client()
    client_emp.force_login(emp_user)
    resp_emp = client_emp.get('/chat/')
    assert resp_emp.status_code == 200
    html_emp = resp_emp.content.decode('utf-8')
    assert f"/app/accounts/{account_a_id}" in html_emp, f"Employee HTML should target /app/accounts/{account_a_id}"
    
    sso_api_emp = client_emp.get('/api/chat/sso-url/').json()
    assert sso_api_emp.get('status') == 'success'
    emp_sso_url = sso_api_emp['sso_url']
    assert f"/app/accounts/{account_a_id}" in emp_sso_url
    assert "agent1" in emp_sso_url or "agent1%40company-alpha.com" in emp_sso_url, f"Employee SSO URL must log in as agent, not employer! Got: {emp_sso_url}"

    # Verify Chatwoot DB: Employee exists, is an Agent (role: 0), and is linked to Tenant A's inboxes
    conn = get_chatwoot_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE email = %s", ('agent1@company-alpha.com',))
    emp_cw_row = cur.fetchone()
    assert emp_cw_row is not None, "Employee user was not provisioned in Chatwoot users table"
    emp_cw_id = emp_cw_row[0]

    cur.execute("SELECT role FROM account_users WHERE account_id = %s AND user_id = %s", (account_a_id, emp_cw_id))
    role_row = cur.fetchone()
    assert role_row is not None and role_row[0] == 0, f"Employee must have role 0 (Agent) in account {account_a_id}"

    cur.execute("SELECT count(*) FROM inbox_members WHERE inbox_id = %s AND user_id = %s", (inbox_a_id, emp_cw_id))
    assert cur.fetchone()[0] == 1, f"Employee was not auto-assigned to Tenant A's inbox #{inbox_a_id}"
    conn.close()

    print(f"✅ Employee successfully mapped to Tenant A's Account #{account_a_id} with distinct Agent ID #{emp_cw_id}!")

    # 7. Embedded Suites Isolation
    print("\n[TEST 7] Testing Embedded Chat Hub (/embed/chat-hub/) multi-tenancy...")
    resp_embed_a = client_a.get('/embed/chat-hub/')
    assert resp_embed_a.status_code == 200
    assert f"/app/accounts/{account_a_id}" in resp_embed_a.content.decode('utf-8')

    resp_embed_b = client_b.get('/embed/chat-hub/')
    assert resp_embed_b.status_code == 200
    assert f"/app/accounts/{account_b_id}" in resp_embed_b.content.decode('utf-8')
    print("✅ Embedded Chat Hub properly isolates accounts for both tenants!")

    # 8. RAG Sync Isolation: Document synced by Tenant A belongs to Account A
    print("\n[TEST 8] Testing Knowledge Base (RAG) Document sync multi-tenancy...")
    doc_a = Document.objects.create(
        user=tenant_a,
        title="سياسة شركة ألفا الداخلية",
        file_type="txt",
        file_size=120
    )
    chunk_a = DocumentChunk.objects.create(
        document=doc_a,
        user=tenant_a,
        chunk_index=0,
        content="مواعيد العمل في شركة ألفا تبدأ من 9 صباحاً حتى 5 مساءً.",
        embedding=[0.0] * 768
    )

    sync_document_to_chatwoot(doc_a)

    conn = get_chatwoot_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, account_id, assistant_id FROM captain_documents WHERE metadata->>'django_doc_id' = %s", (str(doc_a.id),))
    row = cur.fetchone()
    assert row is not None, "Synced document not found in captain_documents"
    synced_doc_id, synced_acc_id, synced_ast_id = row[0], row[1], row[2]

    assert synced_acc_id == account_a_id, f"Document should be in Account #{account_a_id}, got {synced_acc_id}"
    assert synced_ast_id == cfg_a.assistant_id, f"Document should be in Assistant #{cfg_a.assistant_id}, got {synced_ast_id}"

    # Verify responses
    cur.execute("SELECT count(*) FROM captain_assistant_responses WHERE documentable_id = %s AND account_id = %s", (synced_doc_id, account_a_id))
    resp_cnt = cur.fetchone()[0]
    assert resp_cnt >= 1, "No captain_assistant_responses inserted for synced doc"

    # Delete document from Chatwoot
    delete_document_from_chatwoot(doc_a.title, doc_a.id, user=tenant_a)
    cur.execute("SELECT count(*) FROM captain_documents WHERE id = %s", (synced_doc_id,))
    assert cur.fetchone()[0] == 0, "Document was not deleted from Chatwoot"
    conn.close()
    print(f"✅ RAG Document sync verified: Stamped with Account #{account_a_id} and Assistant #{cfg_a.assistant_id}!")

    # 9. Channel convenience functions: create_website_channel and create_telegram_channel
    print("\n[TEST 9] Testing convenience channel creation functions...")
    from voice_assistant.chatwoot_service import create_website_channel, create_telegram_channel
    ok_web, msg_web, data_web = create_website_channel({
        "name": "Beta Website Widget",
        "website_url": "https://beta-company.com"
    }, account_id=account_b_id, assistant_id=cfg_b.assistant_id)
    assert ok_web is True, f"create_website_channel failed: {msg_web}"
    inbox_web_id = data_web['inbox_id']
    print(f"  [+] Created Website channel #{inbox_web_id} for Tenant B")

    # 10. Concurrency safety: simultaneous provisioning calls for same tenant
    print("\n[TEST 10] Testing concurrency safety during auto-provisioning...")
    import threading
    concurrent_user = User.objects.create_user(
        username='cw_concurrent_tenant',
        email='concurrent@company-gamma.com',
        password='PasswordGamma123!'
    )
    results = []
    errors = []

    def provision_worker():
        try:
            cfg = get_or_create_tenant_chatwoot(concurrent_user)
            results.append(cfg.account_id)
        except Exception as ex:
            errors.append(ex)

    threads = [threading.Thread(target=provision_worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Concurrency errors occurred: {errors}"
    assert len(set(results)) == 1, f"Different account IDs returned under concurrency: {results}"
    concurrent_acc_id = results[0]
    print(f"✅ Concurrency verified: All 4 parallel threads mapped to single Account #{concurrent_acc_id}!")

    # Cleanup created channels
    client_a.post(f'/api/chat/channels/{inbox_a_id}/delete/')
    client_b.post(f'/api/chat/channels/{inbox_web_id}/delete/')
    concurrent_user.delete()

    print("\n========================================================")
    print("🎉 ALL 10 CHATWOOT MULTI-TENANCY E2E TESTS PASSED 100%!")
    print("========================================================\n")


if __name__ == '__main__':
    run_chatwoot_multitenancy_e2e()
