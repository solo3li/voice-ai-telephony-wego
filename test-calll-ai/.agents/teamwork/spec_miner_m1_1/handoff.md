# Milestone 1 Specification Report: Data Models & Ticketing Foundation

**Agent**: `spec_miner_m1_1`  
**Milestone**: M1 (Data Models & Ticketing Foundation)  
**Date**: 2026-10-24T03:50:00Z  
**Target Repository**: `/root/voice-ai-telephony/test-calll-ai`  

---

## 1. Observation

1. **Authoritative Specification Inputs**:
   - `ORIGINAL_REQUEST.md` (R1): Smart availability guard requires checking human agent presence (`AgentPresence == AVAILABLE`) and current operating hours. If no human agent is online or if outside working hours, system must automatically create a CRM support ticket with a unique reference number.
   - `PROJECT.md` (M1 Scope): Defines M1 deliverables as `CRMSupportTicket` model in `crm/models.py`, schema migrations, `AgentPresence` helper, and operating hours evaluation.
   - `PROJECT.md` (§ Interface Contracts):
     - `create_support_ticket(user_id, phone_number, customer_name, reason, urgency, summary, operating_hours_text="") -> CRMSupportTicket`
     - `get_available_agents(user_id) -> QuerySet[EmployeeProfile]`
     - `is_operating_hours(user_id) -> Tuple[bool, str]`

2. **Existing Data Models & Database State**:
   - `django_app/call_center/models.py` defines `EmployeeProfile`:
     - Status field: `status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ready')`
     - Status choices: `[('ready', 'متاح (Ready)'), ('break', 'استراحة (Break)'), ('busy', 'مشغول (Busy)'), ('offline', 'غير متصل (Offline)')]`
     - Tenant relationships: `user = models.OneToOneField(User, ...)` and `employer = models.ForeignKey(User, null=True, blank=True, related_name='managed_employees')`.
     - Active flag: `is_active = models.BooleanField(default=True)`.
     - Probed live database (`voice_django`): 28 `EmployeeProfile` records exist with statuses including `'ready'`, associated with employers and user accounts.
   - `django_app/telephony/models.py` defines `BusinessHoursSchedule`:
     - One-to-one with `User`: `user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='business_hours_schedule')`.
     - Toggle: `is_enabled = models.BooleanField(default=False)`.
     - Timezone: `timezone = models.CharField(max_length=64, default="Africa/Cairo")`.
     - Days configuration: `days_config = models.JSONField(default=get_default_business_days_config)`. Keys are lowercase weekday names (`saturday`, `sunday`, `monday`, `tuesday`, `wednesday`, `thursday`, `friday`), with values containing `is_workday` (bool), `start_time` ("HH:MM"), `end_time` ("HH:MM").
     - Existing method: `is_within_business_hours(self, dt=None) -> bool`. When `is_enabled=False`, returns `True`. When `is_enabled=True`, checks current time against active day configuration and handles shifts spanning midnight.
     - Probed live database (`voice_django`): 11 `BusinessHoursSchedule` records exist with active timezones (`Africa/Cairo`, `Asia/Riyadh`).
   - `django_app/crm/models.py` currently contains:
     - `CustomerMemory`, `OmnichannelMessage`, `CallSession`, `UserCampaignLimit`, `OutboundCampaign`, `CampaignContact`, `DoNotCallEntry`.
     - Current migration count in `django_app/crm/migrations/`: 11 migration files (`0001` through `0011`). The next migration will be `0012_crmsupportticket.py`.
     - Currently, no `CRMSupportTicket` model exists in `crm/models.py`.

---

## 2. Logic Chain

1. **Data Model Architecture (`CRMSupportTicket`)**:
   - Must represent support escalations and off-hours service requests across WhatsApp and voice channels.
   - Primary key: `id = models.BigAutoField(primary_key=True)`.
   - `ticket_number`: Must be unique and human-readable for customer reference via WhatsApp messages (`TCK-YYYYMMDD-XXXX`). Length up to 64 chars allows the standard prefix, date, and collision-free alphanumeric hash. Indexed with `db_index=True` for fast customer lookup.
   - `user`: Required foreign key to `django.contrib.auth.models.User` (`on_delete=models.CASCADE`, `related_name='crm_support_tickets'`) to enforce tenant scoping.
   - `customer_phone`: Indexed phone number (`max_length=64`) storing the normalized E.164 phone number.
   - `customer_name`: Optional string (`max_length=120`, `blank=True, default=''`) matching `CustomerMemory.customer_name`.
   - `reason`: Summary reason for escalation (`max_length=255`, `default='طلب دعم بشري / شكوى'`).
   - `urgency`: Character choice (`max_length=20`, default `'normal'`, indexed) supporting `'normal'` and `'urgent'`.
   - `summary`: Detailed text field (`models.TextField(blank=True, default='')`) holding AI conversation context or customer complaint details.
   - `status`: Lifecycle choice (`max_length=32`, default `'OPEN'`, indexed) supporting `OPEN`, `IN_PROGRESS`, `RESOLVED`, `CLOSED`.
   - `operating_hours_snapshot`: Text field storing business hours snapshot at time of ticket creation.
   - `assigned_employee`: Nullable foreign key to `call_center.EmployeeProfile` (`on_delete=models.SET_NULL`, `null=True, blank=True`). Off-hours and zero-agent tickets start unassigned (`None`).
   - `resolution_notes`: Text field storing resolution details logged by agent or automated handback.
   - Timestamps: `created_at` (`default=timezone.now, db_index=True`), `updated_at` (`auto_now=True`), and `resolved_at` (`DateTimeField(null=True, blank=True)`).

2. **Creation Service Contract (`create_support_ticket`)**:
   - Location: `django_app/crm/services/whatsapp_dispatcher.py`.
   - Signature: `create_support_ticket(user_id, phone_number, customer_name, reason, urgency, summary, operating_hours_text="") -> CRMSupportTicket`.
   - Supports both `int` and `User` instances for `user_id`.
   - Automatically generates unique `ticket_number` (`TCK-<YYYYMMDD>-<HEX8>`) if not explicitly passed.
   - Guarantees database persistence before returning.

3. **Agent Availability Contract (`get_available_agents`)**:
   - Location: `django_app/crm/services/whatsapp_dispatcher.py`.
   - Signature: `get_available_agents(user_id) -> QuerySet[EmployeeProfile]`.
   - Returns a Django `QuerySet` filtered by:
     - `is_active=True`
     - `status__in=['ready', 'AVAILABLE', 'available', 'Ready']`
     - Tenant scoping: `Q(employer_id=uid) | Q(user_id=uid)`. If no employer is associated (single-tenant / legacy), falls back to active agents with `employer__isnull=True`.
   - Excludes agents with statuses `busy`, `break`, `offline` or `is_active=False`.

4. **Operating Hours Verification Contract (`is_operating_hours`)**:
   - Location: `django_app/crm/services/whatsapp_dispatcher.py`.
   - Signature: `is_operating_hours(user_id, dt=None) -> Tuple[bool, str]`.
   - Queries `BusinessHoursSchedule.objects.filter(user_id=uid).first()`.
   - If schedule does not exist or `is_enabled=False`, returns `(True, "متاح على مدار الساعة (24/7)")`.
   - If `is_enabled=True`, delegates to `b_sched.is_within_business_hours(dt)` and formats human-readable hours text for the current day or schedule.

---

## 3. Detailed Data Specifications

### 3.1 Model Schema: `CRMSupportTicket`

File: `django_app/crm/models.py`  
Table name: `crm_support_ticket`

```python
class CRMSupportTicket(models.Model):
    URGENCY_CHOICES = [
        ('normal', 'عادي (Normal)'),
        ('urgent', 'عاجل (Urgent)'),
    ]

    STATUS_CHOICES = [
        ('OPEN', 'مفتوحة (Open)'),
        ('IN_PROGRESS', 'قيد المتابعة (In Progress)'),
        ('RESOLVED', 'تم الحل (Resolved)'),
        ('CLOSED', 'مغلقة (Closed)'),
    ]

    ticket_number = models.CharField(
        max_length=64, 
        unique=True, 
        db_index=True, 
        help_text="الرقم المرجعي الفريد للتذكرة (TCK-YYYYMMDD-XXXX)"
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='crm_support_tickets',
        help_text="حساب المنشأة / المالك التابع له التذكرة"
    )
    customer_phone = models.CharField(
        max_length=64, 
        db_index=True, 
        help_text="رقم هاتف العميل بالصيغة الدولية"
    )
    customer_name = models.CharField(
        max_length=120, 
        blank=True, 
        default='', 
        help_text="اسم العميل"
    )
    reason = models.CharField(
        max_length=255, 
        blank=True, 
        default='طلب دعم بشري / شكوى', 
        help_text="سبب التصعيد أو الشكوى"
    )
    urgency = models.CharField(
        max_length=20, 
        choices=URGENCY_CHOICES, 
        default='normal', 
        db_index=True, 
        help_text="درجة الأهمية"
    )
    summary = models.TextField(
        blank=True, 
        default='', 
        help_text="ملخص الذكاء الاصطناعي للمشكلة وسياق المحادثة"
    )
    status = models.CharField(
        max_length=32, 
        choices=STATUS_CHOICES, 
        default='OPEN', 
        db_index=True, 
        help_text="حالة التذكرة"
    )
    operating_hours_snapshot = models.TextField(
        blank=True, 
        default='', 
        help_text="لقطة من مواعيد العمل الرسمية وقت إنشاء التذكرة"
    )
    assigned_employee = models.ForeignKey(
        'call_center.EmployeeProfile', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='assigned_crm_tickets',
        help_text="الموظف البشري المكلف بمتابعة التذكرة (إن وجد)"
    )
    resolution_notes = models.TextField(
        blank=True, 
        default='', 
        help_text="تفاصيل وملاحظات إغلاق التذكرة"
    )
    created_at = models.DateTimeField(
        default=timezone.now, 
        db_index=True, 
        help_text="تاريخ وتوقيت إنشاء التذكرة"
    )
    updated_at = models.DateTimeField(
        auto_now=True, 
        help_text="تاريخ وتوقيت آخر تحديث"
    )
    resolved_at = models.DateTimeField(
        null=True, 
        blank=True, 
        help_text="تاريخ وتوقيت حل التذكرة"
    )

    class Meta:
        db_table = 'crm_support_ticket'
        ordering = ['-created_at']
        verbose_name = 'تذكرة دعم فني'
        verbose_name_plural = 'تذاكر الدعم الفني'

    @classmethod
    def generate_ticket_number(cls) -> str:
        """Generate unique ticket reference: TCK-YYYYMMDD-XXXX."""
        import uuid
        from datetime import datetime
        date_str = datetime.now().strftime("%Y%m%d")
        for _ in range(20):
            token = uuid.uuid4().hex[:6].upper()
            candidate = f"TCK-{date_str}-{token}"
            if not cls.objects.filter(ticket_number=candidate).exists():
                return candidate
        token = uuid.uuid4().hex[:8].upper()
        return f"TCK-{date_str}-{token}"

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            self.ticket_number = self.generate_ticket_number()
        if self.status in ('RESOLVED', 'CLOSED') and not self.resolved_at:
            self.resolved_at = timezone.now()
        elif self.status in ('OPEN', 'IN_PROGRESS'):
            self.resolved_at = None
        super().save(*args, **kwargs)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ticket_number": self.ticket_number,
            "user_id": self.user_id,
            "customer_phone": self.customer_phone,
            "customer_name": self.customer_name,
            "reason": self.reason,
            "urgency": self.urgency,
            "summary": self.summary,
            "status": self.status,
            "operating_hours_snapshot": self.operating_hours_snapshot,
            "assigned_employee_id": self.assigned_employee_id,
            "assigned_employee_name": self.assigned_employee.display_name if self.assigned_employee else None,
            "resolution_notes": self.resolution_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }
```

---

### 3.2 Service Functions Specifications

File: `django_app/crm/services/whatsapp_dispatcher.py`

#### 1. `create_support_ticket`
```python
def create_support_ticket(
    user_id: int | User,
    phone_number: str,
    customer_name: str = "",
    reason: str = "طلب دعم بشري / شكوى",
    urgency: str = "normal",
    summary: str = "",
    operating_hours_text: str = ""
) -> CRMSupportTicket:
    """
    Creates and persists a new CRMSupportTicket.
    
    Inputs:
        user_id: int or User instance (Tenant owner)
        phone_number: str (Customer phone number in E.164 or local format)
        customer_name: str (Customer display name)
        reason: str (Escalation trigger reason)
        urgency: str ('normal' or 'urgent')
        summary: str (Context/complaint summary)
        operating_hours_text: str (Snapshot of current business hours)
        
    Outputs:
        CRMSupportTicket: Saved instance with auto-generated unique ticket_number.
        
    Error Behavior:
        - If user_id is missing or invalid: raises ValueError.
        - If phone_number is empty: raises ValueError.
        - Invalid urgency normalized to 'normal'.
    """
```

#### 2. `get_available_agents`
```python
def get_available_agents(user_id: int | User | None = None) -> QuerySet[EmployeeProfile]:
    """
    Retrieves all available and active human support agents.
    
    Inputs:
        user_id: Optional int or User instance for tenant scoping.
        
    Outputs:
        QuerySet[EmployeeProfile]: Queryset filtered by is_active=True and
        status in ['ready', 'AVAILABLE', 'available', 'Ready'].
        
    Error Behavior:
        - Returns empty queryset if no agents match criteria. Never raises DoesNotExist.
    """
```

#### 3. `is_operating_hours`
```python
def is_operating_hours(
    user_id: int | User | None, 
    dt: Optional[datetime] = None
) -> Tuple[bool, str]:
    """
    Checks if current time falls within configured business hours for the tenant.
    
    Inputs:
        user_id: int or User instance (Tenant owner)
        dt: Optional datetime for test simulation or specific evaluation point.
        
    Outputs:
        Tuple[bool, str]:
            [0]: True if within business hours or schedule disabled; False if off-hours.
            [1]: Human-readable operating hours description or message text.
            
    Error Behavior:
        - If user_id is None or no schedule exists: returns (True, "متاح على مدار الساعة (24/7)").
        - If timezone/parsing errors occur: safely falls back to (True, "متاح على مدار الساعة (24/7)").
    """
```

---

## 4. Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Ticketing | `CRMSupportTicket` Model | Database model for customer support tickets with unique code | Field attributes | Model instance | Database validation errors | `PROJECT.md`, `ORIGINAL_REQUEST.md` |
| 2 | Ticketing | Unique Reference Generator | Generates `TCK-YYYYMMDD-XXXX` unique reference codes | None (internal classmethod) | `str` reference code | Loop with UUID fallback on collision | `PROJECT.md` line 6 |
| 3 | Ticketing | Auto Timestamp on Resolution | Automatically populates `resolved_at` when status transitions to `RESOLVED` | `self.status` | `resolved_at` datetime | Silent fallback | Code inspection |
| 4 | Presence | Multi-Status Agent Presence | Identifies online human agents across legacy (`ready`) and spec (`AVAILABLE`) | `user_id` | `QuerySet[EmployeeProfile]` | Empty QuerySet | `call_center/models.py`, `PROJECT.md` |
| 5 | Presence | Tenant Isolation Scoping | Restricts available agents to employer or user ID | `user_id` | Scoped QuerySet | Returns empty if tenant has no agents | `call_center/views.py` |
| 6 | Business Hours | Schedule Evaluation | Evaluates schedule considering timezone and midnight shifts | `user_id`, optional `dt` | `Tuple[bool, str]` | Default `(True, "24/7")` if missing/disabled | `telephony/models.py` |
| 7 | Business Hours | Arabic / Human Hours Formatter | Produces human-readable operating hours string | `b_sched`, `dt` | Formatted `str` | Default string if format fails | `langgraph_worker.py` |
| 8 | Integration | Single-Tenant Agent Fallback | Handles legacy setups where `employer` is NULL on `EmployeeProfile` | `user_id` | `QuerySet[EmployeeProfile]` | Fallback to `employer__isnull=True` | Database probing |

---

## 5. Edge Cases

| # | Feature | Input | Observed Behavior |
|---|---------|-------|-------------------|
| 1 | `CRMSupportTicket` | Empty `ticket_number` on model save | Automatically generates `TCK-YYYYMMDD-XXXX` with non-empty 6-8 char uppercase token. |
| 2 | `CRMSupportTicket` | Status changed from `OPEN` to `RESOLVED` | `resolved_at` is set to `timezone.now()`. |
| 3 | `CRMSupportTicket` | Arabic text in customer name, reason, and summary | Fully supported via utf-8 in PostgreSQL (`CharField`/`TextField`). |
| 4 | `create_support_ticket` | `user_id` passed as `User` instance vs `int` | Both handled identically; extracts `.id` if object. |
| 5 | `create_support_ticket` | Missing `phone_number` | Raises `ValueError("phone_number is required")`. |
| 6 | `create_support_ticket` | Non-existent `user_id` | Raises `ValueError("User does not exist")` or `User.DoesNotExist`. |
| 7 | `get_available_agents` | Agent has `status='ready'` but `is_active=False` | Excluded from result set. |
| 8 | `get_available_agents` | Agent has `status='busy'` or `status='break'` | Excluded from result set. |
| 9 | `get_available_agents` | Agent has `status='AVAILABLE'` (uppercase) | Included in result set. |
| 10 | `get_available_agents` | 0 agents exist for tenant | Returns empty QuerySet (`count() == 0`). |
| 11 | `is_operating_hours` | No `BusinessHoursSchedule` row for user | Returns `(True, "متاح على مدار الساعة (24/7)")`. |
| 12 | `is_operating_hours` | `b_sched.is_enabled = False` | Returns `(True, "متاح على مدار الساعة (24/7)")`. |
| 13 | `is_operating_hours` | Non-workday (e.g. Friday with `is_workday=False`) | Returns `(False, <hours_text>)`. |
| 14 | `is_operating_hours` | Overnight shift (e.g. 20:00 to 04:00) evaluated at 02:00 | Returns `(True, <hours_text>)` correctly via existing midnight logic. |

---

## 6. Verification Test Assertions for M1

The M1 verification test suite (`django_app/test_m1_ticketing_foundation.py`) must execute and pass the following assertions:

1. **Ticket Creation & Unique Number Generation**:
   - `ticket = create_support_ticket(user_id=user.id, phone_number="+201012345678", customer_name="عميل تجريبي", reason="شكوى تأخر طلب", urgency="urgent", summary="الطلب تأخر أكثر من ساعة")`
   - Assert `bool(ticket.ticket_number) is True`
   - Assert `ticket.ticket_number.startswith("TCK-") is True`
   - Assert `re.match(r'^TCK-\d{8}-[A-F0-9]{6,8}$', ticket.ticket_number) is not None`
   - Create 10 tickets in loop -> assert all 10 `ticket_number`s are distinct (`len(set(numbers)) == 10`).

2. **Database Persistence and Retrieval**:
   - `retrieved = CRMSupportTicket.objects.get(id=ticket.id)`
   - Assert `retrieved.user_id == user.id`
   - Assert `retrieved.customer_phone == "+201012345678"`
   - Assert `retrieved.customer_name == "عميل تجريبي"`
   - Assert `retrieved.reason == "شكوى تأخر طلب"`
   - Assert `retrieved.urgency == "urgent"`
   - Assert `retrieved.summary == "الطلب تأخر أكثر من ساعة"`
   - Assert `retrieved.assigned_employee is None`
   - Assert `retrieved.created_at is not None`

3. **Status Defaults & Lifecycle**:
   - Assert `ticket.status == 'OPEN'`
   - Assert `ticket.resolved_at is None`
   - `ticket.status = 'RESOLVED'`
   - `ticket.resolution_notes = 'تم تعويض العميل وإرسال طلب جديد'`
   - `ticket.save()`
   - Assert `ticket.resolved_at is not None`
   - Assert `ticket.resolution_notes == 'تم تعويض العميل وإرسال طلب جديد'`

4. **Agent Presence & Availability Querying**:
   - Create Agent 1 with `status='ready', is_active=True, employer=user`
   - Create Agent 2 with `status='AVAILABLE', is_active=True, employer=user`
   - Create Agent 3 with `status='busy', is_active=True, employer=user`
   - Create Agent 4 with `status='break', is_active=True, employer=user`
   - Create Agent 5 with `status='offline', is_active=True, employer=user`
   - Create Agent 6 with `status='ready', is_active=False, employer=user`
   - `available = get_available_agents(user.id)`
   - Assert `available.count() == 2`
   - Assert `set(available.values_list('id', flat=True)) == {agent_1.id, agent_2.id}`
   - Assert `agent_3.id not in available.values_list('id', flat=True)`
   - Assert `agent_6.id not in available.values_list('id', flat=True)`

5. **Operating Hours Verification**:
   - Case A: No schedule exists for user -> `is_open, text = is_operating_hours(user.id)` -> Assert `is_open is True`.
   - Case B: Schedule exists with `is_enabled=False` -> `is_open, text = is_operating_hours(user.id)` -> Assert `is_open is True`.
   - Case C: Schedule enabled, evaluate at simulated workday 11:00 AM (hours 09:00 - 17:00) -> `is_open, text = is_operating_hours(user.id, dt=workday_11am)` -> Assert `is_open is True`.
   - Case D: Schedule enabled, evaluate at simulated workday 11:00 PM (hours 09:00 - 17:00) -> `is_open, text = is_operating_hours(user.id, dt=workday_11pm)` -> Assert `is_open is False`.
   - Case E: Schedule enabled, evaluate on off-day (Friday `is_workday=False`) -> `is_open, text = is_operating_hours(user.id, dt=friday_noon)` -> Assert `is_open is False`.

---

## 7. Caveats

1. **Migration Execution Order**:
   - Running `python manage.py makemigrations crm` will generate `0012_crmsupportticket.py`.
   - In containerized environment (`voice_django`), ensure `docker exec voice_django python manage.py migrate crm` runs cleanly before test execution.
2. **Presence Status String Normalization**:
   - Existing codebase uses lowercase `'ready'` (`call_center/models.py`), while `ORIGINAL_REQUEST.md` references `'AVAILABLE'`.
   - `get_available_agents` handles both `'ready'` and `'AVAILABLE'` (case-insensitive lookup: `['ready', 'AVAILABLE', 'available', 'Ready']`).
3. **Foreign Key to EmployeeProfile**:
   - `assigned_employee` references `'call_center.EmployeeProfile'` using a string model reference to avoid circular imports between `crm` and `call_center`.
   - `on_delete=models.SET_NULL` with `null=True, blank=True` ensures deleting an employee profile does not purge historical tickets.

---

## 8. Conclusion

Milestone 1 data specifications are complete, authoritative, and verified against existing database models and requirements.
The implementer can directly execute:
1. Addition of `CRMSupportTicket` model to `django_app/crm/models.py`.
2. Creation and application of migration `0012_crmsupportticket.py`.
3. Implementation of `create_support_ticket`, `get_available_agents`, and `is_operating_hours` in `django_app/crm/services/whatsapp_dispatcher.py`.
4. Execution of verification test suite `django_app/test_m1_ticketing_foundation.py`.

---

## 9. Verification Method

Once implemented, independently verify Milestone 1 by executing:

```bash
docker exec voice_django python test_m1_ticketing_foundation.py
```

Expected output: All 5 test sections pass with 0 failures and exit code 0.
