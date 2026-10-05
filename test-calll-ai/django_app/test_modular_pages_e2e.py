"""
End-to-End Test for Complete Modular Multi-Page Architecture:
- Verifies /calls/ renders dedicated page extending base.html.
- Verifies /billing/ renders dedicated page extending base.html.
- Verifies /crm/ renders dedicated page extending base.html.
- Verifies /documents/ renders dedicated page extending base.html.
- Verifies /personas/ renders dedicated page extending base.html.
- Verifies /campaigns/ renders dedicated page extending base.html.
- Verifies /tools/ renders dedicated page extending base.html.
- Verifies /developer/ renders dedicated page extending base.html.
- Verifies /call-center/ renders dedicated page extending base.html.
- Verifies /telephony/ renders dedicated page extending base.html.
- Verifies /partner/ renders dedicated page extending base.html.
- Verifies / renders room.html with updated sidebar navigation links and ?tab= query parameter support.
- Verifies all 12 static JS files (/static/js/common.js, calls.js, billing.js, crm.js, rag.js, personas.js, campaigns.js, store.js, developer.js, callcenter.js, telephony.js, partner.js).
- Verifies unauthenticated users are redirected to /login/.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from django.urls import reverse


def test_modular_pages():
    print("\n========================================================")
    print("🚀 Running Complete Modular Multi-Page Architecture Test")
    print("========================================================")
    
    client = Client()
    test_user, _ = User.objects.get_or_create(username="test_pages_user", defaults={"email": "pages@example.com"})
    test_user.set_password("pass123")
    test_user.save()

    all_modular_endpoints = [
        '/calls/',
        '/billing/',
        '/crm/',
        '/documents/',
        '/personas/',
        '/campaigns/',
        '/tools/',
        '/developer/',
        '/call-center/',
        '/telephony/',
        '/partner/',
    ]

    # 1. Unauthenticated redirects
    print("\n[TEST 1] Testing unauthenticated redirects to /login/...")
    for endpoint in all_modular_endpoints:
        resp = client.get(endpoint)
        assert resp.status_code == 302, f"Expected 302 redirect for {endpoint}, got {resp.status_code}"
        assert '/login/' in resp.url
    print(f"✅ Unauthenticated protection verified on all {len(all_modular_endpoints)} modular routes!")

    client.force_login(test_user)

    # 2. Authenticated access to /calls/
    print("\n[TEST 2] Testing dedicated /calls/ page...")
    resp_calls = client.get('/calls/')
    assert resp_calls.status_code == 200, f"Expected 200, got {resp_calls.status_code}"
    content_calls = resp_calls.content.decode('utf-8')
    assert 'سجل كافة المكالمات (CDR)' in content_calls
    assert 'calls-table-tbody' in content_calls
    assert 'call-detail-modal' in content_calls
    assert 'cdm-recording-section' in content_calls
    assert 'js/calls.js' in content_calls
    assert 'js/common.js' in content_calls
    print("✅ /calls/ page successfully rendered with base layout, CDR table, audio player modal, and calls.js!")

    # 3. Authenticated access to /billing/
    print("\n[TEST 3] Testing dedicated /billing/ page...")
    resp_billing = client.get('/billing/')
    assert resp_billing.status_code == 200, f"Expected 200, got {resp_billing.status_code}"
    content_billing = resp_billing.content.decode('utf-8')
    assert 'حساب الاستخدام والرصيد' in content_billing
    assert 'billing-wallet-balance' in content_billing
    assert 'billing-transactions-tbody' in content_billing
    assert 'topup-modal' in content_billing
    assert 'js/billing.js' in content_billing
    assert 'js/common.js' in content_billing
    print("✅ /billing/ page successfully rendered with base layout, balance cards, top-up modal, and billing.js!")

    # 4. Authenticated access to /crm/
    print("\n[TEST 4] Testing dedicated /crm/ page...")
    resp_crm = client.get('/crm/')
    assert resp_crm.status_code == 200, f"Expected 200, got {resp_crm.status_code}"
    content_crm = resp_crm.content.decode('utf-8')
    assert 'Two-Tier Distilled Memory' in content_crm
    assert 'memory-permanent-content' in content_crm
    assert 'memory-immediate-content' in content_crm
    assert 'memory-recent-calls' in content_crm
    assert 'js/crm.js' in content_crm
    assert 'js/common.js' in content_crm
    print("✅ /crm/ page successfully rendered with customer memory cards, recent calls, and crm.js!")

    # 5. Authenticated access to /documents/ (RAG)
    print("\n[TEST 5] Testing dedicated /documents/ (RAG) page...")
    resp_rag = client.get('/documents/')
    assert resp_rag.status_code == 200, f"Expected 200, got {resp_rag.status_code}"
    content_rag = resp_rag.content.decode('utf-8')
    assert 'RAG Knowledge Base' in content_rag
    assert 'upload-form' in content_rag
    assert 'docs-tbody' in content_rag
    assert 'js/rag.js' in content_rag
    assert 'js/common.js' in content_rag
    print("✅ /documents/ page successfully rendered with upload form, docs table, and rag.js!")

    # 6. Authenticated access to /personas/
    print("\n[TEST 6] Testing dedicated /personas/ page...")
    resp_personas = client.get('/personas/')
    assert resp_personas.status_code == 200, f"Expected 200, got {resp_personas.status_code}"
    content_personas = resp_personas.content.decode('utf-8')
    assert 'الشخصيات المتاحة للمحادثات' in content_personas
    assert 'personas-cards-grid' in content_personas
    assert 'profile-editor-card' in content_personas
    assert 'profile-modal' in content_personas
    assert 'js/personas.js' in content_personas
    assert 'js/common.js' in content_personas
    print("✅ /personas/ page successfully rendered with studio editor, profile modal, and personas.js!")

    # 7. Authenticated access to /campaigns/
    print("\n[TEST 7] Testing dedicated /campaigns/ page...")
    resp_camp = client.get('/campaigns/')
    assert resp_camp.status_code == 200, f"Expected 200, got {resp_camp.status_code}"
    content_camp = resp_camp.content.decode('utf-8')
    assert 'حملات الاتصال وإدارة العملاء' in content_camp
    assert 'camp-contacts-tbody' in content_camp
    assert 'modal-create-campaign' in content_camp
    assert 'modal-contact-details' in content_camp
    assert 'js/campaigns.js' in content_camp
    assert 'js/common.js' in content_camp
    print("✅ /campaigns/ page successfully rendered with contacts table, Inngest stats, modals, and campaigns.js!")

    # 8. Authenticated access to /tools/ (MCP Store)
    print("\n[TEST 8] Testing dedicated /tools/ page...")
    resp_store = client.get('/tools/')
    assert resp_store.status_code == 200, f"Expected 200, got {resp_store.status_code}"
    content_store = resp_store.content.decode('utf-8')
    assert 'خوادم الأدوات الخارجية' in content_store
    assert 'mcp-servers-grid' in content_store
    assert 'mcp-tools-container' in content_store
    assert 'mcp-modal' in content_store
    assert 'js/store.js' in content_store
    assert 'js/common.js' in content_store
    print("✅ /tools/ page successfully rendered with servers grid, discovered tools, modal, and store.js!")

    # 9. Authenticated access to /developer/ (Developer API Portal)
    print("\n[TEST 9] Testing dedicated /developer/ page...")
    resp_dev = client.get('/developer/')
    assert resp_dev.status_code == 200, f"Expected 200, got {resp_dev.status_code}"
    content_dev = resp_dev.content.decode('utf-8')
    assert 'واجهات المطورين المباشرة' in content_dev
    assert 'dev-api-key-input' in content_dev
    assert 'dev-curl-sample' in content_dev
    assert 'Scalar Docs' in content_dev
    assert 'js/developer.js' in content_dev
    assert 'js/common.js' in content_dev
    print("✅ /developer/ page successfully rendered with API key controls, curl samples, and developer.js!")

    # 10. Authenticated access to /call-center/ (Call Center & Queues)
    print("\n[TEST 10] Testing dedicated /call-center/ page...")
    resp_cc = client.get('/call-center/')
    assert resp_cc.status_code == 200, f"Expected 200, got {resp_cc.status_code}"
    content_cc = resp_cc.content.decode('utf-8')
    assert 'المركز الهاتفي وطوابير الانتظار' in content_cc
    assert 'employees-tbody' in content_cc
    assert 'queues-tbody' in content_cc
    assert 'dashboard-active-call-banner' in content_cc
    assert 'new-queue-modal' in content_cc
    assert 'edit-queue-modal' in content_cc
    assert 'new-employee-modal' in content_cc
    assert 'js/callcenter.js' in content_cc
    assert 'js/common.js' in content_cc
    print("✅ /call-center/ page successfully rendered with employees directory, queues routing, modals, and callcenter.js!")

    # 11. Authenticated access to /telephony/ (Telephony & PBX Trunks)
    print("\n[TEST 11] Testing dedicated /telephony/ page...")
    resp_tel = client.get('/telephony/')
    assert resp_tel.status_code == 200, f"Expected 200, got {resp_tel.status_code}"
    content_tel = resp_tel.content.decode('utf-8')
    assert 'إدارة الاتصالات والسنترالات' in content_tel
    assert 'outbound-trunk-form' in content_tel
    assert 'outbound-trunk-badge' in content_tel
    assert 'pbx-trunks-grid' in content_tel
    assert 'ai-call-modal' in content_tel
    assert 'new-pbx-modal' in content_tel
    assert 'issabel-code-modal' in content_tel
    assert 'js/telephony.js' in content_tel
    assert 'js/common.js' in content_tel
    print("✅ /telephony/ page successfully rendered with SIP trunk form, PBX grid, Issabel config modal, and telephony.js!")

    # 12. Authenticated access to /partner/ (Partner & SaaS Portal)
    print("\n[TEST 12] Testing dedicated /partner/ page...")
    resp_partner = client.get('/partner/')
    assert resp_partner.status_code == 200, f"Expected 200, got {resp_partner.status_code}"
    content_partner = resp_partner.content.decode('utf-8')
    assert 'برنامج الشركاء وحلول الـ SaaS' in content_partner
    assert 'partner-kpi-balance' in content_partner
    assert 'partner-code-input' in content_partner
    assert 'partner-api-key-input' in content_partner
    assert 'partner-shared-mcp-select' in content_partner
    assert 'partner-clients-tbody' in content_partner
    assert 'partner-calls-tbody' in content_partner
    assert 'partner-apply-modal' in content_partner
    assert 'partner-cap-modal' in content_partner
    assert 'partner-docs-modal' in content_partner
    assert 'js/partner.js' in content_partner
    assert 'js/common.js' in content_partner
    print("✅ /partner/ page successfully rendered with KPIs, headless API credentials, sub-clients tables, modals, and partner.js!")

    # 13. Main room.html navigation integration
    print("\n[TEST 13] Testing main / (room.html) links and tab param...")
    resp_room = client.get('/')
    assert resp_room.status_code == 200
    content_room = resp_room.content.decode('utf-8')
    for ep in all_modular_endpoints:
        assert ep in content_room, f"Link {ep} missing in room.html"
    assert 'URLSearchParams(window.location.search).get(\'tab\')' in content_room
    print("✅ / (room.html) contains direct links to all dedicated pages and handles ?tab= parameter!")

    # 14. Static files delivery verification
    print("\n[TEST 14] Testing static JS files delivery...")
    static_files = [
        'common.js',
        'calls.js',
        'billing.js',
        'crm.js',
        'rag.js',
        'personas.js',
        'campaigns.js',
        'store.js',
        'developer.js',
        'callcenter.js',
        'telephony.js',
        'partner.js',
    ]
    for sf in static_files:
        resp_sf = client.get(f'/static/js/{sf}')
        assert resp_sf.status_code in [200, 304], f"{sf} status: {resp_sf.status_code}"
        body = b''.join(resp_sf.streaming_content) if hasattr(resp_sf, 'streaming_content') else resp_sf.content
        assert len(body) > 100, f"{sf} file content too short ({len(body)} bytes)"
    print(f"✅ All {len(static_files)} static JS files are properly served with non-empty content!")

    print("\n========================================================")
    print("🎉 ALL 14/14 MODULAR MULTI-PAGE END-TO-END TESTS PASSED! (100%)")
    print("========================================================\n")


if __name__ == '__main__':
    test_modular_pages()
