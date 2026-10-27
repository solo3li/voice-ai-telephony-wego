#!/usr/bin/env python
"""
Milestone 1 Test Suite: Data Models & Ticketing Foundation
Covers all 8 test cases from explorer_m1_2 and spec_miner_m1_1 specifications:
1. test_ticket_model_and_reference_generation
2. test_ticket_reference_uniqueness_batch
3. test_create_support_ticket_helper
4. test_ticket_foreign_key_constraints
5. test_agent_presence_helper
6. test_get_available_agents_query
7. test_is_operating_hours_evaluation
8. test_migrations_applied_and_clean
"""

import os
import sys
import io
import re
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.contrib.auth.models import User
from django.utils import timezone
from django.core.management import call_command
from django.db.models import QuerySet

from crm.models import CRMSupportTicket
from crm.services.whatsapp_dispatcher import (
    AgentPresence,
    get_available_agents,
    is_operating_hours,
    create_support_ticket,
)
from call_center.models import EmployeeProfile
from telephony.models import BusinessHoursSchedule

passed_count = 0
failed_count = 0


def record_pass(test_name: str, detail: str = ""):
    global passed_count
    passed_count += 1
    msg = f"  ✅ PASS: {test_name}"
    if detail:
        msg += f" ({detail})"
    print(msg)


def record_fail(test_name: str, error: str):
    global failed_count
    failed_count += 1
    print(f"  ❌ FAIL: {test_name} - {error}")


def run_test(test_func):
    test_name = test_func.__name__
    print(f"\n--- Running {test_name} ---")
    try:
        test_func()
    except Exception as e:
        record_fail(test_name, f"Unhandled exception: {e}")
        import traceback
        traceback.print_exc()


# ---------------------------------------------------------------------------
# Test Case 1: Model fields, reference generation, properties, lifecycle, to_dict
# ---------------------------------------------------------------------------
def test_ticket_model_and_reference_generation():
    username = f"m1_user_tc1_{uuid.uuid4().hex[:6]}"
    user = User.objects.create(username=username, email=f"{username}@example.com")

    # 1. Create ticket directly without passing ticket_number
    ticket = CRMSupportTicket.objects.create(
        user=user,
        customer_phone="+201012345678",
        customer_name="عميل تجريبي",
        reason="شكوى تأخر طلب",
        urgency="urgent",
        summary="الطلب تأخر أكثر من ساعة",
        operating_hours_snapshot="ساعات العمل من 9 إلى 5",
        status="OPEN"
    )

    # Assert ticket_number auto-generated
    assert bool(ticket.ticket_number), "ticket_number must be generated"
    assert ticket.ticket_number.startswith("TCK-"), f"ticket_number must start with TCK-, got {ticket.ticket_number}"
    assert re.match(r'^TCK-\d{8}-[A-F0-9]{4,8}$', ticket.ticket_number), (
        f"ticket_number format mismatch: {ticket.ticket_number}"
    )
    record_pass("test_ticket_model_and_reference_generation", f"generated {ticket.ticket_number}")

    # Assert property aliases
    assert ticket.reference_code == ticket.ticket_number, "reference_code must alias ticket_number"
    assert ticket.phone_number == ticket.customer_phone, "phone_number must alias customer_phone"
    assert ticket.assigned_agent == ticket.assigned_employee, "assigned_agent must alias assigned_employee"
    assert ticket.operating_hours_text == ticket.operating_hours_snapshot, "operating_hours_text must alias operating_hours_snapshot"
    record_pass("test_ticket_model_and_reference_generation", "property aliases verified")

    # Assert status defaults and resolution lifecycle
    assert ticket.status == 'OPEN', f"Default status must be OPEN, got {ticket.status}"
    assert ticket.resolved_at is None, "resolved_at must be None for OPEN status"

    ticket.status = 'RESOLVED'
    ticket.resolution_notes = "تم تعويض العميل وقفل الشكوى"
    ticket.save()
    assert ticket.resolved_at is not None, "resolved_at must be set when transitioning to RESOLVED"
    record_pass("test_ticket_model_and_reference_generation", f"resolved_at populated: {ticket.resolved_at}")

    # Re-opening clears resolved_at
    ticket.status = 'IN_PROGRESS'
    ticket.save()
    assert ticket.resolved_at is None, "resolved_at must be cleared when status reverts to IN_PROGRESS"
    record_pass("test_ticket_model_and_reference_generation", "resolved_at cleared on re-open")

    # to_dict verification
    data = ticket.to_dict()
    required_keys = [
        "id", "ticket_number", "reference_code", "user_id", "customer_phone",
        "phone_number", "customer_name", "reason", "urgency", "summary",
        "status", "status_display", "operating_hours_snapshot", "operating_hours_text",
        "assigned_employee_id", "resolution_notes", "created_at", "created_at_iso"
    ]
    for rk in required_keys:
        assert rk in data, f"Missing key {rk} in to_dict()"
    assert data["ticket_number"] == ticket.ticket_number
    assert data["customer_phone"] == "+201012345678"
    record_pass("test_ticket_model_and_reference_generation", "to_dict keys and values validated")


# ---------------------------------------------------------------------------
# Test Case 2: Reference uniqueness batch (100 consecutive generations)
# ---------------------------------------------------------------------------
def test_ticket_reference_uniqueness_batch():
    generated_refs = set()
    total_samples = 100

    for _ in range(total_samples):
        candidate = CRMSupportTicket.generate_ticket_number()
        assert re.match(r'^TCK-\d{8}-[A-F0-9]{4,8}$', candidate), (
            f"Generated reference does not match regex: {candidate}"
        )
        assert candidate not in generated_refs, f"Duplicate reference detected: {candidate}"
        generated_refs.add(candidate)

    assert len(generated_refs) == total_samples, f"Expected {total_samples} unique refs, got {len(generated_refs)}"
    record_pass("test_ticket_reference_uniqueness_batch", f"{total_samples} unique references generated without collision")


# ---------------------------------------------------------------------------
# Test Case 3: create_support_ticket helper contract and validation
# ---------------------------------------------------------------------------
def test_create_support_ticket_helper():
    username = f"m1_user_tc3_{uuid.uuid4().hex[:6]}"
    user = User.objects.create(username=username, email=f"{username}@example.com")

    # 1. Create with int user_id
    ticket_int = create_support_ticket(
        user_id=user.id,
        phone_number="+201099887766",
        customer_name="سارة أحمد",
        reason="استفسار شحنة",
        urgency="urgent",
        summary="سؤال عن موعد التسليم",
        operating_hours_text="متاح 24/7"
    )
    assert ticket_int.id is not None, "ticket_int must be persisted with DB ID"
    assert ticket_int.user_id == user.id, "user_id must match"
    assert ticket_int.customer_phone == "+201099887766"
    assert ticket_int.customer_name == "سارة أحمد"
    assert ticket_int.reason == "استفسار شحنة"
    assert ticket_int.urgency == "urgent"
    assert ticket_int.summary == "سؤال عن موعد التسليم"
    assert ticket_int.operating_hours_snapshot == "متاح 24/7"
    assert ticket_int.status == "OPEN"
    record_pass("test_create_support_ticket_helper", f"ticket created via user.id: {ticket_int.ticket_number}")

    # 2. Create with User model instance
    ticket_obj = create_support_ticket(
        user_id=user,
        phone_number="+201011223344",
        customer_name="محمد علي",
        reason="شكوى فنية"
    )
    assert ticket_obj.id is not None
    assert ticket_obj.user_id == user.id
    record_pass("test_create_support_ticket_helper", "ticket created via User instance")

    # 3. Validation: empty phone_number must raise ValueError
    try:
        create_support_ticket(user_id=user.id, phone_number="")
        assert False, "Empty phone_number should raise ValueError"
    except ValueError:
        record_pass("test_create_support_ticket_helper", "empty phone_number rejected with ValueError")

    # 4. Validation: None user_id must raise ValueError
    try:
        create_support_ticket(user_id=None, phone_number="+201011111111")
        assert False, "None user_id should raise ValueError"
    except ValueError:
        record_pass("test_create_support_ticket_helper", "None user_id rejected with ValueError")

    # 5. Invalid urgency normalized to 'normal'
    ticket_urg = create_support_ticket(
        user_id=user.id,
        phone_number="+201055555555",
        urgency="invalid_urgency_value"
    )
    assert ticket_urg.urgency == "normal", f"Expected urgency normalized to 'normal', got {ticket_urg.urgency}"
    record_pass("test_create_support_ticket_helper", "invalid urgency normalized to normal")


# ---------------------------------------------------------------------------
# Test Case 4: Foreign Key constraints (SET_NULL on employee, CASCADE on user)
# ---------------------------------------------------------------------------
def test_ticket_foreign_key_constraints():
    tenant_user = User.objects.create(
        username=f"m1_tenant_tc4_{uuid.uuid4().hex[:6]}",
        email="tenant_fk@example.com"
    )
    emp_user = User.objects.create(
        username=f"m1_emp_tc4_{uuid.uuid4().hex[:6]}",
        email="emp_fk@example.com"
    )
    emp_profile = EmployeeProfile.objects.create(
        user=emp_user,
        employer=tenant_user,
        extension="9801",
        display_name="موظف الدعم التجريبي",
        status="ready",
        is_active=True
    )

    ticket = create_support_ticket(
        user_id=tenant_user.id,
        phone_number="+201077777777",
        customer_name="عميل الدعم",
        assigned_employee=emp_profile
    )

    assert ticket.assigned_employee_id == emp_profile.id, "ticket must link to assigned employee"

    # Delete EmployeeProfile -> Must SET_NULL without deleting ticket
    ticket_id = ticket.id
    emp_profile.delete()

    reloaded_ticket = CRMSupportTicket.objects.get(id=ticket_id)
    assert reloaded_ticket.assigned_employee is None, (
        "assigned_employee must be NULL after employee deletion (SET_NULL)"
    )
    record_pass("test_ticket_foreign_key_constraints", "SET_NULL verified on employee profile deletion")

    # Delete tenant User -> Must CASCADE and delete ticket
    tenant_user.delete()
    ticket_exists = CRMSupportTicket.objects.filter(id=ticket_id).exists()
    assert not ticket_exists, "ticket must be deleted when tenant User is deleted (CASCADE)"
    record_pass("test_ticket_foreign_key_constraints", "CASCADE verified on tenant user deletion")


# ---------------------------------------------------------------------------
# Test Case 5: AgentPresence helper status checks
# ---------------------------------------------------------------------------
def test_agent_presence_helper():
    assert AgentPresence.AVAILABLE == 'AVAILABLE'
    assert 'ready' in AgentPresence.ONLINE_STATUSES
    assert 'AVAILABLE' in AgentPresence.ONLINE_STATUSES
    assert 'available' in AgentPresence.ONLINE_STATUSES

    # True cases
    assert AgentPresence.is_available('ready') is True
    assert AgentPresence.is_available('AVAILABLE') is True
    assert AgentPresence.is_available('available') is True
    assert AgentPresence.is_available('Ready') is True
    assert AgentPresence.is_available('  ready  ') is True
    record_pass("test_agent_presence_helper", "online statuses evaluated as True")

    # False cases
    assert AgentPresence.is_available('busy') is False
    assert AgentPresence.is_available('break') is False
    assert AgentPresence.is_available('offline') is False
    assert AgentPresence.is_available('DND') is False
    assert AgentPresence.is_available('') is False
    assert AgentPresence.is_available(None) is False
    assert AgentPresence.is_available(12345) is False
    record_pass("test_agent_presence_helper", "offline/busy/invalid statuses evaluated as False")


# ---------------------------------------------------------------------------
# Test Case 6: get_available_agents QuerySet filtering & tenant scoping
# ---------------------------------------------------------------------------
def test_get_available_agents_query():
    tenant_a = User.objects.create(username=f"tenant_a_{uuid.uuid4().hex[:6]}")
    tenant_b = User.objects.create(username=f"tenant_b_{uuid.uuid4().hex[:6]}")

    def create_agent(employer, username_prefix, status, is_active, ext):
        u = User.objects.create(username=f"{username_prefix}_{uuid.uuid4().hex[:6]}")
        return EmployeeProfile.objects.create(
            user=u,
            employer=employer,
            status=status,
            is_active=is_active,
            extension=ext,
            display_name=f"Agent {ext}"
        )

    # Tenant A agents:
    agent_a1 = create_agent(tenant_a, "agent_a1", "ready", True, "101")        # Eligible
    agent_a2 = create_agent(tenant_a, "agent_a2", "AVAILABLE", True, "102")    # Eligible
    agent_a3 = create_agent(tenant_a, "agent_a3", "busy", True, "103")         # Ineligible (busy)
    agent_a4 = create_agent(tenant_a, "agent_a4", "break", True, "104")        # Ineligible (break)
    agent_a5 = create_agent(tenant_a, "agent_a5", "offline", True, "105")      # Ineligible (offline)
    agent_a6 = create_agent(tenant_a, "agent_a6", "ready", False, "106")       # Ineligible (inactive)

    # Tenant B agent:
    agent_b1 = create_agent(tenant_b, "agent_b1", "ready", True, "201")        # Belongs to Tenant B

    # Query Tenant A available agents
    qs_a = get_available_agents(tenant_a.id)
    assert isinstance(qs_a, QuerySet), "Must return a Django QuerySet"
    ids_a = set(qs_a.values_list('id', flat=True))

    assert agent_a1.id in ids_a, "ready agent must be present"
    assert agent_a2.id in ids_a, "AVAILABLE agent must be present"
    assert agent_a3.id not in ids_a, "busy agent must be excluded"
    assert agent_a4.id not in ids_a, "break agent must be excluded"
    assert agent_a5.id not in ids_a, "offline agent must be excluded"
    assert agent_a6.id not in ids_a, "inactive agent must be excluded"
    assert agent_b1.id not in ids_a, "cross-tenant agent must be excluded"
    assert len(ids_a) == 2, f"Expected exactly 2 available agents for Tenant A, got {len(ids_a)}"
    record_pass("test_get_available_agents_query", "Tenant A filtering and tenant isolation confirmed")

    # Query with User object
    qs_a_obj = get_available_agents(tenant_a)
    assert set(qs_a_obj.values_list('id', flat=True)) == ids_a
    record_pass("test_get_available_agents_query", "Query with User instance confirmed")

    # Query tenant with zero agents
    empty_tenant = User.objects.create(username=f"tenant_empty_{uuid.uuid4().hex[:6]}")
    qs_empty = get_available_agents(empty_tenant.id)
    assert qs_empty.count() == 0, "Tenant with 0 agents must return empty QuerySet"
    record_pass("test_get_available_agents_query", "Zero-agent tenant returns empty QuerySet")


# ---------------------------------------------------------------------------
# Test Case 7: is_operating_hours evaluation across all branches
# ---------------------------------------------------------------------------
def test_is_operating_hours_evaluation():
    # 1. No schedule for user -> Default 24/7 open
    user_no_sched = User.objects.create(username=f"no_sched_{uuid.uuid4().hex[:6]}")
    is_open, desc = is_operating_hours(user_no_sched.id)
    assert is_open is True, "No schedule must return True (open 24/7)"
    assert isinstance(desc, str) and len(desc) > 0, "Must return descriptive string"
    record_pass("test_is_operating_hours_evaluation", "Branch 1: No schedule returns (True, 24/7)")

    # 2. Schedule exists but is_enabled = False -> Default 24/7 open
    user_disabled = User.objects.create(username=f"disabled_sched_{uuid.uuid4().hex[:6]}")
    BusinessHoursSchedule.objects.create(
        user=user_disabled,
        is_enabled=False,
        timezone="Africa/Cairo"
    )
    is_open_dis, desc_dis = is_operating_hours(user_disabled.id)
    assert is_open_dis is True, "Disabled schedule must return True"
    record_pass("test_is_operating_hours_evaluation", "Branch 2: Disabled schedule returns (True, 24/7)")

    # 3. Schedule enabled with workday Monday (09:00 - 17:00) and offday Friday
    user_active = User.objects.create(username=f"active_sched_{uuid.uuid4().hex[:6]}")
    days_config = {
        "monday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
        "tuesday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
        "wednesday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
        "thursday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
        "friday": {"is_workday": False, "start_time": "09:00", "end_time": "17:00"},
        "saturday": {"is_workday": False, "start_time": "09:00", "end_time": "17:00"},
        "sunday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
    }
    BusinessHoursSchedule.objects.create(
        user=user_active,
        is_enabled=True,
        timezone="Africa/Cairo",
        days_config=days_config
    )

    tz = ZoneInfo("Africa/Cairo")

    # Evaluation on Monday at 11:00 AM (Within business hours)
    # 2026-10-26 is a Monday
    monday_11am = datetime(2026, 10, 26, 11, 0, 0, tzinfo=tz)
    is_open_work, desc_work = is_operating_hours(user_active.id, dt=monday_11am)
    assert is_open_work is True, f"Monday 11:00 AM must evaluate to True, got {is_open_work}"
    assert "الاثنين" in desc_work or "Monday" in desc_work or "09:00" in desc_work
    record_pass("test_is_operating_hours_evaluation", "Branch 3: Workday within hours returns (True, text)")

    # Evaluation on Monday at 11:00 PM (Outside business hours)
    monday_11pm = datetime(2026, 10, 26, 23, 0, 0, tzinfo=tz)
    is_open_off, desc_off = is_operating_hours(user_active.id, dt=monday_11pm)
    assert is_open_off is False, f"Monday 11:00 PM must evaluate to False, got {is_open_off}"
    record_pass("test_is_operating_hours_evaluation", "Branch 4: Workday after hours returns (False, text)")

    # Evaluation on Friday at 12:00 PM (Official holiday / Off day)
    # 2026-10-30 is a Friday
    friday_noon = datetime(2026, 10, 30, 12, 0, 0, tzinfo=tz)
    is_open_fri, desc_fri = is_operating_hours(user_active, dt=friday_noon)
    assert is_open_fri is False, f"Friday off-day must evaluate to False, got {is_open_fri}"
    assert "عطلة" in desc_fri or "الجمعة" in desc_fri or "Friday" in desc_fri
    record_pass("test_is_operating_hours_evaluation", "Branch 5: Off-day evaluates to (False, holiday text)")


# ---------------------------------------------------------------------------
# Test Case 8: Migrations applied and clean
# ---------------------------------------------------------------------------
def test_migrations_applied_and_clean():
    # 1. makemigrations --check --dry-run
    out = io.StringIO()
    try:
        call_command('makemigrations', 'crm', check=True, dry_run=True, stdout=out)
        record_pass("test_migrations_applied_and_clean", "makemigrations --check reports 0 pending changes")
    except SystemExit as se:
        if se.code != 0:
            raise AssertionError(f"makemigrations --check failed with code {se.code}: {out.getvalue()}")
        record_pass("test_migrations_applied_and_clean", "makemigrations --check reports 0 pending changes")

    # 2. Check model table exists in DB and has columns
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'crm_support_ticket'")
        cols = [row[0] for row in cursor.fetchall()]
    assert "ticket_number" in cols, "ticket_number column must exist in crm_support_ticket table"
    assert "customer_phone" in cols, "customer_phone column must exist in crm_support_ticket table"
    assert "status" in cols, "status column must exist in crm_support_ticket table"
    assert "assigned_employee_id" in cols, "assigned_employee_id column must exist in crm_support_ticket table"
    record_pass("test_migrations_applied_and_clean", f"crm_support_ticket table verified with {len(cols)} columns")


# ---------------------------------------------------------------------------
# Main Execution
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    print("=" * 70)
    print("🚀 RUNNING MILESTONE 1 VERIFICATION: TICKETING & PRESENCE FOUNDATION")
    print("=" * 70)

    tests = [
        test_ticket_model_and_reference_generation,
        test_ticket_reference_uniqueness_batch,
        test_create_support_ticket_helper,
        test_ticket_foreign_key_constraints,
        test_agent_presence_helper,
        test_get_available_agents_query,
        test_is_operating_hours_evaluation,
        test_migrations_applied_and_clean,
    ]

    for t in tests:
        run_test(t)

    print("\n" + "=" * 70)
    print(f"📊 SUMMARY: Passed: {passed_count} | Failed: {failed_count}")
    print("=" * 70)

    if failed_count > 0:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("🎉 ALL 8 MILESTONE 1 TESTS PASSED SUCCESSFULLY!")
        sys.exit(0)
