# Comprehensive Survey Report: Agent Presence, CRM Ticketing, Centrifugo, Agent Desktop, and Test Systems

**Investigator**: `teamwork_preview_explorer` (Survey Instance 2)  
**Target Path**: `/root/voice-ai-telephony/test-calll-ai`  
**Date**: 2026-10-24

---

## 1. Observation

### 1.1 Human Agents, Presence, and Agent States
- **Model**: `EmployeeProfile` defined at `django_app/call_center/models.py:4-30`
  ```python
  class EmployeeProfile(models.Model):
      STATUS_CHOICES = [
          ('ready', 'متاح (Ready)'),
          ('break', 'استراحة (Break)'),
          ('busy', 'مشغول (Busy)'),
          ('offline', 'غير متصل (Offline)'),
      ]
      user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')
      employer = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='managed_employees')
      extension = models.CharField(max_length=32, db_index=True)
      display_name = models.CharField(max_length=100, default='موظف')
      department = models.CharField(max_length=100, default='المبيعات')
      status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ready')
      push_token = models.CharField(max_length=255, blank=True, default='')
      phone_number = models.CharField(max_length=32, blank=True, default='', db_index=True)
      is_active = models.BooleanField(default=True)
  ```
- **Status Updates**: `api_update_employee_status` in `django_app/call_center/views.py:333-360`:
  ```python
  if new_status in ['ready', 'break', 'busy', 'offline']:
      employee.status = new_status
      employee.save(update_fields=['status'])
      publish_to_centrifugo("employees:presence", {
          "event": "status_change",
          "employee": employee.to_dict()
      })
  ```
- **Redis Presence**: In `django_app/voice_assistant/views.py:683-692`, Redis keys track agent status:
  ```python
  r.set(f"agent_state:{participant_identity}", "AVAILABLE")
  r.set(f"agent_state:{clean}", "AVAILABLE")
  publish_to_centrifugo("presence_updates", {
      "event": "agent_presence",
      "sip_username": participant_identity,
      "state": "AVAILABLE"
  })
  ```
- **Operating Hours**: `BusinessHoursSchedule` in `django_app/telephony/models.py:219-280`:
  ```python
  class BusinessHoursSchedule(models.Model):
      user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='business_hours_schedule')
      is_enabled = models.BooleanField(default=False)
      timezone = models.CharField(max_length=64, default="Africa/Cairo")
      days_config = models.JSONField(default=get_default_business_days_config)
      ai_message = models.TextField(...)
      def is_within_business_hours(self, dt=None) -> bool: ...
  ```

### 1.2 Centrifugo Integration, Channel Naming Conventions, and Event Schemas
- **Publishing Service**: `django_app/common/centrifugo.py:9-38`
  ```python
  def publish_to_centrifugo(channel: str, data: dict, timeout: float = 2.0) -> bool:
      api_url = getattr(settings, 'CENTRIFUGO_HTTP_API_URL', 'http://centrifugo:8000/api')
      api_key = getattr(settings, 'CENTRIFUGO_API_KEY', 'centrifugo_api_key_1234567890')
      url = f"{api_url}/publish"
      headers = {"Authorization": f"apikey {api_key}", "Content-Type": "application/json"}
      payload = {"channel": channel, "data": data}
      res = requests.post(url, json=payload, headers=headers, timeout=timeout)
      return res.status_code == 200
  ```
- **Centrifugo Configuration**: `centrifugo/config.json:36-74`
  - Engine: Redis (`redis:6379`).
  - Configured namespaces: `rooms`, `employee`, `employees`, `queues`.
  - `without_namespace`: `"allow_subscribe_for_client": true`, `"presence": true`.
  - Channel pattern `user_{agent_id}` falls under `without_namespace` and is directly subscriable by browser clients without needing a custom namespace.
- **Existing Channel Conventions & Events**:
  - `employees:presence` — event: `status_change` with `{"event": "status_change", "employee": {...}}`.
  - `employee:{employee_id}` — incoming call events (`incoming_call`, `call_ended`).
  - `tenant_{user_id}`, `user_{user_id}`, `whatsapp_{user_id}` — escalation alert in `django_app/crm/services/langgraph_worker.py:541-554`:
    ```python
    alert_payload = {
        "event": "whatsapp_escalation",
        "phone_number": phone,
        "customer_name": c_name or mem_rec.customer_name or phone,
        "reason": reason,
        "urgency": urgency,
        "summary": summary,
        "escalated_at": wm_rec["escalated_at"]
    }
    publish_to_centrifugo(f"tenant_{user_id}", alert_payload)
    publish_to_centrifugo(f"user_{user_id}", alert_payload)
    publish_to_centrifugo(f"whatsapp_{user_id}", alert_payload)
    ```
- **Frontend Client**: `django_app/static/js/common.js:83-120` initializes `globalCentrifugeClient` using `Centrifuge(data.centrifugo_ws_url, { token: data.centrifugo_token })`. Token endpoint is `/api/token/`.

### 1.3 CRM Ticketing Models and Service Stubs
- **Existing Models in `django_app/crm/models.py`**:
  - `CustomerMemory` (lines 5-158): Stores customer identity, `call_memory`, `whatsapp_memory` (JSON fields), `permanent_profile`.
  - `OmnichannelMessage` (lines 159-230): Stores message direction (`inbound`, `outbound_ai`, `outbound_human`), `message_text`, `metadata`, timestamps.
  - `CallSession` (lines 231-323): Call recording and transcript records.
  - `UserCampaignLimit`, `OutboundCampaign`, `CampaignContact`, `DoNotCallEntry`.
- **Finding**: There is **no CRM Ticket model** anywhere in `crm/models.py` or the wider project. Ticketing fields (unique reference number, status, notes, assigned agent) must be added as a new model `SupportTicket` or ticketing engine in `crm/`.

### 1.4 Agent Desktop / Web Inbox Implementation & Endpoints
- **Agent Desktop Template**: `django_app/voice_assistant/templates/voice_assistant/pages/whatsapp.html`:
  - Split view: left column has chat thread, right column has customer conversation list.
  - Controls: manual reply (`sendManualReply`), AI toggle (`toggleCurrentAiAutoReply`).
  - Current refresh mechanism: HTTP polling via `setInterval(..., 12000)` at line 446.
  - **Gaps identified**:
    - No Centrifugo WebSocket listener on `user_{agent_id}`.
    - No audible alert / audio chime on escalation.
    - No "AI Handoff Brief" card display (reason, customer name, urgency, AI summary).
    - No "Resolve & Resume AI" action that captures resolution notes.
- **Existing WhatsApp Endpoints in `django_app/crm/urls.py`**:
  - `whatsapp/conversations/` -> `api_whatsapp_conversations` (GET)
  - `whatsapp/conversations/<path:phone_number>/messages/` -> `api_whatsapp_conversation_messages` (GET)
  - `whatsapp/conversations/<path:phone_number>/reply/` -> `api_whatsapp_conversation_reply` (POST)
  - `whatsapp/conversations/<path:phone_number>/toggle-ai/` -> `api_whatsapp_conversation_toggle_ai` (POST)
  - `whatsapp/conversations/<path:phone_number>/update-contact/` -> `api_whatsapp_conversation_update_contact` (POST)
- **Current Escalation Tool Handling**:
  - In `django_app/crm/services/langgraph_worker.py:524-560`, tool `escalate_to_human_support` unconditionally sets `wm_rec["ai_auto_reply_enabled"] = False` without checking online agents or operating hours, and does not perform agent queue routing.

### 1.5 Test Suite Architecture & Execution
- **Deployment Topology**: Containerized multi-service Docker architecture defined in `docker-compose.yml`.
  - Service `django`: container `voice_django` (`test-calll-ai-django`) mounting `./django_app:/app`.
  - Service `agent`: container `voice_agent` (`test-calll-ai-agent`) mounting `./agent:/app`.
  - Service `centrifugo`: container `voice_centrifugo`.
  - Service `voice_postgres`: container `voice_postgres` (PostgreSQL 16 + pgvector).
  - Service `redis`: container `voice_redis` (Redis 7).
- **Test Runner & Execution**:
  - Host has no direct virtualenv or pytest installed; all test suites run inside the `voice_django` Docker container.
  - Verification commands executed successfully:
    ```bash
    docker exec voice_django python test_whatsapp_and_dnc_gaps_e2e.py   # 58/58 tests PASSED (100%)
    docker exec voice_django python test_new_features_e2e.py           # ALL TESTS PASSED (100%)
    docker exec -i voice_django python manage.py shell < django_app/test_dnc_and_inngest_e2e.py  # 11/11 tests PASSED
    ```
  - Test Structure: Standalone Python scripts that initialize Django via `os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup()`, create mock/test tenant fixtures, execute RequestFactory/Client HTTP calls or model transactions, and assert responses.

---

## 2. Logic Chain

1. **Presence & State Guard (R1)**:
   - Observation: `EmployeeProfile` holds `status` (`'ready'`, `'break'`, `'busy'`, `'offline'`). `BusinessHoursSchedule` holds `is_within_business_hours()`.
   - In WhatsApp escalation (`escalate_to_human_support` in `langgraph_worker.py`), the system must query:
     `available_agents = EmployeeProfile.objects.filter(employer=tenant_user, is_active=True, status__in=['ready', 'AVAILABLE'])`
     and `schedule.is_within_business_hours()`.
   - If `not available_agents.exists()` or outside business hours:
     - Keep `ai_auto_reply_enabled = True` in `CustomerMemory.whatsapp_memory`.
     - Create a `SupportTicket` with unique reference (e.g. `REF-{uuid4().hex[:8].upper()}`).
     - Send automated message with ticket number and operating hours.

2. **Least-Busy Routing & State Transition (R2)**:
   - For online agents, compute active conversation load:
     Count active chats per agent from `CustomerMemory` where `whatsapp_memory__assigned_agent_id == agent.id` and `whatsapp_memory__ai_auto_reply_enabled == False`.
   - Select agent with minimum active count.
   - Update `CustomerMemory.whatsapp_memory`:
     `assigned_agent_id = agent.id`, `conversation_state = 'PENDING_AGENT_REPLY'`, `ai_auto_reply_enabled = False`.

3. **Centrifugo Alerting & Handoff Brief (R3)**:
   - Observation: `common.centrifugo.publish_to_centrifugo` publishes to any channel; `without_namespace` in `centrifugo/config.json` allows client subscription to `user_{agent_id}`.
   - Publish event `whatsapp_escalation_assigned` to channel `user_{agent_id}` with payload: `summary`, `urgency`, `reason`, `phone_number`, `customer_name`, `escalated_at`.
   - In `whatsapp.html`, subscribe to `user_{agent_id}`, trigger Web Audio API / `<audio>` chime on event, and render the AI Handoff Brief badge/accordion.

4. **SLA Watchdog (R4)**:
   - Implement watchdog timer (2 minutes): When chat enters `PENDING_AGENT_REPLY`, record `assigned_at`.
   - If no outbound agent message occurs within 120 seconds, failover reassigns to the next least-busy available agent and sends reassurance WhatsApp message to customer.

5. **Ticket Resolution & AI Handback (R5)**:
   - Add endpoint `POST /api/crm/whatsapp/conversations/<phone>/resolve/`:
     - Updates `CustomerMemory.whatsapp_memory`: sets `ai_auto_reply_enabled = True`, `conversation_state = 'RESOLVED'`, clears `needs_human_attention`.
     - Appends agent resolution notes into `CustomerMemory.permanent_profile` or `whatsapp_memory`.
     - Updates associated `SupportTicket.status = 'RESOLVED'`.

---

## 3. Caveats

- **Existing Docker State**: Containers (`voice_django`, `voice_postgres`, `voice_redis`, `voice_centrifugo`) are actively running and healthy. Code changes in `django_app/` take effect immediately due to the volume mount (`./django_app:/app`).
- **Ticket Model Migration**: Introducing a new model `SupportTicket` in `crm/models.py` requires generating and applying a Django migration (`python manage.py makemigrations crm && python manage.py migrate`).
- **Evolution API Offline Mocking in Tests**: In testing environments, Evolution API instance may be disconnected (`instance 'user_114' is not connected`); tests handle this gracefully by asserting database persistence (`OmnichannelMessage`) and fallback results.

---

## 4. Conclusion

All requisite subsystems and architectural foundations exist and were verified:
1. `EmployeeProfile` and `BusinessHoursSchedule` cleanly represent agent presence and operating hours.
2. `common/centrifugo.py` and `centrifugo/config.json` support arbitrary channels including `user_{agent_id}` without configuration changes.
3. CRM ticketing requires a new `SupportTicket` model and reference generator in `crm/models.py`.
4. Agent desktop at `voice_assistant/pages/whatsapp.html` provides the full chat UI and can be augmented with Centrifugo listener, audio chime, AI brief, and the resolve/handback button.
5. The test execution standard is `docker exec voice_django python <test_script>.py`, demonstrated by 100% pass rates on existing test suites.

---

## 5. Verification Method

To independently verify these findings, run:

1. **Verify Agent & Business Hours Models**:
   ```bash
   docker exec voice_django python -c "
   import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup()
   from call_center.models import EmployeeProfile
   from telephony.models import BusinessHoursSchedule
   print('EmployeeProfile fields:', [f.name for f in EmployeeProfile._meta.get_fields()])
   print('BusinessHoursSchedule fields:', [f.name for f in BusinessHoursSchedule._meta.get_fields()])
   "
   ```

2. **Verify Centrifugo Connectivity**:
   ```bash
   docker exec voice_django python -c "
   import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup()
   from common.centrifugo import publish_to_centrifugo
   res = publish_to_centrifugo('user_test', {'event': 'test_ping', 'ok': True})
   print('Centrifugo publish status:', res)
   "
   ```

3. **Run Existing Verification Suites**:
   ```bash
   docker exec voice_django python test_whatsapp_and_dnc_gaps_e2e.py
   docker exec voice_django python test_new_features_e2e.py
   ```
