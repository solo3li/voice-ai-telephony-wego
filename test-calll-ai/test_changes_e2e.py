#!/usr/bin/env python3
"""
Comprehensive End-to-End Test Suite for Voice AI System:
Validating all 4 requirements:
1. Agent prompt & personality neutrality (no hardcoded store/orders) & caller transfer inquiry rules
2. Removal of WebRTC token endpoints from Developer & Partner APIs
3. Fast AI test call (ext 000) for employees via Call Center backend & Expo dialpad button
4. Disabling direct file uploads across Developer & Partner APIs (Accepting only file_url, content, contacts)
5. Validation of Developer and Partner OpenAPI specifications
"""

import sys
import os
import io
import json
import requests
import urllib3

# Fix encoding & disable SSL warnings for local test domain
sys.stdout.reconfigure(encoding='utf-8')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Setup path for local module imports
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

BASE_URL = "https://app.169.58.32.179.nip.io"
USER_API_KEY = "sk_live_usr_74bfbbd8f42f86acec24df223b5f9e75d46b0b79"
PARTNER_API_KEY = "pk_live_e2e_8a893089ff96e251ec645bb137060b34920d85a7"
PARTNER_CLIENT_ID = 39

session = requests.Session()
session.verify = False

passed_tests = 0
failed_tests = 0

def log_test(name, passed, detail=""):
    global passed_tests, failed_tests
    if passed:
        passed_tests += 1
        print(f"  [PASS] {name}" + (f" -> {detail}" if detail else ""))
    else:
        failed_tests += 1
        print(f"  [FAIL] {name}" + (f" -> {detail}" if detail else ""))

print("=" * 75)
print("  E2E COMPREHENSIVE VERIFICATION SUITE")
print("=" * 75)

# ==============================================================================
# TEST SUITE 1: Prompt Neutrality & Transfer Understanding Rules
# ==============================================================================
print("\n>>> SUITE 1: Prompt Neutrality, Dynamic Personas & Transfer Rules")

import subprocess
from agent.prompts.builder import build_dynamic_system_instruction

# 1.1 Verify absence of hardcoded store/orders in builder output
restaurant_profile = {
    "name": "مضيف المطعم",
    "persona_role": "restaurant_host",
    "custom_instructions": "الرد على استفسارات قائمة الطعام وحجوزات الطاولات والأسعار",
    "dialect": "saudi",
    "gender": "male",
    "speaking_style": "friendly",
    "verbosity": "balanced"
}
prompt_restaurant = build_dynamic_system_instruction(
    profile=restaurant_profile,
    call_queues=[{"code": "100", "name": "الحجوزات والطلبات", "description": "طابور حجوزات المطعم"}]
)

forbidden_strings = ["أنا هفحصلك الأوردر حالا", "متجر المستخدم", "بيانات متجر المستخدم"]
has_forbidden = any(f in prompt_restaurant for f in forbidden_strings)
log_test("Absence of hardcoded store/order assumptions in restaurant prompt", not has_forbidden, "No store hardcoding detected")

# 1.2 Verify persona adaptation to domain
log_test("Prompt reflects restaurant host personality", "مضيف المطعم" in prompt_restaurant and "حجوزات المطعم" in prompt_restaurant)

# 1.3 Verify corporate consultant / customer support adaptation
support_profile = {
    "name": "مستشار الدعم الفني",
    "persona_role": "customer_support",
    "custom_instructions": "دعم عملاء منصة سحابية لإدارة السيرفرات والبنية التحتية",
    "dialect": "fusha",
    "gender": "male",
    "speaking_style": "professional",
    "verbosity": "balanced"
}
prompt_support = build_dynamic_system_instruction(
    profile=support_profile,
    call_queues=[{"code": "200", "name": "الدعم التقني المتقدم", "description": "مهندسو البنية التحتية"}]
)
log_test("Prompt reflects technical customer support personality", "مستشار الدعم الفني" in prompt_support and "السيرفرات" in prompt_support)

# 1.4 Verify call transfer inquiry rule in prompt
transfer_inquiry_phrases = ["فهم المشكلة أولاً وعدم التعجل في التحويل", "يُمنع منعاً باتاً استدعاء أداة 'transfer_to_queue' فوراً", "يجب أولاً أن تسأل العميل بلطف ولباقة"]
has_transfer_rules = all(p in prompt_support for p in transfer_inquiry_phrases)
log_test("Prompt contains strict inquiry rule before call transfer", has_transfer_rules, "Agent instructed to inquire and understand before transferring")

# 1.5 Verify tool schemas neutrality and transfer warnings inside agent container
tool_check_cmd = [
    "docker", "exec", "voice_agent", "python", "-c",
    "import json; from agent.session.tool_dispatcher import build_gemini_tools; "
    "tools = build_gemini_tools({'check_product': {'description': 'فحص المنتج'}}, [{'code': '100', 'name': 'المبيعات', 'description': 'قسم المبيعات'}]); "
    "decls = tools[0]['function_declarations']; "
    "print(json.dumps([{'name': d['name'], 'description': d['description']} for d in decls]))"
]
try:
    tool_out = subprocess.check_output(tool_check_cmd, text=True, stderr=subprocess.STDOUT)
    json_lines = [l.strip() for l in tool_out.strip().splitlines() if l.strip().startswith("[") and l.strip().endswith("]")]
    decls = json.loads(json_lines[-1]) if json_lines else []
    tool_names = [d["name"] for d in decls]
    log_test("Tool dispatcher registers declared tools in agent environment", "search_knowledge_base" in tool_names and "transfer_to_queue" in tool_names and "check_product" in tool_names)
    
    rag_tool = next((d for d in decls if d["name"] == "search_knowledge_base"), None)
    log_test("search_knowledge_base tool description is neutral", "قاعدة المعرفة والمستندات" in (rag_tool["description"] if rag_tool else "") and "متجر" not in (rag_tool["description"] if rag_tool else ""))
    
    transfer_tool = next((d for d in decls if d["name"] == "transfer_to_queue"), None)
    has_transfer_warning = transfer_tool and "ممنوع استدعاء هذه الأداة فوراً" in transfer_tool["description"]
    log_test("transfer_to_queue tool description warns against premature transfers", bool(has_transfer_warning), "Strict inquiry instruction present")
except Exception as e:
    log_test("Tool dispatcher test execution", False, str(e))

# ==============================================================================
# TEST SUITE 2: Developer & Partner OpenAPI Specs
# ==============================================================================
print("\n>>> SUITE 2: OpenAPI Specifications Verification")

from django_app.developer.user_openapi_spec import get_user_openapi_spec
from django_app.partners.openapi_spec import get_partner_openapi_spec

dev_spec = get_user_openapi_spec(lang="ar")
partner_spec = get_partner_openapi_spec(lang="ar")

# 2.1 Developer spec checks
dev_paths = dev_spec.get("paths", {})
log_test("Developer OpenAPI spec has NO /token/ path", "/token/" not in dev_paths)

dev_tag_names = [t["name"] for t in dev_spec.get("tags", [])]
has_dev_token_tag = any("WebRTC" in name and "9" in name for name in dev_tag_names)
log_test("Developer OpenAPI spec has removed WebRTC Token tag", not has_dev_token_tag and len(dev_tag_names) == 11, f"Total tags: {len(dev_tag_names)}")

dev_doc_body = dev_paths.get("/documents/", {}).get("post", {}).get("requestBody", {}).get("content", {})
log_test("Developer /documents/ accepts ONLY application/json (no multipart)", "application/json" in dev_doc_body and "multipart/form-data" not in dev_doc_body)

dev_camp_body = dev_paths.get("/campaigns/", {}).get("post", {}).get("requestBody", {}).get("content", {})
log_test("Developer /campaigns/ accepts ONLY application/json (no multipart)", "application/json" in dev_camp_body and "multipart/form-data" not in dev_camp_body)

# 2.2 Partner spec checks
partner_paths = partner_spec.get("paths", {})
log_test("Partner OpenAPI spec has NO /clients/{client_id}/token/ path", "/clients/{client_id}/token/" not in partner_paths)

partner_tag_names = [t["name"] for t in partner_spec.get("tags", [])]
has_partner_token_tag = any("WebRTC" in name and "9" in name for name in partner_tag_names)
log_test("Partner OpenAPI spec has removed WebRTC Token tag", not has_partner_token_tag and len(partner_tag_names) == 12, f"Total tags: {len(partner_tag_names)}")

partner_doc_body = partner_paths.get("/clients/{client_id}/documents/", {}).get("post", {}).get("requestBody", {}).get("content", {})
log_test("Partner /documents/ accepts ONLY application/json (no multipart)", "application/json" in partner_doc_body and "multipart/form-data" not in partner_doc_body)

partner_camp_body = partner_paths.get("/clients/{client_id}/campaigns/", {}).get("post", {}).get("requestBody", {}).get("content", {})
log_test("Partner /campaigns/ accepts ONLY application/json (no multipart)", "application/json" in partner_camp_body and "multipart/form-data" not in partner_camp_body)

# ==============================================================================
# TEST SUITE 3: HTTP API Verification - WebRTC Token Endpoint Removal
# ==============================================================================
print("\n>>> SUITE 3: HTTP API - Removal of Token Endpoints")

dev_headers = {"X-API-Key": USER_API_KEY, "Content-Type": "application/json"}
partner_headers = {"X-Partner-Key": PARTNER_API_KEY, "Content-Type": "application/json"}

# 3.1 Developer Token Endpoint is 404
res_dev_tok = session.post(f"{BASE_URL}/api/v1/token/", headers=dev_headers, json={})
log_test("POST /api/v1/token/ returns 404 (endpoint removed)", res_dev_tok.status_code == 404, f"Status: {res_dev_tok.status_code}")

# 3.2 Partner Client Token Endpoint is 404
res_part_tok = session.post(f"{BASE_URL}/api/partner/v1/clients/{PARTNER_CLIENT_ID}/token/", headers=partner_headers, json={})
log_test("POST /api/partner/v1/clients/<id>/token/ returns 404 (endpoint removed)", res_part_tok.status_code == 404, f"Status: {res_part_tok.status_code}")

# ==============================================================================
# TEST SUITE 4: Employee App AI Test Call (Target 000) & UI Verification
# ==============================================================================
print("\n>>> SUITE 4: Call Center Employee AI Test Call & Dialpad Button")

# 4.1 Login Regular Employee (Ahmed 101)
login_res = session.post(f"{BASE_URL}/api/call-center/auth/login/", json={
    "identifier": "101",
    "password": "password123"
})
assert login_res.status_code == 200, f"Login failed: {login_res.text}"
emp_data = login_res.json().get("employee", {})
emp_token = login_res.json()["token"]
emp_headers = {"Authorization": f"Bearer {emp_token}", "Content-Type": "application/json"}
log_test("Employee 101 login successful (is_owner: False)", emp_data.get("is_owner") is False)

# 4.2 Regular Employee dialing '000' is restricted (403 Forbidden)
emp_dial_000 = session.post(f"{BASE_URL}/api/call-center/calls/dial/", headers=emp_headers, json={"target": "000"})
log_test("Regular employee dialing '000' restricted with 403", emp_dial_000.status_code == 403, f"Status: {emp_dial_000.status_code}")

# 4.3 Login Owner Employee (test_dev_user)
owner_login = session.post(f"{BASE_URL}/api/call-center/auth/login/", json={
    "identifier": "test_dev_user",
    "password": "password123"
})
assert owner_login.status_code == 200, f"Owner login failed: {owner_login.text}"
owner_data = owner_login.json().get("employee", {})
owner_token = owner_login.json()["token"]
owner_headers = {"Authorization": f"Bearer {owner_token}", "Content-Type": "application/json"}
log_test("Owner employee login successful (is_owner: True)", owner_data.get("is_owner") is True)

# 4.4 Owner dialing '000' triggers AI Test Call (200 OK)
dial_000_res = session.post(f"{BASE_URL}/api/call-center/calls/dial/", headers=owner_headers, json={"target": "000"})
dial_data = dial_000_res.json() if dial_000_res.status_code == 200 else {}
is_ai_test = (
    dial_000_res.status_code == 200 and
    dial_data.get("status") == "success" and
    dial_data.get("call_type") == "ai_test" and
    "livekit_token" in dial_data and
    "room_name" in dial_data and
    "🤖" in dial_data.get("target_name", "")
)
log_test("Owner dialing '000' triggers AI Test Call (status: success, call_type: ai_test)", is_ai_test, f"Room: {dial_data.get('room_name')}")

# 4.5 Owner dialing 'ai' alias
dial_ai_res = session.post(f"{BASE_URL}/api/call-center/calls/dial/", headers=owner_headers, json={"target": "ai"})
log_test("Owner dialing 'ai' alias triggers AI Test Call", dial_ai_res.status_code == 200 and dial_ai_res.json().get("call_type") == "ai_test")

# 4.6 Inspect Employee Expo 57 DialpadView component
dialpad_component_path = os.path.join(CURRENT_DIR, "employee_expo57", "src", "components", "DialpadView.tsx")
with open(dialpad_component_path, "r", encoding="utf-8") as f:
    dialpad_code = f.read()

has_ai_button = "تجربة المساعد الذكي" in dialpad_code and 'startCall("000"' in dialpad_code and "employee?.is_owner" in dialpad_code
log_test("DialpadView.tsx includes fast '🤖 تجربة المساعد الذكي' button guarded by employee?.is_owner", has_ai_button)

# ==============================================================================
# TEST SUITE 5: Document Management - Direct File Upload Rejection
# ==============================================================================
print("\n>>> SUITE 5: Document Management - File Upload Rejection & JSON Indexing")

# 5.1 Developer API - Multipart file upload rejected
fake_pdf = io.BytesIO(b"%PDF-1.4 test document content")
res_dev_doc_file = session.post(
    f"{BASE_URL}/api/v1/documents/",
    headers={"X-API-Key": USER_API_KEY},
    files={"file": ("test.pdf", fake_pdf, "application/pdf")},
    data={"title": "Test PDF"}
)
is_dev_file_blocked = (
    res_dev_doc_file.status_code == 400 and
    res_dev_doc_file.json().get("code") == "direct_file_upload_disabled"
)
log_test("Developer /documents/ rejects multipart file upload (400 direct_file_upload_disabled)", is_dev_file_blocked, res_dev_doc_file.json().get("message", "")[:45] + "...")

# 5.2 Developer API - JSON content accepted
res_dev_doc_json = session.post(
    f"{BASE_URL}/api/v1/documents/",
    headers=dev_headers,
    json={
        "title": "سياسة الخدمة - اختبار E2E",
        "content": "نقدم خدمات الدعم الفني على مدار الساعة لجميع العملاء المشتركين في باقة الأعمال."
    }
)
log_test("Developer /documents/ accepts JSON content text (201 Created)", res_dev_doc_json.status_code == 201)

# 5.3 Partner API - Multipart file upload rejected
fake_docx = io.BytesIO(b"DOCX fake content")
res_part_doc_file = session.post(
    f"{BASE_URL}/api/partner/v1/clients/{PARTNER_CLIENT_ID}/documents/",
    headers={"X-Partner-Key": PARTNER_API_KEY},
    files={"file": ("client_policy.docx", fake_docx, "application/octet-stream")},
    data={"title": "Client Policy"}
)
is_part_file_blocked = (
    res_part_doc_file.status_code == 400 and
    res_part_doc_file.json().get("code") == "direct_file_upload_disabled"
)
log_test("Partner /documents/ rejects multipart file upload (400 direct_file_upload_disabled)", is_part_file_blocked)

# 5.4 Partner API - JSON content accepted
res_part_doc_json = session.post(
    f"{BASE_URL}/api/partner/v1/clients/{PARTNER_CLIENT_ID}/documents/",
    headers=partner_headers,
    json={
        "title": "سياسة استرجاع العميل الفرعي - E2E",
        "content": "يسمح باستبدال واسترجاع المنتجات خلال 14 يوماً من تاريخ الشراء."
    }
)
log_test("Partner /documents/ accepts JSON content text (201 Created)", res_part_doc_json.status_code == 201)

# ==============================================================================
# TEST SUITE 6: Campaigns - Direct File Upload Rejection
# ==============================================================================
print("\n>>> SUITE 6: Campaigns - File Upload Rejection & JSON Contacts")

# 6.1 Developer API - Multipart leads upload rejected
fake_csv = io.BytesIO(b"phone,name\n+966551122334,Ahmed\n")
res_dev_camp_file = session.post(
    f"{BASE_URL}/api/v1/campaigns/",
    headers={"X-API-Key": USER_API_KEY},
    files={"file": ("leads.csv", fake_csv, "text/csv")},
    data={"name": "حملة تجريبية بالملف"}
)
is_dev_camp_file_blocked = (
    res_dev_camp_file.status_code == 400 and
    res_dev_camp_file.json().get("code") == "direct_file_upload_disabled"
)
log_test("Developer /campaigns/ rejects multipart file upload (400 direct_file_upload_disabled)", is_dev_camp_file_blocked)

# 6.2 Developer API - JSON contacts accepted
res_dev_camp_json = session.post(
    f"{BASE_URL}/api/v1/campaigns/",
    headers=dev_headers,
    json={
        "name": "حملة تأكيد الحجوزات - E2E",
        "contacts": [
            {"phone_number": "+966551234567", "name": "سعد الدوسري", "attributes": {"city": "الرياض"}},
            {"phone_number": "+966559876543", "name": "خالد القحطاني", "attributes": {"city": "جدة"}}
        ],
        "call_prompt": "تأكيد موعد استلام الطلب من الفرع"
    }
)
log_test("Developer /campaigns/ accepts JSON contacts array (201 Created)", res_dev_camp_json.status_code == 201)

# 6.3 Partner API - Multipart leads upload rejected
fake_leads = io.BytesIO(b"phone,name\n+966559988776,Client Contact\n")
res_part_camp_file = session.post(
    f"{BASE_URL}/api/partner/v1/clients/{PARTNER_CLIENT_ID}/campaigns/",
    headers={"X-Partner-Key": PARTNER_API_KEY},
    files={"file": ("client_leads.csv", fake_leads, "text/csv")},
    data={"name": "حملة عميل بالملف"}
)
is_part_camp_file_blocked = (
    res_part_camp_file.status_code == 400 and
    res_part_camp_file.json().get("code") == "direct_file_upload_disabled"
)
log_test("Partner /campaigns/ rejects multipart file upload (400 direct_file_upload_disabled)", is_part_camp_file_blocked)

# 6.4 Partner API - JSON contacts accepted
res_part_camp_json = session.post(
    f"{BASE_URL}/api/partner/v1/clients/{PARTNER_CLIENT_ID}/campaigns/",
    headers=partner_headers,
    json={
        "name": "حملة العميل الترويجي - E2E",
        "contacts": [
            {"phone_number": "+966552233445", "name": "سلطان العتيبي"},
            {"phone_number": "+966553344556", "name": "فيصل المطيري"}
        ],
        "call_prompt": "إبلاغ العميل بالعروض الخاصة بنهاية الأسبوع"
    }
)
log_test("Partner /campaigns/ accepts JSON contacts array (201 Created)", res_part_camp_json.status_code == 201)

# ==============================================================================
# SUMMARY
# ==============================================================================
print("\n" + "=" * 75)
print(f"RESULTS SUMMARY: {passed_tests} PASSED, {failed_tests} FAILED")
print("=" * 75)

if failed_tests > 0:
    sys.exit(1)
else:
    print("ALL TESTS PASSED SUCCESSFULLY! End-to-end execution verified.\n")
    sys.exit(0)
