import os
import sys
import io
import json
import unittest.mock as mock
from decimal import Decimal

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from developer.models import UserApiKey
from partners.models import PartnerProfile, PartnerClientRelationship
from knowledge.models import Document, DocumentChunk
from crm.models import OutboundCampaign, CampaignContact
from billing.models import UserWallet

print("=" * 80)
print("🚀 STARTING E2E INTEGRATION TEST SUITE: WEBRTC, RAG CSV FIX & FILE_URL")
print("=" * 80)

# -------------------------------------------------------------
# 1. SETUP FIXTURES: DEVELOPER USER & PARTNER TENANT
# -------------------------------------------------------------
dev_user, _ = User.objects.get_or_create(username='dev_tester_e2e', defaults={'email': 'dev_tester@test.com'})
UserApiKey.objects.filter(user=dev_user).delete()
api_key_obj = UserApiKey.generate_for_user(dev_user, name='E2E Developer Key')
user_api_key = api_key_obj.key

dev_wallet, _ = UserWallet.objects.get_or_create(user=dev_user)
dev_wallet.balance = Decimal('100.0000')
dev_wallet.save()

partner_user, _ = User.objects.get_or_create(username='partner_owner_e2e', defaults={'email': 'partner_owner@test.com'})
partner_profile, _ = PartnerProfile.objects.get_or_create(
    user=partner_user,
    defaults={
        'company_name': 'شركة حلول الذكاء الصوتي',
        'partner_code': 'part_e2e_code_99',
        'status': 'approved',
        'custom_rate_per_minute': Decimal('0.0400')
    }
)
partner_profile.status = 'approved'
import secrets
partner_profile.api_key = f"pk_live_e2e_{secrets.token_hex(20)}"
partner_profile.save()
partner_api_key = partner_profile.api_key

partner_wallet, _ = UserWallet.objects.get_or_create(user=partner_user)
partner_wallet.balance = Decimal('250.0000')
partner_wallet.save()

subclient_user, _ = User.objects.get_or_create(username='partner_client_e2e', defaults={'email': 'subclient@domain.com'})
rel, _ = PartnerClientRelationship.objects.get_or_create(
    partner=partner_profile,
    client=subclient_user,
    defaults={'is_active': True, 'external_reference': 'ext_subclient_e2e'}
)
client_id = rel.id

client = Client()

# -------------------------------------------------------------
# TEST 1: User RAG Documents Upload with CSV (Fix for 500 error)
# -------------------------------------------------------------
print("\n[TEST 1] User RAG Upload: CSV File Ingestion (Fix for RawPostDataException)")
csv_content = b"call_id,caller_name,topic,notes\n101,Ahmed Ali,Inquiry,Interested in Enterprise Voice AI\n102,Sara Salem,Support,WebRTC connection testing\n"
uploaded_csv = SimpleUploadedFile("call_logs.csv", csv_content, content_type="text/csv")

resp1 = client.post(
    '/api/v1/documents/',
    {
        'file': uploaded_csv,
        'title': 'سجلات المكالمات 2026',
    },
    HTTP_X_API_KEY=user_api_key
)
print(f"Status Code: {resp1.status_code}")
data1 = resp1.json()
print("Response Data:", data1)
assert resp1.status_code == 201, f"Expected 201, got {resp1.status_code}: {data1}"
assert data1['status'] == 'success'
doc1 = Document.objects.get(id=data1['document']['id'])
assert doc1.file_type == 'csv'
assert doc1.chunks.count() >= 1
print(f"✅ Test 1 Passed: call_logs.csv uploaded & vector-indexed successfully ({doc1.chunks.count()} chunks) without 500 error!")

# -------------------------------------------------------------
# TEST 2: Section 9 - User WebRTC Token & LiveKit / WebSocket URLs
# -------------------------------------------------------------
print("\n[TEST 2] Section 9: User WebRTC Token & Real-Time Connection URLs")
resp2 = client.post(
    '/api/v1/token/',
    data=json.dumps({"participant_name": "مطور التطبيق"}),
    content_type='application/json',
    HTTP_X_API_KEY=user_api_key
)
print(f"Status Code: {resp2.status_code}")
data2 = resp2.json()
print("Response Data:", data2)
assert resp2.status_code == 200, f"Expected 200, got {resp2.status_code}: {data2}"
assert data2['status'] == 'success'
assert data2['livekit_url'] == 'wss://livekit.169.58.32.179.nip.io', f"Unexpected LiveKit URL: {data2.get('livekit_url')}"
assert len(data2['token']) > 20
assert data2['centrifugo_ws_url'] == 'wss://centrifugo.169.58.32.179.nip.io/connection/websocket'
assert len(data2['centrifugo_token']) > 20
assert len(data2['channel']) > 0
print(f"✅ Test 2 Passed: WebRTC Token endpoint returns LiveKit ({data2['livekit_url']}) and Centrifugo ({data2['centrifugo_ws_url']})!")

# -------------------------------------------------------------
# TEST 3: Section 9 - Partner Client WebRTC Token & WebSocket URLs
# -------------------------------------------------------------
print(f"\n[TEST 3] Section 9: Partner Client #{client_id} WebRTC Token & Connection URLs")
resp3 = client.post(
    f'/api/partner/v1/clients/{client_id}/token/',
    data=json.dumps({"participant_name": "عميل الشريك"}),
    content_type='application/json',
    HTTP_X_PARTNER_KEY=partner_api_key
)
print(f"Status Code: {resp3.status_code}")
data3 = resp3.json()
print("Response Data:", data3)
assert resp3.status_code == 200, f"Expected 200, got {resp3.status_code}: {data3}"
assert data3['livekit_url'] == 'wss://livekit.169.58.32.179.nip.io'
assert data3['centrifugo_ws_url'] == 'wss://centrifugo.169.58.32.179.nip.io/connection/websocket'
assert len(data3['token']) > 20
assert len(data3['centrifugo_token']) > 20
print("✅ Test 3 Passed: Partner Client WebRTC token returns LiveKit & Centrifugo WebSocket connection parameters!")

# -------------------------------------------------------------
# TEST 4: Campaign Creation via file_url
# -------------------------------------------------------------
print("\n[TEST 4] User Campaign Creation via file_url (Remote CSV Contacts)")
mock_csv_bytes = b"phone,customer_name,city\n+966540001111,Fahad Al Otaibi,Riyadh\n+966540002222,Reem Al Dossary,Dammam\n"
mock_resp = mock.MagicMock()
mock_resp.status_code = 200
mock_resp.headers = {'Content-Type': 'text/csv'}
mock_resp.iter_content.return_value = [mock_csv_bytes]

with mock.patch('requests.get', return_value=mock_resp):
    resp4 = client.post(
        '/api/v1/campaigns/',
        data=json.dumps({
            "name": "حملة تم استيرادها عبر الرابط",
            "file_url": "https://cdn.example.com/files/saudi_leads.csv",
            "call_prompt": "مرحبا {name}",
            "max_retries": 1,
            "retry_delay_minutes": 15
        }),
        content_type='application/json',
        HTTP_X_API_KEY=user_api_key
    )

print(f"Status Code: {resp4.status_code}")
data4 = resp4.json()
print("Response Data:", data4)
assert resp4.status_code == 201, f"Expected 201, got {resp4.status_code}: {data4}"
camp4 = OutboundCampaign.objects.get(id=data4['campaign']['id'])
assert camp4.total_contacts == 2
c4 = CampaignContact.objects.filter(campaign=camp4, phone_number='+966540001111').first()
assert c4 is not None and c4.customer_name == 'Fahad Al Otaibi'
assert c4.attributes.get('city') == 'Riyadh'
print(f"✅ Test 4 Passed: Campaign created with {camp4.total_contacts} contacts imported via file_url!")

# -------------------------------------------------------------
# TEST 5: User RAG Document Ingestion via file_url
# -------------------------------------------------------------
print("\n[TEST 5] User RAG Document Ingestion via file_url")
mock_doc_text = b"Antigravity Voice AI Documentation: High performance enterprise conversational voice bots with real-time WebRTC and LiveKit streaming."
mock_doc_resp = mock.MagicMock()
mock_doc_resp.status_code = 200
mock_doc_resp.headers = {'Content-Type': 'text/plain'}
mock_doc_resp.iter_content.return_value = [mock_doc_text]

with mock.patch('requests.get', return_value=mock_doc_resp):
    resp5 = client.post(
        '/api/v1/documents/',
        data=json.dumps({
            "file_url": "https://cdn.example.com/docs/voice_manual.txt",
            "title": "دليل المساعد الصوتي",
        }),
        content_type='application/json',
        HTTP_X_API_KEY=user_api_key
    )

print(f"Status Code: {resp5.status_code}")
data5 = resp5.json()
print("Response Data:", data5)
assert resp5.status_code == 201, f"Expected 201, got {resp5.status_code}: {data5}"
doc5 = Document.objects.get(id=data5['document']['id'])
assert doc5.title == "دليل المساعد الصوتي"
assert doc5.chunks.count() > 0
print("✅ Test 5 Passed: RAG Document downloaded from URL and vector-indexed successfully!")

# -------------------------------------------------------------
# TEST 6: Partner Client Campaign via file_url
# -------------------------------------------------------------
print(f"\n[TEST 6] Partner Client #{client_id} Campaign Creation via file_url")
with mock.patch('requests.get', return_value=mock_resp):
    resp6 = client.post(
        f'/api/partner/v1/clients/{client_id}/campaigns/',
        data=json.dumps({
            "file_url": "https://cdn.example.com/files/partner_leads.csv",
            "call_prompt": "متابعة الطلبات لعملاء الشريك",
        }),
        content_type='application/json',
        HTTP_X_PARTNER_KEY=partner_api_key
    )
print(f"Status Code: {resp6.status_code}")
data6 = resp6.json()
print("Response Data:", data6)
assert resp6.status_code == 201
camp6 = OutboundCampaign.objects.get(id=data6['campaign']['id'])
assert camp6.user == subclient_user
assert camp6.total_contacts == 2
print("✅ Test 6 Passed: Partner Client Campaign via file_url successfully processed & isolated to sub-client!")

# -------------------------------------------------------------
# TEST 7: Partner Client RAG Document Ingestion via file_url
# -------------------------------------------------------------
print(f"\n[TEST 7] Partner Client #{client_id} RAG Ingestion via file_url")
with mock.patch('requests.get', return_value=mock_doc_resp):
    resp7 = client.post(
        f'/api/partner/v1/clients/{client_id}/documents/',
        data=json.dumps({
            "file_url": "https://cdn.example.com/docs/partner_manual.txt",
            "title": "دليل الشريك المستورد عبر الرابط",
        }),
        content_type='application/json',
        HTTP_X_PARTNER_KEY=partner_api_key
    )
print(f"Status Code: {resp7.status_code}")
data7 = resp7.json()
print("Response Data:", data7)
assert resp7.status_code == 201
doc7 = Document.objects.get(id=data7['document']['id'])
assert doc7.user == subclient_user
assert doc7.chunks.count() > 0
print("✅ Test 7 Passed: Partner Client RAG Document indexed via file_url with strict multi-tenant isolation!")

print("\n" + "=" * 80)
print("🎉 ALL 7 END-TO-END INTEGRATION TESTS PASSED 100%!")
print("=" * 80)
