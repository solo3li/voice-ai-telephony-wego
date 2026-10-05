import secrets
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User


class PartnerProfile(models.Model):
    STATUS_CHOICES = [
        ('pending', 'قيد المراجعة (Pending)'),
        ('approved', 'شريك معتمد (Approved)'),
        ('rejected', 'مرفوض (Rejected)'),
        ('suspended', 'موقوف مؤقتاً (Suspended)'),
    ]

    CURRENCY_CHOICES = [
        ('USD', 'US Dollar ($)'),
        ('EGP', 'Egyptian Pound (ج.م)'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='partner_profile', verbose_name="حساب الشريك")
    company_name = models.CharField(max_length=255, verbose_name="اسم الشركة / الساس")
    website = models.URLField(blank=True, default='', verbose_name="موقع الساس أو الخدمة")
    description = models.TextField(blank=True, default='', verbose_name="وصف النشاط وحجم الاستخدام المتوقع")
    partner_code = models.CharField(max_length=32, unique=True, db_index=True, verbose_name="كود الشريك")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True, verbose_name="حالة الشريك")

    # Custom Wholesale Pricing for this partner
    custom_rate_per_minute = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0.0300'),
        verbose_name="سعر الدقيقة المخصص",
        help_text="السعر المخفض المخصوم من محفظة الشريك لكل دقيقة محسوبة لعملائه"
    )
    currency = models.CharField(max_length=8, choices=CURRENCY_CHOICES, default='USD', verbose_name="العملة")

    # Master Partner API Key
    api_key = models.CharField(max_length=80, unique=True, db_index=True, blank=True, verbose_name="مفتاح الـ API الرئيسي")

    # Webhook config for real-time dispatch
    webhook_url = models.URLField(max_length=500, blank=True, default='', verbose_name="رابط الـ Webhook الخاص بساس الشريك")
    webhook_secret = models.CharField(max_length=64, blank=True, default='', verbose_name="مفتاح توقيع الـ Webhook (Secret)")

    # Inherited MCP server for clients
    shared_mcp_server = models.ForeignKey(
        'agents.UserMCPServer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='partner_shared_profiles',
        verbose_name="خادم MCP الافتراضي لعملاء الشريك"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ التقديم")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")

    class Meta:
        verbose_name = "ملف الشريك والـ SaaS"
        verbose_name_plural = "شركاء الـ SaaS (Partner Profiles)"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.company_name} ({self.partner_code}) - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if not self.partner_code:
            self.partner_code = f"PRT-{secrets.token_hex(4).upper()}"
        if not self.api_key:
            self.api_key = f"sk_live_prt_{secrets.token_urlsafe(32)}"
        if not self.webhook_secret:
            self.webhook_secret = secrets.token_hex(24)
        super().save(*args, **kwargs)

    def to_dict(self):
        return {
            "id": self.id,
            "company_name": self.company_name,
            "website": self.website,
            "description": self.description,
            "partner_code": self.partner_code,
            "status": self.status,
            "status_display": self.get_status_display(),
            "custom_rate_per_minute": float(self.custom_rate_per_minute),
            "currency": self.currency,
            "api_key": self.api_key,
            "webhook_url": self.webhook_url,
            "has_webhook_secret": bool(self.webhook_secret),
            "shared_mcp_server_id": self.shared_mcp_server_id,
            "shared_mcp_server_name": self.shared_mcp_server.name if self.shared_mcp_server else None,
            "clients_count": self.clients.count(),
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M"),
        }


class PartnerClientRelationship(models.Model):
    partner = models.ForeignKey(PartnerProfile, on_delete=models.CASCADE, related_name='clients', verbose_name="الشريك")
    client = models.OneToOneField(User, on_delete=models.CASCADE, related_name='partner_client_rel', verbose_name="حساب العميل")
    external_reference = models.CharField(max_length=128, blank=True, default='', db_index=True, verbose_name="معرف العميل في ساس الشريك")
    
    # Spending Caps / Quota
    spending_cap = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="سقف الإنفاق ($)",
        help_text="الحد الأقصى للتكلفة المسموح بها لهذا العميل (فارغ = بلا سقف)"
    )
    minute_cap = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="سقف الدقائق",
        help_text="الحد الأقصى للدقائق الصوتية المسموح بها لهذا العميل"
    )

    total_spent = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'), verbose_name="إجمالي المستهلك ($)")
    total_minutes = models.PositiveIntegerField(default=0, verbose_name="إجمالي الدقائق المحتسبة")
    is_active = models.BooleanField(default=True, verbose_name="مفعل للاتصال")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الانضمام")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخر نشاط")

    class Meta:
        verbose_name = "علاقة عميل الشريك"
        verbose_name_plural = "عملاء الشركاء التابعين (Sub-Clients)"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.client.username} -> {self.partner.company_name} ({self.total_spent}$)"

    def is_cap_exceeded(self, next_minute_cost: Decimal = Decimal('0.0')) -> bool:
        if self.spending_cap is not None and (self.total_spent + next_minute_cost) > self.spending_cap:
            return True
        if self.minute_cap is not None and (self.total_minutes + 1) > self.minute_cap:
            return True
        return False

    def to_dict(self):
        return {
            "id": self.id,
            "client_id": self.client_id,
            "username": self.client.username,
            "name": self.client.first_name or self.client.username,
            "email": self.client.email,
            "external_reference": self.external_reference,
            "spending_cap": float(self.spending_cap) if self.spending_cap is not None else None,
            "minute_cap": self.minute_cap,
            "total_spent": float(self.total_spent),
            "total_minutes": self.total_minutes,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M"),
        }
