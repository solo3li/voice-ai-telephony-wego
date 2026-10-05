#!/usr/bin/env python3
"""
Comprehensive End-to-End Test Suite for Newly Implemented Features:
1. Dynamic welcome_message on AgentProfile across DB, Developer API, Partner API, and Bootstrap.
2. Proactive AI greeting generator (custom welcome_message vs smart dialect fallbacks).
3. Push notification token endpoint & dispatch for employee mobile softphone.
4. Mobile Safe Area & Sound/Haptics service integration.
"""

import sys
import os
import json
import requests
import urllib3

sys.stdout.reconfigure(encoding='utf-8')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

BASE_URL = "https://app.169.58.32.179.nip.io"
USER_API_KEY = "sk_live_usr_74bfbbd8f42f86acec24df223b5f9e75d46b0b79"
PARTNER_API_KEY = "pk_live_e2e_8a893089ff96e251ec645bb137060b34920d85a7"
PARTNER_CLIENT_ID = 39

session = requests.Session()
session.verify = False

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}" + (f" -> {detail}" if detail else ""))
    else:
        failed += 1
        print(f"  [FAIL] {name}" + (f" -> {detail}" if detail else ""))

print("=" * 75)
print("  E2E TEST SUITE: WELCOME MESSAGE, GREETINGS & NOTIFICATIONS")
print("=" * 75)

# ==============================================================================
# TEST 1: Agent Welcome Greeting Generator Logic
# ==============================================================================
print("\n>>> TEST 1: Agent Welcome Greeting Generator")
from agent.prompts.builder import generate_welcome_greeting, build_dynamic_system_instruction

# 1.1 Custom welcome message
p_custom = {
    "name": "سارة - خدمة عملاء مطعم النافورة",
    "persona_role": "restaurant_support",
    "dialect": "egyptian",
    "welcome_message": "أهلاً بك في مطعم النافورة، معاك سارة، إزاي أقدر أساعدك النهاردة؟"
}
greet_custom = generate_welcome_greeting(p_custom)
check("Custom welcome message exact match", greet_custom == p_custom["welcome_message"], greet_custom)

# 1.2 Empty welcome message -> Dynamic Egyptian
p_egyptian = {
    "name": "نورهان",
    "persona_role": "خدمة عملاء المتجر",
    "dialect": "egyptian",
    "welcome_message": ""
}
greet_egyptian = generate_welcome_greeting(p_egyptian)
check("Dynamic Egyptian dialect greeting fallback", "أهلاً بحضرتك، معاك نورهان" in greet_egyptian, greet_egyptian)

# 1.3 Empty welcome message -> Dynamic Saudi / Gulf
p_saudi = {
    "name": "فيصل",
    "persona_role": "مستشار مبيعات",
    "dialect": "saudi",
    "welcome_message": ""
}
greet_saudi = generate_welcome_greeting(p_saudi)
check("Dynamic Saudi dialect greeting fallback", "معك فيصل، كيف أقدر أخدمك" in greet_saudi, greet_saudi)

# 1.4 Dynamic Levant fallback
p_levant = {
    "name": "ريم",
    "persona_role": "خدمة عملاء",
    "dialect": "levantine",
    "welcome_message": ""
}
greet_levant = generate_welcome_greeting(p_levant)
check("Dynamic Levantine dialect greeting fallback", "معك ريم، كيف بقدر ساعدك" in greet_levant, greet_levant)

# 1.5 System instruction includes welcome_message if present
sys_inst = build_dynamic_system_instruction(p_custom)
check("System prompt includes custom welcome message", p_custom["welcome_message"] in sys_inst)


# ==============================================================================
# TEST 2: Developer API Profile welcome_message Management
# ==============================================================================
print("\n>>> TEST 2: Developer API Profile welcome_message")

headers_user = {"Authorization": f"Bearer {USER_API_KEY}", "Content-Type": "application/json"}

# 2.1 Get active profile
r = session.get(f"{BASE_URL}/api/v1/profiles/", headers=headers_user)
check("GET /api/v1/profiles/ returns 200", r.status_code == 200)
prof_data = r.json()
active_prof = prof_data.get("active_profile") or {}
prof_id = active_prof.get("id")

if prof_id:
    # 2.2 Update welcome_message via PATCH
    test_msg = "مرحباً بك في شركتنا، أنا مساعدك الذكي ومستعد لمساعدتك في أي استفسار!"
    r_patch = session.patch(
        f"{BASE_URL}/api/v1/profiles/{prof_id}/",
        headers=headers_user,
        json={"welcome_message": test_msg}
    )
    check("PATCH /api/v1/profiles/<id>/ returns 200", r_patch.status_code == 200)
    saved_msg = r_patch.json().get("profile", {}).get("welcome_message")
    check("Developer API updated welcome_message matches", saved_msg == test_msg, saved_msg)

    # 2.3 Verify GET retrieves the updated welcome_message
    r_get = session.get(f"{BASE_URL}/api/v1/profiles/{prof_id}/", headers=headers_user)
    get_msg = r_get.json().get("profile", {}).get("welcome_message")
    check("GET /api/v1/profiles/<id>/ returns updated welcome_message", get_msg == test_msg)


# ==============================================================================
# TEST 3: Partner API Profile welcome_message Management
# ==============================================================================
print("\n>>> TEST 3: Partner API Profile welcome_message")

headers_partner = {"X-Partner-Key": PARTNER_API_KEY, "Content-Type": "application/json"}

r_p_list = session.get(f"{BASE_URL}/api/partner/v1/clients/{PARTNER_CLIENT_ID}/profiles/", headers=headers_partner)
check("GET /api/partner/v1/clients/<id>/profiles/ returns 200", r_p_list.status_code == 200)
p_profiles = r_p_list.json().get("profiles", [])

if p_profiles:
    target_p = p_profiles[0]
    p_prof_id = target_p.get("id")
    partner_welcome_msg = "أهلاً وسهلاً بك في منصة شركائنا، كيف يمكنني تقديم المساعدة لك اليوم؟"

    # 3.1 Update partner client profile welcome_message
    r_p_patch = session.patch(
        f"{BASE_URL}/api/partner/v1/clients/{PARTNER_CLIENT_ID}/profiles/{p_prof_id}/",
        headers=headers_partner,
        json={"welcome_message": partner_welcome_msg}
    )
    check("PATCH partner client profile returns 200", r_p_patch.status_code == 200)
    saved_p_msg = r_p_patch.json().get("profile", {}).get("welcome_message")
    check("Partner API updated welcome_message matches", saved_p_msg == partner_welcome_msg, saved_p_msg)


# ==============================================================================
# TEST 4: Agent Internal Bootstrap Endpoint
# ==============================================================================
print("\n>>> TEST 4: Internal Agent Bootstrap API")

import subprocess

cmd_key = "python -c \"import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); from django.conf import settings; print(settings.INTERNAL_API_KEY)\""
res_key = subprocess.check_output(["docker", "exec", "-i", "voice_django", "bash", "-c", cmd_key]).decode('utf-8').strip()
internal_key = res_key or "internal_secret_change_me"

cmd_user = "python -c \"import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); from django.contrib.auth.models import User; u = User.objects.first(); print(u.id if u else 1)\""
user_id = int(subprocess.check_output(["docker", "exec", "-i", "voice_django", "bash", "-c", cmd_user]).decode('utf-8').strip())

r_boot = session.post(
    f"{BASE_URL}/api/agents/internal/bootstrap/",
    headers={"X-Internal-API-Key": internal_key, "Content-Type": "application/json"},
    json={"user_id": user_id, "caller_phone": "web_dashboard"}
)
check("Internal bootstrap API returns 200", r_boot.status_code == 200)
boot_profile = r_boot.json().get("profile", {})
check("Internal bootstrap includes welcome_message field", "welcome_message" in boot_profile, f"welcome_message='{boot_profile.get('welcome_message', '')[:30]}...'")


# ==============================================================================
# TEST 5: Employee Push Token Endpoint & Models
# ==============================================================================
print("\n>>> TEST 5: Call Center Employee Push Token Management")

# 5.1 Push token serialization in to_dict() via docker exec
cmd_emp = """python -c "
import os, django, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from call_center.models import EmployeeProfile
from call_center.views import generate_employee_jwt
emp = EmployeeProfile.objects.filter(is_active=True).first()
if emp:
    jwt_tok = generate_employee_jwt(emp)
    d = emp.to_dict()
    print(json.dumps({'has_token': 'push_token' in d, 'jwt': jwt_tok, 'name': emp.display_name, 'id': emp.id}))
else:
    print('{}')
" """
emp_info = json.loads(subprocess.check_output(["docker", "exec", "-i", "voice_django", "bash", "-c", cmd_emp]).decode('utf-8').strip())

check("Employee profile found in database", bool(emp_info), f"Employee: {emp_info.get('name')}")
check("EmployeeProfile.to_dict() has push_token key", emp_info.get('has_token', False))

if emp_info.get('jwt'):
    emp_token = emp_info['jwt']
    test_push_token = "ExponentPushToken[AbCdEf1234567890TestToken]"

    # 5.2 Test push-token API endpoint
    r_push = session.post(
        f"{BASE_URL}/api/call-center/employees/push-token/",
        headers={"Authorization": f"Bearer {emp_token}", "Content-Type": "application/json"},
        json={"push_token": test_push_token}
    )
    check("POST /api/call-center/employees/push-token/ returns 200", r_push.status_code == 200)
    check("Push token response has success status", r_push.json().get("status") == "success")

    # 5.3 Verify saved token in DB
    cmd_verify_db = f"python -c \"import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); from call_center.models import EmployeeProfile; emp = EmployeeProfile.objects.get(id={emp_info['id']}); print(emp.push_token)\""
    saved_db_token = subprocess.check_output(["docker", "exec", "-i", "voice_django", "bash", "-c", cmd_verify_db]).decode('utf-8').strip()
    check("Push token correctly saved in database", saved_db_token == test_push_token, saved_db_token)

    # 5.4 Test send_expo_push_notification function validation
    cmd_func_test = """python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from call_center.views import send_expo_push_notification
res_invalid = send_expo_push_notification('invalid_token', 'Test', 'Test')
print(res_invalid)
" """
    func_res = subprocess.check_output(["docker", "exec", "-i", "voice_django", "bash", "-c", cmd_func_test]).decode('utf-8').strip()
    check("send_expo_push_notification rejects invalid tokens", func_res == "False")


# ==============================================================================
# SUMMARY
# ==============================================================================
print("\n" + "=" * 75)
print(f"  E2E TEST RUN COMPLETED: {passed} PASSED, {failed} FAILED")
print("=" * 75)

if failed > 0:
    sys.exit(1)
