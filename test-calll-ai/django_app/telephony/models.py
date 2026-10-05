from django.db import models
from django.contrib.auth.models import User
from common.crypto import encrypt_secret, decrypt_secret

class OutboundSIPTrunk(models.Model):
    TRANSPORT_CHOICES = [
        ('UDP', 'UDP'),
        ('TCP', 'TCP'),
        ('TLS', 'TLS'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='outbound_sip_trunks')
    name = models.CharField(max_length=100, default='حساب المزود الخارجي (Generic SIP Trunk)')
    sip_host = models.CharField(max_length=255, help_text='عنوان خادم المزود مثل sip.telnyx.com أو mytrunk.pstn.twilio.com')
    sip_port = models.PositiveIntegerField(default=5060)
    transport = models.CharField(max_length=10, choices=TRANSPORT_CHOICES, default='UDP')
    auth_username = models.CharField(max_length=128, blank=True, null=True, help_text='اسم المستخدم للمصادقة في المزود')
    auth_password = models.CharField(max_length=255, blank=True, null=True, help_text='كلمة المرور المشفرة للمزود')
    caller_id = models.CharField(max_length=64, blank=True, null=True, help_text='الرقم المعتمد الذي يظهر للمتصل به بصيغة E.164')
    livekit_outbound_trunk_id = models.CharField(max_length=128, blank=True, default='', help_text='معرف الجذع الصادر في LiveKit (ST_...)')
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'voice_assistant_outboundsiptrunk'
        ordering = ['-is_default', '-created_at']

    def set_auth_password(self, raw_password: str):
        """Encrypt and store plain password."""
        self.auth_password = encrypt_secret(raw_password) if raw_password else ""

    def get_auth_password(self) -> str:
        """Decrypt and return plain password for LiveKit connection."""
        return decrypt_secret(self.auth_password or "")

    def __str__(self):
        status = " [نشط]" if self.is_active else " [معطل]"
        default_str = " [افتراضي]" if self.is_default else ""
        return f"{self.name} ({self.sip_host}){default_str}{status}"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "sip_host": self.sip_host,
            "sip_port": self.sip_port,
            "transport": self.transport,
            "auth_username": self.auth_username or "",
            "has_password": bool(self.auth_password),
            "caller_id": self.caller_id or "",
            "livekit_outbound_trunk_id": self.livekit_outbound_trunk_id,
            "is_active": self.is_active,
            "is_default": self.is_default,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M"),
        }


class InboundPBXTrunk(models.Model):
    AUTH_MODE_CHOICES = [
        ('ip', 'IP Whitelisting (عنوان IP ثابت)'),
        ('credentials', 'SIP Credentials (اسم مستخدم وكلمة مرور)'),
    ]

    DESTINATION_CHOICES = [
        ('ai_assistant', 'المساعد الصوتي الذكي (Smart IVR)'),
        ('call_queue', 'طابور انتظار محدد (Call Queue)'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='inbound_pbx_trunks')
    name = models.CharField(max_length=100, default='سنترال الشركة (Issabel PBX)')
    auth_mode = models.CharField(max_length=20, choices=AUTH_MODE_CHOICES, default='ip')
    pbx_ip = models.CharField(max_length=255, blank=True, null=True, help_text='عنوان IP العام أو المحلي لسنترال Issabel')
    auth_username = models.CharField(max_length=128, blank=True, null=True, help_text='اسم المستخدم الذي يسجل به سنترال Issabel لدينا')
    auth_password = models.CharField(max_length=255, blank=True, null=True, help_text='كلمة المرور المشفرة لسنترال Issabel')
    inbound_numbers = models.CharField(max_length=255, blank=True, default='', help_text='أرقام الاستقبال/DIDs المسموحة مفصولة بفواصل (اختياري)')
    destination_type = models.CharField(max_length=32, choices=DESTINATION_CHOICES, default='ai_assistant')
    target_queue = models.ForeignKey('call_center.CallQueue', on_delete=models.SET_NULL, null=True, blank=True, related_name='pbx_trunks')
    target_profile = models.ForeignKey('agents.AgentProfile', on_delete=models.SET_NULL, null=True, blank=True, related_name='pbx_trunks')
    livekit_trunk_id = models.CharField(max_length=128, blank=True, default='', help_text='معرف الجذع الوارد في LiveKit')
    livekit_rule_id = models.CharField(max_length=128, blank=True, default='', help_text='معرف قاعدة التوجيه في LiveKit')
    enable_outbound = models.BooleanField(default=True, help_text='تمكين إجراء مكالمات صادرة عبر هذا السنترال')
    outbound_port = models.IntegerField(default=5060, help_text='منفذ SIP الصادر للسنترال')
    outbound_transport = models.CharField(max_length=10, default='UDP', choices=[('UDP', 'UDP'), ('TCP', 'TCP'), ('TLS', 'TLS')])
    livekit_outbound_trunk_id = models.CharField(max_length=128, blank=True, default='', help_text='معرف الجذع الصادر في LiveKit')
    is_default_outbound = models.BooleanField(default=False, help_text='تعيين كجذع صادر افتراضي')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'voice_assistant_inboundpbxtrunk'
        ordering = ['-created_at']

    def set_auth_password(self, raw_password: str):
        """Encrypt and store plain password for PBX trunk."""
        self.auth_password = encrypt_secret(raw_password) if raw_password else ""

    def get_auth_password(self) -> str:
        """Decrypt and return plain password for PBX connection."""
        return decrypt_secret(self.auth_password or "")

    def __str__(self):
        status = " [نشط]" if self.is_active else " [معطل]"
        outbound_info = " (ثنائي الاتجاه)" if self.enable_outbound else " (وارد فقط)"
        return f"{self.name} ({self.get_auth_mode_display()}){outbound_info}{status}"

    def generate_issabel_config(self, host_domain="app.localhost", sip_port=5060):
        trunk_name = f"livekit-ai-{self.id}"
        lines = [
            f"; ===========================================================",
            f"; 1. اعدادات الطرفية الصادرة (PEER Details) في Issabel",
            f"; ضع هذا النص في: PBX -> Trunks -> Add SIP Trunk -> PEER Details",
            f"; Trunk Name: {trunk_name}",
            f"; ===========================================================",
            f"[PEER Details]",
            f"host={host_domain}",
            f"port={sip_port}",
            f"type=peer",
            f"qualify=yes",
            f"disallow=all",
            f"allow=alaw,ulaw,opus",
            f"insecure=port,invite",
            f"context=from-internal",
            f"canreinvite=yes",
            f"promiscredir=yes",
        ]
        if self.auth_mode == 'credentials' and self.auth_username:
            lines.extend([
                f"username={self.auth_username}",
                f"secret={self.auth_password or ''}",
                f"fromuser={self.auth_username}",
            ])
        else:
            lines.append(f"; المصادقة: موثوق عبر الـ IP ({self.pbx_ip or 'Any'})")

        peer_text = "\n".join(lines)

        # USER Details (For incoming calls sent from LiveKit into Issabel)
        user_lines = [
            f"; ===========================================================",
            f"; 2. إعدادات استقبال مكالمات الـ AI (USER Details) في Issabel",
            f"; ضع هذا النص في قسم: USER Details / USER Context",
            f"; ===========================================================",
            f"[USER Details]",
            f"type=user",
            f"context=from-internal",
            f"insecure=port,invite",
            f"disallow=all",
            f"allow=alaw,ulaw,opus",
        ]
        if self.auth_mode == 'credentials' and self.auth_username:
            user_lines.extend([
                f"secret={self.auth_password or ''}",
                f"context=from-internal",
            ])
        else:
            user_lines.append(f"; يقبل المكالمات الصادرة من خادمنا ({host_domain})")

        user_text = "\n".join(user_lines)

        register_string = ""
        if self.auth_mode == 'credentials' and self.auth_username and self.auth_password:
            register_string = f"{self.auth_username}:{self.auth_password}@{host_domain}:{sip_port}/{self.auth_username}"

        return {
            "trunk_name": trunk_name,
            "peer_details": peer_text,
            "user_details": user_text,
            "register_string": register_string,
            "host": host_domain,
            "port": sip_port,
        }

    def to_dict(self, host_domain="app.localhost"):
        config = self.generate_issabel_config(host_domain)
        return {
            "id": self.id,
            "name": self.name,
            "auth_mode": self.auth_mode,
            "auth_mode_display": self.get_auth_mode_display(),
            "pbx_ip": self.pbx_ip or "",
            "auth_username": self.auth_username or "",
            "has_password": bool(self.auth_password),
            "inbound_numbers": self.inbound_numbers or "",
            "destination_type": self.destination_type,
            "destination_type_display": self.get_destination_type_display(),
            "target_queue_id": self.target_queue_id,
            "target_queue_name": self.target_queue.name if self.target_queue else "",
            "target_queue_code": self.target_queue.code if self.target_queue else "",
            "target_profile_id": self.target_profile_id,
            "target_profile_name": self.target_profile.name if self.target_profile else "",
            "livekit_trunk_id": self.livekit_trunk_id,
            "livekit_rule_id": self.livekit_rule_id,
            "enable_outbound": self.enable_outbound,
            "outbound_port": self.outbound_port,
            "outbound_transport": self.outbound_transport,
            "livekit_outbound_trunk_id": self.livekit_outbound_trunk_id,
            "is_default_outbound": self.is_default_outbound,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M"),
            "issabel_config": config,
        }


def get_default_business_days_config():
    return {
        "saturday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
        "sunday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
        "monday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
        "tuesday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
        "wednesday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
        "thursday": {"is_workday": True, "start_time": "09:00", "end_time": "17:00"},
        "friday": {"is_workday": False, "start_time": "09:00", "end_time": "17:00"},
    }


class BusinessHoursSchedule(models.Model):
    ACTION_CHOICES = [
        ('ai_message', 'نطق رسالة نصية بالذكاء الاصطناعي (AI Message)'),
        ('audio_file', 'تشغيل ملف صوتي مسجل مسبقاً (Audio File)'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='business_hours_schedule')
    is_enabled = models.BooleanField(default=False, verbose_name="تفعيل جدول مواعيد العمل")
    timezone = models.CharField(max_length=64, default="Africa/Cairo", verbose_name="المنطقة الزمنية")
    days_config = models.JSONField(default=get_default_business_days_config, verbose_name="جدول الأيام وساعات العمل")
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES, default='ai_message', verbose_name="إجراء خارج أوقات العمل")
    ai_message = models.TextField(
        blank=True,
        default="مرحباً بك، نتأسف لاتصالك خارج أوقات العمل الرسمية. نسعد بتواصلك معنا مجدداً خلال أوقات العمل الرسمية من التاسعة صباحاً وحتى الخامسة مساءً.",
        verbose_name="رسالة الذكاء الاصطناعي خارج أوقات العمل"
    )
    audio_file = models.FileField(upload_to='off_hours_audio/', blank=True, null=True, verbose_name="ملف صوتي خارج أوقات العمل")
    audio_file_url = models.URLField(max_length=500, blank=True, default='', verbose_name="رابط الملف الصوتي")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'voice_assistant_businesshoursschedule'
        verbose_name = "جدول مواعيد العمل"
        verbose_name_plural = "جداول مواعيد العمل"

    def __str__(self):
        status = " [مفعل]" if self.is_enabled else " [معطل]"
        return f"مواعيد عمل {self.user.username} ({self.timezone}){status}"

    def is_within_business_hours(self, dt=None) -> bool:
        """
        Check if the current moment (or provided datetime) is within active business hours.
        If schedule is disabled, returns True (always accessible).
        """
        if not self.is_enabled:
            return True

        from zoneinfo import ZoneInfo
        from datetime import datetime, time
        try:
            tz = ZoneInfo(self.timezone)
        except Exception:
            tz = ZoneInfo("UTC")

        now = dt or datetime.now(tz)
        day_key = now.strftime('%A').lower()  # saturday, sunday, monday, etc.

        cfg = self.days_config or get_default_business_days_config()
        day_info = cfg.get(day_key)
        if not day_info or not day_info.get("is_workday", False):
            return False

        start_str = day_info.get("start_time", "09:00")
        end_str = day_info.get("end_time", "17:00")

        try:
            sh, sm = map(int, start_str.split(":"))
            eh, em = map(int, end_str.split(":"))
            start_time = time(sh, sm)
            end_time = time(eh, em)
        except Exception:
            start_time = time(9, 0)
            end_time = time(17, 0)

        current_time = now.time()
        if start_time <= end_time:
            return start_time <= current_time <= end_time
        else:
            # Shift spans midnight e.g. 20:00 to 04:00
            return current_time >= start_time or current_time <= end_time

    def get_audio_url(self, request=None) -> str:
        """Return accessible URL for off-hours audio file."""
        if self.audio_file:
            try:
                url = self.audio_file.url
                if request and url.startswith("/"):
                    return request.build_absolute_uri(url)
                return url
            except Exception:
                pass
        return self.audio_file_url or ""

    def to_dict(self, request=None):
        return {
            "id": self.id,
            "is_enabled": self.is_enabled,
            "timezone": self.timezone,
            "days_config": self.days_config or get_default_business_days_config(),
            "action_type": self.action_type,
            "action_type_display": self.get_action_type_display(),
            "ai_message": self.ai_message or "",
            "audio_file": self.audio_file.url if self.audio_file else None,
            "audio_file_url": self.get_audio_url(request),
            "is_open_now": self.is_within_business_hours(),
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M") if self.updated_at else None,
        }
