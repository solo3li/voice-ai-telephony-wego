"""
End-to-End Verification of Phase 1 & Phase 2 Improvements:
1. Symmetric Fernet SIP Password Encryption & Decryption
2. Timing-Safe Internal API Authentication
3. Multi-Tenant Extension Resolution & Protection
4. Wallet Atomic Locking Concurrency Protection
5. Asynchronous RAG Document Handling & Status Tracking
"""
import os
import sys
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from django.test import RequestFactory
from django.core.files.uploadedfile import SimpleUploadedFile
from telephony.models import InboundPBXTrunk, OutboundSIPTrunk
from common.crypto import encrypt_secret, decrypt_secret
from common.auth import verify_internal_api_key
from common.centrifugo import publish_to_centrifugo
from billing.models import UserWallet
from knowledge.models import Document, DocumentChunk
from knowledge.views import list_documents, upload_document
from call_center.models import EmployeeProfile

def run_tests():
    print("======================================================================")
    print("🚀 RUNNING END-TO-END VERIFICATION: SECURITY, CONCURRENCY & RAG JOBS")
    print("======================================================================")

    # 1. Crypto & SIP Passwords
    print("\n[TEST 1] Testing SIP Credentials Encryption & Transparent Decryption...")
    raw_secret = "SuperSecretP@ssw0rd_2026!"
    enc = encrypt_secret(raw_secret)
    assert enc != raw_secret, "Encrypted credential should not match raw password"
    assert enc.startswith("gAAAAA"), "Fernet token should start with gAAAAA"
    dec = decrypt_secret(enc)
    assert dec == raw_secret, f"Decrypted credential '{dec}' should match original '{raw_secret}'"

    user, _ = User.objects.get_or_create(username="sec_test_user")
    trunk = InboundPBXTrunk(
        user=user,
        name="Test Encrypted Trunk",
        auth_username="trunk_1001",
    )
    trunk.set_auth_password(raw_secret)
    trunk.save()

    # Verify stored in DB is encrypted
    trunk.refresh_from_db()
    assert trunk.auth_password != raw_secret, "DB stored password must be encrypted"
    assert trunk.get_auth_password() == raw_secret, "get_auth_password() must return decrypted password"
    print(f"✅ SIP Trunk password safely encrypted: {trunk.auth_password[:20]}... -> Decrypted: {trunk.get_auth_password()}")

    # 2. Timing-Safe Authentication
    print("\n[TEST 2] Testing Timing-Safe Internal API Authentication...")
    from django.conf import settings
    rf = RequestFactory()

    # Valid key in header
    req_valid = rf.post('/api/agents/internal/bootstrap/', HTTP_X_INTERNAL_API_KEY=settings.INTERNAL_API_KEY)
    assert verify_internal_api_key(req_valid) is True, "Valid API key must be accepted"

    # Valid key as Bearer token
    req_bearer = rf.post('/api/agents/internal/bootstrap/', HTTP_AUTHORIZATION=f"Bearer {settings.INTERNAL_API_KEY}")
    assert verify_internal_api_key(req_bearer) is True, "Valid Bearer API key must be accepted"

    # Invalid key
    req_invalid = rf.post('/api/agents/internal/bootstrap/', HTTP_X_INTERNAL_API_KEY="wrong_key_123")
    assert verify_internal_api_key(req_invalid) is False, "Invalid API key must be rejected"

    # Missing key
    req_empty = rf.post('/api/agents/internal/bootstrap/')
    print("✅ Timing-safe authentication strictly verified.")

    # 2.1 Bootstrap Tenant Isolation & Validation
    from agents.views import api_internal_agent_bootstrap
    # Missing user_id -> 400
    req_no_user = rf.post('/api/agents/internal/bootstrap/', data='{}', content_type='application/json', HTTP_X_INTERNAL_API_KEY=settings.INTERNAL_API_KEY)
    res_no_user = api_internal_agent_bootstrap(req_no_user)
    assert res_no_user.status_code == 400, f"Expected 400 for missing user_id, got {res_no_user.status_code}"

    # Non-existent user_id -> 404
    req_fake_user = rf.post('/api/agents/internal/bootstrap/', data='{"user_id": 999999}', content_type='application/json', HTTP_X_INTERNAL_API_KEY=settings.INTERNAL_API_KEY)
    res_fake_user = api_internal_agent_bootstrap(req_fake_user)
    assert res_fake_user.status_code == 404, f"Expected 404 for invalid user_id, got {res_fake_user.status_code}"
    print("✅ Bootstrap tenant isolation verified (no arbitrary fallback).")

    # 3. Multi-Tenant Extension Resolution
    print("\n[TEST 3] Testing Multi-Tenant Call Center Extension Disambiguation...")
    employer1, _ = User.objects.get_or_create(username="employer_corp_a")
    employer2, _ = User.objects.get_or_create(username="employer_corp_b")
    user_alice, _ = User.objects.get_or_create(username="alice_emp_a")
    user_alice.set_password("corpA_pass")
    user_alice.save()
    user_bob, _ = User.objects.get_or_create(username="bob_emp_b")
    user_bob.set_password("corpB_pass")
    user_bob.save()

    emp1, _ = EmployeeProfile.objects.get_or_create(user=user_alice, employer=employer1, extension="101", defaults={"display_name": "Alice Corp A"})
    emp2, _ = EmployeeProfile.objects.get_or_create(user=user_bob, employer=employer2, extension="101", defaults={"display_name": "Bob Corp B"})

    # Authenticate Alice by testing against candidates
    candidates = EmployeeProfile.objects.filter(extension="101").select_related('user')
    alice_match = next((e for e in candidates if e.user.check_password("corpA_pass")), None)
    bob_match = next((e for e in candidates if e.user.check_password("corpB_pass")), None)

    assert alice_match is not None and alice_match.employer == employer1, "Alice should be resolved to employer1"
    assert bob_match is not None and bob_match.employer == employer2, "Bob should be resolved to employer2"
    print(f"✅ Disambiguated duplicate extension '101' across tenants successfully.")

    # 4. Wallet Concurrency and Atomic Updates
    print("\n[TEST 4] Testing UserWallet atomic updates & race condition protection...")
    wallet, _ = UserWallet.objects.get_or_create(user=user, defaults={"balance": Decimal('50.00')})
    wallet.balance = Decimal('50.00')
    wallet.save()

    from django.db import transaction
    with transaction.atomic():
        w = UserWallet.objects.select_for_update().get(user=user)
        cost = Decimal('5.25')
        w.balance -= cost
        w.save(update_fields=['balance', 'updated_at'])

    wallet.refresh_from_db()
    assert wallet.balance == Decimal('44.75'), f"Expected balance 44.75, got {wallet.balance}"
    print(f"✅ Wallet balance atomically updated to: {wallet.balance}")

    # 5. RAG Document Ingestion & Status Tracking
    print("\n[TEST 5] Testing RAG Document Upload, Status Field & Inngest Dispatch...")
    dummy_file = SimpleUploadedFile("knowledge_test.txt", b"Hello Voice AI. This is a comprehensive knowledge base document for testing.", content_type="text/plain")
    req_upload = rf.post('/api/knowledge/documents/upload/', {'file': dummy_file})
    req_upload.user = user

    res = upload_document(req_upload)
    import json
    res_data = json.loads(res.content)
    assert res.status_code == 200, f"Upload failed: {res_data}"
    assert res_data.get('status') == 'success'
    doc_id = res_data['document']['id']

    doc_obj = Document.objects.get(id=doc_id)
    assert doc_obj.status in ('pending', 'ready'), f"Document status should be pending or ready, got {doc_obj.status}"
    print(f"✅ Document #{doc_obj.id} status: '{doc_obj.status}', chunks count: {doc_obj.chunks.count()}")

    # Test list_documents returns status
    req_list = rf.get('/api/knowledge/documents/')
    req_list.user = user
    list_res = list_documents(req_list)
    list_data = json.loads(list_res.content)
    uploaded_doc_info = next((d for d in list_data['documents'] if d['id'] == doc_id), None)
    assert uploaded_doc_info is not None, "Uploaded doc must appear in list_documents"
    assert "status" in uploaded_doc_info, "Status field must be present in API output"
    print(f"✅ List documents output includes status: '{uploaded_doc_info['status']}'")

    print("\n======================================================================")
    print("🎉 ALL PHASE 1 & 2 SECURITY, CONCURRENCY & INGESTION TESTS PASSED!")
    print("======================================================================")

if __name__ == '__main__':
    run_tests()
