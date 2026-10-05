from django.contrib import admin
from .models import PartnerProfile, PartnerClientRelationship


@admin.register(PartnerProfile)
class PartnerProfileAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'partner_code', 'user', 'status', 'custom_rate_per_minute', 'currency', 'clients_count', 'created_at')
    list_filter = ('status', 'currency', 'created_at')
    search_fields = ('company_name', 'partner_code', 'user__username', 'user__email', 'api_key')
    readonly_fields = ('partner_code', 'api_key', 'created_at', 'updated_at')
    actions = ['approve_partners', 'suspend_partners']

    def clients_count(self, obj):
        return obj.clients.count()
    clients_count.short_description = "عدد العملاء التابعين"

    @admin.action(description="الموافقة على الشركاء المحددين (Approve)")
    def approve_partners(self, request, queryset):
        queryset.update(status='approved')

    @admin.action(description="إيقاف الشركاء المحددين مؤقتاً (Suspend)")
    def suspend_partners(self, request, queryset):
        queryset.update(status='suspended')


@admin.register(PartnerClientRelationship)
class PartnerClientRelationshipAdmin(admin.ModelAdmin):
    list_display = ('client', 'partner', 'external_reference', 'spending_cap', 'total_spent', 'total_minutes', 'is_active', 'created_at')
    list_filter = ('is_active', 'partner__company_name', 'created_at')
    search_fields = ('client__username', 'partner__company_name', 'external_reference')
    readonly_fields = ('created_at', 'updated_at')
