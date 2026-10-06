from django.db import models
from django.contrib.auth.models import User

class EmployeeProfile(models.Model):
    STATUS_CHOICES = [
        ('ready', 'متاح (Ready)'),
        ('break', 'استراحة (Break)'),
        ('busy', 'مشغول (Busy)'),
        ('offline', 'غير متصل (Offline)'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')
    employer = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='managed_employees')
    extension = models.CharField(max_length=32, db_index=True, help_text='رقم التحويلة الداخلية مثل 101 أو 102')
    display_name = models.CharField(max_length=100, default='موظف')
    department = models.CharField(max_length=100, default='المبيعات')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ready')
    avatar_url = models.CharField(max_length=500, blank=True, default='')
    push_token = models.CharField(max_length=255, blank=True, default='', verbose_name="Expo Push Token", help_text="رمز إشعارات الدفع المباشر لجهاز الموظف")
    wazo_user_uuid = models.CharField(max_length=128, blank=True, default='', help_text="معرف المستخدم في سنترال Wazo")
    wazo_line_id = models.CharField(max_length=128, blank=True, default='', help_text="معرف الخط في سنترال Wazo")
    sip_username = models.CharField(max_length=128, blank=True, default='', help_text="اسم مستخدم الـ SIP للهاتف المكتبي أو التطبيق")
    sip_password = models.CharField(max_length=128, blank=True, default='', help_text="كلمة مرور الـ SIP")
    sip_host = models.CharField(max_length=128, blank=True, default='', help_text="عنوان سيرفر الـ SIP")
    sip_port = models.PositiveIntegerField(default=5070, help_text="منفذ سنترال Wazo")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'voice_assistant_employeeprofile'
        ordering = ['extension']
        unique_together = ('employer', 'extension')

    @property
    def name(self):
        return self.display_name

    def __str__(self):
        return f"{self.display_name} (تحويلة: {self.extension}) - {self.get_status_display()}"

    @property
    def is_owner(self) -> bool:
        if self.user.is_superuser:
            return True
        if self.employer_id and self.employer_id == self.user_id:
            return True
        try:
            if self.user.managed_employees.exists() or self.user.agent_profiles.exists():
                return True
        except Exception:
            pass
        return False

    def to_dict(self):
        from django.conf import settings
        effective_host = self.sip_host
        if not effective_host or effective_host in ('asterisk', '127.0.0.1', 'localhost', '169.58.32.179'):
            effective_host = getattr(settings, 'SIP_DOMAIN', f"sip.{getattr(settings, 'EXTERNAL_IP', '169.58.32.179')}.nip.io")

        return {
            "id": self.id,
            "user_id": self.user_id,
            "employer_id": self.employer_id,
            "username": self.user.username,
            "extension": self.extension,
            "display_name": self.display_name,
            "department": self.department,
            "status": self.status,
            "status_display": self.get_status_display(),
            "avatar_url": self.avatar_url or f"https://api.dicebear.com/7.x/bottts/png?seed={self.extension}",
            "push_token": self.push_token,
            "wazo_user_uuid": self.wazo_user_uuid,
            "wazo_line_id": self.wazo_line_id,
            "sip_username": self.sip_username or f"emp{self.extension}",
            "sip_password": self.sip_password,
            "sip_host": effective_host,
            "sip_port": self.sip_port,
            "sip_credentials": {
                "server": f"{effective_host}:{self.sip_port}",
                "host": effective_host,
                "domain": effective_host,
                "port": self.sip_port,
                "username": self.sip_username or f"emp{self.extension}",
                "password": self.sip_password or "******",
                "extension": self.extension
            },
            "is_active": self.is_active,
            "is_owner": self.is_owner,
        }


class CallQueue(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='call_queues')
    name = models.CharField(max_length=100, default='طابور المبيعات')
    code = models.CharField(max_length=32, help_text='كود الطابور للاتصال والتحويل مثل 200 أو 300')
    description = models.TextField(blank=True, default='', help_text='وصف واختصاصات الطابور وتوجيهات الذكاء الاصطناعي للتحويل')
    wazo_queue_id = models.CharField(max_length=128, blank=True, default='', help_text='معرف الطابور في سنترال Wazo')
    strategy = models.CharField(max_length=32, default='round_robin', choices=[
        ('round_robin', 'رنين بالتناوب (Round-Robin)'),
        ('ring_all', 'رنين جماعي متزامن (Ring-All)')
    ])
    ring_timeout_seconds = models.PositiveIntegerField(default=15, help_text='مدة رنين الموظف قبل الانتقال للتالي')
    total_timeout_seconds = models.PositiveIntegerField(default=60, help_text='أقصى مدة انتظار للعميل قبل التحويل للذكاء الاصطناعي')
    hold_music = models.FileField(upload_to='hold_music/', null=True, blank=True, help_text='ملف صوتي لموسيقى الانتظار')
    fallback_action = models.CharField(max_length=32, default='ai_assistant', choices=[
        ('ai_assistant', 'مساعد الذكاء الاصطناعي (Gemini Live)'),
        ('hangup', 'إنهاء المكالمة')
    ])
    livekit_trunk_id = models.CharField(max_length=128, blank=True)
    livekit_rule_id = models.CharField(max_length=128, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'voice_assistant_callqueue'
        ordering = ['code']
        unique_together = ('user', 'code')

    def __str__(self):
        return f"{self.name} (كود: {self.code})"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "wazo_queue_id": self.wazo_queue_id,
            "strategy": self.strategy,
            "ring_timeout_seconds": self.ring_timeout_seconds,
            "total_timeout_seconds": self.total_timeout_seconds,
            "hold_music_url": self.hold_music.url if self.hold_music else None,
            "fallback_action": self.fallback_action,
            "is_active": self.is_active,
            "members": [m.to_dict() for m in self.memberships.filter(is_active=True).select_related('employee')],
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M"),
        }


class QueueMembership(models.Model):
    queue = models.ForeignKey(CallQueue, on_delete=models.CASCADE, related_name='memberships')
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name='queue_memberships')
    order = models.PositiveIntegerField(default=0, help_text='ترتيب أولوية الموظف في التناوب')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'voice_assistant_queuemembership'
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.employee.display_name} في {self.queue.name}"

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "name": self.employee.display_name,
            "extension": self.employee.extension,
            "department": self.employee.department,
            "status": self.employee.status,
            "order": self.order,
            "is_active": self.is_active,
        }


class EmployeeCallLog(models.Model):
    """Per-employee call history record. Each party in a call gets their own log entry."""

    CALL_TYPE_CHOICES = [
        ('inbound',   'مكالمة واردة'),
        ('outbound',  'مكالمة صادرة'),
        ('missed',    'مكالمة فائتة'),
        ('transfer',  'مكالمة محولة'),
    ]

    employee       = models.ForeignKey(
        EmployeeProfile, on_delete=models.CASCADE,
        related_name='call_logs', db_index=True
    )
    other_party    = models.CharField(max_length=200, default='', help_text='اسم الطرف الثاني')
    extension      = models.CharField(max_length=32,  default='', help_text='تحويلة أو كود الطابور')
    room_name      = models.CharField(max_length=200, default='', db_index=True, help_text='اسم الغرفة للربط عند الإنهاء')
    call_type      = models.CharField(max_length=20, choices=CALL_TYPE_CHOICES, default='outbound')
    started_at     = models.DateTimeField(auto_now_add=True)
    ended_at       = models.DateTimeField(null=True, blank=True)
    duration_secs  = models.PositiveIntegerField(default=0)
    recording_url  = models.CharField(max_length=500, blank=True, null=True, default='', help_text='رابط ملف التسجيل الصوتي MP3')

    class Meta:
        db_table = 'call_center_employeecalllog'
        ordering = ['-started_at']

    def __str__(self):
        return f"[{self.call_type}] {self.employee.display_name} ↔ {self.other_party} ({self.duration_secs}s)"

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "other_party": self.other_party,
            "extension": self.extension,
            "room_name": self.room_name,
            "call_type": self.call_type,
            "started_at": self.started_at.strftime("%Y-%m-%d %H:%M:%S"),
            "ended_at": self.ended_at.strftime("%Y-%m-%d %H:%M:%S") if self.ended_at else None,
            "duration_secs": self.duration_secs,
            "recording_url": self.recording_url,
        }


