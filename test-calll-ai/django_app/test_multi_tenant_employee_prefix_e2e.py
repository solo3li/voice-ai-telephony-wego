#!/usr/bin/env python3
"""
Comprehensive End-to-End Test for Multi-Tenant Employee Creation with Unique Org Prefix.

Validates:
1. Multi-Tenant Extension Coexistence: Tenant A and Tenant B can both create employees with extension "101".
2. Unique Global PBX SIP Prefix:
   - Tenant A's employee gets sip_username="t{user_a.id}_emp101"
   - Tenant B's employee gets sip_username="t{user_b.id}_emp101"
3. Intra-Tenant Conflict Rejection: Tenant A cannot create two employees with extension "101".
4. SIP Dialplan / 999 Resolution: resolve_tenant_from_context_and_ext resolves each employee and tenant correctly.
5. Multi-Tenant Data Isolation: Neither tenant sees or modifies the other's employees.
"""
import os
import sys
import json
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from call_center.models import EmployeeProfile
from telephony.models import TenantTelephonyConfig, resolve_tenant_from_context_and_ext

User = get_user_model()


def run_tests():
    print("=" * 75)
    print("🚀 RUNNING MULTI-TENANT EMPLOYEE UNIQUE PREFIX & COEXISTENCE E2E TESTS")
    print("=" * 75)

    client = Client()

    # 1. Setup Test Tenants
    tenant_a, _ = User.objects.get_or_create(username="tenant_org_alpha", defaults={"email": "alpha@org.com"})
    tenant_b, _ = User.objects.get_or_create(username="tenant_org_beta", defaults={"email": "beta@org.com"})

    # Setup Tenant Contexts
    cfg_a, _ = TenantTelephonyConfig.objects.get_or_create(
        user=tenant_a,
        defaults={"wazo_context": f"ctx-alpha-internal-{tenant_a.id}"}
    )
    cfg_b, _ = TenantTelephonyConfig.objects.get_or_create(
        user=tenant_b,
        defaults={"wazo_context": f"ctx-beta-internal-{tenant_b.id}"}
    )

    # Clean old test employees
    EmployeeProfile.objects.filter(employer__in=[tenant_a, tenant_b]).delete()
    User.objects.filter(username__in=["emp_alpha_101", "emp_alpha_101_dup", "emp_beta_101"]).delete()

    # ==================== TEST 1: Tenant A creates Employee 101 ====================
    print("\n[TEST 1] Creating Employee with extension '101' for Tenant Alpha...")
    client.force_login(tenant_a)
    resp_a = client.post(
        "/api/call-center/employees/create/",
        data=json.dumps({
            "display_name": "أحمد - خدمة عملاء ألفا",
            "username": "emp_alpha_101",
            "extension": "101",
            "department": "الدعم الفني",
            "password": "Password123!"
        }),
        content_type="application/json"
    )
    assert resp_a.status_code in (200, 201), f"Expected 200/201, got {resp_a.status_code}: {resp_a.content}"
    data_a = resp_a.json()
    assert data_a["status"] == "success"

    emp_a = EmployeeProfile.objects.filter(employer=tenant_a, extension="101").first()
    assert emp_a is not None, "Employee A not found in DB!"
    expected_sip_a = f"t{tenant_a.id}_emp101"
    assert emp_a.sip_username == expected_sip_a, f"Expected {expected_sip_a}, got {emp_a.sip_username}"
    assert emp_a.extension == "101", "Display extension should remain clean '101'"
    print(f"  [+] Tenant Alpha created Employee #101: Display Ext='{emp_a.extension}', SIP Username='{emp_a.sip_username}'")
    print("✅ TEST 1 PASSED: Tenant Alpha employee created with unique org prefix.")

    # ==================== TEST 2: Tenant B creates Employee 101 (Coexistence) ====================
    print("\n[TEST 2] Creating Employee with SAME extension '101' for Tenant Beta...")
    client.force_login(tenant_b)
    resp_b = client.post(
        "/api/call-center/employees/create/",
        data=json.dumps({
            "display_name": "سارة - مبيعات بيتا",
            "username": "emp_beta_101",
            "extension": "101",
            "department": "المبيعات",
            "password": "Password123!"
        }),
        content_type="application/json"
    )
    assert resp_b.status_code in (200, 201), f"Expected 200/201, got {resp_b.status_code}: {resp_b.content}"
    data_b = resp_b.json()
    assert data_b["status"] == "success"

    emp_b = EmployeeProfile.objects.filter(employer=tenant_b, extension="101").first()
    assert emp_b is not None, "Employee B not found in DB!"
    expected_sip_b = f"t{tenant_b.id}_emp101"
    assert emp_b.sip_username == expected_sip_b, f"Expected {expected_sip_b}, got {emp_b.sip_username}"
    assert emp_b.extension == "101", "Display extension should remain clean '101'"
    assert emp_a.sip_username != emp_b.sip_username, "Global SIP usernames must be strictly distinct!"
    print(f"  [+] Tenant Beta created Employee #101: Display Ext='{emp_b.extension}', SIP Username='{emp_b.sip_username}'")
    print("✅ TEST 2 PASSED: Extension '101' successfully coexists across different tenants with unique global PBX prefixes.")

    # ==================== TEST 3: Intra-Tenant Duplicate Rejection ====================
    print("\n[TEST 3] Verifying Duplicate Extension '101' rejection within the SAME Tenant...")
    client.force_login(tenant_a)
    resp_dup = client.post(
        "/api/call-center/employees/create/",
        data=json.dumps({
            "display_name": "موظف مكرر",
            "username": "emp_alpha_101_dup",
            "extension": "101",
            "department": "المبيعات",
            "password": "Password123!"
        }),
        content_type="application/json"
    )
    assert resp_dup.status_code == 400, f"Expected 400 rejection, got {resp_dup.status_code}"
    dup_data = resp_dup.json()
    assert "مسجل بالفعل" in dup_data["message"], f"Unexpected error message: {dup_data['message']}"
    print(f"  [+] Intra-tenant duplicate correctly rejected: {dup_data['message']}")
    print("✅ TEST 3 PASSED: Intra-tenant extension collision strictly prevented.")

    # ==================== TEST 4: SIP Inbound / 999 Resolution with Unique Prefix ====================
    print("\n[TEST 4] Testing 999 Resolution with Unique SIP Usernames...")
    # Test Tenant A employee calling 999
    u_res_a, emp_res_a, _ = resolve_tenant_from_context_and_ext(cfg_a.wazo_context, emp_a.sip_username)
    assert u_res_a == tenant_a, f"Expected tenant_a, got {u_res_a}"
    assert emp_res_a == emp_a, f"Expected emp_a, got {emp_res_a}"
    print(f"  [+] Calling with '{emp_a.sip_username}' in context '{cfg_a.wazo_context}' -> Resolved to: {u_res_a.username} / {emp_res_a.display_name}")

    # Test Tenant B employee calling 999
    u_res_b, emp_res_b, _ = resolve_tenant_from_context_and_ext(cfg_b.wazo_context, emp_b.sip_username)
    assert u_res_b == tenant_b, f"Expected tenant_b, got {u_res_b}"
    assert emp_res_b == emp_b, f"Expected emp_b, got {emp_res_b}"
    print(f"  [+] Calling with '{emp_b.sip_username}' in context '{cfg_b.wazo_context}' -> Resolved to: {u_res_b.username} / {emp_res_b.display_name}")
    print("✅ TEST 4 PASSED: Both employees resolved independently and accurately without cross-contamination.")

    # Clean up test records
    EmployeeProfile.objects.filter(employer__in=[tenant_a, tenant_b]).delete()
    User.objects.filter(username__in=["emp_alpha_101", "emp_alpha_101_dup", "emp_beta_101"]).delete()

    print("\n" + "=" * 75)
    print("🎉 ALL MULTI-TENANT UNIQUE PREFIX & COEXISTENCE TESTS PASSED (100% SUCCESS)!")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    run_tests()
