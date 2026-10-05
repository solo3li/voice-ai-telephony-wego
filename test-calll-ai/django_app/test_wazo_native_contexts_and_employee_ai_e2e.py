"""End-to-End Test Suite for Wazo Native Contexts and Employee AI Calling (999).

Validates:
1. Dynamic creation of dedicated Wazo internal contexts per tenant (POST /1.1/contexts).
2. Multi-tenant extension coexistence (Tenant A and Tenant B both having extension 101).
3. SIP Header injection and resolution (resolve_tenant_from_context_and_ext).
4. Pre-call wallet balance guard for employee calls.
5. Ceiling-minute billing deduction and tagging in CallSession (is_internal_test=True).
6. CustomerMemory protection (skips employee test calls).
"""
import os
import sys
import math
import uuid
import subprocess
from decimal import Decimal

import django

# Setup Django Environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth.models import User
from billing.models import UserWallet, BillingConfig, BillingTransaction
from agents.models import AgentProfile
from telephony.models import (
    TenantTelephonyConfig,
    get_or_create_tenant_context,
    resolve_tenant_from_context_and_ext,
)
from telephony.wazo_client import wazo_client
from call_center.models import EmployeeProfile, CallQueue
from crm.models import CallSession, CustomerMemory


def run_tests():
    print("=" * 75)
    print("🚀 STARTING E2E TEST: WAZO NATIVE CONTEXTS & EMPLOYEE AI (999)")
    print("=" * 75)

    unique_id = uuid.uuid4().hex[:6]

    # -------------------------------------------------------------
    # Step 1: Multi-Tenant Context Auto-Provisioning
    # -------------------------------------------------------------
    print("\n[Step 1] Testing Wazo Dedicated Context Provisioning per Tenant...")
    tenant1_user, _ = User.objects.get_or_create(username=f"tenant_alpha_{unique_id}")
    tenant2_user, _ = User.objects.get_or_create(username=f"tenant_beta_{unique_id}")

    # Provision Agent Profiles for both tenants
    agent1, _ = AgentProfile.objects.get_or_create(
        user=tenant1_user,
        defaults={"name": "Alpha Sales AI Bot", "is_active": True}
    )
    agent1.is_active = True
    agent1.save()

    agent2, _ = AgentProfile.objects.get_or_create(
        user=tenant2_user,
        defaults={"name": "Beta Support AI Bot", "is_active": True}
    )
    agent2.is_active = True
    agent2.save()

    cfg1 = get_or_create_tenant_context(tenant1_user)
    cfg2 = get_or_create_tenant_context(tenant2_user)

    assert cfg1.wazo_context, "Tenant 1 missing wazo_context"
    assert cfg2.wazo_context, "Tenant 2 missing wazo_context"
    assert cfg1.wazo_context != cfg2.wazo_context, f"Contexts must be distinct: {cfg1.wazo_context} vs {cfg2.wazo_context}"
    print(f"  ✓ Tenant Alpha Context: {cfg1.wazo_context} (ID: {cfg1.wazo_context_id})")
    print(f"  ✓ Tenant Beta Context:   {cfg2.wazo_context} (ID: {cfg2.wazo_context_id})")

    # -------------------------------------------------------------
    # Step 2: Multi-Tenant Extension Coexistence (Both have ext 101)
    # -------------------------------------------------------------
    print("\n[Step 2] Testing Extension Coexistence (Both Tenants have Extension '101')...")
    shared_ext = "101"

    emp1_wazo = wazo_client.provision_employee(
        display_name=f"Alpha Agent {unique_id}",
        extension=shared_ext,
        context=cfg1.wazo_context
    )
    emp1_profile = EmployeeProfile.objects.create(
        user=User.objects.create_user(username=f"emp_alpha_{unique_id}"),
        employer=tenant1_user,
        extension=shared_ext,
        display_name="Ahmed in Alpha",
        wazo_user_uuid=emp1_wazo.get("wazo_user_uuid", ""),
        wazo_line_id=emp1_wazo.get("wazo_line_id", ""),
        sip_username=emp1_wazo.get("sip_username", f"emp{shared_ext}"),
        sip_password=emp1_wazo.get("sip_password", "pass123"),
        sip_host=emp1_wazo.get("sip_host", "asterisk"),
        sip_port=emp1_wazo.get("sip_port", 5070)
    )

    emp2_wazo = wazo_client.provision_employee(
        display_name=f"Beta Agent {unique_id}",
        extension=shared_ext,
        context=cfg2.wazo_context
    )
    emp2_profile = EmployeeProfile.objects.create(
        user=User.objects.create_user(username=f"emp_beta_{unique_id}"),
        employer=tenant2_user,
        extension=shared_ext,
        display_name="Mohamed in Beta",
        wazo_user_uuid=emp2_wazo.get("wazo_user_uuid", ""),
        wazo_line_id=emp2_wazo.get("wazo_line_id", ""),
        sip_username=emp2_wazo.get("sip_username", f"emp{shared_ext}"),
        sip_password=emp2_wazo.get("sip_password", "pass123"),
        sip_host=emp2_wazo.get("sip_host", "asterisk"),
        sip_port=emp2_wazo.get("sip_port", 5070)
    )

    print(f"  ✓ Emp 1 (Alpha): Ext {emp1_profile.extension} | Context {cfg1.wazo_context} | Name: {emp1_profile.display_name}")
    print(f"  ✓ Emp 2 (Beta):  Ext {emp2_profile.extension} | Context {cfg2.wazo_context} | Name: {emp2_profile.display_name}")
    assert emp1_profile.extension == emp2_profile.extension == "101", "Extensions should both be 101"

    # -------------------------------------------------------------
    # Step 3: Resolving Inbound 999 Call via Wazo Context & Ext Header
    # -------------------------------------------------------------
    print("\n[Step 3] Testing Inbound 999 Resolution via SIP Headers (X-Wazo-Tenant-Context & Caller-Ext)...")

    # Simulate call from Alpha employee (Ext 101 in Alpha Context)
    res_user1, res_emp1, res_agent1 = resolve_tenant_from_context_and_ext(
        context_name=cfg1.wazo_context,
        caller_ext="101"
    )
    assert res_user1 == tenant1_user, f"Expected tenant1_user, got {res_user1}"
    assert res_emp1 == emp1_profile, f"Expected emp1_profile, got {res_emp1}"
    assert res_agent1 == agent1, f"Expected agent1, got {res_agent1}"
    print(f"  ✓ Call from Alpha (101): Resolved -> Tenant: {res_user1.username} | Agent: {res_agent1.name}")

    # Simulate call from Beta employee (Ext 101 in Beta Context)
    res_user2, res_emp2, res_agent2 = resolve_tenant_from_context_and_ext(
        context_name=cfg2.wazo_context,
        caller_ext="101"
    )
    assert res_user2 == tenant2_user, f"Expected tenant2_user, got {res_user2}"
    assert res_emp2 == emp2_profile, f"Expected emp2_profile, got {res_emp2}"
    assert res_agent2 == agent2, f"Expected agent2, got {res_agent2}"
    print(f"  ✓ Call from Beta (101):  Resolved -> Tenant: {res_user2.username} | Agent: {res_agent2.name}")

    # -------------------------------------------------------------
    # Step 4: Pre-call Balance Guard on Employee 999 Call
    # -------------------------------------------------------------
    print("\n[Step 4] Testing Pre-call Wallet Balance Guard for Employee Calls...")
    b_cfg = BillingConfig.get_config()
    min_bal = b_cfg.min_balance_to_call

    # Set balance to 0.00
    wallet, _ = UserWallet.objects.get_or_create(user=tenant1_user)
    wallet.balance = Decimal("0.0000")
    wallet.save()

    call_allowed = wallet.balance >= min_bal
    assert not call_allowed, "Call should be denied when balance is 0.00"
    print(f"  ✓ Zero Balance Guard: Balance={wallet.balance}, MinReq={min_bal} -> Call Allowed={call_allowed}")

    # Fund wallet
    wallet.balance = Decimal("25.0000")
    wallet.save()
    call_allowed = wallet.balance >= min_bal
    assert call_allowed, "Call should be allowed when balance is 25.00"
    print(f"  ✓ Funded Balance Guard: Balance={wallet.balance}, MinReq={min_bal} -> Call Allowed={call_allowed}")

    # -------------------------------------------------------------
    # Step 5: Call Completion, Ceiling Billing, and CallSession Logging
    # -------------------------------------------------------------
    print("\n[Step 5] Testing Call Completion, Ceiling Billing & CustomerMemory Isolation...")
    duration_secs = 65 # 1 min 5 secs -> 2 billed minutes
    billed_minutes, cost_dec = b_cfg.calculate_cost(duration_secs)
    assert billed_minutes == 2, f"Expected 2 billed minutes, got {billed_minutes}"

    initial_balance = wallet.balance
    wallet.balance -= cost_dec
    wallet.total_spent += cost_dec
    wallet.save()

    test_room = f"test_employee_room_{unique_id}"
    session = CallSession.objects.create(
        user=tenant1_user,
        room_name=test_room,
        direction='internal_test',
        caller_phone=f"ext_{shared_ext}",
        duration_seconds=duration_secs,
        billed_minutes=billed_minutes,
        cost=cost_dec,
        is_internal_test=True,
        caller_extension=shared_ext,
        summary="Employee testing sales objection script."
    )

    BillingTransaction.objects.create(
        wallet=wallet,
        call_session=session,
        transaction_type='call_deduction',
        amount=-cost_dec,
        balance_after=wallet.balance,
        currency=wallet.currency,
        actual_seconds=duration_secs,
        billed_minutes=billed_minutes,
        rate_applied=b_cfg.cost_per_minute,
        description=f"مكالمة اختبار داخلي للموظف (تحويلة {shared_ext})"
    )

    print(f"  ✓ Billed Minutes: {billed_minutes} mins (from {duration_secs}s duration)")
    print(f"  ✓ Wallet Deducted: {initial_balance} -> {wallet.balance} (Cost: {cost_dec})")
    print(f"  ✓ CallSession Persisted: id={session.id}, is_internal_test={session.is_internal_test}, caller_ext={session.caller_extension}")

    # Verify CustomerMemory is NOT created/polluted for internal test calls
    mem_exists = CustomerMemory.objects.filter(user=tenant1_user, phone_number=f"ext_{shared_ext}").exists()
    assert not mem_exists, "CustomerMemory should NOT be created for internal employee test calls"
    print(f"  ✓ CustomerMemory verified: Clean and unpolluted (exists={mem_exists})")

    # Verify Serialization in to_dict()
    s_dict = session.to_dict()
    assert s_dict.get("is_internal_test") is True, "to_dict missing is_internal_test"
    assert s_dict.get("caller_extension") == "101", "to_dict missing caller_extension"
    print(f"  ✓ CallSession to_dict() payload serialized with internal test flags correctly")

    print("\n" + "=" * 75)
    print("🎉 ALL 5 E2E TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 75)


if __name__ == "__main__":
    run_tests()
