from django.contrib import admin
from .models import OutboundSIPTrunk, InboundPBXTrunk, BusinessHoursSchedule

@admin.register(OutboundSIPTrunk)
class OutboundSIPTrunkAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'user', 'sip_host', 'sip_port', 'transport', 'caller_id', 'livekit_outbound_trunk_id', 'is_default', 'is_active', 'created_at')
    list_filter = ('transport', 'is_active', 'is_default', 'user')
    search_fields = ('name', 'sip_host', 'caller_id', 'user__username')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(InboundPBXTrunk)
class InboundPBXTrunkAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'user', 'auth_mode', 'pbx_ip', 'auth_username', 'destination_type', 'is_active', 'created_at')
    list_filter = ('auth_mode', 'destination_type', 'is_active', 'user')
    search_fields = ('name', 'pbx_ip', 'auth_username', 'user__username')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(BusinessHoursSchedule)
class BusinessHoursScheduleAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'timezone', 'action_type', 'is_enabled', 'created_at')
    list_filter = ('is_enabled', 'action_type', 'timezone')
    search_fields = ('user__username', 'ai_message')
    readonly_fields = ('created_at', 'updated_at')
