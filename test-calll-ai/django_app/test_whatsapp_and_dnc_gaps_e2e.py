import os
import sys
import json
import io
import django

# Setup Django Environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from django.test import RequestFactory
from django.core.files.uploadedfile import SimpleUploadedFile
from developer.models import UserApiKey
from partners.models import PartnerProfile, PartnerClientRelationship
from crm.models import DoNotCallEntry, OutboundCampaign, CampaignContact, OmnichannelMessage, CustomerMemory
import developer.views as dev_views
import partners.views as prt_views

print("=" * 70)
print("🚀 STARTING COMPREHENSIVE END-TO-END VERIFICATION: GAPS 1 & 3")
print("=" * 70)

# Setup Test Users and Authentication Keys
# 1. Tenant A
user_a, _ = User.objects.get_or_create(username='test_tenant_a', defaults={'email': 'tenant_a@test.com'})
api_key_a_obj, _ = UserApiKey.objects.get_or_create(
    user=user_a,
    defaults={'key': 'sk_live_usr_test_tenant_a_12345', 'name': 'Tenant A Key', 'is_active': True}
)
api_key_a = api_key_a_obj.key

# 2. Tenant B
user_b, _ = User.objects.get_or_create(username='test_tenant_b', defaults={'email': 'tenant_b@test.com'})
api_key_b_obj, _ = UserApiKey.objects.get_or_create(
    user=user_b,
    defaults={'key': 'sk_live_usr_test_tenant_b_67890', 'name': 'Tenant B Key', 'is_active': True}
)
api_key_b = api_key_b_obj.key

# 3. Partner & Managed Client
partner_user, _ = User.objects.get_or_create(username='test_partner_admin', defaults={'email': 'partner@test.com'})
partner_profile, _ = PartnerProfile.objects.get_or_create(
    user=partner_user,
    defaults={'company_name': 'Test Partner Co', 'status': 'approved', 'api_key': 'sk_live_prt_test_partner_99999'}
)
if partner_profile.status != 'approved':
    partner_profile.status = 'approved'
    partner_profile.save()
partner_key = partner_profile.api_key

client_user, _ = User.objects.get_or_create(username='test_partner_client', defaults={'email': 'client@test.com'})
client_rel, _ = PartnerClientRelationship.objects.get_or_create(
    partner=partner_profile,
    client=client_user,
    defaults={'external_reference': 'CLI-001', 'is_active': True}
)
client_target_id = client_user.id

# Clean up prior test data
DoNotCallEntry.objects.filter(user__in=[user_a, user_b, client_user]).delete()
OutboundCampaign.objects.filter(user__in=[user_a, user_b, client_user]).delete()
OmnichannelMessage.objects.filter(user__in=[user_a, user_b, client_user]).delete()
CustomerMemory.objects.filter(user__in=[user_a, user_b, client_user]).delete()

factory = RequestFactory()
success_tests = 0
total_tests = 0

def assert_true(cond, msg):
    global total_tests, success_tests
    total_tests += 1
    if not cond:
        print(f"❌ FAILED: {msg}")
        raise AssertionError(msg)
    else:
        print(f"  ✅ PASS: {msg}")
        success_tests += 1

# ==============================================================================
# SECTION 1: GAP 3 - DNC LIST (TENANT ISOLATION & CRUD)
# ==============================================================================
print("\n" + "-" * 50)
print("📌 TEST SECTION 1: DNC Engine & Tenant Isolation")
print("-" * 50)

# 1.1 Developer API: Add +201011111111 to Tenant A DNC
req = factory.post(
    '/api/v1/dnc/',
    data=json.dumps({"phone_number": "+201011111111", "customer_name": "Do Not Call Customer", "reason": "Unsubscribed"}),
    content_type='application/json',
    HTTP_X_API_KEY=api_key_a
)
resp = dev_views.api_user_dnc(req)
data = json.loads(resp.content.decode('utf-8'))
assert_true(resp.status_code in (200, 201), "Add DNC entry to Tenant A returned 200/201")
assert_true(data.get("status") == "success", "Response status is success")
assert_true(data.get("entry", {}).get("phone_number") == "+201011111111", "Entry phone is normalized +201011111111")
entry_a_id = data["entry"]["id"]

# 1.2 Developer API: Check DNC on Tenant A -> must be blacklisted
req = factory.post(
    '/api/v1/dnc/check/',
    data=json.dumps({"phone_number": "+201011111111"}),
    content_type='application/json',
    HTTP_X_API_KEY=api_key_a
)
resp = dev_views.api_user_dnc_check(req)
data = json.loads(resp.content.decode('utf-8'))
assert_true(data.get("is_blacklisted") is True, "Tenant A DNC check reports +201011111111 as blacklisted")

# 1.3 Strict Tenant Isolation: Check DNC for same number on Tenant B -> MUST NOT be blacklisted!
req = factory.post(
    '/api/v1/dnc/check/',
    data=json.dumps({"phone_number": "+201011111111"}),
    content_type='application/json',
    HTTP_X_API_KEY=api_key_b
)
resp = dev_views.api_user_dnc_check(req)
data = json.loads(resp.content.decode('utf-8'))
assert_true(data.get("is_blacklisted") is False, "Tenant B DNC check reports +201011111111 as NOT blacklisted (100% Isolated)")

# 1.4 List DNC for Tenant A and Tenant B
req = factory.get('/api/v1/dnc/', HTTP_X_API_KEY=api_key_a)
resp = dev_views.api_user_dnc(req)
data = json.loads(resp.content.decode('utf-8'))
assert_true(data.get("total") == 1, "Tenant A has exactly 1 DNC entry")

req = factory.get('/api/v1/dnc/', HTTP_X_API_KEY=api_key_b)
resp = dev_views.api_user_dnc(req)
data = json.loads(resp.content.decode('utf-8'))
assert_true(data.get("total") == 0, "Tenant B has exactly 0 DNC entries (no cross-tenant leakage)")

# 1.5 Partner Client DNC Management
req = factory.post(
    f'/api/partner/v1/clients/{client_target_id}/dnc/',
    data=json.dumps({"phone_number": "+201022222222", "customer_name": "Partner Client DNC", "reason": "Requested via Partner"}),
    content_type='application/json',
    HTTP_X_PARTNER_KEY=partner_key
)
resp = prt_views.api_partner_client_dnc(req, client_id=client_target_id)
data = json.loads(resp.content.decode('utf-8'))
assert_true(resp.status_code in (200, 201), "Partner created DNC entry for managed client")
assert_true(data.get("entry", {}).get("phone_number") == "+201022222222", "Managed client DNC entry phone correct")
entry_client_id = data["entry"]["id"]

# 1.6 Partner Client DNC Check
req = factory.post(
    f'/api/partner/v1/clients/{client_target_id}/dnc/check/',
    data=json.dumps({"phone_number": "+201022222222"}),
    content_type='application/json',
    HTTP_X_PARTNER_KEY=partner_key
)
resp = prt_views.api_partner_client_dnc_check(req, client_id=client_target_id)
data = json.loads(resp.content.decode('utf-8'))
assert_true(data.get("is_blacklisted") is True, "Partner reports client number as blacklisted")

# Verify Tenant A does NOT see Partner Client's DNC
req = factory.post(
    '/api/v1/dnc/check/',
    data=json.dumps({"phone_number": "+201022222222"}),
    content_type='application/json',
    HTTP_X_API_KEY=api_key_a
)
resp = dev_views.api_user_dnc_check(req)
data = json.loads(resp.content.decode('utf-8'))
assert_true(data.get("is_blacklisted") is False, "Tenant A cannot see Partner Client DNC entry")

# 1.7 DNC Delete for Tenant A
req = factory.delete(f'/api/v1/dnc/{entry_a_id}/', HTTP_X_API_KEY=api_key_a)
resp = dev_views.api_user_dnc_detail(req, entry_id=entry_a_id)
assert_true(resp.status_code == 200, "Deleted DNC entry from Tenant A")

# Verify delete
assert_true(not DoNotCallEntry.objects.filter(id=entry_a_id).exists(), "Entry deleted from DB")

# Re-add +201011111111 to Tenant A for campaign filtering test below
DoNotCallEntry.objects.create(user=user_a, phone_number="+201011111111", customer_name="Blacklisted Contact")


# ==============================================================================
# SECTION 2: GAP 3 - CAMPAIGNS CSV/EXCEL/JSON INGESTION & AUTO DNC FILTERING
# ==============================================================================
print("\n" + "-" * 50)
print("📌 TEST SECTION 2: Campaigns Ingestion (Multipart CSV & JSON) + DNC Filtering")
print("-" * 50)

# 2.1 Developer API: Multipart CSV Upload with 1 Blacklisted and 2 Valid Contacts
csv_content = (
    "اسم العميل,رقم الهاتف\n"
    "عميل محظور,+201011111111\n"
    "عميل صالح 1,+201033333333\n"
    "عميل صالح 2,+201044444444\n"
).encode('utf-8-sig')

uploaded_file = SimpleUploadedFile("leads_test.csv", csv_content, content_type="text/csv")
req = factory.post(
    '/api/v1/campaigns/',
    data={
        'name': 'حملة اختبار الرفع المباشر CSV',
        'channel': 'hybrid',
        'call_prompt': 'مرحبا بك في الاتصال التجريبي',
        'whatsapp_prompt': 'مرحبا بك في رسالة الواتساب التلقائية',
        'file': uploaded_file
    },
    HTTP_X_API_KEY=api_key_a
)
resp = dev_views.api_user_campaigns(req)
data = json.loads(resp.content.decode('utf-8'))

assert_true(resp.status_code == 201, "Campaign creation via CSV multipart returned 201 Created")
assert_true(data.get("total_extracted") == 3, "Extracted 3 contacts from CSV")
assert_true(data.get("dnc_skipped_count") == 1, "DNC Filter automatically skipped 1 blacklisted contact (+201011111111)")
assert_true(data.get("contacts_imported_count") == 2, "Imported 2 valid non-blacklisted contacts")

camp_id = data["campaign"]["id"]
camp_obj = OutboundCampaign.objects.get(id=camp_id)
assert_true(camp_obj.channel == "hybrid", "Campaign channel is hybrid")
assert_true(camp_obj.whatsapp_prompt == "مرحبا بك في رسالة الواتساب التلقائية", "WhatsApp prompt saved correctly")
assert_true(camp_obj.contacts.count() == 2, "Campaign contacts in DB equals 2")
assert_true(not camp_obj.contacts.filter(phone_number="+201011111111").exists(), "Blacklisted phone +201011111111 is strictly absent from campaign contacts")

# 2.2 Developer API: Append Contacts via JSON Array to existing campaign
req = factory.post(
    '/api/v1/campaigns/upload-contacts/',
    data=json.dumps({
        'campaign_id': camp_id,
        'contacts': [
            {'phone_number': '+201055555555', 'name': 'عميل إضافي جديد'},
            {'phone_number': '+201011111111', 'name': 'محاولة إضافة محظور مرة أخرى'}
        ]
    }),
    content_type='application/json',
    HTTP_X_API_KEY=api_key_a
)
resp = dev_views.api_user_campaigns_upload_contacts(req)
data = json.loads(resp.content.decode('utf-8'))
assert_true(resp.status_code == 200, "upload-contacts appended to existing campaign")
assert_true(data.get("dnc_skipped_count") == 1, "DNC skipped blacklisted contact in JSON batch")
assert_true(data.get("contacts_imported_count") == 1, "Imported 1 new contact (+201055555555)")
assert_true(camp_obj.contacts.count() == 3, "Total campaign contacts is now 3")

# 2.3 Partner Client Campaign Ingestion with Multipart File
partner_csv = (
    "customer_name,phone_number\n"
    "Partner Lead 1,+201066666666\n"
    "Partner Lead 2 DNC,+201022222222\n"
).encode('utf-8')
p_file = SimpleUploadedFile("partner_leads.csv", partner_csv, content_type="text/csv")

req = factory.post(
    f'/api/partner/v1/clients/{client_target_id}/campaigns/',
    data={
        'name': 'حملة عميل الشريك CSV',
        'channel': 'calls',
        'file': p_file
    },
    HTTP_X_PARTNER_KEY=partner_key
)
resp = prt_views.api_partner_client_campaigns(req, client_id=client_target_id)
data = json.loads(resp.content.decode('utf-8'))
assert_true(resp.status_code == 201, "Partner client campaign created via multipart CSV")
assert_true(data.get("total_extracted") == 2, "Partner extracted 2 contacts")
assert_true(data.get("dnc_skipped_count") == 1, "Partner DNC skipped +201022222222")
assert_true(data.get("contacts_imported_count") == 1, "Partner imported 1 valid contact")


# ==============================================================================
# SECTION 3: GAP 1 - WHATSAPP & EVOLUTION API OMNICHANNEL
# ==============================================================================
print("\n" + "-" * 50)
print("📌 TEST SECTION 3: WhatsApp & Omnichannel Endpoints")
print("-" * 50)

# 3.1 Developer API: WhatsApp Status
req = factory.get('/api/v1/whatsapp/status/', HTTP_X_API_KEY=api_key_a)
resp = dev_views.api_user_whatsapp_status(req)
data = json.loads(resp.content.decode('utf-8'))
assert_true(resp.status_code == 200, "Developer WhatsApp status returned 200")
assert_true("state" in data or "status" in data, "WhatsApp status contains state/status")

# 3.2 Developer API: WhatsApp Connect (QR code fetch)
req = factory.post('/api/v1/whatsapp/connect/', HTTP_X_API_KEY=api_key_a)
resp = dev_views.api_user_whatsapp_connect(req)
data = json.loads(resp.content.decode('utf-8'))
assert_true(resp.status_code == 200, "Developer WhatsApp connect returned 200")

# 3.3 Developer API: Send WhatsApp message to a customer
test_target_phone = "+201099887766"
req = factory.post(
    '/api/v1/whatsapp/send/',
    data=json.dumps({"phone": test_target_phone, "message": "رسالة تجريبية موجهة من مطور النظام"}),
    content_type='application/json',
    HTTP_X_API_KEY=api_key_a
)
resp = dev_views.api_user_whatsapp_send(req)
data = json.loads(resp.content.decode('utf-8'))
assert_true(resp.status_code == 200, "Developer WhatsApp send message returned 200")
assert_true(data.get("status") == "success", "Send message status is success")
assert_true(data.get("sent_message", {}).get("phone_number") == test_target_phone, "Sent message phone matches target")
assert_true(data.get("sent_message", {}).get("direction") == "outbound_human", "Direction is outbound_human")

# Verify recorded in OmnichannelMessage DB
db_msg = OmnichannelMessage.objects.filter(user=user_a, phone_number=test_target_phone).first()
assert_true(db_msg is not None, "Message record persisted in OmnichannelMessage database")
assert_true(db_msg.message_text == "رسالة تجريبية موجهة من مطور النظام", "Message text matches")

# 3.4 Developer API: List Conversations (Inbox)
req = factory.get('/api/v1/whatsapp/conversations/', HTTP_X_API_KEY=api_key_a)
resp = dev_views.api_user_whatsapp_conversations(req)
data = json.loads(resp.content.decode('utf-8'))
assert_true(resp.status_code == 200, "Conversations list returned 200")
assert_true(data.get("total") >= 1, "Conversations list contains at least 1 conversation")
conv = [c for c in data.get("conversations", []) if c.get("phone_number") == test_target_phone]
assert_true(len(conv) == 1, "Found target customer in conversations inbox")
assert_true(conv[0].get("ai_active") is True, "Default conversation ai_active is True")

# 3.5 Developer API: Get Conversation Message History
req = factory.get(f'/api/v1/whatsapp/conversations/{test_target_phone}/messages/', HTTP_X_API_KEY=api_key_a)
resp = dev_views.api_user_whatsapp_conversation_messages(req, phone=test_target_phone)
data = json.loads(resp.content.decode('utf-8'))
assert_true(resp.status_code == 200, "Conversation messages returned 200")
assert_true(data.get("total_messages") >= 1, "Message history has at least 1 message")

# 3.6 Developer API: Human Agent Reply
req = factory.post(
    f'/api/v1/whatsapp/conversations/{test_target_phone}/reply/',
    data=json.dumps({"message": "رد الموظف البشري على المحادثة"}),
    content_type='application/json',
    HTTP_X_API_KEY=api_key_a
)
resp = dev_views.api_user_whatsapp_conversation_reply(req, phone=test_target_phone)
data = json.loads(resp.content.decode('utf-8'))
assert_true(resp.status_code == 200, "Reply returned 200")
assert_true(data.get("sent_message", {}).get("message_text") == "رد الموظف البشري على المحادثة", "Reply message recorded")

# 3.7 Developer API: Toggle AI Auto-Reply (Human Takeover)
req = factory.post(
    f'/api/v1/whatsapp/conversations/{test_target_phone}/toggle-ai/',
    data=json.dumps({"ai_active": False}),
    content_type='application/json',
    HTTP_X_API_KEY=api_key_a
)
resp = dev_views.api_user_whatsapp_conversation_toggle_ai(req, phone=test_target_phone)
data = json.loads(resp.content.decode('utf-8'))
assert_true(resp.status_code == 200, "Toggle AI returned 200")
assert_true(data.get("ai_active") is False, "AI auto-reply set to False (Human takeover active)")

mem = CustomerMemory.objects.filter(user=user_a, phone_number=test_target_phone).first()
assert_true(mem.whatsapp_memory.get("ai_auto_reply_enabled") is False, "CustomerMemory in DB saved ai_auto_reply_enabled=False")

# 3.8 Developer API: Trigger AI Follow-up on Demand
req = factory.post(
    '/api/v1/whatsapp/followup/',
    data=json.dumps({"phone": test_target_phone, "customer_name": "عميل متابعة"}),
    content_type='application/json',
    HTTP_X_API_KEY=api_key_a
)
resp = dev_views.api_user_whatsapp_followup(req)
data = json.loads(resp.content.decode('utf-8'))
assert_true(resp.status_code == 200, "Trigger followup returned 200")
assert_true(data.get("status") == "success", "Followup dispatched successfully")

# 3.9 Partner Client WhatsApp Endpoints
# Status
req = factory.get(f'/api/partner/v1/clients/{client_target_id}/whatsapp/status/', HTTP_X_PARTNER_KEY=partner_key)
resp = prt_views.api_partner_client_whatsapp_status(req, client_id=client_target_id)
assert_true(resp.status_code == 200, "Partner client WhatsApp status returned 200")

# Send
p_phone = "+201077665544"
req = factory.post(
    f'/api/partner/v1/clients/{client_target_id}/whatsapp/send/',
    data=json.dumps({"phone": p_phone, "message": "رسالة لعميل الشريك عبر الواتساب"}),
    content_type='application/json',
    HTTP_X_PARTNER_KEY=partner_key
)
resp = prt_views.api_partner_client_whatsapp_send(req, client_id=client_target_id)
data = json.loads(resp.content.decode('utf-8'))
assert_true(resp.status_code == 200, "Partner client WhatsApp send returned 200")
assert_true(OmnichannelMessage.objects.filter(user=client_user, phone_number=p_phone).exists(), "Message recorded under partner's client")
assert_true(not OmnichannelMessage.objects.filter(user=user_a, phone_number=p_phone).exists(), "Message strictly isolated from Tenant A")

# Conversations
req = factory.get(f'/api/partner/v1/clients/{client_target_id}/whatsapp/conversations/', HTTP_X_PARTNER_KEY=partner_key)
resp = prt_views.api_partner_client_whatsapp_conversations(req, client_id=client_target_id)
data = json.loads(resp.content.decode('utf-8'))
assert_true(resp.status_code == 200, "Partner client conversations returned 200")
assert_true(data.get("total") == 1, "Partner client has exactly 1 conversation")

# Toggle AI for partner client
req = factory.post(
    f'/api/partner/v1/clients/{client_target_id}/whatsapp/conversations/{p_phone}/toggle-ai/',
    data=json.dumps({"ai_active": False}),
    content_type='application/json',
    HTTP_X_PARTNER_KEY=partner_key
)
resp = prt_views.api_partner_client_whatsapp_conversation_toggle_ai(req, client_id=client_target_id, phone=p_phone)
data = json.loads(resp.content.decode('utf-8'))
assert_true(data.get("ai_active") is False, "Partner client AI auto-reply toggled to False")

print("\n" + "=" * 70)
print(f"🎉 ALL END-TO-END TESTS COMPLETED SUCCESSFULLY! ({success_tests}/{total_tests} PASSED)")
print("=" * 70)
