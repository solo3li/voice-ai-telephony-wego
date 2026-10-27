#!/usr/bin/env python
"""
Empirical Challenger Adversarial Stress Suite for Milestone 1:
Data Models & Ticketing Foundation (CRMSupportTicket & whatsapp_dispatcher)

Verified Target Project: /root/voice-ai-telephony/test-calll-ai
Container: voice_django

Adversarial Stress Dimensions:
1. Concurrency: High-throughput concurrent ticket generation and creation across parallel threads
2. Suffix Density & Birthday Paradox: Empirical collision rate of 4-hex token generation (secrets.token_hex(2))
3. Boundary Strings: Max length CharField boundaries (150, 255, 64) and unhandled DataError on overflow
4. Unicode & Character Sets: Arabic diacritics (tashkeel), RTL/LTR bi-directional, 4-byte UTF-8 emojis, XSS/SQLi injection strings
5. Timezone & Operating Hours: Timezone conversion failure when aware datetime (UTC) is passed to is_operating_hours
6. User Invalidation: get_available_agents returning profiles with user.is_active = False
7. Type Fuzzing & Malformed Inputs: Nulls, empty strings, invalid user IDs, non-existent FKs
8. Serialization Rigor: to_dict() JSON serializability with null and populated fields
"""

import os
import sys
import json
import re
import uuid
import time
import secrets
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.db import connection, connections, IntegrityError, DataError
from django.contrib.auth.models import User
from django.utils import timezone

from crm.models import CRMSupportTicket
from crm.services.whatsapp_dispatcher import (
    AgentPresence,
    get_available_agents,
    is_operating_hours,
    create_support_ticket,
)
from call_center.models import EmployeeProfile
from telephony.models import BusinessHoursSchedule

findings = []
test_stats = {"total": 0, "passed": 0, "failed": 0}


def record_result(name: str, passed: bool, detail: str = "", vulnerability: str = ""):
    test_stats["total"] += 1
    if passed:
        test_stats["passed"] += 1
        status = "✅ PASS"
    else:
        test_stats["failed"] += 1
        status = "❌ FAIL / VULNERABILITY CONFIRMED"
        findings.append({"test": name, "detail": detail, "vulnerability": vulnerability})
    
    msg = f"{status}: {name}"
    if detail:
        msg += f" | {detail}"
    print(msg)


# ---------------------------------------------------------------------------
# Test 1: Concurrency - Parallel Ticket Creation Under Load
# ---------------------------------------------------------------------------
def test_parallel_ticket_creation_concurrency():
    print("\n--- [CHALLENGER STRESS 1] Concurrency: Parallel Ticket Creation Under Load ---")
    user = User.objects.create(username=f"stress_conc_{uuid.uuid4().hex[:8]}")

    num_workers = 20
    num_tickets = 100
    created_tickets = []
    errors = []

    def worker_create(idx):
        try:
            connections.close_all()
            phone = f"+2010{idx:08d}"
            ticket = create_support_ticket(
                user_id=user.id,
                phone_number=phone,
                customer_name=f"Concurrent Customer {idx}",
                reason=f"Concurrent Stress Reason {idx}",
                summary=f"Automated stress test payload index {idx}"
            )
            return ticket.ticket_number
        except Exception as e:
            errors.append(f"Worker {idx}: {type(e).__name__}: {str(e)}")
            return None

    start_time = time.time()
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(worker_create, i) for i in range(num_tickets)]
        for f in as_completed(futures):
            res = f.result()
            if res:
                created_tickets.append(res)
    duration = time.time() - start_time

    unique_tickets = set(created_tickets)
    success = (len(errors) == 0) and (len(unique_tickets) == num_tickets)
    record_result(
        "Concurrency: 100 parallel ticket creations across 20 threads",
        success,
        f"Completed in {duration:.2f}s ({duration/num_tickets*1000:.1f}ms/op), Created: {len(created_tickets)}/{num_tickets}, Unique: {len(unique_tickets)}, Errors: {len(errors)}"
    )


# ---------------------------------------------------------------------------
# Test 2: Suffix Density & Birthday Collision Risk in generate_ticket_number
# ---------------------------------------------------------------------------
def test_ticket_number_generation_space_and_collisions():
    print("\n--- [CHALLENGER STRESS 2] Ticket Number Suffix Density & Birthday Paradox ---")
    # Generate 500 ticket numbers without persisting them immediately
    # With 16^4 = 65,536 space, birthday paradox probability of collision in 500 samples is ~ 85%
    numbers = []
    for _ in range(500):
        numbers.append(CRMSupportTicket.generate_ticket_number())

    unique_count = len(set(numbers))
    collisions = 500 - unique_count
    format_valid = all(re.match(r'^TCK-\d{8}-[A-F0-9]{4,6}$', n) for n in numbers)

    print(f"    Total generated: 500 | Unique: {unique_count} | In-memory collisions: {collisions}")
    # We record whether in-memory collisions occur due to 4-hex digit suffix limitation
    if collisions > 0:
        record_result(
            "Ticket Generation: 4-hex suffix collision vulnerability (Birthday Paradox)",
            False,
            f"500 generations yielded {collisions} duplicate(s) before DB commit ({unique_count}/500 unique)",
            vulnerability=(
                "generate_ticket_number() relies only on DB existence check without reserving or caching candidate tokens. "
                "Because suffix is 4 hex chars (65,536 space), concurrent uncommitted generations suffer birthday collisions, "
                "leading to potential IntegrityError on concurrent save."
            )
        )
    else:
        record_result(
            "Ticket Generation: 500 ticket number generations uniqueness",
            format_valid,
            f"All 500 unique in this sample run"
        )


# ---------------------------------------------------------------------------
# Test 3: Boundary Strings & Max Length Handling (CharField Overflows)
# ---------------------------------------------------------------------------
def test_string_boundary_values():
    print("\n--- [CHALLENGER STRESS 3] Boundary String Values & Overflows ---")
    user = User.objects.create(username=f"stress_bound_{uuid.uuid4().hex[:8]}")

    # 1. Exact boundary values (150 chars for customer_name, 255 for reason, 64 for phone, 50KB summary)
    exact_name_150 = "A" * 150
    exact_reason_255 = "R" * 255
    exact_phone_64 = "1" * 64
    large_summary_50kb = "S" * (50 * 1024)

    try:
        t_exact = create_support_ticket(
            user_id=user.id,
            phone_number=exact_phone_64,
            customer_name=exact_name_150,
            reason=exact_reason_255,
            summary=large_summary_50kb
        )
        assert len(t_exact.customer_name) == 150
        assert len(t_exact.reason) == 255
        assert len(t_exact.customer_phone) == 64
        record_result("Boundary: Exact field lengths (name=150, reason=255, phone=64, summary=50KB)", True)
    except Exception as e:
        record_result("Boundary: Exact field lengths", False, f"Unexpected error: {e}")

    # 2. String Overflow: AI summary or user input exceeding 150 or 255 chars
    # If create_support_ticket receives a 200-char customer_name or 300-char reason from an AI model,
    # does it crash with DataError or truncate cleanly?
    try:
        create_support_ticket(
            user_id=user.id,
            phone_number="+201012345678",
            customer_name="C" * 200,
            reason="R" * 300
        )
        record_result("Boundary: String overflow handling", True, "Truncated or accepted without error")
    except DataError as de:
        record_result(
            "Boundary: String overflow handling on CharField (customer_name/reason)",
            False,
            f"Crashed with unhandled {type(de).__name__}: {str(de).strip()}",
            vulnerability=(
                "create_support_ticket does not truncate or validate customer_name (varchar 150) or reason (varchar 255). "
                "When LLMs/WhatsApp webhooks pass long names or detailed reasons, it throws an unhandled DataError."
            )
        )
    except Exception as e:
        record_result("Boundary: String overflow handling", False, f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Test 4: Unicode, Arabic Diacritics, RTL/LTR BiDi, Emojis & Injection Payloads
# ---------------------------------------------------------------------------
def test_unicode_and_special_character_sets():
    print("\n--- [CHALLENGER STRESS 4] Unicode, Arabic Diacritics, Emojis & Injection Strings ---")
    user = User.objects.create(username=f"stress_uni_{uuid.uuid4().hex[:8]}")

    payloads = [
        {
            "desc": "Arabic with complex diacritics (Tashkeel)",
            "name": "مُحَمَّد عَبْدُ الرَّحْمَٰنِ القَحْطَانِيُّ",
            "reason": "شَكْوَى تَأَخُّرِ الشُّحْنَةِ وَتَلَفِ الطَّرْدِ",
            "summary": "الْعَمِيلُ يُفِيدُ بِأَنَّ الطَّرْدَ رَقْمَ ٩٨٧٦٥٤ وَصَلَ تَالِفًا وَيَطْلُبُ التَّعْوِيضَ الْفَوْرِيَّ."
        },
        {
            "desc": "Mixed RTL / LTR BiDi with phone numbers and currencies",
            "name": "John Doe (عميل VIP رقم 1024)",
            "reason": "Escalation regarding order #ORD-9988-X for 1,250.50 EGP (جنيه مصري)",
            "summary": "Customer claims: 'I called at 10:30 صباحاً and agent told me تم الإلغاء'."
        },
        {
            "desc": "4-byte UTF-8 Emojis & Symbols",
            "name": "Alex 🚀🔥💯",
            "reason": "🚨 URGENT: Server down 💥⚠️",
            "summary": "Customer sent: 🤖📞❓ -> Need human agent immediately! 👨‍💼👩‍💻"
        },
        {
            "desc": "SQL Injection Payloads",
            "name": "admin' OR '1'='1",
            "reason": "'; DROP TABLE crm_support_ticket; --",
            "summary": "UNION SELECT username, password FROM auth_user; --"
        },
        {
            "desc": "HTML / XSS Payloads",
            "name": "<script>alert('XSS')</script>",
            "reason": "<img src=x onerror=alert(document.cookie)>",
            "summary": "<b>Urgent</b> <iframe src='javascript:alert(1)'></iframe>"
        }
    ]

    for p in payloads:
        try:
            t = create_support_ticket(
                user_id=user.id,
                phone_number="+201099881122",
                customer_name=p["name"],
                reason=p["reason"],
                summary=p["summary"],
                operating_hours_text="ساعات العمل الرسمية: 09:00 - 17:00"
            )
            reloaded = CRMSupportTicket.objects.get(id=t.id)
            assert reloaded.customer_name == p["name"]
            assert reloaded.reason == p["reason"]
            assert reloaded.summary == p["summary"]

            d = reloaded.to_dict()
            json_str = json.dumps(d, ensure_ascii=False)
            assert p["name"] in json_str

            record_result(f"Unicode & Payload: {p['desc']}", True, f"Verified roundtrip & JSON serialization ({len(json_str)} chars)")
        except Exception as e:
            record_result(f"Unicode & Payload: {p['desc']}", False, f"Failed: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Test 5: Timezone Mismatch in is_operating_hours (Cross-Timezone Evaluation)
# ---------------------------------------------------------------------------
def test_operating_hours_timezone_evaluation():
    print("\n--- [CHALLENGER STRESS 5] Operating Hours Cross-Timezone Evaluation ---")
    user = User.objects.create(username=f"stress_tz_{uuid.uuid4().hex[:8]}")

    days_config = {
        "monday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
        "tuesday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
        "wednesday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
        "thursday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
        "friday": {"is_workday": False, "start_time": "09:00", "end_time": "17:00"},
        "saturday": {"is_workday": False, "start_time": "09:00", "end_time": "17:00"},
        "sunday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
    }
    sched = BusinessHoursSchedule.objects.create(
        user=user,
        is_enabled=True,
        timezone="Africa/Cairo",
        days_config=days_config
    )

    tz_cairo = ZoneInfo("Africa/Cairo")
    tz_utc = ZoneInfo("UTC")

    # 1. Native Cairo evaluation at 11:00 AM Monday -> Must be OPEN
    dt_cairo = datetime(2026, 10, 26, 11, 0, 0, tzinfo=tz_cairo)
    is_open_cairo, text_cairo = is_operating_hours(user.id, dt=dt_cairo)
    record_result("Timezone: Cairo 11:00 AM (Monday) within business hours", is_open_cairo is True, f"is_open={is_open_cairo}")

    # 2. Equivalent moment in UTC: 2026-10-26 08:00 AM UTC (Cairo is UTC+3 in summer/DST)
    # Both datetimes represent the EXACT SAME physical instant!
    dt_utc = dt_cairo.astimezone(tz_utc)
    is_open_utc, text_utc = is_operating_hours(user.id, dt=dt_utc)

    # If is_operating_hours handles timezones correctly, is_open_utc MUST EQUAL is_open_cairo (True)
    if is_open_utc is False:
        record_result(
            "Timezone: UTC aware datetime conversion in is_operating_hours",
            False,
            f"08:00 UTC (11:00 Cairo) evaluated as is_open=False | Formatted text: {text_utc}",
            vulnerability=(
                "is_operating_hours does not convert aware datetimes to sched.timezone via astimezone(tz). "
                "Because Django/Celery default to timezone.now() in UTC, callers passing UTC datetimes "
                "evaluate UTC hours against local business hours, causing false 'off-hours' escalations."
            )
        )
    else:
        record_result("Timezone: UTC aware datetime conversion in is_operating_hours", True, f"is_open={is_open_utc}")


# ---------------------------------------------------------------------------
# Test 6: Employee Presence with Disabled Auth User
# ---------------------------------------------------------------------------
def test_get_available_agents_disabled_user_leak():
    print("\n--- [CHALLENGER STRESS 6] Presence: Disabled Auth User Invalidation ---")
    tenant = User.objects.create(username=f"tenant_audit_{uuid.uuid4().hex[:8]}")

    # Create agent whose EmployeeProfile is_active=True, but User is_active=False (e.g. terminated employee)
    u_disabled = User.objects.create(username=f"agent_inactive_{uuid.uuid4().hex[:8]}", is_active=False)
    profile_disabled = EmployeeProfile.objects.create(
        user=u_disabled,
        employer=tenant,
        status="ready",
        is_active=True,
        extension="9988",
        display_name="Terminated Employee"
    )

    available = get_available_agents(tenant.id)
    available_ids = list(available.values_list('id', flat=True))

    if profile_disabled.id in available_ids:
        record_result(
            "Presence: Exclude agents with disabled auth User (user.is_active=False)",
            False,
            f"EmployeeProfile {profile_disabled.id} returned in get_available_agents even though user.is_active=False",
            vulnerability=(
                "get_available_agents() only filters EmployeeProfile.is_active=True without checking "
                "user__is_active=True. Terminated employees whose user accounts were deactivated can still "
                "be assigned customer chats."
            )
        )
    else:
        record_result("Presence: Exclude agents with disabled auth User", True, "Disabled auth user excluded")


# ---------------------------------------------------------------------------
# Test 7: Type Fuzzing & Malformed Inputs on create_support_ticket & AgentPresence
# ---------------------------------------------------------------------------
def test_type_fuzzing_and_error_handling():
    print("\n--- [CHALLENGER STRESS 7] Type Fuzzing & Input Validation ---")
    user = User.objects.create(username=f"stress_fuzz_{uuid.uuid4().hex[:8]}")

    # 1. Whitespace only phone number -> Must raise ValueError
    try:
        create_support_ticket(user_id=user.id, phone_number="   \t\n  ")
        record_result("Fuzzing: Whitespace-only phone_number rejected", False, "Expected ValueError")
    except ValueError:
        record_result("Fuzzing: Whitespace-only phone_number rejected", True, "Raised ValueError as expected")

    # 2. None customer_name, reason, summary, operating_hours_text -> Defaulted cleanly
    try:
        t_nones = create_support_ticket(
            user_id=user.id,
            phone_number="+201098765432",
            customer_name=None,
            reason=None,
            summary=None,
            operating_hours_text=None,
            urgency=None,
            status=None
        )
        assert t_nones.customer_name == ""
        assert t_nones.reason == "طلب دعم بشري / شكوى"
        assert t_nones.summary == ""
        assert t_nones.operating_hours_snapshot == ""
        assert t_nones.urgency == "normal"
        assert t_nones.status == "OPEN"
        record_result("Fuzzing: None values in optional fields cleanly defaulted", True)
    except Exception as e:
        record_result("Fuzzing: None values in optional fields", False, f"Failed: {e}")

    # 3. AgentPresence fuzzing
    test_cases = [
        (None, False),
        ("", False),
        ("   ", False),
        (1234, False),
        (["ready"], False),
        ({"status": "ready"}, False),
        (True, False),
        ("Ready", True),
        ("AVAILABLE", True),
        ("ready", True),
        ("available", True),
        ("  ready  ", True),
        ("ready\n", True),
        ("BUSY", False),
        ("OFFLINE", False),
    ]
    fuzz_clean = all(AgentPresence.is_available(val) == exp for val, exp in test_cases)
    record_result("Fuzzing: AgentPresence.is_available across non-string and dirty strings", fuzz_clean)


# ---------------------------------------------------------------------------
# Test 8: Serialization & JSON Rigor of to_dict()
# ---------------------------------------------------------------------------
def test_to_dict_json_serializability():
    print("\n--- [CHALLENGER STRESS 8] to_dict() Serialization Rigor ---")
    user = User.objects.create(username=f"stress_dict_{uuid.uuid4().hex[:8]}")

    t = create_support_ticket(
        user_id=user.id,
        phone_number="+201122334455",
        customer_name="علي محمود",
        reason="استفسار",
        summary="ملخص المشكلة"
    )

    # OPEN state serialization
    d_open = t.to_dict()
    try:
        json_open = json.dumps(d_open)
        assert d_open["assigned_employee_id"] is None
        assert d_open["resolved_at"] is None
        record_result("Serialization: OPEN ticket to_dict() JSON serializable with nulls", True)
    except Exception as e:
        record_result("Serialization: OPEN ticket to_dict()", False, f"Failed: {e}")

    # RESOLVED state serialization
    t.status = "RESOLVED"
    t.resolution_notes = "تم الحل عبر الهاتف"
    t.save()
    d_res = t.to_dict()
    try:
        json_res = json.dumps(d_res)
        assert d_res["status"] == "RESOLVED"
        assert d_res["resolved_at_iso"] is not None
        record_result("Serialization: RESOLVED ticket to_dict() JSON serializable with ISO timestamps", True)
    except Exception as e:
        record_result("Serialization: RESOLVED ticket to_dict()", False, f"Failed: {e}")


# ---------------------------------------------------------------------------
# Execution & Summary
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    print("=" * 80)
    print("⚔️  EMPIRICAL CHALLENGER ADVERSARIAL STRESS SUITE (MILESTONE 1)")
    print("=" * 80)

    test_parallel_ticket_creation_concurrency()
    test_ticket_number_generation_space_and_collisions()
    test_string_boundary_values()
    test_unicode_and_special_character_sets()
    test_operating_hours_timezone_evaluation()
    test_get_available_agents_disabled_user_leak()
    test_type_fuzzing_and_error_handling()
    test_to_dict_json_serializability()

    print("\n" + "=" * 80)
    print(f"📊 SUMMARY: Total Tests: {test_stats['total']} | Passed: {test_stats['passed']} | Failed/Vulnerabilities: {test_stats['failed']}")
    print("=" * 80)

    if findings:
        print("\n🔍 DETECTED VULNERABILITIES / FAILURE MODES:")
        for idx, f in enumerate(findings, 1):
            print(f"\n[{idx}] {f['test']}")
            print(f"    Observation: {f['detail']}")
            print(f"    Impact: {f['vulnerability']}")

    print("\n" + "=" * 80)
    sys.exit(0)
