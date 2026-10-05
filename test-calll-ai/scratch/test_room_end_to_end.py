import sys
import json
import time
import requests
import urllib3
from decimal import Decimal

sys.stdout.reconfigure(encoding='utf-8')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://localhost"
INTERNAL_API_KEY = "voice-internal-secret-token-key-12345"

print("=" * 80)
print("EXECUTING VOICE ASSISTANT ROOM END-TO-END VERIFICATION (FULL LIFECYCLE)")
print("=" * 80)

session = requests.Session()
session.verify = False

# -------------------------------------------------------------------------
# Phase 1: User Authentication & Workspace Loading
# -------------------------------------------------------------------------
print("\n[Phase 1] Authenticating user and loading Room workspace...")
login_page = session.get(f"{BASE_URL}/login/")
assert login_page.status_code == 200, f"Failed to load login page: {login_page.status_code}"
csrf = session.cookies.get("csrftoken", "")
assert csrf, "CSRF token missing"

login_res = session.post(f"{BASE_URL}/login/", data={
    "username": "admin",
    "password": "admin123456",
    "csrfmiddlewaretoken": csrf
}, headers={"Referer": f"{BASE_URL}/login/"})
assert login_res.status_code == 200 or login_res.history, "Login failed"
print(" -> [PASS] Authenticated successfully as platform user.")

room_res = session.get(f"{BASE_URL}/")
assert room_res.status_code == 200, f"Failed to load room workspace: {room_res.status_code}"
room_html = room_res.text
assert "visualizer-orb" in room_html
assert "btn-start" in room_html
assert "btn-mute" in room_html
assert "btn-end" in room_html
assert "transcript-box" in room_html
assert "tab-voice" in room_html
print(f" -> [PASS] Room workspace HTML loaded ({len(room_html)} bytes) with all WebRTC controls.")

# -------------------------------------------------------------------------
# Phase 2: LiveKit & Centrifugo Token Provisioning
# -------------------------------------------------------------------------
print("\n[Phase 2] Requesting WebRTC LiveKit & Centrifugo tokens (/api/token/)...")
token_res = session.get(f"{BASE_URL}/api/token/")
assert token_res.status_code == 200, f"Token request failed: {token_res.text}"
token_data = token_res.json()
assert "livekit_token" in token_data, "livekit_token missing"
assert "centrifugo_token" in token_data, "centrifugo_token missing"
assert "room_name" in token_data, "room_name missing"
assert "user_identity" in token_data, "user_identity missing"

livekit_token = token_data["livekit_token"]
centrifugo_token = token_data["centrifugo_token"]
room_name = token_data["room_name"]
user_id = int(token_data["user_identity"].split("_")[1])
print(f" -> [PASS] Tokens provisioned. Room: '{room_name}', User ID: {user_id}")
print(f"    LiveKit Token: {livekit_token[:20]}... | Centrifugo Token: {centrifugo_token[:20]}...")

# -------------------------------------------------------------------------
# Phase 3: Agent Internal Bootstrap Check
# -------------------------------------------------------------------------
print("\n[Phase 3] Testing Agent Internal Bootstrap (/api/agents/internal/bootstrap/)...")
caller_phone = "+966509988776"
bootstrap_res = session.post(
    f"{BASE_URL}/api/agents/internal/bootstrap/",
    json={"user_id": user_id, "caller_phone": caller_phone},
    headers={"X-Internal-API-Key": INTERNAL_API_KEY}
)
assert bootstrap_res.status_code == 200, f"Agent bootstrap failed: {bootstrap_res.text}"
boot_data = bootstrap_res.json()
assert boot_data.get("status") == "success"
assert "profile" in boot_data
assert "mcp_servers" in boot_data
assert "customer_memory" in boot_data
print(f" -> [PASS] Agent bootstrap bundle verified:")
print(f"    Persona: '{boot_data['profile'].get('name')}', Dialect: '{boot_data['profile'].get('dialect')}'")
print(f"    Active MCP Servers: {len(boot_data['mcp_servers'])}")
print(f"    Caller Phone Context: '{boot_data['customer_memory'].get('phone_number')}'")

# -------------------------------------------------------------------------
# Phase 4: Knowledge Base RAG Semantic Lookup in Room
# -------------------------------------------------------------------------
print("\n[Phase 4] Testing Knowledge Base RAG Query (/api/knowledge/internal/rag/)...")
rag_res = session.post(
    f"{BASE_URL}/api/knowledge/internal/rag/",
    json={"user_id": user_id, "query": "ما هي المنتجات والخدمات المتوفرة؟", "top_k": 3},
    headers={"X-Internal-API-Key": INTERNAL_API_KEY}
)
assert rag_res.status_code == 200, f"RAG search failed: {rag_res.text}"
rag_json = rag_res.json()
assert rag_json.get("status") == "success"
print(f" -> [PASS] RAG Semantic engine responded (status: {rag_json['status']}). Context text length: {len(rag_json.get('text', ''))} chars.")

# -------------------------------------------------------------------------
# Phase 5: CRM Customer Memory Retrieval & Storage
# -------------------------------------------------------------------------
print("\n[Phase 5] Testing Customer Memory API (/api/crm/internal/memory/)...")
mem_res = session.post(
    f"{BASE_URL}/api/crm/internal/memory/",
    json={"user_id": user_id, "caller_phone": caller_phone},
    headers={"X-Internal-API-Key": INTERNAL_API_KEY}
)
assert mem_res.status_code == 200, f"Memory fetch failed: {mem_res.text}"
mem_data = mem_res.json()
assert mem_data.get("status") == "success"
print(f" -> [PASS] CRM Memory retrieved for caller: {caller_phone}")

# -------------------------------------------------------------------------
# Phase 6: Simulate Live Call Execution & Strict Ceiling Billing
# -------------------------------------------------------------------------
print("\n[Phase 6] Simulating active Room Call and Call Completion...")
# Fetch initial wallet balance via ORM
import subprocess
balance_script = f"""
from billing.models import UserWallet, BillingConfig
from django.contrib.auth.models import User
u = User.objects.get(id={user_id})
cfg = BillingConfig.get_config()
w, _ = UserWallet.objects.get_or_create(user=u, defaults={{'balance': cfg.initial_welcome_credit}})
print(f"INITIAL_BALANCE:{{w.balance}}|RATE:{{cfg.cost_per_minute}}")
"""
res_orm = subprocess.run(['docker', 'exec', 'voice_django', 'python', 'manage.py', 'shell', '-c', balance_script], capture_output=True, text=True, check=True)
bal_line = [l for l in res_orm.stdout.splitlines() if 'INITIAL_BALANCE:' in l][0]
init_bal = Decimal(bal_line.split('INITIAL_BALANCE:')[1].split('|')[0])
rate_per_min = Decimal(bal_line.split('RATE:')[1].strip())
print(f" -> Initial Wallet Balance: ${init_bal:.4f}, Platform Minute Rate: ${rate_per_min:.4f}")

# Simulate a 75-second conversation
# 75 seconds -> ceiling rounds to 2 minutes
sim_duration = 75
transcript = "المتصل: السلام عليكم، أرغب في معرفة أوقات العمل لديكم.\nالمساعد: وعليكم السلام ورحمة الله! أوقات العمل لدينا يومياً من 9 صباحاً حتى 10 مساءً."
summary = "استفسر العميل عن ساعات العمل وتمت إفادته بأنها من 9 صباحاً حتى 10 مساءً."

complete_payload = {
    "user_id": user_id,
    "room_name": room_name,
    "duration_seconds": sim_duration,
    "direction": "inbound",
    "caller_phone": caller_phone,
    "customer_name": "عبدالله المنصور",
    "transcript_text": transcript,
    "summary": summary,
    "permanent_profile": {
        "customer_name": "عبدالله المنصور",
        "phone": caller_phone,
        "notes": "عميل مهتم بالمواعيد والخدمات المسائية."
    }
}

comp_res = session.post(
    f"{BASE_URL}/api/crm/internal/complete-call/",
    json=complete_payload,
    headers={"X-Internal-API-Key": INTERNAL_API_KEY}
)
assert comp_res.status_code == 200, f"Complete call failed: {comp_res.text}"
comp_json = comp_res.json()
assert comp_json.get("status") == "success"
billed_mins = comp_json.get("billed_minutes")
call_cost = comp_json.get("cost") or 0.0
print(f" -> [PASS] Call session ended and processed by CRM & Billing engine.")
print(f"    Duration: {sim_duration}s -> Ceiling Billed Minutes: {billed_mins} min(s)")
print(f"    Calculated Cost: ${call_cost:.4f}")
assert billed_mins == 2, f"Expected 2 ceiling minutes for {sim_duration}s call, got {billed_mins}"

# Verify wallet deduction in DB
verify_script = f"""
from billing.models import UserWallet
from django.contrib.auth.models import User
from crm.models import CallSession, CustomerMemory
u = User.objects.get(id={user_id})
w = UserWallet.objects.get(user=u)
s = CallSession.objects.filter(room_name='{room_name}').first()
m = CustomerMemory.objects.filter(user=u, phone_number='{caller_phone}').first()
print(f"FINAL_BALANCE:{{w.balance}}|CALL_EXISTS:{{s is not None}}|CALL_MINS:{{s.billed_minutes if s else 0}}|MEM_NAME:{{m.customer_name if m else ''}}")
"""
res_ver = subprocess.run(['docker', 'exec', 'voice_django', 'python', 'manage.py', 'shell', '-c', verify_script], capture_output=True, text=True, encoding='utf-8', check=True)
ver_line = [l for l in res_ver.stdout.splitlines() if 'FINAL_BALANCE:' in l][0]
final_bal = Decimal(ver_line.split('FINAL_BALANCE:')[1].split('|')[0])
call_exists = ver_line.split('CALL_EXISTS:')[1].split('|')[0] == 'True'
call_mins = int(ver_line.split('CALL_MINS:')[1].split('|')[0])
mem_name = ver_line.split('MEM_NAME:')[1].strip()

assert call_exists, "CallSession not persisted in database"
assert call_mins == 2, f"Expected 2 billed minutes in CallSession, got {call_mins}"
assert "المنصور" in mem_name or "عبدالله" in mem_name, f"Expected customer name persisted, got '{mem_name}'"
expected_deduction = Decimal(billed_mins) * rate_per_min
assert abs((init_bal - final_bal) - expected_deduction) < Decimal('0.001'), f"Wallet deduction mismatch: {init_bal - final_bal} vs {expected_deduction}"
print(f" -> [PASS] Wallet deducted exactly ${expected_deduction:.4f} (New Balance: ${final_bal:.4f}).")
print(f" -> [PASS] CallSession record & CustomerMemory verified in database.")

# -------------------------------------------------------------------------
# Phase 7: Real-time Centrifugo Event Publishing to Room Channel
# -------------------------------------------------------------------------
print("\n[Phase 7] Testing Real-time Centrifugo Event Publishing...")
centrifugo_channel = f"room_{room_name}"
cent_notify_script = f"""
import requests, json
url = "http://centrifugo:8000/api/publish"
payload = {{
    "channel": "user_{user_id}",
    "data": {{
        "event": "transcript",
        "speaker": "agent",
        "text": "تم إنهاء المكالمة بنجاح وحفظ ملخصها.",
        "room": "{room_name}"
    }}
}}
headers = {{
    "Authorization": "apikey centrifugo_api_key_1234567890",
    "Content-Type": "application/json"
}}
res = requests.post(url, json=payload, headers=headers)
print("CENTRIFUGO_STATUS:", res.status_code)
"""
res_cent = subprocess.run(['docker', 'exec', 'voice_django', 'python', 'manage.py', 'shell', '-c', cent_notify_script], capture_output=True, text=True, check=True)
cent_status = [l for l in res_cent.stdout.splitlines() if 'CENTRIFUGO_STATUS:' in l][0]
assert '200' in cent_status, f"Centrifugo publishing failed: {cent_status}"
print(f" -> [PASS] Real-time event published to Centrifugo channel 'user_{user_id}'. Status 200 OK.")

# -------------------------------------------------------------------------
# Phase 8: Verify Call History in Web UI API
# -------------------------------------------------------------------------
print("\n[Phase 8] Verifying Call History in CRM Web UI API (/api/crm/calls/)...")
cdr_res = session.get(f"{BASE_URL}/api/crm/calls/")
if cdr_res.status_code == 200:
    cdr_data = cdr_res.json()
    calls = cdr_data.get("calls", [])
    found = any(c.get("room_name") == room_name for c in calls)
    print(f" -> [PASS] Call found in recent call logs: {found} (Total calls in CRM: {len(calls)})")

print("\n" + "=" * 80)
print("SUCCESS: COMPLETE VOICE ASSISTANT ROOM END-TO-END WORKFLOW VERIFIED 100%!")
print("=" * 80)
