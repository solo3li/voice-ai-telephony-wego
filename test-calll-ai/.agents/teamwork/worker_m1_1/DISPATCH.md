## 2026-10-24T03:49:21Z
You are teamwork_preview_worker for Milestone 1 (Data Models & Ticketing Foundation).
Your working directory is: /root/voice-ai-telephony/test-calll-ai/.agents/teamwork/worker_m1_1
The target project root is: /root/voice-ai-telephony/test-calll-ai

You MUST read the original user request before starting:
/root/voice-ai-telephony/test-calll-ai/.agents/teamwork/ORIGINAL_REQUEST.md

You MUST read the master project specification:
/root/voice-ai-telephony/test-calll-ai/.agents/teamwork/PROJECT.md

You MUST read the Explorer and Spec Miner handoff reports:
- /root/voice-ai-telephony/test-calll-ai/.agents/teamwork/explorer_m1_1/handoff.md
- /root/voice-ai-telephony/test-calll-ai/.agents/teamwork/explorer_m1_2/handoff.md
- /root/voice-ai-telephony/test-calll-ai/.agents/teamwork/spec_miner_m1_1/handoff.md

FILE WRITE OWNERSHIP:
You own exclusively:
- django_app/crm/models.py
- django_app/crm/admin.py
- django_app/crm/services/whatsapp_dispatcher.py
- django_app/crm/migrations/
- django_app/test_m1_ticketing_and_presence.py

DO NOT modify files outside your ownership.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

TASK IMPLEMENTATION:
1. In django_app/crm/models.py:
   - Implement CRMSupportTicket model per specifications (ticket_number unique index, user FK, customer_phone, customer_name, reason, urgency, summary, status choices [OPEN, IN_PROGRESS, RESOLVED, CLOSED], operating_hours_snapshot, assigned_employee nullable FK to 'call_center.EmployeeProfile', resolution_notes, created_at, resolved_at, updated_at, generate_ticket_number classmethod, save logic setting resolved_at on resolution, to_dict method, and property aliases reference_code, phone_number, assigned_agent).
2. In django_app/crm/admin.py:
   - Register CRMSupportTicket in Django admin.
3. In django_app/crm/services/whatsapp_dispatcher.py:
   - Implement AgentPresence class with AVAILABLE = 'AVAILABLE', ONLINE_STATUSES = ['ready', 'AVAILABLE', 'available'], and is_available classmethod.
   - Implement get_available_agents(user_id) -> QuerySet[EmployeeProfile] filtering is_active=True, status__in=ONLINE_STATUSES, and tenant scoping.
   - Implement is_operating_hours(user_id, dt=None) -> Tuple[bool, str] wrapping BusinessHoursSchedule.is_within_business_hours with formatted description.
   - Implement create_support_ticket(user_id, phone_number, customer_name="", reason="", urgency="normal", summary="", operating_hours_text="") -> CRMSupportTicket.
4. Run migrations:
   - Execute docker exec voice_django python manage.py makemigrations crm
   - Execute docker exec voice_django python manage.py migrate crm
   - Verify with docker exec voice_django python manage.py showmigrations crm
5. Write and execute test suite:
   - Create django_app/test_m1_ticketing_and_presence.py covering all 8 test cases from explorer_m1_2/spec_miner_m1_1 handoffs.
   - Execute docker exec voice_django python test_m1_ticketing_and_presence.py and verify 100% pass.
   - Also run existing regression check docker exec voice_django python test_whatsapp_and_dnc_gaps_e2e.py to ensure zero regressions.
6. Write handoff.md in your working directory with all commands, test outputs, and evidence.
7. Notify orchestrator via send_message when complete.
