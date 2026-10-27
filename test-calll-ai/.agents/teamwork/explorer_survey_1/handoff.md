# Codebase Survey & WhatsApp Escalation Architecture Report

## 1. Observation

### 1.1 Directory Structure, Languages, Frameworks, and Package Managers
Target project root: `/root/voice-ai-telephony/test-calll-ai`

- **Languages & Frameworks**:
  - Python 3.12: Django 5.1.15 (ASGI/WSGI with Uvicorn/Gunicorn), LangGraph 0.2+, LangChain Core 0.3+, Google GenAI SDK (`google-genai` >= 1.0.0), LiveKit Python Agents & SDK, Inngest Python SDK (`inngest` >= 0.4.0), psycopg2-binary, pgvector.
  - JavaScript / HTML: Vanilla JS with Centrifuge JS client (`centrifuge.js`), Tailwind CSS, Django HTML templates.
  - Go / C++ (compiled binaries): LiveKit server, LiveKit SIP, Centrifugo v5, MinIO, Traefik v3, Redis 7.
- **Package Management**:
  - `django_app/requirements.txt`: 27 dependencies (`Django>=5.0,<5.2`, `psycopg2-binary>=2.9.9`, `pgvector>=0.2.5`, `redis>=5.0.1`, `livekit-api>=0.7.2`, `google-genai>=1.0.0`, `inngest>=0.4.0`, `langgraph>=0.2.0`, `djangorestframework>=3.14.0`, `whitenoise>=6.6.0`).
  - `agent/requirements.txt`: 11 dependencies (`livekit>=1.1.20`, `livekit-agents>=1.8.6`, `livekit-plugins-google>=1.8.6`, `google-genai>=1.0.0`).
- **Container Infrastructure (`docker-compose.yml`)**:
  - `voice_django` (port 8000): Django web application and API server.
  - `voice_postgres` (port 5432): PostgreSQL 16 with pgvector.
  - `voice_redis` (port 6379): Redis 7 for caching, presence, and pub/sub.
  - `voice_evolution_api` (port 8080): Evolution API v2.1.2 (Baileys WhatsApp engine).
  - `voice_centrifugo` (port 8000 internal): Centrifugo real-time notification engine.
  - `voice_inngest` (port 8288): Inngest durable queue / background worker runner.
  - `voice_livekit`, `voice_sip`, `voice_agent`, `voice_minio`, `voice_prometheus`, `voice_grafana`.

### 1.2 WhatsApp AI Agent Implementation & Webhook Receiver
- **Evolution API Client**: `django_app/crm/services/evolution_client.py`
  - Sends text: `send_whatsapp_message(phone_number, text, instance_name)` (lines 134-162) to `http://evolution_api:8080/message/sendText/{instance_name}`.
  - Sends typing presence: `send_whatsapp_presence(phone_number, presence="composing", delay_ms=1200)` (lines 164-186) to `http://evolution_api:8080/chat/sendPresence/{instance_name}`.
  - Instance name: `user_{user.id}` (or `default_workspace`).
- **Webhook Entrypoint**: `django_app/crm/views.py`: `api_whatsapp_webhook(request)` (lines 1033-1196).
  - Route: `POST /api/crm/whatsapp/webhook/` in `django_app/crm/urls.py:46`.
  - Filters: Discards outbound messages `key.get("fromMe") == True` (line 1054).
  - Inbound Message Record: Creates `OmnichannelMessage` (lines 1107-1115):
    ```python
    msg_obj = OmnichannelMessage.objects.create(
        user=user,
        phone_number=clean_phone,
        customer_name=push_name,
        channel="whatsapp",
        direction="inbound",
        message_text=display_initial_text,
        metadata=msg_meta
    )
    ```
  - Media Processing: Decrypts audio/images, transcribes voice notes via Gemini 2.5 (lines 1118-1154).
  - Updates `CustomerMemory.whatsapp_memory` with latest message text and timestamp (lines 1157-1172).
  - **Auto-Reply Gate Check** (lines 1175-1177):
    ```python
    if wm.get("ai_auto_reply_enabled", True) is False:
        logger.info(f"AI auto-reply is paused for {clean_phone} (Human takeover active). Skipping LangGraph dispatch.")
        return JsonResponse({"status": "received", "action": "ai_paused_manual_takeover"})
    ```
  - Dispatches to Inngest background job (lines 1180-1189):
    ```python
    from crm.inngest_jobs import dispatch_whatsapp_followup_job
    dispatch_whatsapp_followup_job(
        user_id=user.id,
        phone_number=clean_phone,
        trigger_type="inbound_whatsapp",
        inbound_message=msg_obj.message_text,
        customer_name=push_name,
    )
    ```
- **Inngest Job Runner**: `django_app/crm/inngest_jobs.py` (lines 386-426, 428-479):
  - Event `crm/whatsapp.followup_requested` runs `fn_process_whatsapp_followup`, which calls `run_autonomous_followup(...)` in `django_app/crm/services/langgraph_worker.py`.
- **LangGraph Worker**: `django_app/crm/services/langgraph_worker.py`:
  - `FollowupState` TypedDict (lines 35-53).
  - Graph nodes: `evaluate_context` -> `decision_and_drafting` -> `execute_action` -> `END` (lines 785-798).
  - Mode A (Inbound WhatsApp):
    - Sends typing indicator `send_whatsapp_presence(phone, "composing")` (line 327).
    - Exposes tools to Gemini 2.5 Flash: `search_knowledge_base`, `lookup_customer_memory`, `escalate_to_human_support`, and dynamic MCP tools (`load_user_mcp_tools`) (lines 332-389).
    - Multi-turn tool calling loop up to 3 turns (lines 485-635).
    - `execute_action_node` (lines 703-780): Sends reply via `send_whatsapp_message()`, creates `OmnichannelMessage(direction="outbound_ai")`, updates `CustomerMemory.whatsapp_memory`.

### 1.3 Persistent Storage: CustomerMemory & State Flags
- Model: `django_app/crm/models.py:CustomerMemory` (lines 5-45)
  - Table: `voice_assistant_customermemory`, unique together `('user', 'phone_number')`.
  - Fields:
    - `user`: ForeignKey(User)
    - `phone_number`: CharField(64, db_index=True)
    - `customer_name`: CharField(120)
    - `permanent_profile`: JSONField (addresses, preferences, VIP tier, past complaints)
    - `call_memory`: JSONField (`last_call_summary`, `agreed_next_steps`)
    - `whatsapp_memory`: JSONField. Contains:
      - `ai_auto_reply_enabled`: Boolean (True by default).
      - `needs_human_attention`: Boolean.
      - `escalation_reason`: String.
      - `escalation_urgency`: String ("urgent" | "normal").
      - `escalation_summary`: String.
      - `escalated_at`: ISO datetime string.
      - `last_received_message`: String.
      - `last_sent_message`: String.
      - `last_interaction_at`: ISO datetime string.
      - `last_messages`: List of recent conversation turns.
- Associated message model: `django_app/crm/models.py:OmnichannelMessage` (lines 159-228).
  - Directions: `inbound`, `outbound_ai`, `outbound_human`.

### 1.4 Human Escalation and Complaint Triggers
- In `django_app/crm/services/langgraph_worker.py`:
  - Tool definition `escalate_to_human_support` (lines 358-386):
    ```python
    escalate_decl = types.FunctionDeclaration(
        name="escalate_to_human_support",
        description=(
            "تحويل محادثة الواتساب فوراً إلى موظف خدمة العملاء البشري أو الكاشير، وإيقاف الرد الآلي للذكاء الاصطناعي لهذه المحادثة. "
            "يجب استدعاء هذه الأداة فوراً ودون تردد عند: "
            "1. ورود أي شكوى من العميل بخصوص أوردر أو جودة الطعام أو تأخر التوصيل أو خطأ في الفاتورة أو الحساب. "
            "2. طلب العميل التحدث مع موظف بشري أو خدمة العملاء أو المشرف (مثل: 'حولني لخدمة العملاء'، 'عايز بني آدم'). "
            "3. عندما يكون العميل غاضباً أو غير راضٍ عن الردود التلقائية."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "reason": {"type": "STRING", "description": "سبب التحويل الرئيسي"},
                "urgency": {"type": "STRING", "enum": ["urgent", "normal"]},
                "summary": {"type": "STRING", "description": "ملخص واضح وموجز لشكوى أو طلب العميل"}
            },
            "required": ["reason", "summary"]
        }
    )
    ```
  - System Prompt Rule (line 452): Directs Gemini to invoke `escalate_to_human_support` immediately upon complaint or human handoff request.
  - Current Tool Execution (lines 524-560):
    ```python
    elif t_name == "escalate_to_human_support":
        reason = str(t_args.get("reason", "طلب دعم بشري / شكوى"))
        urgency = str(t_args.get("urgency", "normal"))
        summary = str(t_args.get("summary", inbound_msg))

        mem_rec, _ = CustomerMemory.objects.get_or_create(user_id=user_id, phone_number=phone)
        wm_rec = mem_rec.whatsapp_memory or {}
        wm_rec["ai_auto_reply_enabled"] = False
        wm_rec["needs_human_attention"] = True
        wm_rec["escalation_reason"] = reason
        wm_rec["escalation_urgency"] = urgency
        wm_rec["escalation_summary"] = summary
        wm_rec["escalated_at"] = datetime.now(timezone.utc).isoformat()
        mem_rec.whatsapp_memory = wm_rec
        mem_rec.save()

        alert_payload = {
            "event": "whatsapp_escalation",
            "phone_number": phone,
            "customer_name": c_name or mem_rec.customer_name or phone,
            "reason": reason,
            "urgency": urgency,
            "summary": summary,
            "escalated_at": wm_rec["escalated_at"]
        }
        try:
            publish_to_centrifugo(f"tenant_{user_id}", alert_payload)
            publish_to_centrifugo(f"user_{user_id}", alert_payload)
            publish_to_centrifugo(f"whatsapp_{user_id}", alert_payload)
        except Exception as cent_err:
            logger.warning(f"Failed to publish Centrifugo escalation alert: {cent_err}")
    ```

### 1.5 State Machines, Queues, Presence, and Operating Hours
- **Human Agents**: `django_app/call_center/models.py:EmployeeProfile` (lines 4-110).
  - Statuses: `ready` (available), `break`, `busy`, `offline`.
  - Redis Presence:
    - `call_center:employee:{id}:alive` (TTL 90s, set in `call_center/views.py:480`).
    - `agent_state:{participant_identity}` (set to `"AVAILABLE"` in `voice_assistant/views.py:684`).
    - Centrifugo broadcast: `publish_to_centrifugo("employees:presence", {"event": "status_change", ...})`.
- **Operating Hours**: `django_app/telephony/models.py:BusinessHoursSchedule` (lines 219-300).
  - Fields: `is_enabled`, `timezone` (default "Africa/Cairo"), `days_config`, `ai_message`.
  - Method: `is_within_business_hours(dt=None)` checks if current datetime falls within configured workday start/end hours.
- **Queues**:
  - `CallQueue` & `QueueMembership` exist in `call_center/models.py`, but they currently only handle voice/SIP phone calls via LiveKit SIP trunks and PBX.
  - **No queue or state machine currently exists for WhatsApp chat conversations.**
  - **No CRM Support Ticket model exists in the database.**
  - **No SLA watchdog timer exists for WhatsApp conversations.**

---

## 2. Logic Chain

1. **Inbound Processing**: When a customer sends a message on WhatsApp, Evolution API pushes it to `api_whatsapp_webhook` in `crm/views.py`. The webhook verifies `ai_auto_reply_enabled` from `CustomerMemory.whatsapp_memory`. If `False`, AI reply is suppressed (Human takeover mode). If `True`, the message is queued to Inngest (`crm/whatsapp.followup_requested`).
2. **AI Execution**: Inngest executes `fn_process_whatsapp_followup` -> `run_autonomous_followup()` -> LangGraph `decision_and_drafting_node` in `crm/services/langgraph_worker.py`.
3. **Escalation Trigger**: The LLM model (`gemini-2.5-flash`) calls tool `escalate_to_human_support` whenever customer complaints or human assistance requests are detected.
4. **Current Architectural Deficiencies vs Requirements (R1-R5)**:
   - **Gap R1 (Smart Availability Guard & Off-Hours Ticketing)**: Currently, `escalate_to_human_support` unconditionally sets `ai_auto_reply_enabled = False` without inspecting agent presence (`AgentPresence == AVAILABLE` or `EmployeeProfile.status == 'ready'`) and without calling `BusinessHoursSchedule.is_within_business_hours()`. Furthermore, there is no `CRMTicket` model, no unique ticket reference generator, and no automated off-hours reply message.
   - **Gap R2 (Least-Busy Agent Routing & State Machine)**: When agents are online, the code does not query active conversation loads across available agents, does not assign an `assigned_agent_id`, and does not track conversation state as `PENDING_AGENT_REPLY`.
   - **Gap R3 (Unified Inbox Alerting & AI Handoff Brief)**: Centrifugo event `whatsapp_escalation_assigned` is not published to target agent channel `user_{agent_id}`. The desktop chat interface (`whatsapp.html`) lacks audio chime alerting and an AI Handoff Brief modal.
   - **Gap R4 (SLA Watchdog & Automated Failover)**: There is no scheduled Inngest job or Celery/Redis watchdog checking for agent reply within 2 minutes (`PENDING_AGENT_REPLY` -> reassign to next agent + customer reassurance message).
   - **Gap R5 (Ticket Resolution & Handback to AI)**: There is no unified endpoint/action for an agent to click "Resolve & Resume AI" that persists resolution notes to `CustomerMemory` and resets `ai_auto_reply_enabled = True`.

---

## 3. Caveats

- `EmployeeProfile` in `call_center` represents human staff agents with `status='ready'`, while `voice_assistant/views.py` sets Redis `agent_state:* = 'AVAILABLE'`. A unified lookup for `AgentPresence` must check either `EmployeeProfile.objects.filter(status='ready', is_active=True)` or Redis presence keys, or both.
- WhatsApp JIDs can be standard international numbers (`2010...`), `@lid` internal identifiers, or `@g.us` group chats. Phone normalization via `normalize_jid_to_identifier` and `format_whatsapp_number` must continue to be respected.
- `voice_django` container has all migrations applied up to `crm:0011`. Adding a `CRMTicket` model or modifying models will require generating and running a Django migration (`python manage.py makemigrations crm && python manage.py migrate`).

---

## 4. Conclusion

The repository at `/root/voice-ai-telephony/test-calll-ai` has an operational, well-structured Django + LangGraph + Inngest + Evolution API foundation with existing models for `CustomerMemory`, `OmnichannelMessage`, `EmployeeProfile`, and `BusinessHoursSchedule`.

To satisfy requirements R1-R5:
1. **R1**: Create a `CRMTicket` model (with unique reference e.g. `TCK-XXXXX`). In `escalate_to_human_support`, check `BusinessHoursSchedule.is_within_business_hours()` and human agent presence (`EmployeeProfile.objects.filter(status='ready')`). If offline or off-hours: keep `ai_auto_reply_enabled = True`, generate `CRMTicket`, and return automated message with ticket reference and operating hours.
2. **R2**: When available agents exist, count active chats (`assigned_agent_id` with state `PENDING_AGENT_REPLY`) to select the `least-busy` agent. Set `wm["assigned_agent_id"] = agent.id`, `wm["conversation_state"] = "PENDING_AGENT_REPLY"`, and `wm["ai_auto_reply_enabled"] = False`.
3. **R3**: Broadcast Centrifugo event `whatsapp_escalation_assigned` to channel `user_{agent_id}` containing summary, urgency, reason, customer name, and phone. Add audio chime playback and AI Handoff Brief modal in `whatsapp.html`.
4. **R4**: Dispatch an Inngest delayed event (or Redis delayed task) for 2 minutes (`crm/sla.first_response_timeout`). If state is still `PENDING_AGENT_REPLY` and no `outbound_human` message was recorded from that agent, failover to the next available agent and send customer reassurance message.
5. **R5**: Implement endpoint `POST /api/crm/whatsapp/conversations/<phone>/resolve/` to store resolution summary in `CustomerMemory` and reset `ai_auto_reply_enabled = True`.

---

## 5. Verification Method

1. **Baseline Integrity Test**:
   Execute inside container:
   ```bash
   docker exec voice_django python test_whatsapp_and_dnc_gaps_e2e.py
   ```
   *Expected Output*: 58/58 tests pass (`ALL END-TO-END TESTS COMPLETED SUCCESSFULLY!`).

2. **File Inspection**:
   - Verify `CustomerMemory`: `django_app/crm/models.py:5-45`
   - Verify Webhook entry: `django_app/crm/views.py:1033-1196`
   - Verify LangGraph escalation tool: `django_app/crm/services/langgraph_worker.py:358-386` and `524-560`
   - Verify Human Agent Profile: `django_app/call_center/models.py:4-110`
   - Verify Operating Hours Schedule: `django_app/telephony/models.py:219-300`

3. **Invalidation Conditions**:
   - If `test_whatsapp_and_dnc_gaps_e2e.py` fails on any assertion.
   - If `ai_auto_reply_enabled` flag is relocated outside of `CustomerMemory.whatsapp_memory`.
   - If `messages.upsert` webhook payload schema from Evolution API changes.
