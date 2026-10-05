from django.contrib import admin
from .models import CustomerMemory, CallSession, UserCampaignLimit, OutboundCampaign, CampaignContact

@admin.register(UserCampaignLimit)
class UserCampaignLimitAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'max_concurrent_calls', 'is_auto_dialer_enabled', 'updated_at')
    list_editable = ('max_concurrent_calls', 'is_auto_dialer_enabled')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(CustomerMemory)
class CustomerMemoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'phone_number', 'customer_name', 'total_calls_count', 'last_interaction_at', 'updated_at')
    list_filter = ('updated_at', 'user')
    search_fields = ('user__username', 'phone_number', 'customer_name', 'last_interaction_summary')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(CallSession)
class CallSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'room_name', 'user', 'direction', 'caller_phone', 'destination_phone', 'duration_seconds', 'started_at', 'ended_at')
    list_filter = ('direction', 'started_at', 'user')
    search_fields = ('room_name', 'caller_phone', 'destination_phone', 'call_goal', 'summary', 'user__username')
    readonly_fields = ('started_at',)

class CampaignContactInline(admin.TabularInline):
    model = CampaignContact
    extra = 0
    readonly_fields = ('phone_number', 'customer_name', 'call_status', 'interest_level', 'retries_count', 'duration_seconds')
    fields = ('phone_number', 'customer_name', 'call_status', 'interest_level', 'retries_count', 'duration_seconds')
    can_delete = True
    show_change_link = True

@admin.register(OutboundCampaign)
class OutboundCampaignAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'user', 'status', 'total_contacts', 'completed_contacts', 'answered_contacts', 'hot_leads_count', 'warm_leads_count', 'created_at')
    list_filter = ('status', 'created_at', 'user')
    search_fields = ('name', 'call_prompt', 'user__username')
    readonly_fields = ('total_contacts', 'completed_contacts', 'answered_contacts', 'hot_leads_count', 'warm_leads_count', 'cold_leads_count', 'created_at', 'updated_at')
    inlines = [CampaignContactInline]

@admin.register(CampaignContact)
class CampaignContactAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer_name', 'phone_number', 'campaign', 'call_status', 'interest_level', 'retries_count', 'duration_seconds', 'last_attempt_at')
    list_filter = ('call_status', 'interest_level', 'campaign')
    search_fields = ('customer_name', 'phone_number', 'call_summary', 'campaign__name')
    readonly_fields = ('created_at', 'updated_at')

