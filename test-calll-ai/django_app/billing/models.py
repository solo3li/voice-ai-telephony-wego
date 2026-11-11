import math
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User


class BillingConfig(models.Model):
    """
    Global billing and pricing configuration managed directly by Superadmin in Django Admin.
    Controls minute rates, default currency, minimum balance thresholds, and ceiling rounding.
    """
    CURRENCY_CHOICES = [
        ('USD', 'US Dollar ($)'),
        ('EGP', 'Egyptian Pound (ج.م)'),
    ]

    ROUNDING_CHOICES = [
        ('ceil', 'تقريب لأعلى دقيقة كاملة (Ceiling - أي ثانية تُحسب دقيقة)'),
    ]

    cost_per_minute = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0.0500'),
        verbose_name="سعر الدقيقة",
        help_text="التكلفة المخصومة لكل دقيقة مكالمة محسوبة"
    )
    currency = models.CharField(
        max_length=8,
        choices=CURRENCY_CHOICES,
        default='USD',
        verbose_name="العملة",
        help_text="العملة المعتمدة لحساب الرصيد والخصم (دولار أو مصري)"
    )
    rounding_mode = models.CharField(
        max_length=16,
        choices=ROUNDING_CHOICES,
        default='ceil',
        verbose_name="طريقة احتساب الدقائق",
        help_text="التقريب الصارم لأقرب دقيقة مرتفع: 61 ثانية = دقيقتان"
    )
    min_balance_to_call = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0.0500'),
        verbose_name="الحد الأدنى لبدء مكالمة",
        help_text="الحد الأدنى للرصيد المطلوب لبدء أي مكالمة صوتية جديدة"
    )
    initial_welcome_credit = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('10.0000'),
        verbose_name="رصيد ترحيبي تجريبي",
        help_text="الرصيد المبدئي المجاني الممنوح للمستخدم الجديد للتجربة"
    )
    cost_per_1k_chars = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0.0100'),
        verbose_name="سعر كل 1000 حرف",
        help_text="التكلفة المخصومة لكل 1000 حرف لرسائل شات ووت"
    )
    min_chars_per_message = models.PositiveIntegerField(
        default=50,
        verbose_name="الحد الأدنى لحروف الرسالة",
        help_text="الحد الأدنى لاحتساب الحروف لأي رسالة صادرة"
    )
    media_equivalent_chars = models.PositiveIntegerField(
        default=500,
        verbose_name="عدد الحروف المكافئ للميديا",
        help_text="عدد الحروف المحتسب للرسائل التي تحتوي على وسائط ومرفقات فقط بدون نص"
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")

    class Meta:
        verbose_name = "إعدادات التسعير والفواتير"
        verbose_name_plural = "إعدادات التسعير والفواتير"

    def __str__(self):
        sym = "$" if self.currency == "USD" else "ج.م"
        return f"تسعير النظام: {self.cost_per_minute} {sym} / دقيقة"

    @classmethod
    def get_config(cls):
        """Retrieve the singleton billing configuration or create default."""
        config = cls.objects.first()
        if not config:
            config = cls.objects.create()
        return config

    def calculate_billed_minutes(self, duration_seconds: int) -> int:
        """
        Calculate billed minutes strictly rounding up to ceiling.
        Even 1 second counts as 1 full minute. 61 seconds counts as 2 minutes.
        """
        if duration_seconds <= 0:
            return 0
        return int(math.ceil(duration_seconds / 60.0))

    def calculate_cost(self, duration_seconds: int) -> tuple[int, Decimal]:
        """
        Returns (billed_minutes, total_cost).
        """
        billed_minutes = self.calculate_billed_minutes(duration_seconds)
        cost = Decimal(str(billed_minutes)) * self.cost_per_minute
        return billed_minutes, cost

    def calculate_message_characters(self, content: str = '', has_media: bool = False) -> tuple[int, int]:
        """
        Returns (actual_characters, billed_characters).
        """
        raw_text = (content or '').strip()
        if raw_text:
            actual = len(raw_text)
        elif has_media:
            actual = self.media_equivalent_chars
        else:
            actual = 0

        billed = max(actual, self.min_chars_per_message) if (actual > 0 or has_media) else 0
        return actual, billed

    def calculate_message_cost(self, billed_characters: int, rate: Decimal = None) -> Decimal:
        if rate is None:
            rate = self.cost_per_1k_chars
        if billed_characters <= 0:
            return Decimal('0.0000')
        cost = (Decimal(str(billed_characters)) / Decimal('1000')) * rate
        return round(cost, 4)

    def get_currency_symbol(self) -> str:
        return "$" if self.currency == "USD" else "ج.م"


class UserWallet(models.Model):
    """
    Account balance wallet for each user (OpenRouter style prepaid wallet).
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet', verbose_name="المستخدم")
    balance = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('10.0000'), verbose_name="الرصيد المتاح")
    currency = models.CharField(max_length=8, default='USD', verbose_name="العملة")
    total_spent = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0.0000'), verbose_name="إجمالي المستهلك")
    total_deposited = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('10.0000'), verbose_name="إجمالي المشحون")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ آخر تحديث")

    class Meta:
        verbose_name = "محفظة رصيد العميل"
        verbose_name_plural = "محافظ رصيد العملاء"
        ordering = ['-updated_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(balance__gte=Decimal('0.0000')),
                name='userwallet_balance_non_negative'
            )
        ]

    def __str__(self):
        sym = "$" if self.currency == "USD" else "ج.م"
        return f"محفظة {self.user.username}: {self.balance:.2f} {sym}"

    def get_currency_symbol(self) -> str:
        return "$" if self.currency == "USD" else "ج.م"

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.user.username,
            "balance": float(self.balance),
            "currency": self.currency,
            "currency_symbol": self.get_currency_symbol(),
            "total_spent": float(self.total_spent),
            "total_deposited": float(self.total_deposited),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M"),
        }


class BillingTransaction(models.Model):
    """
    Financial ledger documenting all credit deductions, instant top-ups, and adjustments.
    """
    TYPE_CHOICES = [
        ('call_deduction', 'خصم مكالمة صوتية'),
        ('message_deduction', 'خصم رسائل شات ووت'),
        ('topup', 'شحن رصيد مباشر'),
        ('admin_adjustment', 'تعديل رصيد إداري'),
        ('welcome_bonus', 'رصيد ترحيبي مجاني'),
    ]

    wallet = models.ForeignKey(UserWallet, on_delete=models.CASCADE, related_name='transactions', verbose_name="المحفظة")
    call_session = models.ForeignKey(
        'crm.CallSession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='billing_transactions',
        verbose_name="جلسة المكالمة المرتبطة"
    )
    transaction_type = models.CharField(max_length=32, choices=TYPE_CHOICES, default='call_deduction', verbose_name="نوع الحركة")
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        verbose_name="المبلغ",
        help_text="موجب للشحن وسالب للخصم"
    )
    balance_after = models.DecimalField(max_digits=12, decimal_places=4, verbose_name="الرصيد بعد الحركة")
    currency = models.CharField(max_length=8, default='USD', verbose_name="العملة")
    actual_seconds = models.PositiveIntegerField(default=0, verbose_name="الثواني الفعلية")
    billed_minutes = models.PositiveIntegerField(default=0, verbose_name="الدقائق المحتسبة (Ceiling)")
    chatwoot_message_id = models.BigIntegerField(
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        verbose_name="معرف رسالة شات ووت"
    )
    actual_characters = models.PositiveIntegerField(default=0, verbose_name="عدد الحروف الفعلي")
    billed_characters = models.PositiveIntegerField(default=0, verbose_name="عدد الحروف المحتسب")
    inbox_name = models.CharField(max_length=128, blank=True, default='', verbose_name="اسم القناة / صندوق الوارد")
    rate_applied = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'), verbose_name="السعر المطبق للدقيقة أو الألف حرف")
    description = models.CharField(max_length=255, blank=True, default='', verbose_name="الوصف والبيان")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="التاريخ والوقت")

    class Meta:
        verbose_name = "حركة مالية"
        verbose_name_plural = "سجل الحركات المالية (Ledger)"
        ordering = ['-created_at']

    def __str__(self):
        sym = "$" if self.currency == "USD" else "ج.م"
        sign = "+" if self.amount >= 0 else ""
        return f"{self.get_transaction_type_display()} ({sign}{self.amount:.2f} {sym}) - {self.wallet.user.username}"

    def to_dict(self):
        sym = "$" if self.currency == "USD" else "ج.م"
        if self.transaction_type == 'message_deduction' or (self.amount != 0 and abs(self.amount) < Decimal('0.01')):
            amount_formatted = f"{'+' if self.amount > 0 else ''}{self.amount:.4f} {sym}"
        else:
            amount_formatted = f"{'+' if self.amount > 0 else ''}{self.amount:.2f} {sym}"

        if self.transaction_type == 'message_deduction' or (self.balance_after != round(self.balance_after, 2)):
            balance_after_formatted = f"{self.balance_after:.4f} {sym}"
        else:
            balance_after_formatted = f"{self.balance_after:.2f} {sym}"

        return {
            "id": self.id,
            "transaction_type": self.transaction_type,
            "transaction_type_display": self.get_transaction_type_display(),
            "amount": float(self.amount),
            "amount_formatted": amount_formatted,
            "balance_after": float(self.balance_after),
            "balance_after_formatted": balance_after_formatted,
            "currency": self.currency,
            "currency_symbol": sym,
            "actual_seconds": self.actual_seconds,
            "billed_minutes": self.billed_minutes,
            "chatwoot_message_id": self.chatwoot_message_id,
            "actual_characters": self.actual_characters,
            "billed_characters": self.billed_characters,
            "inbox_name": self.inbox_name,
            "rate_applied": float(self.rate_applied),
            "description": self.description,
            "room_name": self.call_session.room_name if self.call_session else "",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
