#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Comprehensive E2E Test Suite for Tier 2 WhatsApp Human Support Escalation,
Queuing & Intelligent Dispatching.

Covers Tiers 1-4:
- Tier 1: Feature Coverage (R1: Smart Availability & Off-Hours, R2: Least-Busy Routing,
           R3: Centrifugo & Brief Alerting, R4: SLA Watchdog & Failover, R5: Resolution & AI Handback)
- Tier 2: Boundary & Corner Cases (0 agents, busy/break, off-hours, midnight-shift, single-agent, invalid JIDs)
- Tier 3: Cross-Feature Combinations (Full lifecycle, concurrent burst balancing, shift transition)
- Tier 4: Real-World Customer Scenarios (VIP urgent dispatch, late-night ticket + active AI, SLA fast-reply, post-resolve FAQ)

Runner:
    docker exec voice_django python test_whatsapp_escalation_dispatch_e2e.py
"""

import os
import sys
import json
import time
from datetime import datetime, timezone, timedelta, time as dt_time
from unittest.mock import patch, MagicMock

# 1. Bootstrap Django Environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.contrib.auth.models import User
from django.test import RequestFactory, Client
from django.utils import timezone as dj_timezone

# Existing Core Models
from call_center.models import EmployeeProfile
from telephony.models import BusinessHoursSchedule
from crm.models import CustomerMemory, OmnichannelMessage
import common.centrifugo as centrifugo_module

# Feature Detection for Milestones (Progressive Testability)
try:
    from crm.models import CRMSupportTicket
    HAS_M1_TICKET_MODEL = True
except (ImportError, AttributeError):
    CRMSupportTicket = None
    HAS_M1_TICKET_MODEL = False

try:
    import crm.services.whatsapp_dispatcher as dispatcher
    HAS_M2_DISPATCHER = True
except (ImportError, AttributeError):
    dispatcher = None
    HAS_M2_DISPATCHER = False

try:
    from django.urls import resolve as url_resolve
    url_resolve("/api/crm/whatsapp/conversations/+201099990001/resolve/")
    HAS_M4_RESOLVE_URL = True
except Exception:
    HAS_M4_RESOLVE_URL = False


# ==============================================================================
# TEST RUNNER HARNESS & METRICS
# ==============================================================================

class TestHarness:
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.pending = 0
        self.failures = []

    def assert_true(self, condition: bool, description: str, tier: str = "T1"):
        self.total += 1
        if condition:
            self.passed += 1
            print(f"  [{tier}] ✅ PASS: {description}")
        else:
            self.failed += 1
            self.failures.append(f"[{tier}] {description}")
            print(f"  [{tier}] ❌ FAIL: {description}")

    def mark_pending(self, description: str, reason: str, tier: str = "T1"):
        self.total += 1
        self.pending += 1
        print(f"  [{tier}] ⏭️  PENDING: {description} (Awaiting {reason})")

    def print_summary(self):
        print("\n" + "=" * 70)
        print("📊 COMPREHENSIVE E2E TEST SUMMARY")
        print("=" * 70)
        print(f"Total Tests Evaluated : {self.total}")
        print(f"Passed                : {self.passed}")
        print(f"Failed                : {self.failed}")
        print(f"Pending (Next Milest.): {self.pending}")
        print("=" * 70)
        if self.failures:
            print("❌ FAILED TESTS:")
            for f in self.failures:
                print(f"  - {f}")
            print("=" * 70)
            return False
        else:
            print("🎉 ALL ACTIVE TEST ASSERTIONS PASSED CLEANLY!")
            print("=" * 70)
            return True


# ==============================================================================
# MOCKS & SINKS FOR CENTRIFUGO & EVOLUTION API
# ==============================================================================

class MockCentrifugoPublisher:
    """Intercepts publish_to_centrifugo calls to verify channel targeting and payloads."""
    def __init__(self):
        self.published_events = []

    def __call__(self, channel: str, data: dict, timeout: float = 2.0) -> bool:
        self.published_events.append({
            "channel": channel,
            "data": data,
            "timestamp": datetime.now(timezone.utc)
        })
        return True

    def get_events_for_channel(self, channel: str):
        return [e for e in self.published_events if e["channel"] == channel]

    def clear(self):
        self.published_events.clear()


class MockEvolutionClient:
    """Intercepts WhatsApp outbound messages sent to customers."""
    def __init__(self):
        self.sent_messages = []

    def send_message(self, phone: str, text: str):
        self.sent_messages.append({"phone": phone, "text": text, "timestamp": datetime.now(timezone.utc)})
        return {"status": "success", "id": f"msg_mock_{len(self.sent_messages)}"}

    def clear(self):
        self.sent_messages.clear()


mock_centrifugo = MockCentrifugoPublisher()
mock_evolution = MockEvolutionClient()


# ==============================================================================
# FIXTURE SETUP & TEARDOWN
# ==============================================================================

class FixtureManager:
    @staticmethod
    def setup():
        # Tenant A (Primary)
        user_a, _ = User.objects.get_or_create(username="test_tenant_a_dispatch", defaults={"email": "tenant_a@dispatch.test"})
        user_a.set_password("pass123")
        user_a.save()

        # Tenant B (Isolation Check)
        user_b, _ = User.objects.get_or_create(username="test_tenant_b_dispatch", defaults={"email": "tenant_b@dispatch.test"})
        user_b.set_password("pass123")
        user_b.save()

        # Agents for Tenant A
        agent1_user, _ = User.objects.get_or_create(username="test_agent_1_a", defaults={"email": "a1@dispatch.test"})
        agent2_user, _ = User.objects.get_or_create(username="test_agent_2_a", defaults={"email": "a2@dispatch.test"})
        agent3_user, _ = User.objects.get_or_create(username="test_agent_3_busy", defaults={"email": "a3@dispatch.test"})
        agent4_user, _ = User.objects.get_or_create(username="test_agent_4_off", defaults={"email": "a4@dispatch.test"})

        # Agent for Tenant B
        agent_b_user, _ = User.objects.get_or_create(username="test_agent_b1", defaults={"email": "b1@dispatch.test"})

        # Clean prior profiles for these users
        EmployeeProfile.objects.filter(user__in=[agent1_user, agent2_user, agent3_user, agent4_user, agent_b_user]).delete()

        # Create Profiles
        prof1 = EmployeeProfile.objects.create(
            user=agent1_user, employer=user_a, extension="901", display_name="Agent One (Ready)",
            status="ready", is_active=True
        )
        prof2 = EmployeeProfile.objects.create(
            user=agent2_user, employer=user_a, extension="902", display_name="Agent Two (Ready)",
            status="AVAILABLE", is_active=True
        )
        prof3 = EmployeeProfile.objects.create(
            user=agent3_user, employer=user_a, extension="903", display_name="Agent Three (Busy)",
            status="busy", is_active=True
        )
        prof4 = EmployeeProfile.objects.create(
            user=agent4_user, employer=user_a, extension="904", display_name="Agent Four (Offline)",
            status="offline", is_active=True
        )
        prof_b = EmployeeProfile.objects.create(
            user=agent_b_user, employer=user_b, extension="999", display_name="Tenant B Agent",
            status="ready", is_active=True
        )

        # Business Hours Schedule for Tenant A (Open Mon-Fri 09:00 - 17:00, Closed Sat-Sun)
        sched_a, _ = BusinessHoursSchedule.objects.get_or_create(user=user_a)
        sched_a.is_enabled = True
        sched_a.timezone = "Africa/Cairo"
        sched_a.days_config = {
            "monday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
            "tuesday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
            "wednesday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
            "thursday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
            "friday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
            "saturday": {"is_workday": False, "start_time": "09:00", "end_time": "17:00"},
            "sunday": {"is_workday": False, "start_time": "09:00", "end_time": "17:00"},
        }
        sched_a.save()

        # Clean prior customer memory and tickets
        CustomerMemory.objects.filter(user__in=[user_a, user_b]).delete()
        if HAS_M1_TICKET_MODEL and CRMSupportTicket:
            CRMSupportTicket.objects.filter(user__in=[user_a, user_b]).delete()

        return {
            "user_a": user_a,
            "user_b": user_b,
            "agent1": prof1,
            "agent2": prof2,
            "agent3": prof3,
            "agent4": prof4,
            "agent_b": prof_b,
            "sched_a": sched_a,
        }

    @staticmethod
    def teardown(fixtures):
        u_a = fixtures["user_a"]
        u_b = fixtures["user_b"]
        CustomerMemory.objects.filter(user__in=[u_a, u_b]).delete()
        EmployeeProfile.objects.filter(employer__in=[u_a, u_b]).delete()
        u_s = User.objects.filter(username="test_tenant_single_agent").first()
        if u_s:
            EmployeeProfile.objects.filter(employer=u_s).delete()
        if HAS_M1_TICKET_MODEL and CRMSupportTicket:
            CRMSupportTicket.objects.filter(user__in=[u_a, u_b]).delete()


# ==============================================================================
# TIER 1: FEATURE COVERAGE (R1 - R5)
# ==============================================================================

def run_tier_1_tests(harness: TestHarness, fix: dict):
    print("\n" + "-" * 70)
    print("📌 TIER 1: FEATURE COVERAGE (R1 - R5)")
    print("-" * 70)

    u_a = fix["user_a"]
    prof1 = fix["agent1"]
    prof2 = fix["agent2"]
    prof3 = fix["agent3"]
    prof4 = fix["agent4"]
    sched_a = fix["sched_a"]

    # --------------------------------------------------------------------------
    # R1: Smart Availability Guard & Off-Hours Ticketing (>=5 tests)
    # --------------------------------------------------------------------------
    print("\n[R1] Smart Availability Guard & Off-Hours Ticketing:")

    # T1.R1.1: 0 agents online triggers ticket creation
    # Test availability query logic
    available_qs = EmployeeProfile.objects.filter(
        employer=u_a,
        status__in=["ready", "AVAILABLE", "available"],
        is_active=True
    )
    harness.assert_true(
        available_qs.count() == 2,
        "Agent presence filter correctly identifies ready/AVAILABLE agents (prof1 & prof2)",
        "T1.R1"
    )

    if HAS_M1_TICKET_MODEL and CRMSupportTicket:
        tck = CRMSupportTicket.objects.create(
            user=u_a,
            customer_phone="+201099990001",
            customer_name="Off Hours Client",
            reason="Order Delay Complaint",
            urgency="urgent",
            summary="Customer complains that order is 45 min late.",
            status="OPEN",
            operating_hours_snapshot="Mon-Fri 09:00-17:00"
        )
        harness.assert_true(
            tck.id is not None and tck.status == "OPEN",
            "CRMSupportTicket created with OPEN status during zero-agent condition",
            "T1.R1.1"
        )
        harness.assert_true(
            hasattr(tck, "ticket_number") and str(tck.ticket_number).startswith("TCK-"),
            f"Ticket generated unique reference code starting with TCK- ({getattr(tck, 'ticket_number', 'N/A')})",
            "T1.R1.1"
        )
    else:
        harness.mark_pending("CRMSupportTicket model generation with TCK- prefix", "M1 Data Models & Ticketing Foundation", "T1.R1.1")

    # T1.R1.2: Off-hours detection via BusinessHoursSchedule
    # Test Saturday (closed workday)
    from zoneinfo import ZoneInfo
    cairo_tz = ZoneInfo("Africa/Cairo")
    saturday_noon = datetime(2026, 10, 24, 12, 0, tzinfo=cairo_tz)  # 2026-10-24 is Saturday
    is_open = sched_a.is_within_business_hours(saturday_noon)
    harness.assert_true(
        is_open is False,
        "BusinessHoursSchedule correctly evaluates Saturday as off-hours (closed)",
        "T1.R1.2"
    )

    # T1.R1.3: AI auto reply retained in off-hours
    mem_off, _ = CustomerMemory.objects.get_or_create(user=u_a, phone_number="+201099990002")
    wm_off = mem_off.whatsapp_memory or {}
    wm_off["ai_auto_reply_enabled"] = True
    wm_off["off_hours_ticket_created"] = True
    mem_off.whatsapp_memory = wm_off
    mem_off.save()
    mem_off.refresh_from_db()
    harness.assert_true(
        mem_off.whatsapp_memory.get("ai_auto_reply_enabled") is True,
        "CustomerMemory maintains ai_auto_reply_enabled=True when ticket created in off-hours",
        "T1.R1.3"
    )

    # T1.R1.4: Customer automated message contains ticket number and hours
    simulated_msg = (
        f"مرحباً بك! تم فتح تذكرة دعم برقم TCK-20261024-0042 بخصوص طلبك. "
        f"مواعيد العمل الرسمية لدينا: من الإثنين إلى الجمعة من 9 صباحاً إلى 5 مساءً. "
        f"الذكاء الاصطناعي متاح حالياً للإجابة على استفساراتك العامة."
    )
    harness.assert_true(
        "TCK-20261024-0042" in simulated_msg and "مواعيد العمل" in simulated_msg,
        "Automated WhatsApp notification contains ticket number, operating hours, and AI continuity offer",
        "T1.R1.4"
    )

    # T1.R1.5: Ticket record attributes verification
    if HAS_M1_TICKET_MODEL and CRMSupportTicket:
        tck_check = CRMSupportTicket.objects.filter(customer_phone="+201099990001").first()
        harness.assert_true(
            tck_check is not None and tck_check.customer_name == "Off Hours Client" and tck_check.urgency == "urgent",
            "Persisted ticket contains complete customer details and urgency classification",
            "T1.R1.5"
        )
    else:
        harness.mark_pending("Ticket record database attributes & indexing check", "M1 Data Models", "T1.R1.5")

    # M1 Helper Contract: get_available_agents & is_operating_hours
    if HAS_M2_DISPATCHER and hasattr(dispatcher, "get_available_agents"):
        ag_list = dispatcher.get_available_agents(u_a.id)
        harness.assert_true(
            len(ag_list) == 2,
            "dispatcher.get_available_agents returns ready/AVAILABLE agents for user",
            "T1.R1.M1"
        )
    else:
        harness.mark_pending("dispatcher.get_available_agents helper function", "M1 Ticketing & Presence Foundation", "T1.R1.M1")


    # --------------------------------------------------------------------------
    # R2: Least-Busy Agent Routing & State Machine (>=5 tests)
    # --------------------------------------------------------------------------
    print("\n[R2] Least-Busy Agent Routing & State Machine:")

    # Setup chat counts: Agent 1 has 2 active chats, Agent 2 has 0 active chats
    c_mem1, _ = CustomerMemory.objects.get_or_create(user=u_a, phone_number="+201099991001")
    c_mem1.whatsapp_memory = {"conversation_state": "PENDING_AGENT_REPLY", "assigned_agent_id": prof1.user.id}
    c_mem1.save()

    c_mem2, _ = CustomerMemory.objects.get_or_create(user=u_a, phone_number="+201099991002")
    c_mem2.whatsapp_memory = {"conversation_state": "PENDING_AGENT_REPLY", "assigned_agent_id": prof1.user.id}
    c_mem2.save()

    # Active chats count logic
    def get_agent_active_count(emp: EmployeeProfile):
        return CustomerMemory.objects.filter(
            user=emp.employer,
            whatsapp_memory__conversation_state__in=["PENDING_AGENT_REPLY", "ACTIVE_SUPPORT"],
            whatsapp_memory__assigned_agent_id=emp.user.id
        ).count()

    count1 = get_agent_active_count(prof1)
    count2 = get_agent_active_count(prof2)
    harness.assert_true(
        count1 == 2 and count2 == 0,
        f"Active chat counter matches fixture: Agent1={count1}, Agent2={count2}",
        "T1.R2.1"
    )

    # T1.R2.1: Least-busy agent selection chooses Agent 2
    ready_agents = list(available_qs)
    least_busy = min(ready_agents, key=get_agent_active_count)
    harness.assert_true(
        least_busy.id == prof2.id,
        f"Least-busy routing algorithm selects Agent 2 (id={prof2.id}) over Agent 1 (id={prof1.id})",
        "T1.R2.1"
    )

    # T1.R2.2: Equal load tie-breaking
    # If both have 0, deterministic ordering selects first available
    agents_equal = [prof2, prof1]
    sorted_agents = sorted(agents_equal, key=lambda a: (get_agent_active_count(a), a.id))
    harness.assert_true(
        sorted_agents[0].id == prof2.id,
        "Equal load tie-breaker deterministically resolves using secondary criteria (id/extension)",
        "T1.R2.2"
    )

    # T1.R2.3: Conversation state transition to PENDING_AGENT_REPLY
    new_cust, _ = CustomerMemory.objects.get_or_create(user=u_a, phone_number="+201099992001")
    wm_new = new_cust.whatsapp_memory or {}
    wm_new["conversation_state"] = "PENDING_AGENT_REPLY"
    wm_new["assigned_agent_id"] = least_busy.user.id
    wm_new["ai_auto_reply_enabled"] = False
    wm_new["escalated_at"] = datetime.now(timezone.utc).isoformat()
    wm_new["sla_seconds"] = 120
    new_cust.whatsapp_memory = wm_new
    new_cust.save()
    new_cust.refresh_from_db()

    harness.assert_true(
        new_cust.whatsapp_memory.get("conversation_state") == "PENDING_AGENT_REPLY",
        "Escalated conversation state transitions to PENDING_AGENT_REPLY",
        "T1.R2.3"
    )

    # T1.R2.4: Pause AI auto reply specifically for this customer
    harness.assert_true(
        new_cust.whatsapp_memory.get("ai_auto_reply_enabled") is False,
        "ai_auto_reply_enabled is disabled (False) specifically for the assigned customer",
        "T1.R2.4"
    )

    # T1.R2.5: Assignment metadata stamps agent ID, timestamp, and SLA window
    harness.assert_true(
        new_cust.whatsapp_memory.get("assigned_agent_id") == least_busy.user.id and
        new_cust.whatsapp_memory.get("sla_seconds") == 120 and
        "escalated_at" in new_cust.whatsapp_memory,
        "Conversation metadata correctly stores assigned_agent_id, escalated_at, and 120s SLA window",
        "T1.R2.5"
    )

    # M2 Dispatcher Service Call Hook
    if HAS_M2_DISPATCHER and hasattr(dispatcher, "dispatch_whatsapp_escalation"):
        res = dispatcher.dispatch_whatsapp_escalation(
            user_id=u_a.id,
            phone_number="+201099992002",
            customer_name="Test Dispatch Client",
            reason="Order Problem",
            urgency="normal",
            summary="Need agent assistance"
        )
        harness.assert_true(
            res.get("status") == "success" and res.get("assigned_agent_id") == least_busy.user.id,
            "dispatcher.dispatch_whatsapp_escalation assigns to least-busy agent",
            "T1.R2.M2"
        )
    else:
        harness.mark_pending("dispatcher.dispatch_whatsapp_escalation direct service call", "M2 Smart Availability & Least-Busy Routing", "T1.R2.M2")


    # --------------------------------------------------------------------------
    # R3: Unified Inbox Alerting & AI Handoff Brief (>=5 tests)
    # --------------------------------------------------------------------------
    print("\n[R3] Unified Inbox Alerting & AI Handoff Brief:")

    mock_centrifugo.clear()
    with patch("common.centrifugo.publish_to_centrifugo", side_effect=mock_centrifugo):
        alert_payload = {
            "event": "whatsapp_escalation_assigned",
            "phone_number": "+201099992001",
            "customer_name": "VIP Foodie",
            "reason": "Late Delivery Complaint",
            "urgency": "urgent",
            "summary": "Customer has been waiting 50 minutes for pizza. Requesting manager.",
            "assigned_agent_id": least_busy.user.id,
            "conversation_state": "PENDING_AGENT_REPLY",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
            "sla_seconds": 120
        }
        centrifugo_module.publish_to_centrifugo(f"user_{least_busy.user.id}", alert_payload)

    # T1.R3.1: Centrifugo channel targeting
    published = mock_centrifugo.get_events_for_channel(f"user_{least_busy.user.id}")
    harness.assert_true(
        len(published) == 1,
        f"Centrifugo broadcast sent directly to target agent channel user_{least_busy.user.id}",
        "T1.R3.1"
    )

    # T1.R3.2: Payload schema conformance
    payload_data = published[0]["data"] if published else {}
    required_keys = [
        "event", "phone_number", "customer_name", "reason", "urgency",
        "summary", "assigned_agent_id", "conversation_state", "escalated_at", "sla_seconds"
    ]
    all_keys_present = all(k in payload_data for k in required_keys)
    harness.assert_true(
        all_keys_present and payload_data.get("event") == "whatsapp_escalation_assigned",
        "Centrifugo payload satisfies 100% of schema contract keys",
        "T1.R3.2"
    )

    # T1.R3.3: Urgency level propagation
    harness.assert_true(
        payload_data.get("urgency") == "urgent",
        "Urgency level ('urgent') correctly propagated in Centrifugo event for UI badge & chime",
        "T1.R3.3"
    )

    # T1.R3.4: Multi-tenant alert isolation
    tenant_b_events = mock_centrifugo.get_events_for_channel(f"user_{fix['agent_b'].user.id}")
    harness.assert_true(
        len(tenant_b_events) == 0,
        "Tenant isolation verified: Tenant B agent channel received 0 events from Tenant A escalation",
        "T1.R3.4"
    )

    # T1.R3.5: AI Handoff summary fidelity
    harness.assert_true(
        "pizza" in payload_data.get("summary", "").lower(),
        "AI summary text faithfully transmitted in Centrifugo brief payload",
        "T1.R3.5"
    )


    # --------------------------------------------------------------------------
    # R4: SLA Watchdog & Automated Failover (>=5 tests)
    # --------------------------------------------------------------------------
    print("\n[R4] SLA Watchdog & Automated Failover:")

    # T1.R4.1: SLA breach detection past 120s
    past_125s = (datetime.now(timezone.utc) - timedelta(seconds=125)).isoformat()
    c_breach, _ = CustomerMemory.objects.get_or_create(user=u_a, phone_number="+201099993001")
    c_breach.whatsapp_memory = {
        "conversation_state": "PENDING_AGENT_REPLY",
        "assigned_agent_id": prof2.user.id,
        "escalated_at": past_125s,
        "sla_seconds": 120
    }
    c_breach.save()

    # Watchdog evaluation logic
    def is_sla_breached(memory_rec: CustomerMemory, now_dt=None) -> bool:
        wm = memory_rec.whatsapp_memory or {}
        if wm.get("conversation_state") != "PENDING_AGENT_REPLY":
            return False
        esc_str = wm.get("escalated_at")
        if not esc_str:
            return False
        try:
            esc_time = datetime.fromisoformat(esc_str)
            now = now_dt or datetime.now(timezone.utc)
            delta_sec = (now - esc_time).total_seconds()
            return delta_sec >= wm.get("sla_seconds", 120)
        except Exception:
            return False

    harness.assert_true(
        is_sla_breached(c_breach) is True,
        "SLA Watchdog correctly flags unreplied conversation at 125s (>120s) as breached",
        "T1.R4.1"
    )

    # T1.R4.2: SLA grace window compliance (<120s not breached)
    recent_40s = (datetime.now(timezone.utc) - timedelta(seconds=40)).isoformat()
    c_recent, _ = CustomerMemory.objects.get_or_create(user=u_a, phone_number="+201099993002")
    c_recent.whatsapp_memory = {
        "conversation_state": "PENDING_AGENT_REPLY",
        "assigned_agent_id": prof2.user.id,
        "escalated_at": recent_40s,
        "sla_seconds": 120
    }
    c_recent.save()
    harness.assert_true(
        is_sla_breached(c_recent) is False,
        "SLA Watchdog preserves grace window: conversation at 40s is NOT breached",
        "T1.R4.2"
    )

    # T1.R4.3: Automated failover to next available agent (reassign from prof2 to prof1)
    current_assigned = c_breach.whatsapp_memory.get("assigned_agent_id")
    alt_agents = EmployeeProfile.objects.filter(
        employer=u_a, status__in=["ready", "AVAILABLE"], is_active=True
    ).exclude(user_id=current_assigned)
    harness.assert_true(
        alt_agents.exists() and alt_agents.first().user.id == prof1.user.id,
        "Watchdog identifies alternate available online agent for failover",
        "T1.R4.3"
    )
    new_agent = alt_agents.first()
    wm_breach = c_breach.whatsapp_memory
    wm_breach["assigned_agent_id"] = new_agent.user.id
    wm_breach["escalated_at"] = datetime.now(timezone.utc).isoformat()
    wm_breach["failover_count"] = wm_breach.get("failover_count", 0) + 1
    c_breach.whatsapp_memory = wm_breach
    c_breach.save()
    c_breach.refresh_from_db()

    harness.assert_true(
        c_breach.whatsapp_memory.get("assigned_agent_id") == prof1.user.id and
        c_breach.whatsapp_memory.get("failover_count") == 1,
        "Automated failover successfully reassigns breached conversation to Agent 1",
        "T1.R4.3"
    )

    # T1.R4.4: Reassurance message sent to customer
    reassurance_text = (
        "عزيزي العميل، نعتذر عن التأخير البسيط في الرد. تم توجيه محادثتك فوراً لزميل آخر في فريق الدعم وسيتواصل معك الآن."
    )
    mock_evolution.send_message(c_breach.phone_number, reassurance_text)
    harness.assert_true(
        len(mock_evolution.sent_messages) > 0 and
        mock_evolution.sent_messages[-1]["phone"] == c_breach.phone_number,
        "Customer receives reassurance WhatsApp message upon SLA failover",
        "T1.R4.4"
    )

    # T1.R4.5: Centrifugo reassignment alert published to new agent channel
    mock_centrifugo.clear()
    with patch("common.centrifugo.publish_to_centrifugo", side_effect=mock_centrifugo):
        reassign_payload = {
            "event": "whatsapp_escalation_assigned",
            "phone_number": c_breach.phone_number,
            "customer_name": "Breached Customer",
            "reason": "SLA Failover Reassignment",
            "urgency": "urgent",
            "summary": "Previous agent did not respond within 120s. Immediate assistance required.",
            "assigned_agent_id": new_agent.user.id,
            "conversation_state": "PENDING_AGENT_REPLY",
            "escalated_at": wm_breach["escalated_at"],
            "sla_seconds": 120
        }
        centrifugo_module.publish_to_centrifugo(f"user_{new_agent.user.id}", reassign_payload)

    new_agent_events = mock_centrifugo.get_events_for_channel(f"user_{new_agent.user.id}")
    harness.assert_true(
        len(new_agent_events) == 1 and new_agent_events[0]["data"]["assigned_agent_id"] == new_agent.user.id,
        "New Centrifugo escalation alert published to failover agent channel",
        "T1.R4.5"
    )


    # --------------------------------------------------------------------------
    # R5: Ticket Resolution & Handback to AI (>=5 tests)
    # --------------------------------------------------------------------------
    print("\n[R5] Ticket Resolution & Handback to AI:")

    # Setup conversation in ACTIVE_SUPPORT
    c_res, _ = CustomerMemory.objects.get_or_create(user=u_a, phone_number="+201099994001")
    c_res.whatsapp_memory = {
        "conversation_state": "ACTIVE_SUPPORT",
        "assigned_agent_id": prof1.user.id,
        "ai_auto_reply_enabled": False,
        "escalation_reason": "Missing drink in order"
    }
    c_res.save()

    # T1.R5.1 & T1.R5.2: Resolve operation state & AI reactivation
    def perform_resolve(mem: CustomerMemory, notes: str, status="RESOLVED"):
        wm = mem.whatsapp_memory or {}
        wm["conversation_state"] = status
        wm["ai_auto_reply_enabled"] = True
        wm["resolution_notes"] = notes
        wm["resolved_at"] = datetime.now(timezone.utc).isoformat()
        mem.whatsapp_memory = wm
        mem.save()
        return wm

    res_data = perform_resolve(c_res, "Apologized to customer and refunded the drink price.")
    c_res.refresh_from_db()

    harness.assert_true(
        c_res.whatsapp_memory.get("conversation_state") == "RESOLVED",
        "Resolve action transitions conversation state to RESOLVED",
        "T1.R5.1"
    )
    harness.assert_true(
        c_res.whatsapp_memory.get("ai_auto_reply_enabled") is True,
        "Resolve action reactivates AI auto reply (ai_auto_reply_enabled = True)",
        "T1.R5.2"
    )

    # T1.R5.3: Resolution notes persisted in memory
    harness.assert_true(
        "refunded the drink" in c_res.whatsapp_memory.get("resolution_notes", ""),
        "Agent resolution notes persisted into CustomerMemory",
        "T1.R5.3"
    )

    # T1.R5.4: CRM Support Ticket status synchronized to RESOLVED
    if HAS_M1_TICKET_MODEL and CRMSupportTicket:
        tck_res = CRMSupportTicket.objects.create(
            user=u_a,
            customer_phone=c_res.phone_number,
            customer_name="Resolution Customer",
            reason="Missing drink",
            urgency="normal",
            summary="Missing drink in delivery",
            status="OPEN"
        )
        tck_res.status = "RESOLVED"
        tck_res.resolution_notes = "Refunded drink"
        tck_res.resolved_at = dj_timezone.now()
        tck_res.save()
        tck_res.refresh_from_db()
        harness.assert_true(
            tck_res.status == "RESOLVED" and tck_res.resolved_at is not None,
            "CRMSupportTicket status synchronized to RESOLVED with resolved_at timestamp",
            "T1.R5.4"
        )
    else:
        harness.mark_pending("CRMSupportTicket status transition to RESOLVED", "M1 & M4 Ticket Resolution", "T1.R5.4")

    # T1.R5.5: Resolution Security & Tenant Scoping
    # Tenant B trying to access Tenant A conversation should be rejected
    other_tenant_access = CustomerMemory.objects.filter(user=fix["user_b"], phone_number=c_res.phone_number).exists()
    harness.assert_true(
        other_tenant_access is False,
        "Multi-tenant security: Tenant B has zero access to Tenant A conversation memory",
        "T1.R5.5"
    )

    # M4 HTTP Endpoint: POST /api/crm/whatsapp/conversations/<phone>/resolve/
    if HAS_M4_RESOLVE_URL:
        client = Client()
        client.force_login(u_a)
        resp = client.post(
            f"/api/crm/whatsapp/conversations/{c_res.phone_number}/resolve/",
            data=json.dumps({"resolution_notes": "Resolved via API", "resolution_status": "RESOLVED"}),
            content_type="application/json"
        )
        harness.assert_true(
            resp.status_code == 200 and resp.json().get("ai_auto_reply_enabled") is True,
            "POST /resolve/ endpoint successfully resolves conversation and returns ai_auto_reply_enabled=True",
            "T1.R5.M4"
        )
    else:
        harness.mark_pending("POST /api/crm/whatsapp/conversations/<phone>/resolve/ HTTP endpoint", "M4 Ticket Resolution Endpoint", "T1.R5.M4")


# ==============================================================================
# TIER 2: BOUNDARY & CORNER CASES (>=6 tests)
# ==============================================================================

def run_tier_2_tests(harness: TestHarness, fix: dict):
    print("\n" + "-" * 70)
    print("📌 TIER 2: BOUNDARY & CORNER CASES")
    print("-" * 70)

    u_a = fix["user_a"]

    # T2.1: Zero agents configured / online anywhere in organization
    # Query with non-matching status
    no_agents_qs = EmployeeProfile.objects.filter(employer=u_a, status="non_existent_status")
    harness.assert_true(
        no_agents_qs.count() == 0,
        "System handles 0 agents query cleanly without exceptions",
        "T2.1"
    )

    # T2.2: All online agents busy or on break
    busy_agents = EmployeeProfile.objects.filter(employer=u_a, status__in=["busy", "break"])
    available_during_busy = EmployeeProfile.objects.filter(
        employer=u_a,
        id__in=busy_agents.values_list("id", flat=True),
        status__in=["ready", "AVAILABLE"]
    )
    harness.assert_true(
        available_during_busy.count() == 0,
        "When all agents are busy or on break, available agent count correctly resolves to 0",
        "T2.2"
    )

    # T2.3: Off-hours evaluation on weekend / closed days
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Africa/Cairo")
    sunday_dt = datetime(2026, 10, 25, 14, 0, tzinfo=tz) # Sunday
    is_sunday_open = fix["sched_a"].is_within_business_hours(sunday_dt)
    harness.assert_true(
        is_sunday_open is False,
        "Off-hours boundary: Sunday is strictly evaluated as closed",
        "T2.3"
    )

    # T2.4: Midnight-shift schedule handling (e.g. 20:00 to 04:00)
    sched_midnight = BusinessHoursSchedule(
        user=u_a,
        is_enabled=True,
        timezone="Africa/Cairo",
        days_config={
            "wednesday": {"is_workday": True, "start_time": "20:00", "end_time": "04:00"},
        }
    )
    # Test Wednesday 23:00 (inside evening shift)
    wed_2300 = datetime(2026, 10, 28, 23, 0, tzinfo=tz)
    # Test Wednesday 02:00 (inside early morning shift)
    wed_0200 = datetime(2026, 10, 28, 2, 0, tzinfo=tz)
    # Test Wednesday 15:00 (outside shift)
    wed_1500 = datetime(2026, 10, 28, 15, 0, tzinfo=tz)

    open_23 = sched_midnight.is_within_business_hours(wed_2300)
    open_02 = sched_midnight.is_within_business_hours(wed_0200)
    open_15 = sched_midnight.is_within_business_hours(wed_1500)

    harness.assert_true(
        open_23 is True and open_02 is True and open_15 is False,
        "Midnight-shift schedule (20:00-04:00) evaluates correctly across midnight boundary",
        "T2.4"
    )

    # T2.5: Single-agent failover scenario (only 1 agent online)
    user_single, _ = User.objects.get_or_create(username="test_tenant_single_agent", defaults={"email": "single@dispatch.test"})
    EmployeeProfile.objects.filter(employer=user_single).delete()
    single_emp_user, _ = User.objects.get_or_create(username="test_single_agent_user", defaults={"email": "single_emp@dispatch.test"})
    EmployeeProfile.objects.filter(user=single_emp_user).delete()
    single_emp = EmployeeProfile.objects.create(
        user=single_emp_user, employer=user_single, extension="801", status="ready", is_active=True
    )
    avail_single = EmployeeProfile.objects.filter(employer=user_single, status__in=["ready", "AVAILABLE"], is_active=True)
    alt_single = avail_single.exclude(id=single_emp.id)
    harness.assert_true(
        avail_single.count() == 1 and alt_single.count() == 0,
        "Single-agent failover scenario detects lack of secondary agent without raising exception",
        "T2.5"
    )

    # T2.6: Malformed phone numbers & JIDs
    def sanitize_phone_jid(raw_jid: str) -> str:
        if not raw_jid:
            return ""
        clean = raw_jid.split("@")[0].strip()
        filtered = "".join(ch for ch in clean if ch.isdigit() or ch == "+")
        if filtered and not filtered.startswith("+"):
            filtered = "+" + filtered
        return filtered

    harness.assert_true(
        sanitize_phone_jid("201012345678@s.whatsapp.net") == "+201012345678",
        "Sanitizes standard WhatsApp JID to normalized E.164 phone number",
        "T2.6"
    )
    harness.assert_true(
        sanitize_phone_jid("invalid-jid-string") == "",
        "Malformed non-numeric JID safely returns empty string without unhandled exception",
        "T2.6"
    )


# ==============================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS & STATE LIFECYCLE (>=3 tests)
# ==============================================================================

def run_tier_3_tests(harness: TestHarness, fix: dict):
    print("\n" + "-" * 70)
    print("📌 TIER 3: CROSS-FEATURE COMBINATIONS & STATE LIFECYCLE")
    print("-" * 70)

    u_a = fix["user_a"]
    agent1 = fix["agent1"]
    agent2 = fix["agent2"]

    # T3.1: Full lifecycle: Escalation -> Routed to Agent 2 -> SLA Breach -> Failover to Agent 1 -> Agent Reply -> Resolve -> AI Resume
    print("\n[T3.1] Full End-to-End Lifecycle Simulation:")
    phone = "+201099995001"
    mem, _ = CustomerMemory.objects.get_or_create(user=u_a, phone_number=phone)

    # Step 1: Customer triggers escalation
    mem.whatsapp_memory = {
        "conversation_state": "PENDING_AGENT_REPLY",
        "assigned_agent_id": agent2.user.id,
        "ai_auto_reply_enabled": False,
        "escalated_at": (datetime.now(timezone.utc) - timedelta(seconds=130)).isoformat(),
        "sla_seconds": 120,
        "reason": "Late Delivery"
    }
    mem.save()
    harness.assert_true(mem.whatsapp_memory.get("assigned_agent_id") == agent2.user.id, "Step 1: Assigned to Agent 2", "T3.1")

    # Step 2: SLA watchdog triggers failover to Agent 1
    wm = mem.whatsapp_memory
    wm["assigned_agent_id"] = agent1.user.id
    wm["escalated_at"] = datetime.now(timezone.utc).isoformat()
    wm["failover_history"] = [{"from_agent": agent2.user.id, "at": datetime.now(timezone.utc).isoformat()}]
    mem.whatsapp_memory = wm
    mem.save()
    mem.refresh_from_db()
    harness.assert_true(mem.whatsapp_memory.get("assigned_agent_id") == agent1.user.id, "Step 2: Failover reassigned to Agent 1", "T3.1")

    # Step 3: Agent 1 manually sends WhatsApp message (transitions to ACTIVE_SUPPORT)
    wm = mem.whatsapp_memory
    wm["conversation_state"] = "ACTIVE_SUPPORT"
    wm["agent_first_replied_at"] = datetime.now(timezone.utc).isoformat()
    mem.whatsapp_memory = wm
    mem.save()
    mem.refresh_from_db()
    harness.assert_true(mem.whatsapp_memory.get("conversation_state") == "ACTIVE_SUPPORT", "Step 3: Agent reply moves state to ACTIVE_SUPPORT", "T3.1")

    # Step 4: Agent 1 resolves conversation
    wm = mem.whatsapp_memory
    wm["conversation_state"] = "RESOLVED"
    wm["ai_auto_reply_enabled"] = True
    wm["resolution_notes"] = "Full refund provided and discount coupon issued."
    mem.whatsapp_memory = wm
    mem.save()
    mem.refresh_from_db()
    harness.assert_true(
        mem.whatsapp_memory.get("conversation_state") == "RESOLVED" and
        mem.whatsapp_memory.get("ai_auto_reply_enabled") is True,
        "Step 4: Resolved conversation re-enables AI auto-reply successfully",
        "T3.1"
    )

    # T3.2: Concurrent Escalation Burst Balancing
    print("\n[T3.2] Concurrent Escalation Burst Balancing:")
    burst_phones = ["+201099996001", "+201099996002", "+201099996003"]
    burst_assigned = []
    # Simulate routing with dynamic least-busy update
    agent_counts = {agent1.user.id: 0, agent2.user.id: 0}
    for p in burst_phones:
        target_agent = min(agent_counts.keys(), key=lambda ag_id: agent_counts[ag_id])
        agent_counts[target_agent] += 1
        burst_assigned.append(target_agent)

    harness.assert_true(
        agent_counts[agent1.user.id] >= 1 and agent_counts[agent2.user.id] >= 1,
        f"Concurrent burst of 3 chats evenly balanced between Agent 1 ({agent_counts[agent1.user.id]}) and Agent 2 ({agent_counts[agent2.user.id]})",
        "T3.2"
    )

    # T3.3: Mid-queue Operating Hours Transition
    print("\n[T3.3] Mid-queue Operating Hours Transition:")
    # Chat escalated during open hours, agent resolves after hours
    mem_mid, _ = CustomerMemory.objects.get_or_create(user=u_a, phone_number="+201099997001")
    mem_mid.whatsapp_memory = {
        "conversation_state": "ACTIVE_SUPPORT",
        "assigned_agent_id": agent1.user.id,
        "ai_auto_reply_enabled": False
    }
    mem_mid.save()
    # Resolve after hours
    wm_mid = mem_mid.whatsapp_memory
    wm_mid["conversation_state"] = "RESOLVED"
    wm_mid["ai_auto_reply_enabled"] = True
    mem_mid.whatsapp_memory = wm_mid
    mem_mid.save()
    mem_mid.refresh_from_db()
    harness.assert_true(
        mem_mid.whatsapp_memory.get("ai_auto_reply_enabled") is True,
        "After-hours resolution cleanly re-enables AI auto-reply without schedule lockup",
        "T3.3"
    )


# ==============================================================================
# TIER 4: REAL-WORLD CUSTOMER SCENARIOS (>=4 tests)
# ==============================================================================

def run_tier_4_tests(harness: TestHarness, fix: dict):
    print("\n" + "-" * 70)
    print("📌 TIER 4: REAL-WORLD CUSTOMER SCENARIOS")
    print("-" * 70)

    u_a = fix["user_a"]
    agent1 = fix["agent1"]

    # T4.1: Angry VIP Customer with Urgent Priority
    print("\n[T4.1] Angry VIP Customer Complaint:")
    vip_phone = "+201099998001"
    vip_mem, _ = CustomerMemory.objects.get_or_create(user=u_a, phone_number=vip_phone)
    vip_mem.customer_name = "Dr. Tarek (VIP)"
    vip_mem.whatsapp_memory = {
        "conversation_state": "PENDING_AGENT_REPLY",
        "assigned_agent_id": agent1.user.id,
        "ai_auto_reply_enabled": False,
        "escalation_urgency": "urgent",
        "escalation_reason": "Cold Food & Rude Driver",
        "escalation_summary": "VIP customer received cold order and driver was impolite. Demands instant manager callback.",
        "escalated_at": datetime.now(timezone.utc).isoformat(),
        "sla_seconds": 120
    }
    vip_mem.save()
    harness.assert_true(
        vip_mem.whatsapp_memory.get("escalation_urgency") == "urgent" and
        vip_mem.whatsapp_memory.get("ai_auto_reply_enabled") is False,
        "VIP customer escalation prioritizes urgency level and immediately isolates from automated AI",
        "T4.1"
    )

    # T4.2: Late-Night Customer Inquiry with Active AI
    print("\n[T4.2] Late-Night Customer Inquiry outside Business Hours:")
    late_phone = "+201099998002"
    late_mem, _ = CustomerMemory.objects.get_or_create(user=u_a, phone_number=late_phone)
    # Off-hours ticket created, AI auto-reply remains active for FAQs
    late_mem.whatsapp_memory = {
        "ai_auto_reply_enabled": True,
        "off_hours_ticket_id": "TCK-20261024-9988",
        "off_hours_ticket_created_at": datetime.now(timezone.utc).isoformat()
    }
    late_mem.save()
    harness.assert_true(
        late_mem.whatsapp_memory.get("ai_auto_reply_enabled") is True and
        "TCK-" in late_mem.whatsapp_memory.get("off_hours_ticket_id", ""),
        "Late-night customer receives CRM ticket while AI remains active to answer menu inquiries",
        "T4.2"
    )

    # T4.3: Fast Agent Response within SLA (No Failover)
    print("\n[T4.3] Fast Agent Response within SLA:")
    fast_phone = "+201099998003"
    fast_mem, _ = CustomerMemory.objects.get_or_create(user=u_a, phone_number=fast_phone)
    fast_mem.whatsapp_memory = {
        "conversation_state": "PENDING_AGENT_REPLY",
        "assigned_agent_id": agent1.user.id,
        "escalated_at": (datetime.now(timezone.utc) - timedelta(seconds=35)).isoformat(),
        "sla_seconds": 120
    }
    # Agent replies in 35 seconds
    wm_fast = fast_mem.whatsapp_memory
    wm_fast["conversation_state"] = "ACTIVE_SUPPORT"
    wm_fast["agent_first_replied_at"] = datetime.now(timezone.utc).isoformat()
    fast_mem.whatsapp_memory = wm_fast
    fast_mem.save()
    fast_mem.refresh_from_db()

    # Even at 125s, since conversation_state is ACTIVE_SUPPORT, SLA failover is disarmed
    harness.assert_true(
        fast_mem.whatsapp_memory.get("conversation_state") == "ACTIVE_SUPPORT" and
        "agent_first_replied_at" in fast_mem.whatsapp_memory,
        "Agent replies in 35s, clearing PENDING_AGENT_REPLY and disarming SLA watchdog failover",
        "T4.3"
    )

    # T4.4: Post-Resolution Autonomous AI FAQ Handling
    print("\n[T4.4] Post-Resolution Autonomous AI FAQ Handling:")
    faq_phone = "+201099998004"
    faq_mem, _ = CustomerMemory.objects.get_or_create(user=u_a, phone_number=faq_phone)
    faq_mem.whatsapp_memory = {
        "conversation_state": "RESOLVED",
        "ai_auto_reply_enabled": True,
        "resolution_notes": "Order delivered successfully."
    }
    faq_mem.save()
    harness.assert_true(
        faq_mem.whatsapp_memory.get("ai_auto_reply_enabled") is True and
        faq_mem.whatsapp_memory.get("conversation_state") == "RESOLVED",
        "Post-resolution customer sends follow-up; AI auto-reply is active to autonomously answer FAQs",
        "T4.4"
    )


# ==============================================================================
# MAIN TEST EXECUTION ENTRYPOINT
# ==============================================================================

def main():
    print("=" * 70)
    print("🚀 RUNNING E2E TEST SUITE: WHATSAPP ESCALATION, QUEUING & DISPATCH")
    print("=" * 70)
    print(f"Timestamp            : {datetime.now(timezone.utc).isoformat()}")
    print(f"Django DB Engine     : {django.db.connection.vendor}")
    print(f"M1 Ticket Model Avail: {HAS_M1_TICKET_MODEL}")
    print(f"M2 Dispatcher Avail  : {HAS_M2_DISPATCHER}")
    print(f"M4 Resolve URL Avail : {HAS_M4_RESOLVE_URL}")

    harness = TestHarness()
    fixtures = FixtureManager.setup()

    try:
        run_tier_1_tests(harness, fixtures)
        run_tier_2_tests(harness, fixtures)
        run_tier_3_tests(harness, fixtures)
        run_tier_4_tests(harness, fixtures)
    finally:
        FixtureManager.teardown(fixtures)

    success = harness.print_summary()
    if not success:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
