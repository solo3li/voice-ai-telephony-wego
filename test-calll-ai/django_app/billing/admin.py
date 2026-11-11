from django.contrib import admin
from .models import BillingConfig, UserWallet, BillingTransaction


@admin.register(BillingConfig)
class BillingConfigAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'cost_per_minute', 'cost_per_1k_chars', 'min_chars_per_message',
        'media_equivalent_chars', 'currency', 'rounding_mode', 'min_balance_to_call',
        'initial_welcome_credit', 'updated_at'
    )
    list_editable = (
        'cost_per_minute', 'cost_per_1k_chars', 'min_chars_per_message',
        'media_equivalent_chars', 'currency', 'min_balance_to_call', 'initial_welcome_credit'
    )

    def has_add_permission(self, request):
        # Allow creating only if none exists (singleton)
        return not BillingConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(UserWallet)
class UserWalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'currency', 'total_spent', 'total_deposited', 'updated_at')
    search_fields = ('user__username', 'user__email')
    list_filter = ('currency', 'created_at')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(BillingTransaction)
class BillingTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'wallet', 'transaction_type', 'amount', 'balance_after',
        'billed_minutes', 'actual_seconds', 'chatwoot_message_id',
        'billed_characters', 'inbox_name', 'rate_applied', 'created_at'
    )
    list_filter = ('transaction_type', 'currency', 'created_at')
    search_fields = ('wallet__user__username', 'wallet__user__email', '=chatwoot_message_id', 'description', 'call_session__room_name', 'inbox_name')
    readonly_fields = (
        'wallet', 'call_session', 'transaction_type', 'amount', 'balance_after',
        'currency', 'actual_seconds', 'billed_minutes', 'chatwoot_message_id',
        'actual_characters', 'billed_characters', 'inbox_name', 'rate_applied',
        'description', 'created_at'
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
