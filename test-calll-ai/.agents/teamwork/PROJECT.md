# Project: Tier 2 WhatsApp Human Support Escalation, Queuing & Intelligent Dispatching

## Architecture
The system augments the existing Django + LangGraph + Inngest + Evolution API + Centrifugo stack to provide a robust human escalation pipeline:
- **Presence & Operating Hours**: Evaluates `EmployeeProfile.status in ['ready', 'AVAILABLE']` and `BusinessHoursSchedule.is_within_business_hours()`.
- **Ticketing Engine**: `CRMSupportTicket` in `crm/models.py` with unique reference codes (`TCK-YYYYMMDD-XXXX`) when 0 agents are online or during off-hours.
- **Routing Engine**: `crm/services/whatsapp_dispatcher.py` handles least-busy agent selection, active chat tracking, conversation state transitions (`PENDING_AGENT_REPLY`), and pause/resume of `ai_auto_reply_enabled`.
- **Real-Time PubSub**: Uses Centrifugo (`common.centrifugo.publish_to_centrifugo`) publishing `whatsapp_escalation_assigned` to channel `user_{agent_id}`.
- **Agent Desktop**: `voice_assistant/pages/whatsapp.html` augmented with Centrifugo listener on `user_{agent_id}`, Web Audio chime alert, AI Handoff Brief card, and "Resolve & Resume AI" modal.
- **SLA Watchdog**: 2-minute timer watchdog evaluating unhandled chats in `PENDING_AGENT_REPLY`, reassigning to alternate agents with customer reassurance messaging.
- **Handback & Continuity**: `POST /api/crm/whatsapp/conversations/<phone>/resolve/` stores resolution notes in `CustomerMemory` and sets `ai_auto_reply_enabled = True`.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | CRM Support Ticket Model | `CRMSupportTicket` model in `crm/models.py` with unique reference generator and status | M1 | R1, survey |
| 2 | Agent Presence Definition | `AgentPresence` helper supporting `AVAILABLE` (`status in ['ready', 'AVAILABLE']`) | M1 | R1, survey |
| 3 | Operating Hours Verification | Evaluation of `BusinessHoursSchedule.is_within_business_hours()` during escalation | M1 | R1, survey |
| 4 | Off-Hours / Zero-Agent Ticketing | Auto-create ticket, send WhatsApp message with ticket ref & hours, keep AI enabled | M2 | R1, survey |
| 5 | Least-Busy Agent Selection | Query online agents and route to agent with lowest active chat count | M2 | R2, survey |
| 6 | Conversation State Transition | Set `assigned_agent_id`, state `PENDING_AGENT_REPLY`, `ai_auto_reply_enabled=False` | M2 | R2, survey |
| 7 | Centrifugo Escalation Publishing | Broadcast `whatsapp_escalation_assigned` to `user_{agent_id}` with brief payload | M3 | R3, survey |
| 8 | Agent Desktop Chime Alert | Web Audio / HTML5 audio chime triggered on incoming escalation event | M3 | R3, survey |
| 9 | AI Handoff Brief Display | UI card displaying reason, customer name, urgency, AI summary, and SLA timer | M3 | R3, survey |
| 10 | 2-Minute SLA First-Response Watchdog | Detect unreplied chats past 120s threshold and trigger automated failover | M4 | R4, survey |
| 11 | SLA Failover & Customer Reassurance | Reassign to next available agent and send automated reassurance message | M4 | R4, survey |
| 12 | Ticket Resolution & AI Handback | Endpoint `/resolve/` persisting notes to `CustomerMemory` and re-enabling AI | M4 | R5, survey |
| 13 | 100% E2E Test Suite (Tiers 1-4) | Comprehensive opaque-box test suite covering all features and acceptance criteria | E2E / M5 | All ACs |
| 14 | Adversarial Hardening (Tier 5) | White-box stress tests, concurrency, and boundary edge cases | M5 | ACs |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Data Models & Ticketing Foundation | `CRMSupportTicket` model, migrations, `AgentPresence` & hours helpers | none | PLANNED |
| M2 | Smart Availability & Least-Busy Routing | Escalation handler, off-hours ticketing flow, least-busy selection, state machine | M1 | PLANNED |
| M3 | Real-Time Centrifugo Alerting & Desktop UI | Centrifugo publisher, `user_{agent_id}` listener, chime, AI Handoff Brief card | M2 | PLANNED |
| M4 | SLA Watchdog & AI Handback / Resolution | 2-min SLA watchdog timer, reassignment, reassurance message, `/resolve/` endpoint | M2, M3 | PLANNED |
| M5 | Final Milestone: E2E Test Pass & Hardening | Pass 100% of E2E test suite (Tiers 1-4) + Tier 5 adversarial hardening | M1, M2, M3, M4, E2E | PLANNED |

## Interface Contracts

### M1 ↔ M2: Ticketing & Presence
- `create_support_ticket(user_id, phone_number, customer_name, reason, urgency, summary, operating_hours_text="") -> CRMSupportTicket`
- `get_available_agents(user_id) -> QuerySet[EmployeeProfile]`
- `is_operating_hours(user_id) -> (bool, str)`

### M2 ↔ M3: Escalation Payload
- Centrifugo event: `whatsapp_escalation_assigned`
- Channel: `user_{agent_id}`
- Payload Schema:
  ```json
  {
    "event": "whatsapp_escalation_assigned",
    "phone_number": "str",
    "customer_name": "str",
    "reason": "str",
    "urgency": "urgent | normal",
    "summary": "str",
    "assigned_agent_id": "int",
    "conversation_state": "PENDING_AGENT_REPLY",
    "escalated_at": "ISO-8601 string",
    "sla_seconds": 120
  }
  ```

### M3 / M4 ↔ Memory & Resolution
- Endpoint: `POST /api/crm/whatsapp/conversations/<path:phone_number>/resolve/`
- Request body:
  ```json
  {
    "resolution_notes": "Issue resolved with customer",
    "resolution_status": "RESOLVED"
  }
  ```
- Response:
  ```json
  {
    "status": "success",
    "ai_auto_reply_enabled": true,
    "conversation_state": "RESOLVED"
  }
  ```

## Code Layout
- `django_app/crm/models.py`: `CRMSupportTicket`, `CustomerMemory`, `OmnichannelMessage`
- `django_app/crm/services/whatsapp_dispatcher.py`: Routing, presence guard, ticket generator, SLA watchdog
- `django_app/crm/services/langgraph_worker.py`: `escalate_to_human_support` tool integration
- `django_app/crm/views.py`: `api_whatsapp_conversation_resolve`, webhook handling
- `django_app/crm/urls.py`: URL routing for resolve endpoint
- `django_app/voice_assistant/templates/voice_assistant/pages/whatsapp.html`: Desktop UI, Centrifugo subscriber, chime, AI brief
- `test_whatsapp_escalation_dispatch_e2e.py`: E2E test suite
