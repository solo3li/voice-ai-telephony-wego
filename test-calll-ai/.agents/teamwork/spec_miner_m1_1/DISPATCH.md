## 2026-10-24T03:42:03Z
You are teamwork_preview_spec_miner for Milestone 1 (Data Models & Ticketing Foundation).
Your working directory is: /root/voice-ai-telephony/test-calll-ai/.agents/teamwork/spec_miner_m1_1
The target project root is: /root/voice-ai-telephony/test-calll-ai

You MUST read the original user request before starting:
/root/voice-ai-telephony/test-calll-ai/.agents/teamwork/ORIGINAL_REQUEST.md

You MUST read the master project specification:
/root/voice-ai-telephony/test-calll-ai/.agents/teamwork/PROJECT.md

Your task is to establish the precise data specifications and validation criteria for Milestone 1:
1. Specify field types, nullability, defaults, max_lengths, and choice tuples for CRMSupportTicket.
2. Specify the exact signature and return types for:
   - create_support_ticket(user_id, phone_number, customer_name, reason, urgency, summary, operating_hours_text="") -> CRMSupportTicket
   - get_available_agents(user_id) -> QuerySet[EmployeeProfile]
   - is_operating_hours(user_id) -> Tuple[bool, str]
3. Specify verification test assertions for M1:
   - Ticket creation generates non-empty unique ticket_number with prefix.
   - Database persistence and retrieval.
   - Status defaults to OPEN.
   - get_available_agents returns only ready/available agents.
   - is_operating_hours correctly reflects business hours schedule.
4. Write your specification report to:
   /root/voice-ai-telephony/test-calll-ai/.agents/teamwork/spec_miner_m1_1/handoff.md
Notify orchestrator when complete.
