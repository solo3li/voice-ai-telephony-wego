# BRIEFING — 2026-10-24T03:37:45Z

## Mission
Investigate existing codebase at /root/voice-ai-telephony/test-calll-ai: directory structure, tech stack, WhatsApp AI agent, webhooks, state management, CustomerMemory, message processing, escalation triggers, routing.

## 🔒 My Identity
- Archetype: explorer
- Roles: codebase investigation, architecture survey, synthesis
- Working directory: /root/voice-ai-telephony/test-calll-ai/.agents/teamwork/explorer_survey_1
- Original parent: 772fee3e-ac8a-491b-9b20-9989b9fd5361
- Milestone: Survey phase (instance 1 of 3)

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Target project: /root/voice-ai-telephony/test-calll-ai
- Write only to working folder: /root/voice-ai-telephony/test-calll-ai/.agents/teamwork/explorer_survey_1
- Output 5-component handoff report to handoff.md
- Report to parent via send_message

## Current Parent
- Conversation ID: 772fee3e-ac8a-491b-9b20-9989b9fd5361
- Updated: 2026-10-24T03:32:40Z

## Investigation State
- **Explored paths**:
  - `django_app/crm/services/langgraph_worker.py` (LangGraph WhatsApp bot, tools, escalation)
  - `django_app/crm/services/whatsapp_sync.py` & `evolution_client.py` (Evolution API integration)
  - `django_app/crm/views.py` (webhook `api_whatsapp_webhook`, conversations API)
  - `django_app/crm/models.py` (`CustomerMemory`, `OmnichannelMessage`)
  - `django_app/crm/inngest_jobs.py` (`fn_process_whatsapp_followup`)
  - `django_app/call_center/models.py` & `views.py` (`EmployeeProfile`, presence, queues)
  - `django_app/telephony/models.py` (`BusinessHoursSchedule`)
  - `centrifugo/config.json` & `django_app/common/centrifugo.py` (WebSocket channels)
  - `django_app/voice_assistant/templates/voice_assistant/pages/whatsapp.html` (Chat inbox UI)
  - Test suites (`test_whatsapp_and_dnc_gaps_e2e.py` - 58/58 passed)
- **Key findings**:
  - Webhook entrypoint is `api_whatsapp_webhook` in `crm/views.py`.
  - Background AI processing runs asynchronously via Inngest durable job `crm/whatsapp.followup_requested` invoking `langgraph_worker.py`.
  - Customer state and `ai_auto_reply_enabled` flag live in `CustomerMemory.whatsapp_memory`.
  - Tool `escalate_to_human_support` in `langgraph_worker.py` currently disables AI unconditionally without presence verification or business hours check.
  - Human presence exists via `EmployeeProfile.status` and Redis `agent_state:*` / `employees:presence`.
  - No Support Ticket model, no WhatsApp conversation state machine, no least-busy queue, and no SLA timer currently exist.
- **Unexplored areas**: None regarding survey scope.

## Key Decisions Made
- Fully documented all 5 survey dimensions with verbatim file and line citations.
- Ran live test verification inside `voice_django` container confirming baseline integrity.

## Artifact Index
- /root/voice-ai-telephony/test-calll-ai/.agents/teamwork/explorer_survey_1/DISPATCH.md
- /root/voice-ai-telephony/test-calll-ai/.agents/teamwork/explorer_survey_1/BRIEFING.md
- /root/voice-ai-telephony/test-calll-ai/.agents/teamwork/explorer_survey_1/progress.md
- /root/voice-ai-telephony/test-calll-ai/.agents/teamwork/explorer_survey_1/handoff.md
