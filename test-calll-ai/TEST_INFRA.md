# TEST INFRASTRUCTURE: Tier 2 WhatsApp Human Support Escalation, Queuing & Intelligent Dispatching

## Overview
This document specifies the end-to-end testing architecture, test runner conventions, mock strategies, and four-tier test methodology for the **Tier 2 WhatsApp Human Support Escalation, Queuing & Intelligent Dispatching** system.

Target Project: `/root/voice-ai-telephony/test-calll-ai`  
Container Environment: `voice_django` (Docker container executing Python 3.11 with Django 4.2+)  
Test Suite File: `test_whatsapp_escalation_dispatch_e2e.py`

---

## 1. Test Architecture & Environment

### 1.1 Docker Container Runner
The entire Django application and its dependencies (PostgreSQL with pgvector, Redis, Centrifugo, Inngest, Evolution API) operate within containerized Docker networks (`voice_net`). Tests must be executed directly inside the Django runtime container:

```bash
docker exec voice_django python test_whatsapp_escalation_dispatch_e2e.py
```

### 1.2 Django Environment Bootstrap
The test suite initializes Django's ORM and configuration prior to importing any model or service modules:

```python
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
```

### 1.3 Isolation and Teardown
To ensure deterministic execution and prevent test pollution:
- Each test run uses dedicated test tenant accounts (e.g., `test_tenant_escalation_admin`).
- Associated employee profiles, customer memory records, support tickets, and omnichannel messages are prefixed with test identifiers (e.g., `+201099990001`, `TCK-TEST-...`).
- The suite provides automatic cleanup fixtures before test execution and upon completion.

### 1.4 Mocking and Interception Strategies
1. **Centrifugo PubSub (`common.centrifugo.publish_to_centrifugo`)**:
   - Monitored and intercepted using monkeypatching / mock sinks to verify published channels (`user_{agent_id}`, `tenant_{user_id}`) and exact payload schemas without requiring live browser clients.
2. **Evolution API Client (`crm.services.evolution_client` / `send_whatsapp_message`)**:
   - Mocked to intercept outbound WhatsApp messages, verifying message text, ticket reference inclusion, and target phone JID.
3. **Time / Clock Control for SLA Watchdog**:
   - Virtualized time offsets (`datetime.now(timezone.utc) - timedelta(seconds=125)`) to simulate 120-second first-response SLA breaches deterministically without sleeping in test execution.

---

## 2. Methodology: Tiers 1 to 4

### Tier 1: Feature Coverage (>=5 test cases per requirement)

#### Requirement 1 (R1): Smart Availability Guard & Off-Hours Ticketing
- **T1.R1.1: Zero Agents Online Ticket Creation**: When all agents are offline, escalation creates a `CRMSupportTicket` with unique `TCK-YYYYMMDD-XXXX` format.
- **T1.R1.2: Off-Hours Escalation Guard**: When escalation occurs outside active business hours, a CRM support ticket is created with operating hours snapshot.
- **T1.R1.3: AI Continuity Flag in Off-Hours**: In zero-agent or off-hours conditions, `ai_auto_reply_enabled` remains `True` in `CustomerMemory`.
- **T1.R1.4: Automated Customer WhatsApp Notification**: Off-hours escalation dispatches a polite WhatsApp message with ticket number and operating hours.
- **T1.R1.5: Ticket Record Schema & Status Validation**: Validates that created tickets persist with status `OPEN`, correct customer phone, urgency, reason, and summary.

#### Requirement 2 (R2): Least-Busy Agent Routing & State Machine
- **T1.R2.1: Least-Busy Agent Selection**: When agents have unequal active chats (e.g. Agent A: 2 chats, Agent B: 0 chats), routing selects Agent B.
- **T1.R2.2: Equal-Load Tie Breaking**: Deterministic selection when multiple available agents have identical active conversation counts.
- **T1.R2.3: Conversation State Transition**: Escalation transitions the conversation state to `PENDING_AGENT_REPLY`.
- **T1.R2.4: Pause AI Auto-Reply on Assignment**: Escalation sets `ai_auto_reply_enabled = False` specifically for the escalated customer.
- **T1.R2.5: Assignment Metadata Persistence**: Verifies `assigned_agent_id`, `escalated_at`, and `sla_seconds` are stamped in conversation metadata.

#### Requirement 3 (R3): Unified Inbox Alerting & AI Handoff Brief
- **T1.R3.1: Centrifugo Channel Targeting**: Event `whatsapp_escalation_assigned` is published specifically to the target channel `user_{agent_id}`.
- **T1.R3.2: Payload Schema Conformance**: Verifies payload contains required fields: `event`, `phone_number`, `customer_name`, `reason`, `urgency`, `summary`, `assigned_agent_id`, `conversation_state`, `escalated_at`, `sla_seconds`.
- **T1.R3.3: Urgency Level Propagation**: Verifies `urgent` vs `normal` urgency is correctly set in the Centrifugo alert for UI badge rendering.
- **T1.R3.4: Multi-Tenant Alert Isolation**: Confirms alerts for Tenant A agents are never sent to Tenant B agent channels.
- **T1.R3.5: AI Handoff Summary Fidelity**: Confirms concise AI summary of the customer complaint is faithfully transmitted in the alert payload.

#### Requirement 4 (R4): SLA Watchdog & Automated Failover
- **T1.R4.1: SLA Breach Detection**: Watchdog detects unhandled conversations in `PENDING_AGENT_REPLY` past the 120s threshold.
- **T1.R4.2: SLA Grace Window Compliance**: Unhandled conversations within 120s are not prematurely reassigned.
- **T1.R4.3: Automated Failover to Secondary Agent**: Watchdog reassigns the breached chat to the next available agent (`assigned_agent_id` updated).
- **T1.R4.4: Reassurance Messaging to Customer**: Customer receives automated WhatsApp message reassuring them of the brief delay.
- **T1.R4.5: Centrifugo Reassignment Broadcast**: Reassignment publishes updated escalation event to the newly assigned agent's channel.

#### Requirement 5 (R5): Ticket Resolution & Handback to AI
- **T1.R5.1: Resolution Endpoint Execution**: `POST /api/crm/whatsapp/conversations/<phone>/resolve/` transitions conversation state to `RESOLVED`.
- **T1.R5.2: AI Auto-Reply Reactivation**: Resolution sets `ai_auto_reply_enabled = True` in `CustomerMemory`.
- **T1.R5.3: Resolution Notes Persistence**: Agent resolution notes are recorded into `CustomerMemory.whatsapp_memory["resolution_notes"]`.
- **T1.R5.4: CRM Ticket Status Synchronization**: Corresponding `CRMSupportTicket` is marked `RESOLVED` with `resolved_at` timestamp.
- **T1.R5.5: Resolution Security & Tenant Scoping**: Rejects unauthorized requests or attempts to resolve conversations owned by another tenant.

---

### Tier 2: Boundary & Corner Cases

- **T2.1: Zero Agents Configured / Online**: System gracefully handles organizations with 0 employees or all employees offline without 500 errors.
- **T2.2: All Online Agents Busy or on Break**: When all agents are logged in but have status `busy` or `break`, treated as unavailable; falls back to ticketing.
- **T2.3: Off-Hours Schedule Boundary**: Tests escalation at exact boundary minutes (e.g., 17:00:01 vs 16:59:59).
- **T2.4: Midnight-Shift Schedule Handling**: Schedules spanning midnight (e.g. 20:00 to 04:00) evaluated correctly during both PM and AM segments.
- **T2.5: Single-Agent Failover Scenario**: When only 1 agent is online and breaches SLA, watchdog does not enter infinite reassignment loop.
- **T2.6: Malformed Phone Numbers & JIDs**: Handles invalid phone numbers, missing country codes, and non-numeric characters gracefully.

---

### Tier 3: Cross-Feature Combinations & State Lifecycle

- **T3.1: Full Lifecycle End-to-End**: Customer Escalation -> Routed to Agent A -> SLA Timer Breached (120s) -> Failover to Agent B -> Agent B Manual Reply -> Resolution -> AI Resume Verified.
- **T3.2: Concurrent Escalation Burst**: Simultaneous escalations from multiple customers distributed across available agents according to least-busy algorithm.
- **T3.3: Operating Hours Transition Mid-Queue**: Escalation during business hours followed by agent resolution after business hours completes cleanly.

---

### Tier 4: Real-World Customer Scenarios

- **T4.1: Angry VIP Customer Complaint**: Urgent priority escalation for high-value customer, immediate routing to least-busy agent with full AI brief.
- **T4.2: Late-Night Delivery Inquiry**: Customer messages at 23:30; automated ticket generated with next-morning opening time, AI continues answering menu queries.
- **T4.3: Fast Agent Response within SLA**: Agent replies in 35 seconds, clearing `PENDING_AGENT_REPLY` and disabling SLA watchdog failover.
- **T4.4: Post-Resolution Autonomous AI Assistance**: Customer inquires about store location after complaint resolution; AI autonomously answers without human agent intervention.

---

## 3. Test Execution & Reporting

Run command:
```bash
docker exec voice_django python test_whatsapp_escalation_dispatch_e2e.py
```

Expected Output:
- Section-by-section breakdown of Tiers 1-4.
- Explicit pass/fail counts.
- Exit code 0 on all assertions satisfied.
