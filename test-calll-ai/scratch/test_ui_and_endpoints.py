import sys
import requests
import urllib3

sys.stdout.reconfigure(encoding='utf-8')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://localhost"

def test_full_ui_stack():
    print("=" * 65)
    print("STARTING FULL SCRIPT-BASED UI & ARCHITECTURE VERIFICATION")
    print("=" * 65)

    session = requests.Session()
    session.verify = False

    # 1. Test Login Page GET
    print("\n[1] Testing Login Page GET (https://localhost/login/)...")
    res_login_page = session.get(f"{BASE_URL}/login/")
    assert res_login_page.status_code == 200, f"Failed: {res_login_page.status_code}"
    csrftoken = session.cookies.get('csrftoken', '')
    assert csrftoken, "CSRF token not found in cookies"
    print(" -> Login page loaded successfully (200 OK), CSRF token acquired.")

    # 2. Test Super Admin Authentication
    print("\n[2] Testing Super Admin Login POST...")
    login_data = {
        'username': 'admin',
        'password': 'admin123456',
        'csrfmiddlewaretoken': csrftoken
    }
    res_auth = session.post(f"{BASE_URL}/login/", data=login_data, headers={'Referer': f"{BASE_URL}/login/"})
    assert res_auth.status_code == 200, f"Auth POST failed: {res_auth.status_code}"
    print(f" -> Logged in successfully! Redirected to: {res_auth.url}")

    # 3. Test Room View HTML Retrieval
    print("\n[3] Fetching Main Workspace (https://localhost/)...")
    res_room = session.get(f"{BASE_URL}/")
    assert res_room.status_code == 200, f"Room GET failed: {res_room.status_code}"
    html = res_room.text
    print(f" -> Workspace loaded successfully ({len(html)} bytes).")

    # 4. Verify Luxury Design System & Fonts
    print("\n[4] Verifying Luxury Design System & Color Palette...")
    design_checks = [
        ("Google Fonts (Tajawal)", "Tajawal"),
        ("Google Fonts (Inter)", "Inter"),
        ("Off-White Canvas (#FAF7F2)", "#FAF7F2"),
        ("Burgundy Primary (#680E23)", "#680E23"),
        ("Champagne Gold Accent (#D4AF37)", "#D4AF37"),
        ("Acoustic Orb Animation", "luxury-voice-orb"),
        ("Active Pulse Glow", "luxury-pulse"),
    ]
    for label, pattern in design_checks:
        assert pattern in html, f"Missing design element: {label} ({pattern})"
        print(f" -> [PASS] {label}")

    # 5. Verify Collapsible Sidebar & 7 Navigation Items
    print("\n[5] Verifying Sidebar & Navigation Tabs...")
    sidebar_checks = [
        ("Sidebar Container", 'id="sidebar"'),
        ("Sidebar Toggle Button", 'onclick="toggleSidebar()"'),
        ("Tab 1: Voice Room", 'id="nav-btn-voice"'),
        ("Tab 2: AI Personas & Dialects", 'id="nav-btn-personas"'),
        ("Tab 3: Knowledge Base RAG", 'id="nav-btn-rag"'),
        ("Tab 4: Call Center & Queues", 'id="nav-btn-callcenter"'),
        ("Tab 5: Telephony & PBX", 'id="nav-btn-telephony"'),
        ("Tab 6: Customer CRM & Memory", 'id="nav-btn-crm"'),
        ("Tab 7: Store & Tools MCP", 'id="nav-btn-store"'),
    ]
    for label, pattern in sidebar_checks:
        assert pattern in html, f"Missing sidebar item: {label}"
        print(f" -> [PASS] {label}")

    # 6. Verify 7 SPA Tab Panels in Main Content Area
    print("\n[6] Verifying SPA Tab Content Panels...")
    panel_checks = [
        ("Panel 1: Voice Room", 'id="tab-voice"'),
        ("Panel 2: Personas", 'id="tab-personas"'),
        ("Panel 3: Knowledge RAG", 'id="tab-rag"'),
        ("Panel 4: Call Center", 'id="tab-callcenter"'),
        ("Panel 5: Telephony", 'id="tab-telephony"'),
        ("Panel 6: CRM Memory", 'id="tab-crm"'),
        ("Panel 7: FastMCP Store", 'id="tab-store"'),
    ]
    for label, pattern in panel_checks:
        assert pattern in html, f"Missing panel: {label}"
        print(f" -> [PASS] {label}")

    # 7. Verify Floating Persistent Voice Widget
    print("\n[7] Verifying Floating Persistent Voice Bar...")
    floating_checks = [
        ("Floating Voice Bar Container", 'id="floating-voice-bar"'),
        ("Floating Mini Acoustic Orb", 'id="floating-orb"'),
        ("Floating Status Display", 'id="floating-status"'),
        ("Floating Quick Mute Button", 'id="floating-btn-mute"'),
        ("Floating Quick End Button", 'id="floating-btn-end"'),
        ("Return to Voice Room Action", 'switchTab(\'voice\')'),
    ]
    for label, pattern in floating_checks:
        assert pattern in html, f"Missing floating widget element: {label}"
        print(f" -> [PASS] {label}")

    # 8. Verify Bilingual Engine & Localization Keys
    print("\n[8] Verifying Bilingual Translation System (I18N)...")
    i18n_checks = [
        ("Language Switcher Button", 'id="lang-switch-btn"'),
        ("Toggle Language Function", 'toggleLanguage()'),
        ("Apply Language Function", 'applyLanguage(lang)'),
        ("I18N Dictionary Definition", 'const I18N = {'),
        ("Arabic Translations (ar)", 'nav_voice: "غرفة المساعد الصوتي"'),
        ("English Translations (en)", 'nav_voice: "Voice Assistant Room"'),
    ]
    for label, pattern in i18n_checks:
        assert pattern in html, f"Missing bilingual key: {label}"
        print(f" -> [PASS] {label}")

    # 9. Verify All Preserved Functional IDs (Zero Regressions)
    print("\n[9] Verifying Functional IDs for LiveKit, Centrifugo, RAG & PBX...")
    core_functional_ids = [
        "visualizer-orb", "btn-start", "btn-mute", "btn-end", "call-status",
        "transcript-box", "mic-level-container", "mic-level-bar", "mic-level-text",
        "livekit-status", "centrifugo-status",
        "profile-select", "field-gender", "field-dialect", "field-voice",
        "upload-form", "file-input", "btn-upload", "docs-tbody",
        "employees-tbody", "queues-tbody",
        "crm-customer-select", "crm-customer-search", "crm-active-customer-badge",
        "memory-permanent-content", "memory-immediate-content", "memory-calls-badge", "memory-recent-calls",
        "mcp-active-badge", "mcp-tools-container"
    ]
    for el_id in core_functional_ids:
        assert f'id="{el_id}"' in html, f"CRITICAL: Missing original functional ID: {el_id}"
    print(f" -> [PASS] All {len(core_functional_ids)} critical functional IDs verified intact.")

    # 10. Verify Live Dynamic APIs as Authenticated Admin
    print("\n[10] Testing Dynamic JSON APIs via Admin Session...")
    
    # LiveKit Token API
    res_token = session.get(f"{BASE_URL}/api/token/")
    assert res_token.status_code == 200, f"Token API failed: {res_token.status_code}"
    token_data = res_token.json()
    assert "livekit_token" in token_data and "centrifugo_token" in token_data
    print(" -> [PASS] /api/token/ returned valid LiveKit & Centrifugo JWTs.")

    # Profiles API
    res_profiles = session.get(f"{BASE_URL}/api/profiles/")
    assert res_profiles.status_code == 200
    print(f" -> [PASS] /api/profiles/ returned {len(res_profiles.json().get('profiles', []))} voice profiles.")

    # Documents API
    res_docs = session.get(f"{BASE_URL}/api/documents/")
    assert res_docs.status_code == 200
    print(f" -> [PASS] /api/documents/ returned {len(res_docs.json().get('documents', []))} RAG documents.")

    # Employees API
    res_emp = session.get(f"{BASE_URL}/api/employees/")
    assert res_emp.status_code == 200
    print(f" -> [PASS] /api/employees/ returned {len(res_emp.json().get('employees', []))} active employees.")

    # Queues API
    res_q = session.get(f"{BASE_URL}/api/queues/")
    assert res_q.status_code == 200
    print(f" -> [PASS] /api/queues/ returned {len(res_q.json().get('queues', []))} call queues.")

    print("\n" + "=" * 65)
    print("ALL SCRIPT-BASED UI & ENDPOINT VERIFICATION TESTS PASSED 100%!")
    print("=" * 65)

if __name__ == '__main__':
    test_full_ui_stack()
