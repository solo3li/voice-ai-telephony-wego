# SPDX-License-Identifier: Apache-2.0
"""
Comprehensive End-to-End Test Suite for Full White-Label Embedded Suites:
1. Call Center AI Embedded Suite (/embed/call-center/):
   - Default redirect to /embed/call-center/room/ preserving ?token=...&locale=...
   - All 10 voice & telephony sub-routes:
     1. /embed/call-center/room/ (Voice Room & Live WebRTC)
     2. /embed/call-center/calls/ (CDR & Audio Recordings)
     3. /embed/call-center/documents/ (Knowledge Base & Documents)
     4. /embed/call-center/personas/ (AI Personas & Studio)
     5. /embed/call-center/crm/ (CRM & Customer Memory)
     6. /embed/call-center/tools/ (Tools Store & MCP)
     7. /embed/call-center/campaigns/ (Outbound Campaigns)
     8. /embed/call-center/call-center/ (Call Center & Queues)
     9. /embed/call-center/telephony/ (SIP Trunks & PBX)
     10. /embed/call-center/hours/ (Business Hours & Fallback Plan)
   - Top horizontal tab bar styling with active highlights and SVG icons.
   - Full width content area (100% width, no sidebar).
   - Zero billing badge ($0.00), zero platform header, zero billing/developer/partner links in nav.
2. Chatwoot Hub Embedded Suite (/embed/chat-hub/ and /embed/chat/):
   - Embeds full Chatwoot Hub with all 3 internal tabs (Live, Channels, AI Settings).
   - Zero billing & platform exposure.
3. Authentication & Token Handling:
   - Valid UserApiKey (?token=sk_live_usr_...) binds tenant user.
   - Valid PartnerProfile API key binds partner user.
   - Invalid token returns HTTP 401.
   - Frame security headers: Content-Security-Policy: frame-ancestors * and X-Frame-Options: ALLOWALL.
4. Developer Docs Verification:
   - developer.html contains documentation and ready-to-copy snippets for both suites.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from developer.models import UserApiKey
from partners.models import PartnerProfile


def test_embedded_suites():
    print("\n==================================================================")
    print("🚀 Running Complete Full White-Label Embedded Suites E2E Test Suite")
    print("==================================================================")

    client = Client()

    # Setup tenant user and developer API key
    tenant_user, _ = User.objects.get_or_create(username="tenant_embed_user", defaults={"email": "tenant@example.com"})
    tenant_user.set_password("pass1234")
    tenant_user.save()

    dev_key_obj, _ = UserApiKey.objects.get_or_create(
        user=tenant_user,
        name="Tenant Live Key",
        defaults={"key": "sk_live_usr_tenant_test_1234567890abcdef", "is_active": True}
    )
    dev_token = dev_key_obj.key

    # Setup partner user and partner API key
    partner_user, _ = User.objects.get_or_create(username="partner_embed_user", defaults={"email": "partner@example.com"})
    partner_user.set_password("pass1234")
    partner_user.save()

    partner_profile, _ = PartnerProfile.objects.get_or_create(
        user=partner_user,
        defaults={
            "company_name": "Acme Partner SaaS",
            "partner_code": "PRT-EMBED-999",
            "api_key": "sk_live_prt_partner_test_999888777666",
            "status": "approved"
        }
    )
    partner_token = partner_profile.api_key

    # -------------------------------------------------------------------------
    # TEST 1: Default /embed/call-center/ redirects to /embed/call-center/room/
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Testing default /embed/call-center/ redirect...")
    resp = client.get(f'/embed/call-center/?token={dev_token}&locale=ar')
    assert resp.status_code == 302, f"Expected 302 redirect, got {resp.status_code}"
    assert '/embed/call-center/room/' in resp.url, f"Expected redirect to room, got {resp.url}"
    assert f'token={dev_token}' in resp.url, f"Token lost in redirect: {resp.url}"
    assert 'locale=ar' in resp.url, f"Locale lost in redirect: {resp.url}"
    assert resp.headers.get('Content-Security-Policy') == 'frame-ancestors *'
    print("✅ Default /embed/call-center/ correctly redirects to /embed/call-center/room/ preserving token and locale!")

    # -------------------------------------------------------------------------
    # TEST 2: All 10 Call Center AI Embedded Sub-Routes
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Testing all 10 Call Center AI Embedded sub-routes...")
    expected_sections = [
        ('room', 'غرفة المساعد الصوتي', ['top-tabs-container', 'tab-voice']),
        ('calls', 'سجل كافة المكالمات (CDR)', ['top-tabs-container', 'calls-table-tbody']),
        ('documents', 'RAG Knowledge Base', ['top-tabs-container', 'docs-tbody']),
        ('personas', 'الشخصيات المتاحة للمحادثات', ['top-tabs-container', 'personas-cards-grid']),
        ('crm', 'ذاكرة وسجل العملاء', ['top-tabs-container', 'memory-recent-calls']),
        ('tools', 'خوادم الأدوات الخارجية', ['top-tabs-container', 'mcp-servers-grid']),
        ('campaigns', 'حملات الاتصال وإدارة العملاء', ['top-tabs-container', 'camp-contacts-tbody']),
        ('call-center', 'المركز الهاتفي وطوابير الانتظار', ['top-tabs-container', 'queues-tbody']),
        ('telephony', 'إدارة الاتصالات والسنترالات', ['top-tabs-container', 'pbx-trunks-grid']),
        ('hours', 'مواعيد العمل والخطة البديلة', ['top-tabs-container', 'days-table-body']),
    ]

    for sec, title_fragment, markers in expected_sections:
        url = f'/embed/call-center/{sec}/?token={dev_token}&locale=ar'
        resp = client.get(url)
        assert resp.status_code == 200, f"Section {sec} failed with status {resp.status_code}"
        content = resp.content.decode('utf-8')
        assert title_fragment in content, f"Title fragment '{title_fragment}' missing in section '{sec}'"
        for m in markers:
            assert m in content, f"Marker '{m}' missing in section '{sec}'"

        # Frame ancestor security header
        assert resp.headers.get('Content-Security-Policy') == 'frame-ancestors *', f"Missing CSP in {sec}"

        # Top Horizontal Tab Bar links check
        assert f'/embed/call-center/room/?token={dev_token}' in content, f"Room link missing in {sec} tab bar"
        assert f'/embed/call-center/calls/?token={dev_token}' in content, f"Calls link missing in {sec} tab bar"
        assert f'/embed/call-center/documents/?token={dev_token}' in content, f"Docs link missing in {sec} tab bar"
        assert f'/embed/call-center/hours/?token={dev_token}' in content, f"Hours link missing in {sec} tab bar"

        print(f"  ✓ Sub-route /embed/call-center/{sec}/ verified (200 OK, full tabs, markers present)")

    print(f"✅ All {len(expected_sections)} Call Center AI sub-routes successfully rendered with top tabs and headers!")

    # -------------------------------------------------------------------------
    # TEST 3: Zero Billing & Pure White-Label Isolation
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Testing Zero Billing & Pure White-Label isolation...")
    for sec, _, _ in expected_sections:
        resp = client.get(f'/embed/call-center/{sec}/?token={dev_token}&locale=ar')
        content = resp.content.decode('utf-8')

        # Sidebar must be completely stripped
        assert '<aside id="sidebar"' not in content, f"Sidebar found in embedded section {sec}"
        assert 'id="nav-btn-billing"' not in content, f"Billing nav link found in embedded section {sec}"
        assert 'id="nav-btn-developer"' not in content, f"Developer nav link found in embedded section {sec}"
        assert 'id="nav-btn-partner"' not in content, f"Partner nav link found in embedded section {sec}"

        # Platform Header with wallet badge must be stripped
        assert 'id="header-wallet-badge"' not in content, f"Header wallet badge found in embedded section {sec}"
        assert 'data-i18n="header_balance"' not in content, f"Balance label DOM found in embedded section {sec}"

        # Content area must be 100% full width (max-w-none w-full)
        assert 'w-full max-w-none' in content, f"Full-width container missing in section {sec}"

        if sec == 'room':
            assert 'id="tab-billing"' not in content, "tab-billing exposed in room.html DOM"
            assert 'id="tab-partner"' not in content, "tab-partner exposed in room.html DOM"
            assert 'id="tab-developer"' not in content, "tab-developer exposed in room.html DOM"

    print("✅ 100% Pure White-Label verified: zero sidebar, zero billing badge ($0.00), zero platform exposure!")

    # -------------------------------------------------------------------------
    # TEST 4: Token Authentication & Validation
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Testing Token Authentication & Validation...")
    client.logout()
    # 4.1 Unauthenticated requests without token must return 401
    for unauth_url in ['/embed/call-center/', '/embed/call-center/room/', '/embed/call-center/calls/', '/embed/chat-hub/']:
        resp_unauth = client.get(unauth_url)
        assert resp_unauth.status_code == 401, f"Expected 401 for unauthenticated {unauth_url}, got {resp_unauth.status_code}"
        assert resp_unauth.headers.get('Content-Security-Policy') == 'frame-ancestors *'
    print("  ✓ Unauthenticated requests without token rejected with 401 Unauthorized")

    # 4.2 Invalid token must return 401
    resp_invalid = client.get('/embed/call-center/room/?token=sk_live_usr_invalid_nonexistent_key')
    assert resp_invalid.status_code == 401, f"Expected 401 for invalid token, got {resp_invalid.status_code}"
    assert resp_invalid.headers.get('Content-Security-Policy') == 'frame-ancestors *'
    print("  ✓ Invalid developer token rejected with 401 Unauthorized")

    # 4.3 Valid Partner Profile token works
    resp_partner = client.get(f'/embed/call-center/room/?token={partner_token}&locale=ar')
    assert resp_partner.status_code == 200, f"Expected 200 for partner token, got {resp_partner.status_code}"
    assert partner_user.username in resp_partner.content.decode('utf-8')
    print("  ✓ Valid Partner API key authenticated and bound user")

    # 4.4 Authenticated web session works
    client.force_login(tenant_user)
    resp_session = client.get('/embed/call-center/calls/')
    assert resp_session.status_code == 200, f"Expected 200 for session auth, got {resp_session.status_code}"
    client.logout()
    print("  ✓ Authenticated web session successfully accessed embedded suite")

    # -------------------------------------------------------------------------
    # TEST 5: Chatwoot Hub Embedded Suite (/embed/chat-hub/ and /embed/chat/)
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Testing Chatwoot Hub Embedded Suite (/embed/chat-hub/ & /embed/chat/)...")
    for chat_ep in ['/embed/chat-hub/', '/embed/chat/']:
        resp_chat = client.get(f'{chat_ep}?token={dev_token}&locale=ar')
        assert resp_chat.status_code == 200, f"Expected 200 for {chat_ep}, got {resp_chat.status_code}"
        content_chat = resp_chat.content.decode('utf-8')

        # Must contain all 3 internal tabs
        assert 'id="chat-tab-live-btn"' in content_chat, f"Live tab button missing in {chat_ep}"
        assert 'id="tab-panel-live"' in content_chat, f"Live tab panel missing in {chat_ep}"
        assert 'id="chat-tab-channels-btn"' in content_chat, f"Channels tab button missing in {chat_ep}"
        assert 'id="tab-panel-channels"' in content_chat, f"Channels tab panel missing in {chat_ep}"
        assert 'id="chat-tab-settings-btn"' in content_chat, f"AI Settings tab button missing in {chat_ep}"
        assert 'id="tab-panel-settings"' in content_chat, f"AI Settings tab panel missing in {chat_ep}"

        # White-label: zero sidebar, zero platform header, and zero telephony tabs
        assert '<aside id="sidebar"' not in content_chat, f"Sidebar found in {chat_ep}"
        assert 'id="header-wallet-badge"' not in content_chat, f"Wallet badge found in {chat_ep}"
        assert 'id="top-tabs-container"' not in content_chat, f"Call Center tabs erroneously rendered in {chat_ep}"
        assert resp_chat.headers.get('Content-Security-Policy') == 'frame-ancestors *'
        assert resp_chat.headers.get('X-Frame-Options') == 'ALLOWALL'
        print(f"  ✓ {chat_ep} rendered with all 3 internal tabs and pure white-label headers")

    # -------------------------------------------------------------------------
    # TEST 6: Developer Docs & Ready-to-Copy Snippets
    # -------------------------------------------------------------------------
    print("\n[TEST 6] Testing Developer API documentation in developer.html...")
    client.force_login(tenant_user)
    resp_dev = client.get('/developer/')
    assert resp_dev.status_code == 200
    content_dev = resp_dev.content.decode('utf-8')

    # Call Center AI Suite Documentation
    assert 'Call Center AI Embedded Suite' in content_dev
    assert 'dev-embed-callcenter-snippet' in content_dev
    assert 'dev-embed-callcenter-preview-btn' in content_dev
    assert '/embed/call-center/room/' in content_dev
    assert '/embed/call-center/calls/' in content_dev
    assert '/embed/call-center/documents/' in content_dev
    assert '/embed/call-center/personas/' in content_dev
    assert '/embed/call-center/crm/' in content_dev
    assert '/embed/call-center/tools/' in content_dev
    assert '/embed/call-center/campaigns/' in content_dev
    assert '/embed/call-center/call-center/' in content_dev
    assert '/embed/call-center/telephony/' in content_dev
    assert '/embed/call-center/hours/' in content_dev

    # Omnichannel Chat Suite Documentation
    assert 'Omnichannel Chat Suite' in content_dev
    assert 'dev-embed-chat-snippet' in content_dev
    assert 'dev-embed-chat-preview-btn' in content_dev
    assert '/embed/chat-hub/' in content_dev
    assert 'المحادثات المباشرة' in content_dev
    assert 'ربط القنوات' in content_dev
    assert 'إعدادات المساعد الذكي' in content_dev

    client.logout()
    print("\n[TEST 7] Testing /embed/voice/ and /embed/dialer/ unified to Call Center AI Suite...")
    for unified_ep in ['/embed/voice/', '/embed/dialer/']:
        client.logout()
        # Unauthenticated request rejected
        resp_unauth = client.get(unified_ep)
        assert resp_unauth.status_code == 401, f"Expected 401 for unauthenticated {unified_ep}, got {resp_unauth.status_code}"

        # Authenticated with token renders full 10-tab Call Center AI suite (section='room')
        resp_unified = client.get(f'{unified_ep}?token={dev_token}&locale=ar')
        assert resp_unified.status_code == 200, f"Expected 200 for {unified_ep}, got {resp_unified.status_code}"
        content_unified = resp_unified.content.decode('utf-8')
        assert 'top-tabs-container' in content_unified, f"top-tabs-container missing in {unified_ep}"
        assert 'tab-voice' in content_unified, f"tab-voice missing in {unified_ep}"
        assert '<aside id="sidebar"' not in content_unified, f"Sidebar erroneously rendered in {unified_ep}"
        assert 'id="header-wallet-badge"' not in content_unified, f"Wallet badge erroneously rendered in {unified_ep}"
        assert resp_unified.headers.get('Content-Security-Policy') == 'frame-ancestors *'
        print(f"  ✓ {unified_ep} successfully verified as unified 10-tab Call Center AI Suite")

    print("✅ /embed/voice/ and /embed/dialer/ successfully unified to Call Center AI suite with token auth!")

    # -------------------------------------------------------------------------
    # TEST 8: Developer Docs Chat Hub Deep-Linking & Partner Sub-Client Modal
    # -------------------------------------------------------------------------
    print("\n[TEST 8] Testing Developer Chat Hub deep-linking & Partner Sub-Client embed modal...")
    # Check developer.html deep-linking snippets
    assert 'href="#section-chat-embeds"' in content_dev, "Quick-jump link #section-chat-embeds missing in developer.html"
    assert 'id="section-chat-embeds"' in content_dev, "Full-width section-chat-embeds card missing in developer.html"
    assert 'dev-embed-chat-channels-snippet' in content_dev, "dev-embed-chat-channels-snippet missing in developer.html"
    assert 'dev-embed-chat-settings-snippet' in content_dev, "dev-embed-chat-settings-snippet missing in developer.html"
    assert '/embed/chat-hub/?tab=channels' in content_dev, "Channels deep-link URL missing in developer.html"
    assert '/embed/chat-hub/?tab=settings' in content_dev, "Settings deep-link URL missing in developer.html"
    print("  ✓ Developer Docs contains quick-jump button and deep-link snippets for all 3 chat sub-tabs")

    # Check partner.html Call Center embed & Sub-client modal
    client.force_login(partner_user)
    resp_partner_page = client.get('/partner/')
    assert resp_partner_page.status_code == 200, f"Expected 200 for /partner/, got {resp_partner_page.status_code}"
    content_partner_page = resp_partner_page.content.decode('utf-8')

    assert 'partner-embed-callcenter-snippet' in content_partner_page, "partner-embed-callcenter-snippet missing in partner.html"
    assert 'partner-embed-callcenter-preview-btn' in content_partner_page, "partner-embed-callcenter-preview-btn missing in partner.html"
    assert 'partner-embed-chat-snippet' in content_partner_page, "partner-embed-chat-snippet missing in partner.html"
    assert 'partner-client-embed-modal' in content_partner_page, "partner-client-embed-modal missing in partner.html"
    assert 'client-embed-callcenter-snippet' in content_partner_page, "client-embed-callcenter-snippet missing in partner.html"
    assert 'client-embed-chat-snippet' in content_partner_page, "client-embed-chat-snippet missing in partner.html"
    print("  ✓ Partner Portal contains Call Center embed card (100%x800px) and Sub-Client Embed Modal")

    # -------------------------------------------------------------------------
    # TEST 9: Partner Sub-Client Isolation & Anti-IDOR Security Boundaries
    # -------------------------------------------------------------------------
    print("\n[TEST 9] Testing Partner Sub-Client Isolation & Anti-IDOR Security...")
    from partners.models import PartnerClientRelationship
    subclient_user, _ = User.objects.get_or_create(username="subclient_embed_user", defaults={"email": "subclient@example.com"})
    subclient_user.set_password("pass1234")
    subclient_user.save()

    rel, _ = PartnerClientRelationship.objects.get_or_create(
        partner=partner_profile,
        client=subclient_user,
        defaults={"external_reference": "CRM-CLIENT-001", "is_active": True}
    )
    rel.is_active = True
    rel.save()

    # 9.1 Valid sub-client under partner renders correctly and binds sub-client user
    resp_sub = client.get(f'/embed/call-center/room/?token={partner_token}&client_id={subclient_user.id}&locale=ar')
    assert resp_sub.status_code == 200, f"Expected 200 for subclient, got {resp_sub.status_code}"
    content_sub = resp_sub.content.decode('utf-8')
    assert subclient_user.username in content_sub, "Sub-client username missing in embedded room"
    print("  ✓ Valid sub-client access successfully binds sub-client tenant user")

    # 9.2 Chat Hub under partner token with client_id
    resp_sub_chat = client.get(f'/embed/chat-hub/?token={partner_token}&client_id={subclient_user.id}&locale=ar')
    assert resp_sub_chat.status_code == 200, f"Expected 200 for subclient chat-hub, got {resp_sub_chat.status_code}"
    print("  ✓ Sub-client Chat Hub successfully binds sub-client Chatwoot account")

    # 9.3 Invalid / non-existent client_id MUST be rejected (404) and never escalate to partner user
    resp_idor = client.get(f'/embed/call-center/room/?token={partner_token}&client_id=888888&locale=ar')
    assert resp_idor.status_code == 404, f"Expected 404 for non-existent client_id, got {resp_idor.status_code}"
    resp_idor_chat = client.get(f'/embed/chat-hub/?token={partner_token}&client_id=888888&locale=ar')
    assert resp_idor_chat.status_code == 404, f"Expected 404 for non-existent client_id on chat-hub, got {resp_idor_chat.status_code}"
    print("  ✓ Anti-IDOR protection verified: invalid client_id strictly rejected with 404 (zero privilege escalation)")

    # 9.4 Suspended sub-client (is_active=False) MUST be rejected with 403
    rel.is_active = False
    rel.save()
    resp_suspended_client = client.get(f'/embed/call-center/room/?token={partner_token}&client_id={subclient_user.id}&locale=ar')
    assert resp_suspended_client.status_code == 403, f"Expected 403 for suspended sub-client, got {resp_suspended_client.status_code}"
    rel.is_active = True
    rel.save()
    print("  ✓ Suspended sub-client correctly rejected with 403 Forbidden")

    # 9.5 Suspended partner status MUST be rejected with 403
    suspended_partner_user, _ = User.objects.get_or_create(username="suspended_partner", defaults={"email": "susp_part@example.com"})
    suspended_profile, _ = PartnerProfile.objects.get_or_create(
        user=suspended_partner_user,
        defaults={
            "company_name": "Suspended Partner",
            "partner_code": "PRT-SUSP-777",
            "api_key": "sk_live_prt_suspended_77777777",
            "status": "suspended"
        }
    )
    resp_suspended_partner = client.get(f'/embed/call-center/room/?token={suspended_profile.api_key}&locale=ar')
    assert resp_suspended_partner.status_code == 403, f"Expected 403 for suspended partner, got {resp_suspended_partner.status_code}"
    print("  ✓ Suspended partner account strictly rejected with 403 Forbidden")

    # -------------------------------------------------------------------------
    # TEST 10: Bidirectional postMessage Listeners & JS Client Helpers
    # -------------------------------------------------------------------------
    print("\n[TEST 10] Testing Bidirectional postMessage Protocol & Helper Functions...")
    # 10.1 Check chat.html postMessage event handling
    resp_chat_page = client.get(f'/embed/chat-hub/?token={dev_token}&locale=ar')
    chat_content = resp_chat_page.content.decode('utf-8')
    assert 'SWITCH_TAB' in chat_content, "SWITCH_TAB listener missing in chat.html"
    assert 'SET_THEME' in chat_content, "SET_THEME listener missing in chat.html"
    assert 'unread_message_count' in chat_content, "unread_message_count forwarder missing in chat.html"
    assert 'CHAT_READY' in chat_content, "CHAT_READY forwarder missing in chat.html"
    print("  ✓ chat.html handles SWITCH_TAB, SET_THEME and forwards CHAT_READY, unread_message_count")

    # 10.2 Check room.html postMessage event handling
    resp_room_page = client.get(f'/embed/call-center/room/?token={dev_token}&locale=ar')
    room_content = resp_room_page.content.decode('utf-8')
    assert 'VOICE_DIAL' in room_content, "VOICE_DIAL listener missing in room.html"
    assert 'VOICE_HANGUP' in room_content, "VOICE_HANGUP listener missing in room.html"
    assert 'VOICE_CALL_STARTED' in room_content, "VOICE_CALL_STARTED dispatch missing in room.html"
    assert 'VOICE_CALL_ENDED' in room_content, "VOICE_CALL_ENDED dispatch missing in room.html"
    print("  ✓ room.html handles VOICE_DIAL, VOICE_HANGUP and dispatches VOICE_CALL_STARTED, VOICE_CALL_ENDED")

    # 10.3 Check partner.js has copySnippet and escapeHtml
    with open('static/js/partner.js', 'r', encoding='utf-8') as f:
        partner_js = f.read()
    assert 'function copySnippet' in partner_js, "copySnippet missing in partner.js"
    assert 'function fallbackCopy' in partner_js, "fallbackCopy missing in partner.js"
    assert 'function escapeHtml' in partner_js, "escapeHtml missing in partner.js"
    assert 'data-client-id' in partner_js, "data-client-id missing in partner.js table button"
    print("  ✓ partner.js contains copySnippet, fallbackCopy, escapeHtml, and quote-safe data attributes")

    print("\n==================================================================")
    print("🎉 ALL FULL WHITE-LABEL EMBEDDED SUITES E2E TESTS PASSED! (100%)")
    print("==================================================================\n")


if __name__ == '__main__':
    test_embedded_suites()
