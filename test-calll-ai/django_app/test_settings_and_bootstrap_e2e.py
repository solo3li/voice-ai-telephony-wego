"""
End-to-End Test Script:
1. Verify mock_store removal
2. Test SystemSetting (Google Gemini API Key) in Django Admin & Model
3. Test dynamic retrieval via internal bootstrap API (/api/agents/internal/bootstrap/)
4. Test instantaneous update without container restarts
"""
import os
import sys
import django
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from agents.models import SystemSetting, AgentProfile, UserMCPServer
from agents.admin import SystemSettingAdmin
from django.contrib.admin.sites import AdminSite

def run_tests():
    print("=============================================================")
    print("🚀 RUNNING E2E TEST: MOCK_STORE REMOVAL & GEMINI SETTINGS API")
    print("=============================================================")

    # Test 1: Verify mock_store removal
    print("\n[TEST 1] Verifying mock_store removal from project structure...")
    mock_store_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'mock_store')
    assert not os.path.exists(mock_store_path), f"Error: mock_store folder still exists at {mock_store_path}!"
    print("✅ Verified: mock_store folder successfully removed from disk.")

    # Test 2: Verify SystemSetting Model & Admin
    print("\n[TEST 2] Testing SystemSetting model creation and admin integration...")
    # Clean previous
    SystemSetting.objects.all().delete()
    setting = SystemSetting.get_settings()
    assert setting.id == 1, "Expected SystemSetting singleton ID to be 1"
    print(f"✅ Singleton SystemSetting instance created: {setting}")

    admin_obj = SystemSettingAdmin(SystemSetting, AdminSite())
    setting.gemini_api_key = "AIzaSyTestKey1234567890abcdef"
    setting.save()

    masked = admin_obj.masked_api_key(setting)
    print(f"   Masked representation in Admin: {masked}")
    assert masked.startswith("AIza") and masked.endswith("cdef"), f"Unexpected masking: {masked}"
    assert admin_obj.has_add_permission(None) is False, "Admin should prevent adding multiple instances"
    assert admin_obj.has_delete_permission(None) is False, "Admin should prevent deleting setting"
    print("✅ SystemSetting Admin restrictions and masking verified.")

    # Test 3: Test SystemSetting.get_gemini_api_key()
    print("\n[TEST 3] Testing SystemSetting.get_gemini_api_key() helper...")
    test_key = "AIzaSyLiveGoogleKey_XYZ_987654321"
    setting.gemini_api_key = test_key
    setting.save()
    retrieved_key = SystemSetting.get_gemini_api_key()
    assert retrieved_key == test_key, f"Expected {test_key}, got {retrieved_key}"
    print(f"✅ SystemSetting.get_gemini_api_key() successfully retrieved: {retrieved_key[:8]}...{retrieved_key[-6:]}")

    # Test 4: Internal Bootstrap API reflects the key dynamically
    print("\n[TEST 4] Testing /api/agents/internal/bootstrap/ integration...")
    # Ensure test user exists
    test_user, _ = User.objects.get_or_create(username="e2e_test_user")
    AgentProfile.objects.get_or_create(user=test_user, is_active=True, defaults={"name": "مساعد الاختبار"})

    internal_api_key = os.getenv("INTERNAL_API_KEY", "voice-internal-secret-token-key-12345")
    bootstrap_url = "http://127.0.0.1:8000/api/agents/internal/bootstrap/"

    headers = {
        "X-Internal-API-Key": internal_api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "user_id": test_user.id,
        "caller_phone": "01000000000"
    }

    resp = requests.post(bootstrap_url, json=payload, headers=headers, timeout=5)
    assert resp.status_code == 200, f"Bootstrap API returned status {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("status") == "success", f"Bootstrap API did not return success: {data}"
    assert data.get("gemini_api_key") == test_key, f"Bootstrap did not return the expected Gemini key: {data.get('gemini_api_key')}"
    print(f"✅ Bootstrap API returned correct Gemini API Key: {data.get('gemini_api_key')[:8]}...{data.get('gemini_api_key')[-6:]}")

    # Test 5: Dynamic Key Update without restart
    print("\n[TEST 5] Testing dynamic update of Gemini API Key in Admin...")
    updated_key = "AIzaSyNEWUpdatedKey_999888777"
    setting.gemini_api_key = updated_key
    setting.save()

    resp2 = requests.post(bootstrap_url, json=payload, headers=headers, timeout=5)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2.get("gemini_api_key") == updated_key, f"Bootstrap did not reflect updated key: {data2.get('gemini_api_key')}"
    print(f"✅ Immediate dynamic update verified! Bootstrap returned new key: {data2.get('gemini_api_key')[:8]}...{data2.get('gemini_api_key')[-6:]}")

    # Test 6: Fallback to environment variable when empty
    print("\n[TEST 6] Testing fallback when Admin key is left empty...")
    setting.gemini_api_key = ""
    setting.save()
    fallback_key = SystemSetting.get_gemini_api_key()
    print(f"   Empty DB fallback result: '{fallback_key}' (from env GEMINI_API_KEY)")
    resp3 = requests.post(bootstrap_url, json=payload, headers=headers, timeout=5)
    data3 = resp3.json()
    assert data3.get("gemini_api_key") == fallback_key
    print("✅ Fallback logic verified.")

    print("\n=============================================================")
    print("🎉 ALL TESTS PASSED SUCCESSFULLY! (6/6)")
    print("=============================================================")

if __name__ == "__main__":
    run_tests()
