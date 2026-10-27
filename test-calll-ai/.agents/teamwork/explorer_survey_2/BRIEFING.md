# BRIEFING — 2026-10-24T03:40:00Z

## Mission
Investigate agent presence, Centrifugo notifications, CRM ticketing, agent desktop/APIs, and testing systems at /root/voice-ai-telephony/test-calll-ai.

## 🔒 My Identity
- Archetype: explorer
- Roles: investigator, synthesizer
- Working directory: /root/voice-ai-telephony/test-calll-ai/.agents/teamwork/explorer_survey_2
- Original parent: 772fee3e-ac8a-491b-9b20-9989b9fd5361
- Milestone: Survey Phase (instance 2 of 3)

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Strictly read-only analysis; report findings to handoff.md
- Terse communication style

## Current Parent
- Conversation ID: 772fee3e-ac8a-491b-9b20-9989b9fd5361
- Updated: not yet

## Investigation State
- **Explored paths**:
  - `django_app/call_center/models.py`, `views.py`, `urls.py` (EmployeeProfile, presence, queues)
  - `django_app/common/centrifugo.py`, `centrifugo/config.json` (Centrifugo config, channels, publish helper)
  - `django_app/crm/models.py`, `views.py`, `urls.py` (CustomerMemory, OmnichannelMessage, WhatsApp APIs)
  - `django_app/crm/services/langgraph_worker.py`, `whatsapp_sync.py` (escalate_to_human_support tool, memory handling)
  - `django_app/telephony/models.py` (BusinessHoursSchedule, is_within_business_hours)
  - `django_app/voice_assistant/templates/voice_assistant/pages/whatsapp.html`, `callcenter.html` (agent inbox / chat UI)
  - Test suites: `test_whatsapp_and_dnc_gaps_e2e.py`, `test_new_features_e2e.py`, `test_dnc_and_inngest_e2e.py`
  - Docker architecture: `docker-compose.yml`, `voice_django` container
- **Key findings**:
  1. Human agents are `EmployeeProfile` in `call_center/models.py` with `status` ('ready', 'break', 'busy', 'offline'). Redis keys `agent_state:<id>` also track 'AVAILABLE'. `BusinessHoursSchedule` in `telephony/models.py` provides `is_within_business_hours()`.
  2. Centrifugo client in `common/centrifugo.py` uses HTTP API `/publish`. Namespaces `rooms`, `employee`, `employees`, `queues` exist; `without_namespace` allows client subscriptions (`user_{agent_id}`).
  3. No CRM Ticket model currently exists in `crm/models.py`. Needs new model + ref number generation.
  4. WhatsApp inbox UI exists at `pages/whatsapp.html` with polling, but lacks Centrifugo WebSocket listener for `user_{agent_id}`, audible sound/chime, AI Handoff Brief, and "Resolve & Resume AI" action.
  5. Tests are self-contained Python scripts executed via `docker exec voice_django python test_<name>_e2e.py`.
- **Unexplored areas**: none within survey scope.

## Key Decisions Made
- Complete findings and structure into 5-component handoff report.

## Artifact Index
- DISPATCH.md — record of orchestrator instructions
- progress.md — liveness heartbeat and step tracker
- BRIEFING.md — working memory
- handoff.md — final 5-component handoff report
