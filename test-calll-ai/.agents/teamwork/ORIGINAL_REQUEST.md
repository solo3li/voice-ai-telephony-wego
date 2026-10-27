# Original User Request

## Initial Request — 2026-10-24T03:29:51Z

Build a Tier 2 Human Support handoff, queuing, and intelligent dispatching system for the WhatsApp AI agent, supporting least-busy agent routing, presence verification with off-hours CRM ticketing, and a unified agent desktop inbox with sound alerts and SLA failover.

Working directory: `/root/voice-ai-telephony/test-calll-ai`
Integrity mode: development

## Requirements

### R1. Smart Availability Guard & Off-Hours Ticketing
When customer complaints or human escalation are triggered via WhatsApp, verify human agent presence (`AgentPresence == AVAILABLE`) and current operating hours. If no human agent is online or if outside working hours:
- Keep the AI active (`ai_auto_reply_enabled = True`).
- Automatically create a CRM support ticket with a unique reference number.
- Send a polite automated message containing the ticket number, operating hours, and offer continued assistance.

### R2. Least-Busy Agent Routing & State Machine
When qualified human agents are online:
- Identify the available agent with the lowest number of currently active conversations (`least-busy`).
- Assign the conversation to that agent (`assigned_agent_id`) and transition the conversation state to `PENDING_AGENT_REPLY`.
- Pause automated AI replies for this specific customer (`ai_auto_reply_enabled = False`).

### R3. Unified Inbox Alerting & AI Handoff Brief
Deliver real-time notifications to the assigned agent desktop via Centrifugo:
- Trigger an audible chime / ring tone on the agent's web interface.
- Display an AI Handoff Brief containing: escalation reason, customer name, urgency level, and concise AI summary of the issue.

### R4. SLA Watchdog & Automated Failover
Implement a 2-minute first-response SLA timer:
- If the assigned agent does not send a message to the customer within the SLA window, automatically reassign the conversation to the next available agent.
- Emit a real-time reassurance message to the customer regarding the brief delay.

### R5. Ticket Resolution & Handback to AI
Provide an explicit action in the agent inbox for "Resolve & Resume AI":
- Log the agent's resolution details into `CustomerMemory`.
- Reactivate AI auto-replies (`ai_auto_reply_enabled = True`).

## Acceptance Criteria

### Presence & Off-Hours Behavior
- [ ] Automated tests verify that when 0 agents are online, a CRM ticket is created, the customer receives the ticket number, and `ai_auto_reply_enabled` remains True.

### Dispatching & Queue Management
- [ ] Automated tests verify that when multiple agents are online, the chat is assigned to the agent with the lowest active chat count.
- [ ] The conversation state is updated and AI auto-reply is disabled for that phone number.

### Real-Time Notification & Centrifugo Events
- [ ] Centrifugo event `whatsapp_escalation_assigned` is published to the target agent channel (`user_{agent_id}`) with complete payload (summary, urgency, reason).

### SLA Watchdog
- [ ] An automated test simulates an unhandled chat past the 2-minute threshold, confirming reassignment to another agent.

### Handback & Memory Continuity
- [ ] Calling the resolve action re-enables `ai_auto_reply_enabled` in `CustomerMemory` and stores resolution notes.
