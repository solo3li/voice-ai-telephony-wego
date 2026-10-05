import os
import sys
import django
import requests
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from crm.models import CustomerMemory, CallSession
from django.conf import settings

INTERNAL_API_KEY = getattr(settings, 'INTERNAL_API_KEY', 'voice-internal-secret-token-key-12345')

def run_multi_customer_tests():
    print("==========================================================")
    print("🧠 MULTI-CUSTOMER CRM TWO-TIER MEMORY E2E VERIFICATION")
    print("==========================================================")

    # Setup 2 Test Users (Company A and Company B)
    u_a, _ = User.objects.get_or_create(username="test_company_a", defaults={"email": "a@example.com"})
    u_b, _ = User.objects.get_or_create(username="test_company_b", defaults={"email": "b@example.com"})
    
    # Clean previous test memories
    CustomerMemory.objects.filter(user__in=[u_a, u_b]).delete()
    CallSession.objects.filter(user__in=[u_a, u_b]).delete()

    base_url = "http://localhost:8000"
    headers = {
        "X-Internal-API-Key": INTERNAL_API_KEY,
        "Content-Type": "application/json"
    }

    # ----------------------------------------------------
    # TEST 1: Save Call & Memory for Customer 1 (Ahmed) on Company A
    # ----------------------------------------------------
    print("\n[TEST 1] Saving Call & Memory for Customer Ahmed (+201011111111) on Company A...")
    payload_ahmed = {
        "user_id": u_a.id,
        "caller_phone": "+201011111111",
        "room_name": "room_ahmed_101",
        "direction": "inbound",
        "call_goal": "استفسار عن أسعار الأجهزة",
        "duration_seconds": 45,
        "transcript_text": "العميل: السلام عليكم، أنا أحمد وعاوز أسأل عن أسعار اللابتوبات.",
        "summary": "العميل أحمد مهتم بشراء لابتوب ديل بمواصفات عالية.",
        "distilled_profile": {
            "customer_name": "أحمد محمود",
            "phone": "+201011111111",
            "preferences": ["لابتوبات ديل", "شاشات 4K"],
            "city": "القاهرة"
        }
    }
    r = requests.post(f"{base_url}/api/crm/internal/save-session-and-memory/", json=payload_ahmed, headers=headers)
    assert r.status_code == 200, f"Failed: {r.text}"
    data = r.json()
    assert data["status"] == "success"
    assert data["phone_number"] == "+201011111111"
    print("✅ Customer Ahmed memory successfully created.")

    # ----------------------------------------------------
    # TEST 2: Save Call & Memory for Customer 2 (Sara) on Company A
    # ----------------------------------------------------
    print("\n[TEST 2] Saving Call & Memory for Customer Sara (+201022222222) on Company A...")
    payload_sara = {
        "user_id": u_a.id,
        "caller_phone": "+201022222222",
        "room_name": "room_sara_202",
        "direction": "inbound",
        "call_goal": "استفسار عن الشحن للإسكندرية",
        "duration_seconds": 60,
        "transcript_text": "العميل: أهلاً، أنا سارة ومقيمة في الإسكندرية وعاوزة أعرف مصاريف الشحن.",
        "summary": "العميلة سارة استفسرت عن مواعيد الشحن للإسكندرية.",
        "distilled_profile": {
            "customer_name": "سارة علي",
            "phone": "+201022222222",
            "preferences": ["شحن سريع"],
            "city": "الإسكندرية"
        }
    }
    r = requests.post(f"{base_url}/api/crm/internal/save-session-and-memory/", json=payload_sara, headers=headers)
    assert r.status_code == 200
    print("✅ Customer Sara memory successfully created.")

    # ----------------------------------------------------
    # TEST 3: Verify Multi-Customer Isolation on Company A
    # ----------------------------------------------------
    print("\n[TEST 3] Verifying Customer Isolation between Ahmed and Sara...")
    r_ahmed = requests.get(f"{base_url}/api/crm/internal/memory/", params={"user_id": u_a.id, "caller_phone": "+201011111111"}, headers=headers)
    assert r_ahmed.status_code == 200
    ahmed_data = r_ahmed.json()
    assert "أحمد" in ahmed_data["card_text"], f"Expected Ahmed in card: {ahmed_data['card_text']}"
    assert "سارة" not in ahmed_data["card_text"], "Data leak! Sara appeared in Ahmed's card!"
    assert ahmed_data["phone_number"] == "+201011111111"

    r_sara = requests.get(f"{base_url}/api/crm/internal/memory/", params={"user_id": u_a.id, "caller_phone": "+201022222222"}, headers=headers)
    assert r_sara.status_code == 200
    sara_data = r_sara.json()
    assert "سارة" in sara_data["card_text"], f"Expected Sara in card: {sara_data['card_text']}"
    assert "أحمد" not in sara_data["card_text"], "Data leak! Ahmed appeared in Sara's card!"
    assert sara_data["phone_number"] == "+201022222222"
    print("✅ Perfect customer isolation verified between Customer 1 and Customer 2!")

    # ----------------------------------------------------
    # TEST 4: Verify Multi-Tenant Isolation (Company A vs Company B)
    # ----------------------------------------------------
    print("\n[TEST 4] Verifying Tenant Isolation (Company B calling with Ahmed's phone number)...")
    r_b = requests.get(f"{base_url}/api/crm/internal/memory/", params={"user_id": u_b.id, "caller_phone": "+201011111111"}, headers=headers)
    assert r_b.status_code == 200
    b_data = r_b.json()
    assert b_data["card_text"] == "", f"Expected empty card for Company B, got: {b_data['card_text']}"
    print("✅ Multi-tenant isolation verified: Company B cannot see Company A's customer memory!")

    # ----------------------------------------------------
    # TEST 5: Anonymous Caller with In-Call Phone Rebinding
    # ----------------------------------------------------
    print("\n[TEST 5] Anonymous Caller who speaks phone number during call...")
    payload_anon = {
        "user_id": u_a.id,
        "caller_phone": "web_dashboard",
        "room_name": "room_anon_303",
        "direction": "inbound",
        "call_goal": "طلب توصيل",
        "duration_seconds": 30,
        "transcript_text": "أنا طارق ورقمي 01099999999 سجله عندك للطلب.",
        "summary": "العميل طارق أعطى رقمه للتواصل بخصوص الطلب.",
        "distilled_profile": {
            "customer_name": "طارق عثمان",
            "phone": "+201099999999",
            "preferences": ["دفع عند الاستلام"]
        }
    }
    r = requests.post(f"{base_url}/api/crm/internal/save-session-and-memory/", json=payload_anon, headers=headers)
    assert r.status_code == 200
    anon_resp = r.json()
    assert anon_resp["phone_number"] == "+201099999999", f"Expected phone rebound to +201099999999, got: {anon_resp['phone_number']}"
    
    # Check CallSession has caller_phone updated
    cs = CallSession.objects.get(room_name="room_anon_303")
    assert cs.caller_phone == "+201099999999", f"Expected CallSession caller_phone rebound, got: {cs.caller_phone}"
    print("✅ In-call phone extraction rebound anonymous session to +201099999999 successfully!")

    # ----------------------------------------------------
    # TEST 6: Customer Search API (/api/crm/customers/)
    # ----------------------------------------------------
    print("\n[TEST 6] Testing Customer Search API...")
    # Use session to authenticate as u_a
    sess = requests.Session()
    # Force login session for u_a via client
    from django.test import Client
    client = Client()
    client.force_login(u_a)
    
    resp = client.get("/api/crm/customers/")
    assert resp.status_code == 200
    cust_data = resp.json()
    assert cust_data["status"] == "success"
    phones = [c["phone_number"] for c in cust_data["customers"]]
    assert "+201011111111" in phones
    assert "+201022222222" in phones
    assert "+201099999999" in phones
    print(f"   Found {cust_data['count']} customer memories for Company A: {phones}")

    # Search query
    resp_search = client.get("/api/crm/customers/?q=سارة")
    search_data = resp_search.json()
    assert search_data["count"] == 1
    assert search_data["customers"][0]["customer_name"] == "سارة علي"
    print("✅ Search filter (?q=سارة) returned exactly Sara!")

    # ----------------------------------------------------
    # TEST 7: Reset Memory per Customer
    # ----------------------------------------------------
    print("\n[TEST 7] Testing Customer Memory Reset for Sara (+201022222222)...")
    resp_reset = client.post("/api/crm/memory/reset/", data=json.dumps({"phone": "+201022222222"}), content_type="application/json")
    assert resp_reset.status_code == 200
    assert resp_reset.json()["status"] == "success"

    # Verify Sara's memory is empty, but Ahmed's is untouched
    sara_mem = CustomerMemory.objects.get(user=u_a, phone_number="+201022222222")
    assert sara_mem.permanent_profile == {}
    assert sara_mem.last_interaction_summary == ""

    ahmed_mem = CustomerMemory.objects.get(user=u_a, phone_number="+201011111111")
    assert "أحمد محمود" in ahmed_mem.customer_name
    assert "لابتوبات ديل" in str(ahmed_mem.permanent_profile)
    print("✅ Resetting Sara's memory cleared only Sara, Ahmed's memory remained 100% intact!")

    print("\n==========================================================")
    print("🎉 ALL MULTI-CUSTOMER MEMORY TESTS PASSED WITH 100% SUCCESS!")
    print("==========================================================")

if __name__ == '__main__':
    run_multi_customer_tests()
