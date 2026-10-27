#!/usr/bin/env python
"""
Empirical Challenger Probe Suite for Milestone 1
Adversarially probes:
1. is_operating_hours: Corrupted timezones, midnight crossing, empty days_config, non-workdays, leap days.
2. get_available_agents: Non-existent tenants, 0-agent tenants, case-variant statuses, cross-tenant isolation.
3. create_support_ticket: Missing args, None values, SQL injection strings, invalid urgency strings, max length boundaries.
"""

import os
import sys
import uuid
from datetime import datetime, time
from zoneinfo import ZoneInfo

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.contrib.auth.models import User
from django.db import connection, transaction
from django.utils import timezone
from crm.models import CRMSupportTicket
from crm.services.whatsapp_dispatcher import (
    AgentPresence,
    get_available_agents,
    is_operating_hours,
    create_support_ticket,
)
from call_center.models import EmployeeProfile
from telephony.models import BusinessHoursSchedule, get_default_business_days_config


class TestResultCollector:
    def __init__(self):
        self.passes = []
        self.failures = []
        self.warnings = []

    def check(self, condition: bool, description: str, details: str = ""):
        if condition:
            self.passes.append(description)
            print(f"  ✅ PASS: {description}")
        else:
            self.failures.append((description, details))
            print(f"  ❌ FAIL: {description} | Details: {details}")

    def warn(self, description: str, details: str = ""):
        self.warnings.append((description, details))
        print(f"  ⚠️  WARN: {description} | Details: {details}")

    def summary(self):
        print("\n" + "=" * 70)
        print(f"📊 CHALLENGER EMPIRICAL RESULTS SUMMARY")
        print(f"   Passes:   {len(self.passes)}")
        print(f"   Failures: {len(self.failures)}")
        print(f"   Warnings: {len(self.warnings)}")
        print("=" * 70)
        if self.failures:
            print("\n❌ CRITICAL FAILURES:")
            for desc, det in self.failures:
                print(f"   - {desc}: {det}")
        if self.warnings:
            print("\n⚠️ WARNINGS / EDGE CASE FINDINGS:")
            for desc, det in self.warnings:
                print(f"   - {desc}: {det}")


results = TestResultCollector()


def probe_is_operating_hours():
    print("\n" + "=" * 70)
    print("🔥 PROBING 1: is_operating_hours Boundary Conditions & Fail-safes")
    print("=" * 70)

    test_user, _ = User.objects.get_or_create(username=f"challenger_hours_{uuid.uuid4().hex[:6]}")
    schedule, _ = BusinessHoursSchedule.objects.get_or_create(user=test_user)
    schedule.is_enabled = True

    # 1.1 Invalid and Corrupted Timezones
    print("\n--- 1.1 Invalid / Corrupted Timezones ---")
    corrupt_tz_candidates = [
        ("Invalid/NonExistentZone", "non-existent zone"),
        ("", "empty timezone string"),
        ("GMT+99", "out-of-bounds offset"),
        ("../../../etc/passwd", "path traversal pattern"),
        ("12345", "numeric string"),
    ]

    for bad_tz, label in corrupt_tz_candidates:
        schedule.timezone = bad_tz
        schedule.save()
        try:
            # Monday 10:00 AM UTC
            test_dt = datetime(2026, 10, 26, 10, 0, 0, tzinfo=ZoneInfo("UTC"))
            is_open, hours_text = is_operating_hours(test_user, test_dt)
            results.check(
                isinstance(is_open, bool) and isinstance(hours_text, str) and len(hours_text) > 0,
                f"Corrupted timezone ({label}: {bad_tz!r}) handled safely without exception",
                f"returned: ({is_open}, {hours_text})"
            )
            results.check(
                "UTC" in hours_text or "Africa/Cairo" in hours_text,
                f"Corrupted timezone ({label}) falls back gracefully to standard timezone in snapshot text",
                f"snapshot: {hours_text}"
            )
        except Exception as e:
            results.check(False, f"Corrupted timezone ({label}) raised unhandled exception", str(e))

    # 1.2 Midnight-Crossing Business Hours
    print("\n--- 1.2 Midnight-Crossing Business Hours ---")
    # Set Monday shift from 22:00 to 04:00 (crossing midnight)
    night_days_cfg = {
        "monday": {"is_workday": True, "start_time": "22:00", "end_time": "04:00"},
        "tuesday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
        "wednesday": {"is_workday": False, "start_time": "09:00", "end_time": "17:00"},
        "thursday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
        "friday": {"is_workday": False, "start_time": "09:00", "end_time": "17:00"},
        "saturday": {"is_workday": False, "start_time": "09:00", "end_time": "17:00"},
        "sunday": {"is_workday": False, "start_time": "09:00", "end_time": "17:00"},
    }
    schedule.timezone = "UTC"
    schedule.days_config = night_days_cfg
    schedule.save()

    # Test times for Monday night shift (22:00 -> 04:00)
    # A. Monday 21:59 (before shift) -> Should be Closed (False)
    mon_closed = datetime(2026, 10, 26, 21, 59, 0, tzinfo=ZoneInfo("UTC"))
    is_open, text = is_operating_hours(test_user, mon_closed)
    results.check(is_open is False, "Monday 21:59 is closed before 22:00-04:00 shift", f"is_open={is_open}")

    # B. Monday 22:00 (exact start) -> Should be Open (True)
    mon_start = datetime(2026, 10, 26, 22, 0, 0, tzinfo=ZoneInfo("UTC"))
    is_open, text = is_operating_hours(test_user, mon_start)
    results.check(is_open is True, "Monday 22:00 exact start is open", f"is_open={is_open}")

    # C. Monday 23:30 (during late night) -> Should be Open (True)
    mon_night = datetime(2026, 10, 26, 23, 30, 0, tzinfo=ZoneInfo("UTC"))
    is_open, text = is_operating_hours(test_user, mon_night)
    results.check(is_open is True, "Monday 23:30 is open", f"is_open={is_open}")

    # D. Monday 00:00 (midnight of Monday morning: 00:00 <= 04:00 is within 22:00-04:00 shift)
    mon_midnight = datetime(2026, 10, 26, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
    is_open, text = is_operating_hours(test_user, mon_midnight)
    results.check(is_open is True, "Monday 00:00 (midnight) is open under 22:00-04:00 window", f"is_open={is_open}")

    # E. Monday 03:59 (just before end) -> Should be Open (True)
    mon_late = datetime(2026, 10, 26, 3, 59, 0, tzinfo=ZoneInfo("UTC"))
    is_open, text = is_operating_hours(test_user, mon_late)
    results.check(is_open is True, "Monday 03:59 is open", f"is_open={is_open}")

    # F. Monday 04:00 (exact end) -> Should be Open (True)
    mon_end = datetime(2026, 10, 26, 4, 0, 0, tzinfo=ZoneInfo("UTC"))
    is_open, text = is_operating_hours(test_user, mon_end)
    results.check(is_open is True, "Monday 04:00 exact end is open", f"is_open={is_open}")

    # G. Monday 04:01 (after shift) -> Should be Closed (False)
    mon_after = datetime(2026, 10, 26, 4, 1, 0, tzinfo=ZoneInfo("UTC"))
    is_open, text = is_operating_hours(test_user, mon_after)
    results.check(is_open is False, "Monday 04:01 is closed after 04:00 end", f"is_open={is_open}")

    # H. Edge case: Zero-duration window (00:00 to 00:00)
    zero_cfg = {
        "monday": {"is_workday": True, "start_time": "00:00", "end_time": "00:00"}
    }
    schedule.days_config = zero_cfg
    schedule.save()
    zero_dt = datetime(2026, 10, 26, 12, 0, 0, tzinfo=ZoneInfo("UTC"))
    is_open, text = is_operating_hours(test_user, zero_dt)
    # 00:00 <= 12:00 <= 00:00 is False
    results.check(is_open is False, "Zero-duration window (00:00 to 00:00) at 12:00 returns False safely", f"is_open={is_open}")

    # 1.3 Empty & Corrupted days_config Dicts
    print("\n--- 1.3 Empty & Corrupted days_config Dicts ---")
    # A. Completely empty dict {}
    schedule.days_config = {}
    schedule.save()
    test_dt = datetime(2026, 10, 26, 10, 0, 0, tzinfo=ZoneInfo("UTC")) # Monday 10:00 AM
    is_open, hours_text = is_operating_hours(test_user, test_dt)
    print(f"     [Observation empty days_config={{}}] is_open={is_open}, hours_text={hours_text}")
    # Check consistency: If is_open is True, does hours_text claim holiday or open?
    if is_open and "عطلة" in hours_text:
        results.warn(
            "Semantic discrepancy on empty days_config={}: is_open=True but text says holiday",
            f"is_open={is_open}, hours_text={hours_text}"
        )
    else:
        results.check(isinstance(is_open, bool), "Empty days_config={} handled without crash", f"is_open={is_open}")

    # B. Missing day key entirely
    schedule.days_config = {"tuesday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"}}
    schedule.save()
    is_open, hours_text = is_operating_hours(test_user, test_dt) # Checking Monday
    results.check(is_open is False, "Missing day key evaluates is_open=False", f"is_open={is_open}")
    results.check("عطلة" in hours_text, "Missing day key describes day as holiday/off-day", f"text={hours_text}")

    # C. Day key is empty dict: {"monday": {}}
    schedule.days_config = {"monday": {}}
    schedule.save()
    is_open, hours_text = is_operating_hours(test_user, test_dt)
    results.check(is_open is False, "Day config is empty dict evaluates is_open=False safely", f"is_open={is_open}")

    # D. Malformed time strings in day config
    schedule.days_config = {"monday": {"is_workday": True, "start_time": "corrupt", "end_time": "invalid"}}
    schedule.save()
    try:
        is_open, hours_text = is_operating_hours(test_user, test_dt)
        # Should catch ValueError and fallback to default 09:00-17:00
        results.check(
            is_open is True,
            "Malformed time strings ('corrupt', 'invalid') fallback to default (09:00-17:00) during 10:00 AM",
            f"is_open={is_open}, hours_text={hours_text}"
        )
    except Exception as e:
        results.check(False, "Malformed time strings raised exception", str(e))

    # 1.4 Non-Workdays
    print("\n--- 1.4 Non-Workdays ---")
    schedule.days_config = {
        "friday": {"is_workday": False, "start_time": "09:00", "end_time": "17:00"},
        "sunday": {"is_workday": False, "start_time": "09:00", "end_time": "17:00"},
    }
    schedule.save()
    friday_noon = datetime(2026, 10, 30, 12, 0, 0, tzinfo=ZoneInfo("UTC")) # Friday
    is_open, hours_text = is_operating_hours(test_user, friday_noon)
    results.check(is_open is False, "Explicit non-workday (Friday) evaluates is_open=False at noon", f"is_open={is_open}")
    results.check("عطلة رسمية" in hours_text and "الجمعة" in hours_text, "Non-workday returns localized Arabic holiday snapshot", f"text={hours_text}")

    # 1.5 Leap Days & Temporal Edge Cases
    print("\n--- 1.5 Leap Days & Temporal Boundaries ---")
    # Restore standard schedule
    schedule.days_config = get_default_business_days_config()
    schedule.save()

    # Leap day 2024-02-29 (Thursday)
    leap_workday = datetime(2024, 2, 29, 11, 0, 0, tzinfo=ZoneInfo("Africa/Cairo"))
    is_open, text = is_operating_hours(test_user, leap_workday)
    results.check(is_open is True, "Past leap day 2024-02-29 (Thursday 11:00 AM) evaluates is_open=True", f"is_open={is_open}")

    # Leap day 2028-02-29 (Tuesday)
    future_leap = datetime(2028, 2, 29, 14, 0, 0, tzinfo=ZoneInfo("Africa/Cairo"))
    is_open, text = is_operating_hours(test_user, future_leap)
    results.check(is_open is True, "Future leap day 2028-02-29 (Tuesday 2:00 PM) evaluates is_open=True", f"is_open={is_open}")

    # Non-leap year transition: Feb 28 23:59:59 -> March 1 00:00:01 (2025)
    feb28_night = datetime(2025, 2, 28, 23, 59, 59, tzinfo=ZoneInfo("Africa/Cairo"))
    is_open, text = is_operating_hours(test_user, feb28_night)
    results.check(is_open is False, "Non-leap year Feb 28 23:59:59 evaluates is_open=False", f"is_open={is_open}")

    mar1_dawn = datetime(2025, 3, 1, 0, 0, 1, tzinfo=ZoneInfo("Africa/Cairo"))
    is_open, text = is_operating_hours(test_user, mar1_dawn)
    results.check(is_open is False, "Non-leap year March 1 00:00:01 evaluates is_open=False", f"is_open={is_open}")

    # Naive datetime passed into is_operating_hours
    naive_dt = datetime(2026, 10, 26, 11, 0, 0)
    try:
        is_open, text = is_operating_hours(test_user, naive_dt)
        results.check(isinstance(is_open, bool), "Naive datetime input handled gracefully without tzinfo crash", f"is_open={is_open}")
    except Exception as e:
        results.check(False, "Naive datetime input caused exception", str(e))


def probe_get_available_agents():
    print("\n" + "=" * 70)
    print("🔥 PROBING 2: get_available_agents Boundary Conditions & Casing")
    print("=" * 70)

    # 2.1 Non-existent Tenant IDs
    print("\n--- 2.1 Non-existent Tenant IDs ---")
    non_existent_ids = [999999, -1, 0]
    for nid in non_existent_ids:
        qs = get_available_agents(nid)
        results.check(
            qs.count() == 0,
            f"Non-existent tenant ID ({nid}) returns empty QuerySet without error",
            f"count={qs.count()}"
        )

    # 2.2 Tenants with 0 Agents or Inactive Agents
    print("\n--- 2.2 Tenants with 0 Agents / Inactive Agents ---")
    empty_tenant, _ = User.objects.get_or_create(username=f"challenger_zero_{uuid.uuid4().hex[:6]}")
    qs = get_available_agents(empty_tenant)
    results.check(qs.count() == 0 and not qs.exists(), "Tenant with 0 agents returns empty QuerySet", f"count={qs.count()}")

    # Tenant with only inactive agents
    inactive_tenant, _ = User.objects.get_or_create(username=f"challenger_inactive_{uuid.uuid4().hex[:6]}")
    inact_user, _ = User.objects.get_or_create(username=f"agent_inact_{uuid.uuid4().hex[:6]}")
    EmployeeProfile.objects.create(
        user=inact_user,
        employer=inactive_tenant,
        display_name="Inactive Agent",
        status="AVAILABLE",
        is_active=False
    )
    qs_inact = get_available_agents(inactive_tenant)
    results.check(qs_inact.count() == 0, "Tenant with is_active=False agents returns empty QuerySet", f"count={qs_inact.count()}")

    # Tenant with only offline agents
    offline_tenant, _ = User.objects.get_or_create(username=f"challenger_offline_{uuid.uuid4().hex[:6]}")
    off_user, _ = User.objects.get_or_create(username=f"agent_off_{uuid.uuid4().hex[:6]}")
    EmployeeProfile.objects.create(
        user=off_user,
        employer=offline_tenant,
        display_name="Offline Agent",
        status="offline",
        is_active=True
    )
    qs_off = get_available_agents(offline_tenant)
    results.check(qs_off.count() == 0, "Tenant with status='offline' agents returns empty QuerySet", f"count={qs_off.count()}")

    # 2.3 Status Case-Variants and Inconsistencies
    print("\n--- 2.3 Case-Variant Statuses & Presence Matching ---")
    case_tenant, _ = User.objects.get_or_create(username=f"challenger_case_{uuid.uuid4().hex[:6]}")

    status_matrix = [
        ("ready", True, "canonical lowercase ready"),
        ("Ready", True, "Titlecase Ready"),
        ("READY", True, "UPPERCASE READY"),
        ("available", True, "canonical lowercase available"),
        ("AVAILABLE", True, "UPPERCASE AVAILABLE"),
        ("Available", True, "Titlecase Available"),
        ("busy", False, "lowercase busy"),
        ("BUSY", False, "UPPERCASE BUSY"),
        ("break", False, "lowercase break"),
        ("BREAK", False, "UPPERCASE BREAK"),
        ("offline", False, "lowercase offline"),
    ]

    agent_map = {}
    for idx, (st, expected_presence, label) in enumerate(status_matrix):
        u, _ = User.objects.get_or_create(username=f"agent_{st.lower()}_{uuid.uuid4().hex[:6]}")
        ep = EmployeeProfile.objects.create(
            user=u,
            employer=case_tenant,
            display_name=f"Agent {st}",
            extension=f"{2000 + idx}",
            status=st,
            is_active=True
        )
        agent_map[st] = ep

        # Check AgentPresence.is_available
        presence_eval = AgentPresence.is_available(st)
        results.check(
            presence_eval == expected_presence,
            f"AgentPresence.is_available('{st}') == {expected_presence} ({label})",
            f"got {presence_eval}"
        )

    # Now query get_available_agents for this tenant
    available_qs = get_available_agents(case_tenant)
    found_statuses = set(available_qs.values_list('status', flat=True))
    print(f"     [Observation] Found statuses in get_available_agents: {found_statuses}")

    # Check which expected-available statuses were matched by get_available_agents
    for st in ["ready", "Ready", "available", "AVAILABLE"]:
        results.check(
            st in found_statuses,
            f"get_available_agents matched standard status '{st}'",
            f"found={found_statuses}"
        )

    # Critical check: UPPERCASE 'READY' and Titlecase 'Available'
    if "READY" not in found_statuses:
        results.warn(
            "DISCREPANCY DETECTED: 'READY' (uppercase) is accepted by AgentPresence.is_available() but NOT returned by get_available_agents() SQL query",
            f"get_available_agents filters status__in=['ready', 'AVAILABLE', 'available', 'Ready'] missing 'READY'"
        )
    else:
        results.check(True, "get_available_agents matches 'READY'")

    if "Available" not in found_statuses:
        results.warn(
            "DISCREPANCY DETECTED: 'Available' (Titlecase) is accepted by AgentPresence.is_available() but NOT returned by get_available_agents() SQL query",
            f"get_available_agents filters status__in=['ready', 'AVAILABLE', 'available', 'Ready'] missing 'Available'"
        )
    else:
        results.check(True, "get_available_agents matches 'Available'")

    # Non-available statuses MUST NEVER be returned
    for non_st in ["busy", "BUSY", "break", "BREAK", "offline"]:
        results.check(
            non_st not in found_statuses,
            f"get_available_agents excludes non-available status '{non_st}'",
            f"found in queryset: {non_st in found_statuses}"
        )

    # 2.4 Unscoped / None user_id Isolation Check
    print("\n--- 2.4 None user_id Cross-Tenant Query ---")
    all_qs = get_available_agents(None)
    results.check(
        all_qs.count() >= len(found_statuses),
        "get_available_agents(None) returns global queryset across tenants when user_id is None",
        f"count={all_qs.count()}"
    )


def probe_create_support_ticket():
    print("\n" + "=" * 70)
    print("🔥 PROBING 3: create_support_ticket Boundary Conditions & Injection")
    print("=" * 70)

    test_user, _ = User.objects.get_or_create(username=f"challenger_tck_{uuid.uuid4().hex[:6]}")

    # 3.1 Missing and None Arguments
    print("\n--- 3.1 Missing Arguments & None Values ---")
    # None user_id
    try:
        create_support_ticket(None, "+201001234567")
        results.check(False, "None user_id rejected with ValueError", "did not raise")
    except ValueError as e:
        results.check(True, "None user_id rejected with ValueError", str(e))

    # Empty phone_number
    for bad_phone in ["", "   ", None]:
        try:
            create_support_ticket(test_user, bad_phone)
            results.check(False, f"Invalid phone_number ({bad_phone!r}) rejected with ValueError", "did not raise")
        except ValueError as e:
            results.check(True, f"Invalid phone_number ({bad_phone!r}) rejected with ValueError", str(e))

    # Non-existent user integer ID
    try:
        create_support_ticket(999999, "+201001234567")
        results.check(False, "Non-existent user_id (999999) raises User.DoesNotExist", "did not raise")
    except User.DoesNotExist:
        results.check(True, "Non-existent user_id (999999) raises User.DoesNotExist safely")
    except Exception as e:
        results.check(False, f"Non-existent user_id unexpected exception type: {type(e)}", str(e))

    # Optional fields passed as None
    try:
        t_none = create_support_ticket(
            user_id=test_user,
            phone_number="+201000000000",
            customer_name=None,
            reason=None,
            urgency=None,
            summary=None,
            operating_hours_text=None,
            assigned_employee=None,
            status=None
        )
        results.check(
            t_none.customer_name == "" and t_none.reason == "طلب دعم بشري / شكوى" and t_none.urgency == "normal" and t_none.status == "OPEN",
            "Optional fields with None values default safely to non-null defaults",
            f"name={t_none.customer_name!r}, reason={t_none.reason!r}, urgency={t_none.urgency!r}, status={t_none.status!r}"
        )
    except Exception as e:
        results.check(False, "None values in optional fields caused crash", str(e))

    # 3.2 SQL Injection Probes
    print("\n--- 3.2 SQL Injection Probes ---")
    sql_payloads = [
        ("customer_name", "Robert'); DROP TABLE crm_support_ticket; --"),
        ("phone_number", "+201000' OR '1'='1"),
        ("reason", "Escalation'; DELETE FROM auth_user WHERE '1'='1'; --"),
        ("summary", "AI Summary' UNION SELECT id, username, password FROM auth_user --"),
        ("operating_hours_text", "Hours'; UPDATE auth_user SET is_superuser=TRUE; --"),
        ("status", "OPEN'; DROP TABLE crm_support_ticket; --"),
    ]

    initial_ticket_count = CRMSupportTicket.objects.count()
    initial_user_count = User.objects.count()

    try:
        inj_ticket = create_support_ticket(
            user_id=test_user,
            phone_number=sql_payloads[1][1],
            customer_name=sql_payloads[0][1],
            reason=sql_payloads[2][1],
            urgency="normal",
            summary=sql_payloads[3][1],
            operating_hours_text=sql_payloads[4][1],
            status="OPEN"
        )
        # Check database table exists and uncorrupted
        post_ticket_count = CRMSupportTicket.objects.count()
        post_user_count = User.objects.count()
        results.check(
            post_ticket_count == initial_ticket_count + 1 and post_user_count == initial_user_count,
            "SQL injection payloads stored as literal escaped text; database tables intact",
            f"tickets: {initial_ticket_count}->{post_ticket_count}, users: {initial_user_count}->{post_user_count}"
        )
        # Verify literal string is stored without truncation
        results.check(
            inj_ticket.customer_name == sql_payloads[0][1],
            "customer_name preserved verbatim with SQL metacharacters",
            inj_ticket.customer_name
        )
        results.check(
            inj_ticket.summary == sql_payloads[3][1],
            "summary preserved verbatim with SQL UNION SELECT payload",
            inj_ticket.summary
        )
    except Exception as e:
        results.check(False, "SQL injection test crashed with error", str(e))

    # 3.3 Urgency Normalization Probes
    print("\n--- 3.3 Urgency Normalization Probes ---")
    urgency_test_cases = [
        ("normal", "normal", "standard normal"),
        ("urgent", "urgent", "standard urgent"),
        ("URGENT", "normal", "uppercase URGENT normalized to normal"),
        ("high", "normal", "unsupported 'high' normalized to normal"),
        ("CRITICAL", "normal", "unsupported 'CRITICAL' normalized to normal"),
        ("urgent; DROP TABLE", "normal", "malicious urgency string normalized to normal"),
        ("", "normal", "empty urgency string normalized to normal"),
        (None, "normal", "None urgency normalized to normal"),
        (12345, "normal", "integer urgency normalized to normal"),
    ]

    for input_urg, expected_urg, label in urgency_test_cases:
        t = create_support_ticket(
            user_id=test_user,
            phone_number="+201099999999",
            urgency=input_urg
        )
        results.check(
            t.urgency == expected_urg,
            f"Urgency {input_urg!r} normalized to {expected_urg!r} ({label})",
            f"got {t.urgency!r}"
        )

    # 3.4 Max Length & Text Field Boundaries
    print("\n--- 3.4 Boundary & Length Probes ---")
    # A. 64-character phone number (exact max length)
    phone_64 = "1" * 64
    t_64 = create_support_ticket(test_user, phone_64)
    results.check(t_64.customer_phone == phone_64, "64-character customer_phone stored cleanly")

    # B. 150-character customer_name (exact max length)
    name_150 = "A" * 150
    t_name = create_support_ticket(test_user, "+201011111111", customer_name=name_150)
    results.check(t_name.customer_name == name_150, "150-character customer_name stored cleanly")

    # C. 255-character reason (exact max length)
    reason_255 = "R" * 255
    t_reason = create_support_ticket(test_user, "+201022222222", reason=reason_255)
    results.check(t_reason.reason == reason_255, "255-character reason stored cleanly")

    # D. Huge TextFields (10,000 chars summary & operating_hours_snapshot)
    big_summary = "S" * 10000
    big_snapshot = "H" * 10000
    t_big = create_support_ticket(
        test_user,
        "+201033333333",
        summary=big_summary,
        operating_hours_text=big_snapshot
    )
    results.check(
        len(t_big.summary) == 10000 and len(t_big.operating_hours_snapshot) == 10000,
        "10,000-character TextField payloads (summary & operating_hours_snapshot) stored without truncation",
        f"summary_len={len(t_big.summary)}, snapshot_len={len(t_big.operating_hours_snapshot)}"
    )

    # E. Unicode, Emoji, and Mixed RTL/LTR Text
    unicode_name = "م. أحمد الشريف 👨‍💻 — Support VIP! 🚀"
    unicode_reason = "شكوى انقطاع الخدمة المفاجئ + Special chars: <>&\"'/%#!"
    t_unicode = create_support_ticket(
        test_user,
        "+201044444444",
        customer_name=unicode_name,
        reason=unicode_reason
    )
    results.check(
        t_unicode.customer_name == unicode_name and t_unicode.reason == unicode_reason,
        "Unicode, Arabic RTL, Emojis, and HTML/XML metacharacters stored and retrieved faithfully",
        f"name={t_unicode.customer_name}"
    )


if __name__ == '__main__':
    print("=" * 70)
    print("🚀 RUNNING EMPIRICAL ADVERSARIAL CHALLENGER PROBES (M1)")
    print("=" * 70)

    try:
        probe_is_operating_hours()
        probe_get_available_agents()
        probe_create_support_ticket()
    except Exception as e:
        import traceback
        print(f"\n💥 CRITICAL TEST HARNESS FAILURE: {e}")
        traceback.print_exc()

    results.summary()
