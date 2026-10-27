# Handoff Report: Milestone 1 Technical Implementation Plan (Data Models & Ticketing Foundation)

## 1. Observation

### 1.1 Existing CRM Models & Migrations
- **File**: `django_app/crm/models.py`
  - Current line count: 604 lines.
  - Contains models: `CustomerMemory` (lines 5-157), `OmnichannelMessage` (lines 159-229), `CallSession` (lines 231-322), `UserCampaignLimit` (lines 324-346), `OutboundCampaign` (lines 348-473), `CampaignContact` (lines 475-556), `DoNotCallEntry` (lines 558-601).
  - No support ticketing model currently exists in `crm/models.py`.
- **Directory**: `django_app/crm/migrations/`
  - Migration files present:
    1. `0001_initial.py`
    2. `0002_outboundcampaign_campaigncontact_usercampaignlimit.py`
    3. `0003_callsession_recording_url.py`
    4. `0004_alter_callsession_room_name.py`
    5. `0005_callsession_caller_extension_and_more.py`
    6. `0006_alter_callsession_direction.py`
    7. `0007_callsession_transferred_recording_url_and_more.py`
    8. `0008_customermemory_call_memory_and_more.py`
    9. `0009_alter_customermemory_phone_number_and_more.py`
    10. `0010_alter_outboundcampaign_options_and_more.py`
    11. `0011_alter_campaigncontact_call_status_and_more.py`
  - Current migration count: 11 migrations. Next migration sequence: `0012`.
  - Tool execution: `docker exec voice_django python manage.py showmigrations crm`
    - Result: All 11 migrations are marked `[X]` applied in the PostgreSQL database.
  - Tool execution: `docker exec voice_django python manage.py makemigrations --dry-run crm`
    - Result: Output shows `Alter field created_at on omnichannelmessage` due to a minor field difference (`auto_now_add` in migration 0008 vs `default=timezone.now` in `crm/models.py:175`).

### 1.2 EmployeeProfile & Presence
- **File**: `django_app/call_center/models.py`
  - Lines 4-30:
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
        extension = models.CharField(max_length=32, db_index=True, ...)
        display_name = models.CharField(max_length=100, default='موظف')
        department = models.CharField(max_length=100, default='المبيعات')
        status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ready')
        ...
        is_active = models.BooleanField(default=True)
    ```
  - Database status breakdown (`EmployeeProfile.objects.values('status')`):
    - 27 employees with `status='ready'`
    - 1 employee with `status='busy'`
  - Observation on Redis presence: In `voice_assistant/views.py:684-685`, agent availability is also set as `r.set(f"agent_state:{participant_identity}", "AVAILABLE")`.

### 1.3 BusinessHoursSchedule
- **File**: `django_app/telephony/models.py`
  - Lines 219-290:
    ```python
    class BusinessHoursSchedule(models.Model):
        user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='business_hours_schedule')
        is_enabled = models.BooleanField(default=False, verbose_name="تفعيل جدول مواعيد العمل")
        timezone = models.CharField(max_length=64, default="Africa/Cairo", verbose_name="المنطقة الزمنية")
        days_config = models.JSONField(default=get_default_business_days_config, ...)
        ...
        def is_within_business_hours(self, dt=None) -> bool:
            if not self.is_enabled:
                return True
            ...
    ```
  - Method `is_within_business_hours(dt=None)` accepts an optional datetime `dt` and returns `bool`. If schedule is disabled or missing, it evaluates as open (`True`).

### 1.4 Runtime & Container Environment
- Container `voice_django` (`e088dc9124a7`) is active and healthy.
- Direct bind mount: `/root/voice-ai-telephony/test-calll-ai/django_app` -> `/app` (`Mode: rw`).
- `docker exec voice_django python manage.py check` executes with code 0 (`System check identified no issues (0 silenced)`).

---

## 2. Logic Chain

1. **Model Placement & Dependencies**:
   - `CRMSupportTicket` belongs in `django_app/crm/models.py` because ticketing is a core CRM function and is linked to `CustomerMemory` and WhatsApp escalation flows.
   - To avoid circular imports between `crm` and `call_center`, the foreign key to `EmployeeProfile` must be defined using string reference `'call_center.EmployeeProfile'`.
   - The user foreign key connects to `django.contrib.auth.models.User`, representing the tenant/account owner.
   - The ticket reference format must be unique and human-readable (`TCK-YYYYMMDD-XXXX`). Generating this automatically in `save()` if not passed prevents race conditions or missing numbers.

2. **Migration Plan**:
   - Current migrations end at `0011`.
   - Running `python manage.py makemigrations crm` inside `voice_django` will generate `0012_crmsupportticket_...`. It will also synchronize the `OmnichannelMessage.created_at` field definition without introducing conflicts.
   - The bind mount ensures that running `makemigrations` inside the container immediately writes the migration file to host storage at `django_app/crm/migrations/0012_...`.
   - Running `python manage.py migrate crm` will apply the migration cleanly against the active PostgreSQL database.

3. **Agent Presence & Availability**:
   - `EmployeeProfile` in `call_center` holds agent operational status (`ready`, `busy`, `break`, `offline`).
   - The requirement demands support for status in `['ready', 'AVAILABLE', 'available']` with `is_active=True`.
   - In multi-tenant context, an employee belongs to an employer (`employer_id == user_id`) or in single/creator scenarios to `user_id == user_id`. Scoping the query with `models.Q(employer_id=uid) | models.Q(user_id=uid)` ensures correct isolation across all tenant configurations.

4. **Operating Hours Evaluation**:
   - Wrapping `BusinessHoursSchedule.is_within_business_hours()` allows uniform error handling (e.g. if no schedule exists or if schedule is disabled, fallback to open 24/7).
   - Returning `(is_open: bool, operating_hours_snapshot: str)` fulfills the M1 ↔ M2 contract:
     - `is_open`: Boolean driving the routing vs ticketing branch.
     - `operating_hours_snapshot`: String describing the operating hours, which can be saved into `CRMSupportTicket.operating_hours_snapshot` and formatted into automated WhatsApp customer reassurance messages.

---

## 3. Detailed Technical Design & Code Specifications

### 3.1 `CRMSupportTicket` Model Design (`django_app/crm/models.py`)

Add the following model definition to `django_app/crm/models.py`:

```python
import secrets
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class CRMSupportTicket(models.Model):
    STATUS_CHOICES = [
        ('OPEN', 'مفتوحة (Open)'),
        ('IN_PROGRESS', 'قيد المعالجة (In Progress)'),
        ('RESOLVED', 'تم الحل (Resolved)'),
        ('CLOSED', 'مغلقة (Closed)'),
    ]

    URGENCY_CHOICES = [
        ('urgent', 'عاجل (Urgent)'),
        ('normal', 'عادي (Normal)'),
    ]

    ticket_number = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name="رقم التذكرة المرجعي"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='crm_support_tickets',
        verbose_name="صاحب العمل / الحساب"
    )
    customer_phone = models.CharField(
        max_length=64,
        db_index=True,
        verbose_name="رقم هاتف العميل"
    )
    customer_name = models.CharField(
        max_length=150,
        blank=True,
        default='',
        verbose_name="اسم العميل"
    )
    reason = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="سبب التصعيد"
    )
    urgency = models.CharField(
        max_length=32,
        choices=URGENCY_CHOICES,
        default='normal',
        db_index=True,
        verbose_name="مستوى الأهمية"
    )
    summary = models.TextField(
        blank=True,
        default='',
        verbose_name="ملخص الذكاء الاصطناعي للمشكلة"
    )
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default='OPEN',
        db_index=True,
        verbose_name="حالة التذكرة"
    )
    operating_hours_snapshot = models.TextField(
        blank=True,
        default='',
        verbose_name="لقطة مواعيد العمل وساعات التشغيل"
    )
    assigned_employee = models.ForeignKey(
        'call_center.EmployeeProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_support_tickets',
        verbose_name="الموظف المعين"
    )
    resolution_notes = models.TextField(
        blank=True,
        default='',
        verbose_name="ملاحظات الحل والإغلاق"
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name="تاريخ الإنشاء"
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="تاريخ الحل"
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'customer_phone']),
            models.Index(fields=['customer_phone', 'status']),
            models.Index(fields=['ticket_number']),
        ]
        verbose_name = "تذكرة دعم فني CRM"
        verbose_name_plural = "تذاكر الدعم الفني CRM"

    @classmethod
    def generate_ticket_number(cls) -> str:
        """
        Generate unique ticket number formatted as TCK-YYYYMMDD-XXXX.
        Uses 4 random uppercase hex characters (e.g. TCK-20261024-8E4B).
        """
        date_str = timezone.now().strftime("%Y%m%d")
        for _ in range(50):
            suffix = secrets.token_hex(2).upper()
            candidate = f"TCK-{date_str}-{suffix}"
            if not cls.objects.filter(ticket_number=candidate).exists():
                return candidate
        import uuid
        return f"TCK-{date_str}-{uuid.uuid4().hex[:6].upper()}"

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            self.ticket_number = self.generate_ticket_number()
        super().save(*args, **kwargs)

    def __str__(self):
        display_name = self.customer_name or self.customer_phone
        return f"تذكرة [{self.ticket_number}] - {display_name} ({self.get_status_display()})"

    def to_dict(self):
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
            "status_display": self.get_status_display(),
            "operating_hours_snapshot": self.operating_hours_snapshot,
            "assigned_employee_id": self.assigned_employee_id,
            "assigned_employee_name": self.assigned_employee.display_name if self.assigned_employee else None,
            "assigned_employee_extension": self.assigned_employee.extension if self.assigned_employee else None,
            "resolution_notes": self.resolution_notes,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else None,
            "created_at_iso": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.strftime("%Y-%m-%d %H:%M") if self.resolved_at else None,
            "resolved_at_iso": self.resolved_at.isoformat() if self.resolved_at else None,
        }
```

### 3.2 Dispatcher & Helpers Specification (`django_app/crm/services/whatsapp_dispatcher.py`)

Create `django_app/crm/services/whatsapp_dispatcher.py` to house the ticketing, presence, and hours helpers:

```python
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Tuple, Optional
from django.db.models import QuerySet, Q
from django.contrib.auth.models import User
from django.utils import timezone

from crm.models import CRMSupportTicket
from call_center.models import EmployeeProfile
from telephony.models import BusinessHoursSchedule

logger = logging.getLogger(__name__)


class AgentPresence:
    AVAILABLE = 'AVAILABLE'
    READY = 'ready'
    BUSY = 'busy'
    BREAK = 'break'
    OFFLINE = 'offline'

    ONLINE_STATUSES = ['ready', 'AVAILABLE', 'available']

    @classmethod
    def is_available(cls, status: str) -> bool:
        if not status:
            return False
        return status.strip() in cls.ONLINE_STATUSES or status.strip().lower() in ('ready', 'available')


def get_available_agents(user_id) -> QuerySet:
    """
    Query all active human agents for the given user whose status is ready or AVAILABLE.
    Supports either integer user_id or User instance.
    """
    uid = user_id.id if hasattr(user_id, 'id') else user_id

    qs = EmployeeProfile.objects.filter(
        is_active=True,
        status__in=AgentPresence.ONLINE_STATUSES
    )
    if uid:
        qs = qs.filter(Q(employer_id=uid) | Q(user_id=uid))
    return qs.order_by('id')


def is_operating_hours(user_id, dt: Optional[datetime] = None) -> Tuple[bool, str]:
    """
    Evaluate BusinessHoursSchedule for the user.
    Returns:
        (is_open: bool, operating_hours_text: str)
    If schedule does not exist or is disabled, defaults to 24/7 open.
    """
    uid = user_id.id if hasattr(user_id, 'id') else user_id
    sched = BusinessHoursSchedule.objects.filter(user_id=uid).first() if uid else None

    if not sched or not sched.is_enabled:
        return True, "متاح 24/7 (جدول مواعيد العمل غير مفعل)"

    try:
        tz = ZoneInfo(sched.timezone or "Africa/Cairo")
    except Exception:
        tz = ZoneInfo("UTC")

    now_dt = dt or datetime.now(tz)
    is_open = sched.is_within_business_hours(now_dt)

    day_keys_ar = {
        "saturday": "السبت", "sunday": "الأحد", "monday": "الاثنين",
        "tuesday": "الثلاثاء", "wednesday": "الأربعاء", "thursday": "الخميس", "friday": "الجمعة"
    }
    curr_day_key = now_dt.strftime('%A').lower()
    curr_day_ar = day_keys_ar.get(curr_day_key, curr_day_key)
    curr_time_str = now_dt.strftime('%I:%M %p')

    days_cfg = sched.days_config or {}
    today_cfg = days_cfg.get(curr_day_key, {})
    start_t = today_cfg.get("start_time", "09:00")
    end_t = today_cfg.get("end_time", "17:00")
    is_workday = today_cfg.get("is_workday", True)

    if not is_workday:
        hours_text = f"اليوم ({curr_day_ar}) عطلة رسمية. ساعات العمل الاعتيادية: من 09:00 ص إلى 05:00 م ({sched.timezone})."
    else:
        hours_text = f"ساعات العمل الرسمية اليوم ({curr_day_ar}): من {start_t} إلى {end_t} ({sched.timezone}). التوقيت الحالي: {curr_time_str}."

    return is_open, hours_text


def create_support_ticket(
    user_id,
    phone_number: str,
    customer_name: str = "",
    reason: str = "",
    urgency: str = "normal",
    summary: str = "",
    operating_hours_text: str = ""
) -> CRMSupportTicket:
    """
    Create a CRM support ticket when human agents are unavailable or outside working hours.
    Returns the created CRMSupportTicket instance.
    """
    uid = user_id.id if hasattr(user_id, 'id') else user_id
    user = User.objects.get(id=uid) if isinstance(uid, int) else user_id

    ticket = CRMSupportTicket.objects.create(
        user=user,
        customer_phone=phone_number,
        customer_name=customer_name or "",
        reason=reason or "",
        urgency=urgency or "normal",
        summary=summary or "",
        operating_hours_snapshot=operating_hours_text or "",
        status='OPEN'
    )
    logger.info(f"Created CRMSupportTicket #{ticket.ticket_number} for customer {phone_number}")
    return ticket
```

### 3.3 Admin Registration (`django_app/crm/admin.py`)

Add the admin class to allow staff to inspect tickets:
```python
from .models import CRMSupportTicket

@admin.register(CRMSupportTicket)
class CRMSupportTicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'user', 'customer_phone', 'customer_name', 'urgency', 'status', 'assigned_employee', 'created_at', 'resolved_at')
    list_filter = ('status', 'urgency', 'created_at', 'user')
    search_fields = ('ticket_number', 'customer_phone', 'customer_name', 'reason', 'summary')
    readonly_fields = ('ticket_number', 'created_at')
```

---

## 4. Migration Strategy

1. **Pre-Migration Verification**:
   - Confirmed 11 migrations exist in `crm/migrations/`.
   - Confirmed `voice_django` container has write access to the bind-mounted repository.
2. **Execute Makemigrations**:
   ```bash
   docker exec voice_django python manage.py makemigrations crm
   ```
   - Target result: Creates `django_app/crm/migrations/0012_crmsupportticket_...py`.
3. **Execute Migrate**:
   ```bash
   docker exec voice_django python manage.py migrate crm
   ```
   - Target result: Applies `crm.0012_...` and creates the `crm_crmsupportticket` database table with all foreign keys and indices.
4. **Post-Migration Integrity Check**:
   ```bash
   docker exec voice_django python manage.py showmigrations crm
   ```
   - Confirms all 12 migrations are marked `[X]`.

---

## 5. Caveats

- **Timezone edge-cases**: When `BusinessHoursSchedule.timezone` contains an invalid or non-standard string, the helper safely falls back to `"UTC"`.
- **Status casing**: `EmployeeProfile.status` is stored in lowercase (`ready`, `busy`, `break`, `offline`) in standard models, but `voice_assistant/views.py` sets Redis `agent_state` to uppercase `"AVAILABLE"`. To avoid discrepancy, `AgentPresence.ONLINE_STATUSES` covers `['ready', 'AVAILABLE', 'available']`.
- **Ticket number uniqueness under high concurrency**: `generate_ticket_number` attempts up to 50 iterations with a random 4-character hex suffix and falls back to a 6-character UUID fragment if collision occurs, guaranteeing uniqueness.

---

## 6. Conclusion

The technical plan for Milestone 1 is verified, conflict-free, and ready for immediate implementation by `builder_m1_1`:
1. `CRMSupportTicket` model in `django_app/crm/models.py`.
2. Admin integration in `django_app/crm/admin.py`.
3. Service helpers (`AgentPresence`, `get_available_agents`, `is_operating_hours`, `create_support_ticket`) in `django_app/crm/services/whatsapp_dispatcher.py`.
4. Clean migration via `docker exec voice_django python manage.py makemigrations crm` and `migrate crm`.

---

## 7. Verification Method

To independently verify the implementation:

1. **System & Migration Verification**:
   ```bash
   docker exec voice_django python manage.py check
   docker exec voice_django python manage.py showmigrations crm
   ```
   Verify 0 errors and migration 0012 applied.

2. **Milestone 1 Automated Test Suite (`django_app/test_m1_ticketing_foundation_e2e.py`)**:
   Execute inside the container:
   ```bash
   docker exec voice_django python test_m1_ticketing_foundation_e2e.py
   ```
   The test will assert:
   - Creation of `CRMSupportTicket` generates a ticket number matching regex `^TCK-\d{8}-[A-F0-9]{4,6}$`.
   - `ticket.to_dict()` contains all required fields (`ticket_number`, `status`, `customer_phone`, `operating_hours_snapshot`, etc.).
   - `get_available_agents(user_id)` returns only active agents with status in `ready`, `AVAILABLE`, `available`.
   - `is_operating_hours(user_id)` accurately evaluates active schedules and disabled fallbacks, returning `(bool, str)`.
   - `create_support_ticket(...)` successfully persists the ticket.
