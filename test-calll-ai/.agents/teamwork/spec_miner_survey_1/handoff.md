# Specification Mining Report: WhatsApp Human Support Escalation & Dispatching

## Features Discovered
| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | R1: Availability & Off-Hours | Presence & Hours Verification | Evaluates `AgentPresence == AVAILABLE` and `BusinessHoursSchedule.is_within_business_hours()` when escalation is triggered. | `user_id: int`, `phone_number: str` | `is_available: bool`, `reason_code: 'off_hours' \| 'no_agents' \| 'ok'` | Defaults to 24/7 if schedule disabled or missing; handles timezone and overnight shifts. | `telephony/models.py:249`, `call_center/models.py:17` |
| 2 | R1: Availability & Off-Hours | CRM Support Ticket Generation | Automatically creates a support ticket with a unique reference number when 0 agents are online or during off-hours. | `user_id`, `phone_number`, `customer_name`, `reason`, `urgency`, `summary` | `ticket_number: str` (e.g. `TCK-20261024-XXXX`), `ticket_id: int` | Generates collision-resistant unique reference number; logs error if DB save fails. | `ORIGINAL_REQUEST.md:15`, `crm/models.py` |
| 3 | R1: Availability & Off-Hours | Off-Hours Automated Notification | Sends polite automated WhatsApp message containing ticket number, operating hours, and offer for ongoing AI help; keeps `ai_auto_reply_enabled=True`. | `phone_number`, `ticket_number`, `operating_hours_text` | Sent via Evolution API; recorded in `OmnichannelMessage` (outbound_ai) | If Evolution API is disconnected, logs error and queues/saves message locally. | `crm/services/evolution_client.py:134`, `crm/services/langgraph_worker.py:524` |
| 4 | R2: Dispatching & State | Least-Busy Agent Routing | Queries active agents (`status in ['ready', 'AVAILABLE']`) and assigns conversation to agent with lowest active chat count (`conversation_state == 'PENDING_AGENT_REPLY'`). | `user_id`, candidate agents list | `target_agent: EmployeeProfile` | Deterministic tie-breaking on lowest agent ID; fallback to ticketing if all candidate agents busy/offline. | `call_center/models.py:4`, `crm/views.py:748` |
| 5 | R2: Dispatching & State | Conversation State Transition | Updates `CustomerMemory.whatsapp_memory`: sets `assigned_agent_id`, sets `conversation_state = 'PENDING_AGENT_REPLY'`, sets `ai_auto_reply_enabled = False`. | `phone_number`, `agent_id`, escalation details | Updated `CustomerMemory` row in DB | Gracefully initializes `whatsapp_memory` dict if null. | `crm/models.py:14`, `crm/views.py:935` |
| 6 | R3: Real-Time Alerting | Centrifugo Escalation Publishing | Publishes `whatsapp_escalation_assigned` event to Centrifugo channel `user_{agent_id}` with full handoff brief payload. | `channel: f"user_{agent_id}"`, event data | `bool` (success / failure) | Non-blocking try/except logging to prevent escalation transaction rollback on Centrifugo failure. | `common/centrifugo.py:9`, `ORIGINAL_REQUEST.md:49` |
| 7 | R3: Real-Time Alerting | Agent Desktop Inbox Alert & Brief | Triggers audible chime and displays AI Handoff Brief (reason, customer name, urgency, AI summary, SLA countdown) on web UI. | Centrifugo WebSocket event payload | Audio chime playback + UI card / modal render | Silent fallback if browser autoplay audio permission is blocked. | `whatsapp.html:528`, `static/js/common.js:83` |
| 8 | R4: SLA Watchdog | 2-Minute SLA First-Response Watchdog | Monitors unhandled conversations; if assigned agent does not reply within 120s, reassigns to next available agent and sends customer reassurance message. | `phone_number`, `escalated_at`, `current_time` | Reassigned agent ID, reassurance message sent, reset SLA timer | If no alternate agent online, alerts supervisor and maintains waiting state without dropping conversation. | `ORIGINAL_REQUEST.md:29-33`, `call_center/inngest_jobs.py:203` |
| 9 | R4: SLA Watchdog | Customer Reassurance Notification | Emits automated message to customer notifying of brief delay and active reassignment. | `phone_number`, `reassurance_text` | Outbound WhatsApp message sent via Evolution API | Logged to `OmnichannelMessage` (outbound_ai). | `crm/services/evolution_client.py:134` |
| 10 | R5: Handback & Continuity | Resolve & Resume AI Action | Dedicated endpoint for agent to submit resolution notes, re-enable `ai_auto_reply_enabled = True`, transition state, and update memory. | `phone_number`, `resolution_notes`, `resolution_status` | `status: 'success'`, `ai_active: True`, updated `CustomerMemory` | Requires authenticated agent/user; returns 404 if phone number not found. | `crm/views.py:918`, `ORIGINAL_REQUEST.md:34-38` |

---

## Edge Cases
| # | Feature | Input | Observed / Specified Behavior |
|---|---------|-------|-------------------------------|
| 1 | Operating Hours | `BusinessHoursSchedule.is_enabled == False` | Business is treated as open 24/7. `is_within_business_hours()` returns `True`. Routing proceeds to online agents. |
| 2 | Operating Hours | Midnight-spanning shift (e.g., 20:00 to 04:00) | `start_time > end_time`; system correctly checks `current_time >= start_time or current_time <= end_time`. |
| 3 | Operating Hours | Escalation on non-working day (e.g. Friday in Egypt) | `day_info["is_workday"] == False`; immediately triggers off-hours ticketing branch. |
| 4 | Agent Presence | All agents have status `break`, `busy`, or `offline` | 0 available agents online. Triggers off-hours CRM ticket generation and sends automated response with ticket number. |
| 5 | Routing Tie-Break | 2 available agents with identical active chat counts (e.g., 0 chats) | Lowest `EmployeeProfile.id` wins deterministically. |
| 6 | Concurrency | 2 customer escalations arrive simultaneously | Least-busy routing query uses DB transaction / `select_for_update` or atomic increment to prevent assigning both chats to same agent. |
| 7 | SLA Timer | Assigned agent sends manual reply within 120s | Conversation state transitions to `IN_PROGRESS` / active; SLA watchdog timer disarms; no reassignment occurs. |
| 8 | SLA Timer | SLA expires after 120s with only 1 agent online in tenant | No alternate agent available; system sends customer reassurance message, retains assignment, and flags conversation as `SLA_BREACHED`. |
| 9 | Resolution Handback | AI resumes after ticket resolution; customer sends new question | Gemini loads resolution notes from `CustomerMemory` (`format_for_system_instruction`), allowing seamless continuation without re-asking questions. |
| 10 | Identification | Inbound message identifier is WhatsApp JID (e.g. `2010xxxxxx@s.whatsapp.net` or LID) | `format_whatsapp_number` strips `@...` and non-digits to ensure clean phone mapping and DB lookups. |

---

## 1. Observation

Direct inspection of `/root/voice-ai-telephony/test-calll-ai` reveals:

1. **Operating Hours Engine**:
   - Model `BusinessHoursSchedule` is defined at `django_app/telephony/models.py:219`.
   - Fields: `is_enabled` (bool), `timezone` (default: `"Africa/Cairo"`), `days_config` (JSONField with days of week, start_time, end_time, is_workday), `ai_message` (TextField).
   - Method: `is_within_business_hours(self, dt=None) -> bool` (line 249) cleanly handles weekday checks and midnight-spanning schedules.

2. **Customer State & Memory Storage**:
   - Model `CustomerMemory` is defined at `django_app/crm/models.py:5` with `table = 'voice_assistant_customermemory'`.
   - Stores `whatsapp_memory` (JSONField, default=dict) and `call_memory` (JSONField).
   - `CustomerMemory.whatsapp_memory` currently holds:
     - `ai_auto_reply_enabled` (bool): Checked in `crm/views.py:1175` before dispatching LangGraph.
     - `needs_human_attention` (bool): Toggled in `crm/views.py:937` and `crm/services/langgraph_worker.py:532`.
     - `escalation_reason`, `escalation_urgency`, `escalation_summary`, `escalated_at`: Written in `langgraph_worker.py:533-536`.

3. **LangGraph Escalation Tool**:
   - `langgraph_worker.py:358-386` defines the Gemini function declaration:
     ```python
     types.FunctionDeclaration(
         name="escalate_to_human_support",
         description="تحويل محادثة الواتساب فوراً إلى موظف خدمة العملاء البشري...",
         parameters={
             "type": "OBJECT",
             "properties": {
                 "reason": {"type": "STRING"},
                 "urgency": {"type": "STRING", "enum": ["urgent", "normal"]},
                 "summary": {"type": "STRING"}
             },
             "required": ["reason", "summary"]
         }
     )
     ```
   - Current implementation (`langgraph_worker.py:524-560`) unconditionally disables AI (`wm_rec["ai_auto_reply_enabled"] = False`) without checking agent presence or operating hours.

4. **Human Agents & Presence Representation**:
   - Model `EmployeeProfile` is defined at `django_app/call_center/models.py:4`.
   - Fields: `user` (OneToOneField User), `employer` (ForeignKey User), `extension` (CharField), `display_name` (CharField), `status` (choices: `ready`, `break`, `busy`, `offline`, default: `ready`).
   - In `call_center/inngest_jobs.py:165`, presence is checked as:
     `cand.status in ['ready', 'available']`.
   - Dispatch requirement specifies `AgentPresence == AVAILABLE`, which maps to `EmployeeProfile.status in ['ready', 'AVAILABLE', 'available']`.

5. **Centrifugo Configuration & Publishing**:
   - Client service: `django_app/common/centrifugo.py:9` (`publish_to_centrifugo(channel: str, data: dict, timeout: float = 2.0)`).
   - Server config: `centrifugo/config.json`.
     Namespaces configured: `rooms`, `employee`, `employees`, `queues`, and `without_namespace` (which allows client subscriptions to `user_{agent_id}`).
   - Requirement specifies publishing event `whatsapp_escalation_assigned` to channel `user_{agent_id}`.

6. **Test Environment**:
   - Containerized Django stack: `docker exec voice_django python <test_script.py>`.
   - Verification executed: `docker exec voice_django python test_whatsapp_and_dnc_gaps_e2e.py` passed with 58/58 tests passing.

---

## 2. Logic Chain

1. **Trigger Phase (Inbound Complaint / Escalation)**:
   - When a WhatsApp message arrives, if Gemini invokes `escalate_to_human_support(reason, urgency, summary)` or escalation is triggered, the system must not blindly shut off the AI.
   - It must first query `BusinessHoursSchedule.objects.filter(user_id=user_id).first().is_within_business_hours()` and query online agents (`EmployeeProfile.objects.filter(employer_id=user_id, status__in=['ready', 'AVAILABLE'], is_active=True)`).

2. **Branch A: Off-Hours or 0 Agents Online (R1)**:
   - If `not is_within_hours` OR `online_agents.count() == 0`:
     - Maintain `ai_auto_reply_enabled = True` in `CustomerMemory.whatsapp_memory`.
     - Create a new `CRMSupportTicket` instance with auto-generated reference number `TCK-<YYYYMMDD>-<UUID4_HEX8>`.
     - Formulate polite automated message with ticket number, business hours, and reassurance that AI remains available to help.
     - Send message via `send_whatsapp_message` and record in `OmnichannelMessage` (`direction="outbound_ai"`).
     - Inform Gemini in tool output that ticket has been logged and to continue answering customer inquiries.

3. **Branch B: Qualified Agents Online & Within Hours (R2 & R3)**:
   - Fetch all online available agents.
   - Count active chats per agent: count `CustomerMemory` records where `whatsapp_memory__assigned_agent_id == agent.id` and `whatsapp_memory__conversation_state == 'PENDING_AGENT_REPLY'`.
   - Select least-busy agent (`min(agents, key=active_count)`).
   - Update `CustomerMemory.whatsapp_memory`:
     - `assigned_agent_id = target_agent.id`
     - `conversation_state = 'PENDING_AGENT_REPLY'`
     - `ai_auto_reply_enabled = False`
     - `needs_human_attention = True`
     - `escalated_at = timezone.now().isoformat()`
     - `sla_deadline = (timezone.now() + timedelta(minutes=2)).isoformat()`
   - Publish Centrifugo event `whatsapp_escalation_assigned` to `user_{target_agent.id}` (and `user_{target_agent.user_id}`).
   - Payload matches contract:
     ```json
     {
       "event": "whatsapp_escalation_assigned",
       "phone_number": phone_number,
       "customer_name": customer_name,
       "reason": reason,
       "urgency": urgency,
       "summary": summary,
       "assigned_agent_id": target_agent.id,
       "conversation_state": "PENDING_AGENT_REPLY",
       "escalated_at": "...",
       "sla_deadline": "...",
       "sla_seconds": 120
     }
     ```
   - Agent Desktop interface plays chime and displays AI Handoff Brief.

4. **SLA Watchdog Execution (R4)**:
   - 2-minute watchdog timer checks for first response.
   - If conversation remains in `PENDING_AGENT_REPLY` after 120 seconds without an outbound human reply:
     - Find next available agent (`EmployeeProfile.objects.filter(status__in=['ready', 'AVAILABLE']).exclude(id=current_agent_id)`).
     - Reassign `assigned_agent_id = next_agent.id` and reset `escalated_at`.
     - Send customer reassurance message via WhatsApp.
     - Publish `whatsapp_escalation_assigned` to `user_{next_agent.id}`.

5. **Resolution Handback (R5)**:
   - Agent clicks "Resolve & Resume AI" in inbox (`POST /api/crm/whatsapp/conversations/<phone_number>/resolve/`).
   - Updates `CustomerMemory.whatsapp_memory`:
     - `ai_auto_reply_enabled = True`
     - `conversation_state = "RESOLVED"`
     - `needs_human_attention = False`
     - `resolution_notes = request.data["resolution_notes"]`
     - `resolved_at = timezone.now().isoformat()`
   - Appends resolution notes to `CustomerMemory` summary / context so Gemini remembers the resolution.
   - If an open `CRMSupportTicket` exists for this conversation, marks it `status='RESOLVED'`.

---

## 3. Caveats

1. **Ticketing Model Scope**:
   - No dedicated `CRMSupportTicket` model currently exists in `crm/models.py`. It must be added with fields: `ticket_number` (unique), `user`, `customer_phone`, `customer_name`, `reason`, `urgency`, `summary`, `status`, `operating_hours_snapshot`, `created_at`, `resolved_at`.
2. **Channel Format Alignment**:
   - `centrifugo/config.json` allows unrestricted subscription for client channels without namespace (`user_{agent_id}`). In `call_center/views.py`, employees also subscribe to `employee:{id}`. To guarantee compatibility, events should be published to `user_{agent.id}` as required by the specification.
3. **Presence Enum Alignment**:
   - In `EmployeeProfile`, status is stored as lowercase `'ready'`, while the specification states `AgentPresence == AVAILABLE`. The implementation should support both `status in ['ready', 'AVAILABLE', 'available']` and an explicit `AgentPresence` enum/property.
4. **SLA Simulation for Automated Tests**:
   - Automated tests cannot wait 120 real seconds. An explicit `evaluate_sla_watchdog(phone_number, current_time=None)` service method accepting simulated `current_time` must be exposed alongside any background Inngest/Celery job.

---

## 4. Conclusion

All 5 requirements (R1–R5) and their acceptance criteria map cleanly to the existing Django/Centrifugo/CustomerMemory architecture.
The specification requires:
1. `CRMSupportTicket` model in `crm/models.py`.
2. `AgentPresence` helper supporting `AVAILABLE` (`status in ['ready', 'AVAILABLE']`).
3. Escalation dispatcher implementing smart availability guard (R1) & least-busy routing (R2).
4. Centrifugo publishing of `whatsapp_escalation_assigned` to `user_{agent_id}` with AI handoff brief payload (R3).
5. SLA watchdog with 2-minute threshold, reassignment, and customer reassurance messaging (R4).
6. Resolve & Resume AI endpoint `POST /api/crm/whatsapp/conversations/<phone>/resolve/` updating `CustomerMemory` and re-enabling AI (R5).

---

## 5. Verification Method

To independently verify the implementation against the acceptance criteria, run the following command in the project environment:

```bash
docker exec voice_django python test_whatsapp_escalation_dispatch_e2e.py
```

### Specific Assertions to Include in the Test Suite:
1. **AC-1 (Presence & Off-Hours)**:
   - Set 0 agents online (`EmployeeProfile.objects.update(status='offline')`).
   - Trigger escalation.
   - Assert `CRMSupportTicket.objects.filter(customer_phone=phone).exists() == True`.
   - Assert `ticket.ticket_number` is non-empty and starts with ticket prefix.
   - Assert `CustomerMemory.whatsapp_memory["ai_auto_reply_enabled"] is True`.
   - Assert outbound message was recorded containing the ticket number and business hours text.
2. **AC-2 & AC-3 (Dispatching, Least-Busy, State)**:
   - Create Agent 1 (status `ready`, 1 active chat) and Agent 2 (status `ready`, 0 active chats).
   - Trigger escalation.
   - Assert `whatsapp_memory["assigned_agent_id"] == agent_2.id`.
   - Assert `whatsapp_memory["conversation_state"] == "PENDING_AGENT_REPLY"`.
   - Assert `whatsapp_memory["ai_auto_reply_enabled"] is False`.
3. **AC-4 (Centrifugo Alerting)**:
   - Mock `publish_to_centrifugo`.
   - Assert call to channel `f"user_{agent_2.id}"` with payload:
     - `event == "whatsapp_escalation_assigned"`
     - `reason`, `urgency`, `summary`, `customer_name`, `phone_number` all present.
4. **AC-5 (SLA Watchdog 2-Minute Threshold)**:
   - Create conversation assigned to Agent 1 with `escalated_at = now - 125 seconds`.
   - Execute SLA watchdog evaluation.
   - Assert chat reassigned to Agent 2 (`assigned_agent_id == agent_2.id`).
   - Assert customer reassurance message emitted.
   - Assert Centrifugo event sent to `f"user_{agent_2.id}"`.
5. **AC-6 (Handback & Continuity)**:
   - Post to `/api/crm/whatsapp/conversations/<phone>/resolve/` with `resolution_notes="Issue fixed"`.
   - Assert HTTP 200 response.
   - Assert `CustomerMemory.whatsapp_memory["ai_auto_reply_enabled"] is True`.
   - Assert `CustomerMemory.whatsapp_memory["conversation_state"] == "RESOLVED"`.
   - Assert `resolution_notes` stored in `CustomerMemory`.
