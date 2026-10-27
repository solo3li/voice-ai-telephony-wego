# M1 Integration Exploration & Ticketing Foundation Handoff Report

## Observation

### 1. Services Structure (`django_app/crm/services/`)
- Existing files in `django_app/crm/services/`:
  - `campaign_whatsapp.py` (12,220 bytes)
  - `evolution_client.py` (12,912 bytes)
  - `langgraph_worker.py` (45,620 bytes)
  - `whatsapp_media.py` (11,605 bytes)
  - `whatsapp_sync.py` (21,948 bytes)
- `whatsapp_dispatcher.py` does not currently exist.
- In `django_app/crm/services/langgraph_worker.py`:
  - Lines 358–360 define Gemini function declaration `escalate_to_human_support`.
  - Lines 524–560 handle tool execution inline:
    ```python
    elif t_name == "escalate_to_human_support":
        reason = str(t_args.get("reason", "طلب دعم بشري / شكوى"))
        urgency = str(t_args.get("urgency", "normal"))
        summary = str(t_args.get("summary", inbound_msg))
        mem_rec, _ = CustomerMemory.objects.get_or_create(user_id=user_id, phone_number=phone)
        wm_rec = mem_rec.whatsapp_memory or {}
        wm_rec["ai_auto_reply_enabled"] = False
        wm_rec["needs_human_attention"] = True
        ...
        alert_payload = {
            "event": "whatsapp_escalation",
            ...
        }
        publish_to_centrifugo(f"tenant_{user_id}", alert_payload)
        publish_to_centrifugo(f"user_{user_id}", alert_payload)
        publish_to_centrifugo(f"whatsapp_{user_id}", alert_payload)
    ```
  - This inline logic lacks presence verification, operating hours checks, least-busy agent selection, ticket creation, and assignment to `user_{agent_id}`.
- `PROJECT.md` specifies:
  - Architecture: "`crm/services/whatsapp_dispatcher.py` handles least-busy agent selection, active chat tracking, conversation state transitions (`PENDING_AGENT_REPLY`), and pause/resume of `ai_auto_reply_enabled`."
  - Code Layout: "- `django_app/crm/services/whatsapp_dispatcher.py`: Routing, presence guard, ticket generator, SLA watchdog".

### 2. Database Schema & Conflicting Table Inspection
- PostgreSQL container: `voice_postgres` (image `pgvector/pgvector:pg16`), DB `voice_db`, user `voice_user`.
- Tables list verification (`\dt`):
  - `auth_user`: PK `id` (integer)
  - `voice_assistant_employeeprofile`: PK `id` (bigint), `user_id` (FK `auth_user.id`), `employer_id` (FK `auth_user.id`), `status` (varchar(20)), `is_active` (boolean)
  - `voice_assistant_businesshoursschedule`: PK `id` (bigint), `user_id` (OneToOne `auth_user.id`), `is_enabled` (boolean), `days_config` (jsonb), `ai_message` (text)
  - Existing CRM tables: `crm_omnichannelmessage`, `crm_campaigncontact`, `crm_donotcallentry`, `crm_outboundcampaign`, `crm_usercampaignlimit`, `voice_assistant_customermemory`, `voice_assistant_callsession`.
- Query executed: `SELECT relname, relkind FROM pg_class WHERE relname ILIKE '%ticket%';` returned 0 rows.
- No existing table or view named `crm_crmsupportticket`, `crm_supportticket`, or `crm_support_ticket` exists.

### 3. Migration Dry-Run & Foreign Key Constraints
- Running `python manage.py makemigrations --dry-run` in `voice_django` returned:
  ```text
  Migrations for 'crm':
    crm/migrations/0012_alter_omnichannelmessage_created_at.py
      ~ Alter field created_at on omnichannelmessage
  ```
  This pending alter is due to `OmnichannelMessage.created_at` in `crm/models.py:175` using `default=timezone.now` while migration `0008` had `auto_now_add=True`.
- Model dependencies & Foreign Key constraints:
  - `auth_user`: In `crm/models.py`, `models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_tickets')` is directly supported. `User` is imported from `django.contrib.auth.models` and matches existing models in `crm`.
  - `EmployeeProfile`: Located in `call_center/models.py`. In `config/settings.py:49-51`, `call_center` is loaded prior to `crm`. In `crm/models.py`, using lazy string reference `'call_center.EmployeeProfile'` (`on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_support_tickets'`) avoids circular imports.
  - Deletion behavior: When tenant `User` is deleted, tickets cascade (`CASCADE`). When an agent (`EmployeeProfile`) is deleted, `assigned_agent` sets to `NULL` (`SET_NULL`), ensuring ticket audit history is preserved.

### 4. Existing Model Implementations for M1 Helpers
- `EmployeeProfile` (`call_center/models.py:4`):
  - `STATUS_CHOICES = [('ready', 'متاح (Ready)'), ('break', 'استراحة (Break)'), ('busy', 'مشغول (Busy)'), ('offline', 'غير متصل (Offline)')]`
  - Queries for tenant agents use `Q(employer_id=user_id) | Q(user_id=user_id)`.
  - Verified active agent count across existing tenants in DB: Tenant 49 has 7 available agents, Tenant 48 has 3, Tenant 8 has 2, Tenant 99999 has 0.
- `BusinessHoursSchedule` (`telephony/models.py:219`):
  - Has method `is_within_business_hours(self, dt=None) -> bool`.
  - If `is_enabled` is False, returns `True` (always open).
  - Verified via shell test: User 42 has `is_enabled=True` and currently returns `False` with `ai_message="مرحباً بكم في متجرنا بالرياض، الاتصال خارج الدوام."`.

---

## Logic Chain

1. **Service Placement Logic**:
   - `PROJECT.md` establishes a modular separation where `crm/models.py` owns data models and `crm/services/whatsapp_dispatcher.py` owns routing, presence guard, ticket generation, and SLA monitoring.
   - Placing `create_support_ticket`, `get_available_agents`, `is_operating_hours`, and `AgentPresence` in `crm/services/whatsapp_dispatcher.py` fulfills the M1 ↔ M2 interface contract while keeping `langgraph_worker.py` and `views.py` clean callers.

2. **Database & Table Naming Logic**:
   - In `crm/models.py`, standard models (`CampaignContact`, `DoNotCallEntry`, `OmnichannelMessage`) use Django default naming (`crm_<lowercase_modelname>`).
   - Defining `CRMSupportTicket` with `db_table = 'crm_support_ticket'` provides explicit, clean SQL table naming without repeating `crm_crm`.
   - Inspection confirmed no collision with existing tables in `voice_db`.

3. **Foreign Key Integrity Logic**:
   - `CRMSupportTicket` requires a link to tenant `User` (`auth_user.id`) and optional link to assigned agent `EmployeeProfile` (`voice_assistant_employeeprofile.id`).
   - Using `'call_center.EmployeeProfile'` with `on_delete=models.SET_NULL, null=True, blank=True` enablestickets to be created during off-hours or 0-agent states without an assigned agent, and allows reassignment during SLA failover without orphan deletion.

4. **Reference Code Generation Logic**:
   - Requirements specify format `TCK-YYYYMMDD-XXXX`.
   - `datetime.now().strftime("%Y%m%d")` combined with 4-character uppercase alphanumeric / hex tokens (`secrets.token_hex(2).upper()`) and a database uniqueness check provides collision-free reference codes.
   - Supplying both `ticket_number` field and `reference_code` property ensures compatibility with both naming conventions across specifications.

---

## Caveats

1. **Pending Migration Alter in `crm`**:
   - Running `makemigrations` in `crm` will generate an alter operation for `OmnichannelMessage.created_at` alongside `Create CRMSupportTicket`. The implementer can generate them together in `0012_crmsupportticket_and_alter_created_at.py` or apply the alter separately.
2. **Channel Target in Centrifugo (`user_{agent_id}`)**:
   - `EmployeeProfile` has both `id` (bigint) and `user_id` (integer FK to `auth_user`). In desktop views and Centrifugo subscriptions, if an agent logs in via employee extension (`api_employee_login`), their token subject is `employee_{id}_{ext}`. The dispatcher should publish to `user_{agent.id}` and `user_{agent.user_id}` or support both to ensure uninterrupted delivery.
3. **Timezone Configuration**:
   - `BusinessHoursSchedule.is_within_business_hours()` utilizes the record's `timezone` field (default `"Africa/Cairo"`). When testing time-boundary conditions in M1 unit tests, test cases should pass explicit `dt` arguments to avoid flaky tests based on system clock execution time.

---

## Conclusion

1. **Helper Placement**: Implement `AgentPresence`, `create_support_ticket`, `get_available_agents`, and `is_operating_hours` inside `django_app/crm/services/whatsapp_dispatcher.py`.
2. **Model Schema**: Implement `CRMSupportTicket` in `django_app/crm/models.py` with:
   - `user`: `ForeignKey(User, on_delete=CASCADE, related_name='support_tickets')`
   - `ticket_number`: `CharField(max_length=64, unique=True, db_index=True)`
   - `reference_code`: property aliased to `ticket_number`
   - `phone_number`: `CharField(max_length=64, db_index=True)`
   - `customer_name`: `CharField(max_length=120, blank=True, default='')`
   - `reason`: `CharField(max_length=255, blank=True, default='')`
   - `urgency`: `CharField(max_length=32, choices=[('normal', 'عادي'), ('urgent', 'عاجل')], default='normal')`
   - `summary`: `TextField(blank=True, default='')`
   - `status`: `CharField(max_length=32, choices=[('OPEN', 'Open'), ('PENDING', 'Pending'), ('RESOLVED', 'Resolved'), ('CLOSED', 'Closed')], default='OPEN')`
   - `operating_hours_text`: `TextField(blank=True, default='')`
   - `assigned_agent`: `ForeignKey('call_center.EmployeeProfile', on_delete=SET_NULL, null=True, blank=True, related_name='assigned_support_tickets')`
   - `resolution_notes`: `TextField(blank=True, default='')`
   - `resolved_at`: `DateTimeField(null=True, blank=True)`
   - `created_at`: `DateTimeField(auto_now_add=True, db_index=True)`
   - `updated_at`: `DateTimeField(auto_now=True)`
   - `db_table = 'crm_support_ticket'`
3. **M1 Unit Test Suite**: Implement `django_app/test_m1_ticketing_and_presence.py` containing 8 tests to verify all M1 acceptance gates prior to M2.

---

## Verification Method

### Test Cases Outline (`django_app/test_m1_ticketing_and_presence.py`)

| Test # | Test Name | Purpose | Invalidation Condition |
|---|---|---|---|
| 1 | `test_ticket_model_and_reference_generation` | Verifies `CRMSupportTicket` fields, default status `'OPEN'`, and `reference_code` regex `^TCK-\d{8}-[A-F0-9]{4}$` | `ticket_number` format mismatch or missing fields in `to_dict()` |
| 2 | `test_ticket_reference_uniqueness_batch` | Generates 100 consecutive references to guarantee no collisions | Any collision in 100 generated references |
| 3 | `test_create_support_ticket_helper` | Verifies `create_support_ticket` contract creates and saves record with supplied parameters | Record not saved or parameters corrupted |
| 4 | `test_ticket_foreign_key_constraints` | Verifies `SET_NULL` when `EmployeeProfile` is deleted, and `CASCADE` when tenant `User` is deleted | Deleting `EmployeeProfile` deletes ticket or raises IntegrityError |
| 5 | `test_agent_presence_helper` | Verifies `AgentPresence.is_available` returns `True` for `'ready'` and `'AVAILABLE'`, `False` for `'busy'`, `'break'`, `'offline'` | Case mismatch or invalid state considered available |
| 6 | `test_get_available_agents_query` | Verifies QuerySet returns only active agents with `status in ['ready', 'AVAILABLE']` for target tenant | Inactive agents or agents from other tenants returned |
| 7 | `test_is_operating_hours_evaluation` | Tests 4 branches: no schedule, disabled schedule, within hours, and outside hours | Outside hours returns `True` or within hours returns `False` |
| 8 | `test_migrations_applied_and_clean` | Runs `python manage.py makemigrations --check --dry-run` to prove no pending model changes | Unmigrated changes detected |

### Verification Commands
```bash
# 1. Run M1 unit tests inside Django container
docker exec -e DJANGO_SETTINGS_MODULE=config.settings voice_django python test_m1_ticketing_and_presence.py

# 2. Verify migration dry run
docker exec -e DJANGO_SETTINGS_MODULE=config.settings voice_django python manage.py makemigrations --check --dry-run

# 3. Verify PostgreSQL constraints
docker exec voice_postgres psql -U voice_user -d voice_db -c "\d crm_support_ticket"
```
