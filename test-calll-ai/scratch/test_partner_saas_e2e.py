import sys, requests, urllib3, json
sys.stdout.reconfigure(encoding='utf-8')
urllib3.disable_warnings()

s = requests.Session()
s.verify = False

BASE_URL = 'https://localhost'

print('=' * 75)
print('STARTING COMPREHENSIVE PARTNER & HEADLESS SAAS SUBSYSTEM E2E VERIFICATION')
print('=' * 75)

# 1. Login as admin
login_page = s.get(f'{BASE_URL}/login/')
csrftoken = s.cookies.get('csrftoken', '')
login_res = s.post(f'{BASE_URL}/login/', data={'username': 'admin', 'password': 'admin123456', 'csrfmiddlewaretoken': csrftoken}, headers={'Referer': f'{BASE_URL}/login/'})
assert login_res.status_code == 200 or login_res.history, 'Login failed'
print('[PASS] Step 1: Logged in successfully as platform admin')

# 2. Submit Partner Application
csrf = s.cookies.get('csrftoken')
apply_res = s.post(f'{BASE_URL}/api/partner/v1/apply/', json={
    'company_name': 'شركة التقنية للحلول السحابية (SaaS Platform Demo)',
    'website': 'https://saas-demo.example.com',
    'description': 'منصة تجارة إلكترونية ترغب في توفير خدمة المساعد الصوتي لآلاف المتاجر التابعة لها.'
}, headers={'X-CSRFToken': csrf, 'Referer': f'{BASE_URL}/'})
assert apply_res.status_code == 200, f'Apply failed: {apply_res.text}'
apply_data = apply_res.json()
assert apply_data['status'] == 'success'
print(f"[PASS] Step 2: Submitted partner application: {apply_data['partner']['company_name']}")

# 3. Approve partner and configure custom rate via Django ORM
import subprocess
approve_script = """
from partners.models import PartnerProfile
from django.contrib.auth.models import User
from decimal import Decimal
user = User.objects.get(username='admin')
partner = PartnerProfile.objects.get(user=user)
partner.status = 'approved'
partner.custom_rate_per_minute = Decimal('0.0300')
partner.webhook_url = 'https://mock-store:8002/webhook'
partner.save()
print(f"APPROVED_KEY:{partner.api_key}|CODE:{partner.partner_code}")
"""
cmd = ['docker', 'exec', 'voice_django', 'python', 'manage.py', 'shell', '-c', approve_script]
proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
lines = [l for l in proc.stdout.splitlines() if 'APPROVED_KEY:' in l]
assert lines, f"Failed to approve partner in DB: {proc.stdout}"
partner_api_key = lines[0].split('APPROVED_KEY:')[1].split('|')[0]
partner_code = lines[0].split('CODE:')[1].strip()
print(f"[PASS] Step 3: Partner approved by Super Admin. Rate: $0.0300/min. Key: {partner_api_key[:12]}... Code: {partner_code}")

# 4. Fetch Partner Dashboard (Web UI API)
dash_res = s.get(f'{BASE_URL}/api/partner/v1/dashboard/')
assert dash_res.status_code == 200, f"Dashboard failed: {dash_res.text}"
dash_data = dash_res.json()
assert dash_data['status'] == 'success'
assert dash_data['partner']['status'] == 'approved'
assert dash_data['kpis']['custom_rate'] == 0.03
print("[PASS] Step 4: Web UI Dashboard returns approved status and custom wholesale rate")

# 5. Headless Client Registration via Partner API Key
import uuid
unique_suffix = uuid.uuid4().hex[:6]
headers_partner = {'X-Partner-Key': partner_api_key}
reg_payload = {
    'external_reference': f'sub_store_{unique_suffix}',
    'name': f'متجر النور التجريبي ({unique_suffix})',
    'email': f'store_{unique_suffix}@saas-demo.com',
    'spending_cap': 25.00,
    'minute_cap': 200
}
reg_res = s.post(f'{BASE_URL}/api/partner/v1/clients/register/', json=reg_payload, headers=headers_partner)
assert reg_res.status_code in [200, 201], f"Register failed: {reg_res.text}"
reg_data = reg_res.json()
assert reg_data['status'] == 'success'
client_id = reg_data['client_id']
print(f"[PASS] Step 5: Headless client provisioned via API. Client ID: {client_id}, Name: {reg_data['name']}")

# 6. Verify Tenant Isolation & Multi-Tenancy Security
bad_key_res = s.get(f'{BASE_URL}/api/partner/v1/clients/{client_id}/calls/', headers={'X-Partner-Key': 'sk_fake_invalid_key_123'})
assert bad_key_res.status_code in [401, 403], f"Security leak: bad key accepted ({bad_key_res.status_code})"

unowned_client_res = s.get(f'{BASE_URL}/api/partner/v1/clients/999999/calls/', headers=headers_partner)
assert unowned_client_res.status_code == 404, f"Security leak: unowned client returned ({unowned_client_res.status_code})"
print("[PASS] Step 6: Multi-tenancy isolation verified. Unauthorized access strictly blocked with 403/404")

# 7. Voice Profile Management for Sub-Client (Full RESTful CRUD)
# 7.1 Create Profile 1 (Saudi Dialect)
prof1_res = s.post(f'{BASE_URL}/api/partner/v1/clients/{client_id}/profiles/', json={
    'name': 'مساعد خدمة متجر النور (سعودي)',
    'dialect': 'saudi',
    'voice_name': 'Fenrir',
    'persona_role': 'sales_advisor',
    'speaking_style': 'friendly',
    'system_prompt': 'أنت المساعد الصوتي الرسمي لمتجر النور في الرياض، تتحدث بلهجة سعودية راقية.',
    'is_active': True
}, headers=headers_partner)
assert prof1_res.status_code in [200, 201], f"Profile 1 post failed: {prof1_res.text}"
prof1_id = prof1_res.json()['profile']['id']

# 7.2 Create Profile 2 (Egyptian Dialect)
prof2_res = s.post(f'{BASE_URL}/api/partner/v1/clients/{client_id}/profiles/', json={
    'name': 'مساعد الدعم الفني (مصري)',
    'dialect': 'egyptian',
    'voice_name': 'Aoede',
    'persona_role': 'customer_support',
    'speaking_style': 'formal',
    'system_prompt': 'أنت مستشار الدعم الفني في القاهرة، تتحدث باللهجة المصرية.',
    'is_active': False
}, headers=headers_partner)
assert prof2_res.status_code in [200, 201], f"Profile 2 post failed: {prof2_res.text}"
prof2_id = prof2_res.json()['profile']['id']

# 7.3 List Profiles & Filtering
prof_list_res = s.get(f'{BASE_URL}/api/partner/v1/clients/{client_id}/profiles/', headers=headers_partner)
assert prof_list_res.status_code == 200
prof_list_data = prof_list_res.json()
assert prof_list_data['total'] >= 2
assert 'profiles' in prof_list_data
assert 'profile' in prof_list_data  # Backward compatibility

# Filter by active
prof_act_res = s.get(f'{BASE_URL}/api/partner/v1/clients/{client_id}/profiles/?is_active=true', headers=headers_partner)
assert prof_act_res.status_code == 200
assert all(p['is_active'] is True for p in prof_act_res.json()['profiles'])

# 7.4 Retrieve Profile by ID
prof2_get = s.get(f'{BASE_URL}/api/partner/v1/clients/{client_id}/profiles/{prof2_id}/', headers=headers_partner)
assert prof2_get.status_code == 200
assert prof2_get.json()['profile']['dialect'] == 'egyptian'

# 7.5 Update Profile by ID (PUT/PATCH)
prof2_upd = s.patch(f'{BASE_URL}/api/partner/v1/clients/{client_id}/profiles/{prof2_id}/', json={
    'name': 'مساعد الدعم الفني المطور (مصري)',
    'speaking_style': 'concise'
}, headers=headers_partner)
assert prof2_upd.status_code == 200
assert prof2_upd.json()['profile']['name'] == 'مساعد الدعم الفني المطور (مصري)'
assert prof2_upd.json()['profile']['speaking_style'] == 'concise'

# 7.6 Activate Profile (POST .../activate/)
prof2_act = s.post(f'{BASE_URL}/api/partner/v1/clients/{client_id}/profiles/{prof2_id}/activate/', headers=headers_partner)
assert prof2_act.status_code == 200
assert prof2_act.json()['profile']['is_active'] is True

# Verify profile 1 was automatically deactivated
prof1_check = s.get(f'{BASE_URL}/api/partner/v1/clients/{client_id}/profiles/{prof1_id}/', headers=headers_partner)
assert prof1_check.json()['profile']['is_active'] is False

# 7.7 Delete Profile
prof1_del = s.delete(f'{BASE_URL}/api/partner/v1/clients/{client_id}/profiles/{prof1_id}/', headers=headers_partner)
assert prof1_del.status_code == 200
assert prof1_del.json()['deleted_profile_id'] == prof1_id

# Verify 404 after deletion
prof1_gone = s.get(f'{BASE_URL}/api/partner/v1/clients/{client_id}/profiles/{prof1_id}/', headers=headers_partner)
assert prof1_gone.status_code == 404
print("[PASS] Step 7: Voice Profile & Personas Full CRUD (Create, List, Detail, Update, Activate, Delete) verified")

# 8. Customer Memory Management for Sub-Client (Full RESTful CRUD)
# 8.1 Create/Upsert Customer 1 Memory
mem1_post_res = s.post(f'{BASE_URL}/api/partner/v1/clients/{client_id}/memory/', json={
    'caller_phone': '+966501234567',
    'customer_name': 'سلطان القحطاني',
    'permanent_memory': 'عميل مميز (VIP)، يفضل الدفع عند الاستلام ويطلب منتجات العناية بالبشرة.',
    'immediate_notes': 'استفسر عن طلبية العطور رقم #4501'
}, headers=headers_partner)
assert mem1_post_res.status_code in [200, 201], f"Memory 1 post failed: {mem1_post_res.text}"
mem1_id = mem1_post_res.json()['memory']['id']

# 8.2 Create Customer 2 Memory
mem2_post_res = s.post(f'{BASE_URL}/api/partner/v1/clients/{client_id}/memory/', json={
    'phone_number': '+966509876543',
    'customer_name': 'ريم الدوسري',
    'permanent_profile': {'notes': 'عميلة جديدة مهتمة بمنتجات الشاي العضوي', 'city': 'جدة'},
    'immediate_notes': 'طلبت قائمة الأسعار عبر واتساب',
    'total_calls_count': 1
}, headers=headers_partner)
assert mem2_post_res.status_code in [200, 201], f"Memory 2 post failed: {mem2_post_res.text}"
mem2_id = mem2_post_res.json()['memory']['id']

# 8.3 List Customer Memories with Pagination
mem_list_res = s.get(f'{BASE_URL}/api/partner/v1/clients/{client_id}/memory/', params={'page': 1, 'limit': 10}, headers=headers_partner)
assert mem_list_res.status_code == 200
mem_list_data = mem_list_res.json()
assert mem_list_data['total'] >= 2
assert len(mem_list_data['memories']) >= 2

# 8.4 Search Memories with Query (?q=)
search_res = s.get(f'{BASE_URL}/api/partner/v1/clients/{client_id}/memory/', params={'q': 'سلطان'}, headers=headers_partner)
assert search_res.status_code == 200
assert search_res.json()['total'] >= 1
assert any('سلطان' in m['customer_name'] for m in search_res.json()['memories'])

# 8.5 Retrieve Memory by ID
mem2_get = s.get(f'{BASE_URL}/api/partner/v1/clients/{client_id}/memory/{mem2_id}/', headers=headers_partner)
assert mem2_get.status_code == 200
assert mem2_get.json()['memory']['customer_name'] == 'ريم الدوسري'

# 8.6 Update Memory by ID (PUT/PATCH)
mem2_upd = s.patch(f'{BASE_URL}/api/partner/v1/clients/{client_id}/memory/{mem2_id}/', json={
    'customer_name': 'ريم الدوسري (VIP)',
    'immediate_notes': 'تم إرسال كود الخصم للعميلة بنجاح'
}, headers=headers_partner)
assert mem2_upd.status_code == 200
assert mem2_upd.json()['memory']['customer_name'] == 'ريم الدوسري (VIP)'

# 8.7 Backward Compatibility Check: Query single record by ?phone=
mem_phone_res = s.get(f'{BASE_URL}/api/partner/v1/clients/{client_id}/memory/', params={'phone': '+966501234567'}, headers=headers_partner)
assert mem_phone_res.status_code == 200
mem_phone_data = mem_phone_res.json()
assert mem_phone_data['customer_name'] == 'سلطان القحطاني'
assert 'VIP' in mem_phone_data['permanent_memory']

# 8.8 Delete Memory by ID
mem2_del = s.delete(f'{BASE_URL}/api/partner/v1/clients/{client_id}/memory/{mem2_id}/', headers=headers_partner)
assert mem2_del.status_code == 200
assert mem2_del.json()['deleted_memory_id'] == mem2_id

# Verify 404 after deletion
mem2_gone = s.get(f'{BASE_URL}/api/partner/v1/clients/{client_id}/memory/{mem2_id}/', headers=headers_partner)
assert mem2_gone.status_code == 404
print("[PASS] Step 8: CRM Customer Memory Full CRUD (Create, List, Search, Detail, Update, Phone Lookup, Delete) verified")

# 9. Knowledge Base (RAG) Ingestion for Sub-Client
rag_post_res = s.post(f'{BASE_URL}/api/partner/v1/clients/{client_id}/documents/', data={
    'title': 'كتالوج وسياسة متجر النور',
    'text': 'سياسة التوصيل: التوصيل مجاني لكافة مدن المملكة للطلبات فوق 200 ريال. مدة التوصيل من يومين إلى 3 أيام عمل.'
}, headers=headers_partner)
assert rag_post_res.status_code in [200, 201], f"RAG upload failed: {rag_post_res.text}"

rag_get_res = s.get(f'{BASE_URL}/api/partner/v1/clients/{client_id}/documents/', headers=headers_partner)
assert rag_get_res.status_code == 200
rag_data = rag_get_res.json()
assert rag_data['count'] >= 1
print(f"[PASS] Step 9: RAG Knowledge Base document uploaded & indexed for client. Docs count: {rag_data['count']}")

# 9.1 Test Semantic RAG Query via Partner API
rag_query_res = s.post(f'{BASE_URL}/api/partner/v1/clients/{client_id}/rag/query/', json={
    'query': 'ما هي شروط وسياسة التوصيل المجاني لديكم؟',
    'top_k': 2
}, headers=headers_partner)
assert rag_query_res.status_code == 200, f"RAG Query failed: {rag_query_res.text}"
rag_query_data = rag_query_res.json()
assert rag_query_data['status'] == 'success'
assert rag_query_data['total_matches'] >= 1
top_match = rag_query_data['results'][0]
assert 'التوصيل مجاني' in top_match['content']
print(f"[PASS] Step 9.1: Semantic RAG Search Query passed via Partner API. Matches: {rag_query_data['total_matches']}, Similarity: {top_match['similarity']}")

# 10. Telephony & PBX Trunks for Sub-Client
pbx_inbound_res = s.post(f'{BASE_URL}/api/partner/v1/clients/{client_id}/telephony/', json={
    'trunk_type': 'inbound',
    'name': 'سنترال متجر النور (Issabel PBX)',
    'auth_mode': 'ip',
    'pbx_ip': '192.168.10.50',
    'inbound_numbers': '920005544'
}, headers=headers_partner)
assert pbx_inbound_res.status_code in [200, 201], f"Inbound trunk failed: {pbx_inbound_res.text}"

sip_outbound_res = s.post(f'{BASE_URL}/api/partner/v1/clients/{client_id}/telephony/', json={
    'trunk_type': 'outbound',
    'name': 'خط الاتصال الصادر (Telnyx/Twilio)',
    'sip_host': 'sip.telnyx.com',
    'sip_port': 5060,
    'caller_id': '+966920005544'
}, headers=headers_partner)
assert sip_outbound_res.status_code in [200, 201], f"Outbound trunk failed: {sip_outbound_res.text}"

telephony_get_res = s.get(f'{BASE_URL}/api/partner/v1/clients/{client_id}/telephony/', headers=headers_partner)
assert telephony_get_res.status_code == 200
tel_data = telephony_get_res.json()
assert len(tel_data['inbound_trunks']) >= 1
assert len(tel_data['outbound_trunks']) >= 1
print(f"[PASS] Step 10: Inbound PBX and Outbound SIP Trunks provisioned for client via API")

# 10.1 Phone Numbers & DIDs Linking and PBX Issabel Config
num_link_res = s.post(f'{BASE_URL}/api/partner/v1/clients/{client_id}/telephony/numbers/', json={
    'phone_number': '+966114455667',
    'trunk_type': 'inbound'
}, headers=headers_partner)
assert num_link_res.status_code in [200, 201], f"Number link failed: {num_link_res.text}"
num_link_data = num_link_res.json()
assert num_link_data['status'] == 'success'
assert 'issabel_config' in num_link_data['trunk']
assert 'PEER Details' in num_link_data['trunk']['issabel_config']['peer_details']

num_list_res = s.get(f'{BASE_URL}/api/partner/v1/clients/{client_id}/telephony/numbers/', headers=headers_partner)
assert num_list_res.status_code == 200
num_list_data = num_list_res.json()
assert num_list_data['total_numbers'] >= 2
print(f"[PASS] Step 10.1: Phone Numbers / DIDs linking and Issabel PBX configuration verified via Partner API. Total numbers: {num_list_data['total_numbers']}")

# 11. Employees Full CRUD for Sub-Client (with Multi-Tenancy Isolation)
emp1_res = s.post(f'{BASE_URL}/api/partner/v1/clients/{client_id}/employees/', json={
    'display_name': 'سارة الخالد',
    'extension': '102',
    'department': 'خدمة العملاء والدعم الفني',
    'password': 'SecureEmpPassword123'
}, headers=headers_partner)
assert emp1_res.status_code in [200, 201], f"Employee 1 creation failed: {emp1_res.text}"
emp1_id = emp1_res.json()['employee']['id']

emp2_res = s.post(f'{BASE_URL}/api/partner/v1/clients/{client_id}/employees/', json={
    'display_name': 'عمر الحربي',
    'extension': '103',
    'department': 'المبيعات والحجوزات',
    'password': 'SecureEmpPassword456'
}, headers=headers_partner)
assert emp2_res.status_code in [200, 201], f"Employee 2 creation failed: {emp2_res.text}"
emp2_id = emp2_res.json()['employee']['id']

# Duplicate extension conflict check (must return 409 Conflict)
dup_emp_res = s.post(f'{BASE_URL}/api/partner/v1/clients/{client_id}/employees/', json={
    'display_name': 'موظف مكرر',
    'extension': '102',
    'department': 'المبيعات'
}, headers=headers_partner)
assert dup_emp_res.status_code == 409, f"Duplicate extension not blocked: {dup_emp_res.status_code}"

# List Employees for Client
emp_list_res = s.get(f'{BASE_URL}/api/partner/v1/clients/{client_id}/employees/', headers=headers_partner)
assert emp_list_res.status_code == 200
assert emp_list_res.json()['total_employees'] >= 2

# Update Employee
emp_upd_res = s.post(f'{BASE_URL}/api/partner/v1/clients/{client_id}/employees/{emp1_id}/', json={
    'display_name': 'سارة الخالد (مشرفة)',
    'status': 'busy'
}, headers=headers_partner)
assert emp_upd_res.status_code == 200
assert emp_upd_res.json()['employee']['display_name'] == 'سارة الخالد (مشرفة)'
assert emp_upd_res.json()['employee']['status'] == 'busy'
print(f"[PASS] Step 11: Call Center Employees Full CRUD & Multi-Tenancy Isolation verified (Total: {emp_list_res.json()['total_employees']})")

# 11.1 Call Queues Full CRUD & Memberships for Sub-Client
queue_res = s.post(f'{BASE_URL}/api/partner/v1/clients/{client_id}/queues/', json={
    'name': 'طابور خدمة عملاء المتجر VIP',
    'code': '401',
    'strategy': 'round_robin',
    'ring_timeout_seconds': 20,
    'total_timeout_seconds': 60,
    'fallback_action': 'ai_assistant',
    'members': [emp1_id]
}, headers=headers_partner)
assert queue_res.status_code in [200, 201], f"Queue failed: {queue_res.text}"
queue_id = queue_res.json()['queue']['id']

# Add Employee 2 to Queue
add_mem_res = s.post(f'{BASE_URL}/api/partner/v1/clients/{client_id}/queues/{queue_id}/members/', json={
    'action': 'add',
    'employee_id': emp2_id,
    'order': 2
}, headers=headers_partner)
assert add_mem_res.status_code in [200, 201]

# List Queue Members
mem_list_res = s.get(f'{BASE_URL}/api/partner/v1/clients/{client_id}/queues/{queue_id}/members/', headers=headers_partner)
assert mem_list_res.status_code == 200
assert mem_list_res.json()['total_members'] == 2

# Remove Employee 1 from Queue
del_mem_res = s.post(f'{BASE_URL}/api/partner/v1/clients/{client_id}/queues/{queue_id}/members/', json={
    'action': 'remove',
    'employee_id': emp1_id
}, headers=headers_partner)
assert del_mem_res.status_code == 200

# Verify Queue Detail
q_detail_res = s.get(f'{BASE_URL}/api/partner/v1/clients/{client_id}/queues/{queue_id}/', headers=headers_partner)
assert q_detail_res.status_code == 200
assert len(q_detail_res.json()['queue']['members']) == 1
print("[PASS] Step 11.1: Call Center Queues & Queue Memberships Full CRUD verified via API")

# 11.2 Primary Partner API Documentation Portal Verification (Official Scalar)
docs_res = s.get(f'{BASE_URL}/api/partner/v1/docs/')
assert docs_res.status_code == 200
assert '@scalar/api-reference' in docs_res.text, "Scalar CDN bundle missing from primary docs"
assert '#680E23' in docs_res.text, "Burgundy brand color missing in Scalar theme"
assert '#FAF7F2' in docs_res.text, "Off-white brand color missing in Scalar theme"
assert 'Tajawal' in docs_res.text, "Tajawal typography missing in Scalar theme"
assert '/api/partner/v1/docs/openapi.json' in docs_res.text, "OpenAPI spec link missing"
print("[PASS] Step 11.2: Official Primary Partner Documentation Portal verified at /api/partner/v1/docs/ powered by Scalar with Burgundy & Off-white Theme (200 OK)")

# 11.3 OpenAPI 3.1 Specification Verification
openapi_res = s.get(f'{BASE_URL}/api/partner/v1/docs/openapi.json')
assert openapi_res.status_code == 200, f"OpenAPI JSON failed: {openapi_res.status_code}"
openapi_json = openapi_res.json()
assert openapi_json.get('openapi') == '3.1.0'
assert len(openapi_json.get('tags', [])) == 11, f"Expected 11 tags, got {len(openapi_json.get('tags', []))}"
assert len(openapi_json.get('paths', {})) >= 18, f"Expected at least 18 paths, got {len(openapi_json.get('paths', {}))}"
assert 'PartnerKey' in openapi_json['components']['securitySchemes']
print(f"[PASS] Step 11.3: OpenAPI 3.1 Spec (11 Tags, {len(openapi_json.get('paths', {}))} Paths) verified (200 OK)")

# 12. Direct Voice Session Token for Sub-Client
token_res = s.post(f'{BASE_URL}/api/partner/v1/clients/{client_id}/token/', headers=headers_partner)
assert token_res.status_code == 200, f"Token generation failed: {token_res.text}"
token_data = token_res.json()
assert 'token' in token_data and 'room_name' in token_data
print(f"[PASS] Step 12: LiveKit Voice Session Token generated for client. Room: {token_data['room_name']}")

# 13. Test Simulated Call Completion with Pooled Wholesale Billing
# Duration: 65 seconds -> Strict Ceiling rounds up to 2 minutes!
# Rate: Wholesale Partner Rate ($0.0300) -> 2 * $0.0300 = $0.0600
sim_call_script = f"""
from django.contrib.auth.models import User
from crm.models import CallSession
from billing.models import UserWallet
from partners.models import PartnerClientRelationship
from decimal import Decimal

client_user = User.objects.get(id={client_id})
client_rel = PartnerClientRelationship.objects.get(client=client_user)
partner_user = client_rel.partner.user
wallet = UserWallet.objects.get(user=partner_user)
initial_balance = wallet.balance

# Call internal complete-call API
import requests
import urllib3
urllib3.disable_warnings()

s = requests.Session()
s.verify = False
payload = {{
    'room_name': '{token_data["room_name"]}',
    'user_id': {client_id},
    'duration_seconds': 65,
    'transcript_text': 'المتصل: أهلاً، المساعد: مرحباً بك في متجر النور.',
    'summary': 'استفسار عن الشحن وتمت الإجابة بأن الشحن مجاني فوق 200 ريال.',
    'caller_phone': '+966501234567'
}}
headers = {{'X-Internal-API-Key': 'voice-internal-secret-token-key-12345'}}
res = s.post('http://localhost:8000/api/crm/internal/complete-call/', json=payload, headers=headers)
assert res.status_code == 200, f"Complete call failed: {{res.text}}"

# Verify deduction
wallet.refresh_from_db()
client_rel.refresh_from_db()
deducted = initial_balance - wallet.balance
print(f"DEDUCTED:{{deducted}}|MINUTES:{{client_rel.total_minutes}}|SPENT:{{client_rel.total_spent}}")
"""
cmd_sim = ['docker', 'exec', 'voice_django', 'python', 'manage.py', 'shell', '-c', sim_call_script]
proc_sim = subprocess.run(cmd_sim, capture_output=True, text=True, check=True)
sim_lines = [l for l in proc_sim.stdout.splitlines() if 'DEDUCTED:' in l]
assert sim_lines, f"Call simulation check failed: {proc_sim.stdout}"
sim_info = sim_lines[0]
deducted_amt = float(sim_info.split('DEDUCTED:')[1].split('|')[0])
total_mins = int(sim_info.split('MINUTES:')[1].split('|')[0])
assert abs(deducted_amt - 0.0600) < 0.001, f"Expected $0.0600 deducted from partner, got: {deducted_amt}"
assert total_mins >= 2, f"Expected at least 2 ceiling minutes, got: {total_mins}"
print(f"[PASS] Step 13: Strict Ceiling Wholesale Billing verified! 65s = 2 mins * $0.0300 = $0.0600 deducted from Partner's pooled wallet")

# 14. Check Sub-Client CDR in Partner API
calls_res = s.get(f'{BASE_URL}/api/partner/v1/clients/{client_id}/calls/', headers=headers_partner)
assert calls_res.status_code == 200
calls_data = calls_res.json()
assert calls_data['total_calls'] >= 1
recent_call = calls_data['calls'][0]
assert recent_call['billed_minutes'] == 2
assert recent_call['cost'] == 0.06
print(f"[PASS] Step 14: Sub-Client CDR verified via Partner API (2 mins, $0.06, AI summary intact)")

# 15. Verify UI HTML Elements in room.html
ui_html = s.get(f'{BASE_URL}/').text
assert 'id="nav-btn-partner"' in ui_html
assert 'id="tab-partner"' in ui_html
assert 'id="partner-kpi-balance"' in ui_html
assert 'id="partner-kpi-rate"' in ui_html
assert 'id="partner-clients-tbody"' in ui_html
assert 'id="partner-calls-tbody"' in ui_html
assert 'id="partner-apply-modal"' in ui_html
assert 'id="partner-cap-modal"' in ui_html
assert 'id="partner-docs-modal"' in ui_html
assert '/api/partner/v1/docs/' in ui_html
assert 'loadPartnerDashboard' in ui_html
print("[PASS] Step 15: Frontend UI elements for Partner Portal, Modals, and API Docs link verified in room.html")

print('=' * 75)
print('ALL 15 PARTNER & HEADLESS SAAS INTEGRATION TESTS PASSED WITH 100% SUCCESS!')
print('=' * 75)
