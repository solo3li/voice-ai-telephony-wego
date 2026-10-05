from django.db import models
from django.contrib.auth.models import User

class CustomerMemory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='customer_memories')
    phone_number = models.CharField(max_length=32, db_index=True, default='web_dashboard')
    customer_name = models.CharField(max_length=120, blank=True, default='')
    permanent_profile = models.JSONField(default=dict, blank=True)
    last_interaction_summary = models.TextField(blank=True, default='')
    last_interaction_at = models.DateTimeField(null=True, blank=True)
    total_calls_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'voice_assistant_customermemory'
        ordering = ['-updated_at']
        unique_together = ('user', 'phone_number')

    def __str__(self):
        display = self.customer_name or self.phone_number
        return f"ذاكرة العميل: {display} ({self.user.username})"

    def to_dict(self):
        c_name = self.customer_name
        if not c_name and isinstance(self.permanent_profile, dict):
            c_name = self.permanent_profile.get("customer_name") or ""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "phone_number": self.phone_number,
            "customer_name": c_name,
            "permanent_profile": self.permanent_profile or {},
            "last_interaction_summary": self.last_interaction_summary or "",
            "last_interaction_at": self.last_interaction_at.strftime("%Y-%m-%d %H:%M") if self.last_interaction_at else None,
            "total_calls_count": self.total_calls_count,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M"),
        }

    def format_for_system_instruction(self) -> str:
        """Format the two-tier memory into a compact ~100-150 token block."""
        parts = []
        prof = self.permanent_profile or {}
        if prof:
            items = []
            name_val = self.customer_name or prof.get("customer_name")
            if name_val:
                items.append(f"اسم العميل: {name_val}")
            phone_val = self.phone_number if self.phone_number != 'web_dashboard' else prof.get("phone")
            if phone_val:
                items.append(f"الهاتف: {phone_val}")
            if prof.get("city") or prof.get("address"):
                items.append(f"العنوان/المدينة: {prof.get('city') or prof.get('address')}")
            if prof.get("preferences"):
                prefs = prof['preferences']
                if isinstance(prefs, list):
                    prefs = "، ".join(str(p) for p in prefs)
                items.append(f"الاهتمامات والتفضيلات: {prefs}")
            if prof.get("notes"):
                items.append(f"ملاحظات: {prof['notes']}")
            if items:
                parts.append("البيانات الدائمة للعميل:\n- " + "\n- ".join(items))

        if self.last_interaction_summary:
            time_str = self.last_interaction_at.strftime("%Y-%m-%d %H:%M") if self.last_interaction_at else "مكالمة سابقة"
            parts.append(f"الذاكرة اللحظية من آخر تواصل ({time_str}):\n{self.last_interaction_summary}")

        if not parts:
            return ""
        return "سياق وذاكرة العميل التراكمية (استخدمها بذكاء وعفوية للتذكر دون سردها للمستخدم كقائمة):\n" + "\n\n".join(parts)


class CallSession(models.Model):
    DIRECTION_CHOICES = [
        ('inbound', 'مكالمة واردة'),
        ('outbound_agent', 'صادرة (موظف)'),
        ('outbound_ai', 'صادرة (ذكاء اصطناعي)'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='call_sessions')
    room_name = models.CharField(max_length=120, db_index=True)
    direction = models.CharField(max_length=32, choices=DIRECTION_CHOICES, default='inbound')
    caller_phone = models.CharField(max_length=64, blank=True, default='')
    destination_phone = models.CharField(max_length=64, blank=True, default='')
    call_goal = models.TextField(blank=True, default='')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    billed_minutes = models.PositiveIntegerField(default=0, verbose_name="الدقائق المحتسبة (Ceiling)")
    cost = models.DecimalField(max_digits=10, decimal_places=4, default=0.0000, verbose_name="تكلفة المكالمة")
    transcript_text = models.TextField(blank=True, default='')
    summary = models.TextField(blank=True, default='')
    recording_url = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        db_table = 'voice_assistant_callsession'
        ordering = ['-started_at']

    def __str__(self):
        return f"جلسة مكالمة {self.room_name} ({self.get_direction_display()}) - {self.user.username}"

    @property
    def dialogue_turns(self):
        """Parse transcript text into structured dialogue turns."""
        if not self.transcript_text:
            return []
        turns = []
        for line in self.transcript_text.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            if ':' in line:
                speaker, _, text = line.partition(':')
                turns.append({"speaker": speaker.strip(), "text": text.strip()})
            elif ' - ' in line:
                speaker, _, text = line.partition(' - ')
                turns.append({"speaker": speaker.strip(), "text": text.strip()})
            else:
                turns.append({"speaker": "dialogue", "text": line})
        return turns

    def to_dict(self, request=None):
        rec_url = self.recording_url or ""
        if rec_url and request and not (rec_url.startswith('http://') or rec_url.startswith('https://')):
            try:
                rec_url = request.build_absolute_uri(rec_url)
            except Exception:
                pass
        return {
            "id": self.id,
            "room_name": self.room_name,
            "direction": self.direction,
            "direction_display": self.get_direction_display(),
            "caller_phone": self.caller_phone or "",
            "destination_phone": self.destination_phone or "",
            "call_goal": self.call_goal or "",
            "started_at": self.started_at.strftime("%Y-%m-%d %H:%M"),
            "ended_at": self.ended_at.strftime("%Y-%m-%d %H:%M") if self.ended_at else None,
            "duration_seconds": self.duration_seconds,
            "billed_minutes": self.billed_minutes,
            "cost": float(self.cost),
            "cost_formatted": f"{self.cost:.2f}",
            "summary": self.summary or "",
            "transcript_text": self.transcript_text or "",
            "recording_url": rec_url,
            "dialogue_turns": self.dialogue_turns,
        }


class UserCampaignLimit(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='campaign_limit')
    max_concurrent_calls = models.PositiveIntegerField(default=1, verbose_name="الحد الأقصى للمكالمات المتزامنة")
    is_auto_dialer_enabled = models.BooleanField(default=True, verbose_name="تمكين الاتصال التلقائي للحملات")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "حد الحملات المتزامنة للعميل"
        verbose_name_plural = "حدود الحملات المتزامنة للعملاء"

    def __str__(self):
        return f"حد التزامن: {self.user.username} ({self.max_concurrent_calls} مكالمة)"

    @classmethod
    def get_limit_for_user(cls, user) -> int:
        if not user or not user.is_authenticated:
            return 1
        limit_obj = cls.objects.filter(user=user).first()
        if limit_obj:
            return max(1, limit_obj.max_concurrent_calls)
        return 1


class OutboundCampaign(models.Model):
    STATUS_CHOICES = [
        ('draft', 'مسودة / جاهزة للاتصال'),
        ('running', 'قيد الاتصال الآلي'),
        ('paused', 'متوقف مؤقتاً'),
        ('completed', 'مكتملة'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='outbound_campaigns')
    name = models.CharField(max_length=200, verbose_name="اسم الحملة")
    agent_profile = models.ForeignKey('agents.AgentProfile', on_delete=models.SET_NULL, null=True, blank=True, related_name='campaigns')
    call_prompt = models.TextField(blank=True, default='', verbose_name="سيناريو وهدف المكالمة المخصص (Prompt)")
    max_retries = models.PositiveIntegerField(default=1, verbose_name="الحد الأقصى لمحاولات إعادة الاتصال")
    retry_delay_minutes = models.PositiveIntegerField(default=15, verbose_name="المدة بالدقائق قبل إعادة المحاولة")
    gateway_type = models.CharField(max_length=32, default='auto')
    gateway_id = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='draft')

    total_contacts = models.PositiveIntegerField(default=0)
    completed_contacts = models.PositiveIntegerField(default=0)
    answered_contacts = models.PositiveIntegerField(default=0)
    hot_leads_count = models.PositiveIntegerField(default=0)
    warm_leads_count = models.PositiveIntegerField(default=0)
    cold_leads_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "حملة اتصالات صادرة"
        verbose_name_plural = "حملات الاتصالات الصادرة"

    def __str__(self):
        return f"حملة: {self.name} ({self.get_status_display()}) - {self.user.username}"

    def update_metrics(self):
        self.total_contacts = self.contacts.count()
        self.completed_contacts = self.contacts.filter(call_status__in=['answered', 'busy', 'no_answer', 'failed']).count()
        self.answered_contacts = self.contacts.filter(call_status='answered').count()
        self.hot_leads_count = self.contacts.filter(interest_level='hot').count()
        self.warm_leads_count = self.contacts.filter(interest_level='warm').count()
        self.cold_leads_count = self.contacts.filter(interest_level='cold').count()
        if self.total_contacts > 0 and self.completed_contacts >= self.total_contacts and self.status == 'running':
            self.status = 'completed'
        self.save(update_fields=[
            'total_contacts', 'completed_contacts', 'answered_contacts',
            'hot_leads_count', 'warm_leads_count', 'cold_leads_count', 'status', 'updated_at'
        ])

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "agent_profile_id": self.agent_profile_id,
            "agent_profile_name": self.agent_profile.name if self.agent_profile else "المساعد الافتراضي",
            "call_prompt": self.call_prompt or "",
            "max_retries": self.max_retries,
            "retry_delay_minutes": self.retry_delay_minutes,
            "gateway_type": self.gateway_type,
            "gateway_id": self.gateway_id,
            "status": self.status,
            "status_display": self.get_status_display(),
            "total_contacts": self.total_contacts,
            "completed_contacts": self.completed_contacts,
            "answered_contacts": self.answered_contacts,
            "hot_leads_count": self.hot_leads_count,
            "warm_leads_count": self.warm_leads_count,
            "cold_leads_count": self.cold_leads_count,
            "progress_percent": round((self.completed_contacts / self.total_contacts * 100), 1) if self.total_contacts > 0 else 0,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M"),
        }


class CampaignContact(models.Model):
    CALL_STATUS_CHOICES = [
        ('pending', 'جديد - في الانتظار'),
        ('in_progress', 'جارِ الاتصال به الآن'),
        ('answered', 'تم الرد والتواصل'),
        ('busy', 'مشغول'),
        ('no_answer', 'لم يرد'),
        ('failed', 'فشل الاتصال / غير متاح'),
    ]

    INTEREST_CHOICES = [
        ('uncontacted', 'لم يتحدد بعد'),
        ('hot', '🔥 مهتم جداً / جاهز للمرحلة التالية'),
        ('warm', '🟡 مهتم / يحتاج متابعة'),
        ('cold', '❄️ غير مهتم / تم الرفض'),
        ('callback', '⏰ طلب اتصال لاحقاً'),
        ('unreached', '❌ تعذر الوصول إليه'),
    ]

    campaign = models.ForeignKey(OutboundCampaign, on_delete=models.CASCADE, related_name='contacts')
    phone_number = models.CharField(max_length=32, db_index=True)
    customer_name = models.CharField(max_length=150, blank=True, default='')
    attributes = models.JSONField(default=dict, blank=True, help_text="بيانات العميل الإضافية من الملف")
    call_status = models.CharField(max_length=32, choices=CALL_STATUS_CHOICES, default='pending', db_index=True)
    interest_level = models.CharField(max_length=32, choices=INTEREST_CHOICES, default='uncontacted', db_index=True)
    call_summary = models.TextField(blank=True, default='')
    extracted_data = models.JSONField(default=dict, blank=True, help_text="البيانات المستخرجة بالذكاء الاصطناعي")
    retries_count = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    call_session = models.ForeignKey(CallSession, null=True, blank=True, on_delete=models.SET_NULL, related_name='campaign_contacts')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']
        verbose_name = "جهة اتصال حملة"
        verbose_name_plural = "جهات اتصال الحملات"

    def __str__(self):
        display = self.customer_name or self.phone_number
        return f"{display} ({self.get_call_status_display()}) - {self.campaign.name}"

    def to_dict(self):
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "phone_number": self.phone_number,
            "customer_name": self.customer_name or "",
            "attributes": self.attributes or {},
            "call_status": self.call_status,
            "call_status_display": self.get_call_status_display(),
            "interest_level": self.interest_level,
            "interest_level_display": self.get_interest_level_display(),
            "call_summary": self.call_summary or "",
            "extracted_data": self.extracted_data or {},
            "retries_count": self.retries_count,
            "last_attempt_at": self.last_attempt_at.strftime("%Y-%m-%d %H:%M") if self.last_attempt_at else None,
            "duration_seconds": self.duration_seconds,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M"),
        }



