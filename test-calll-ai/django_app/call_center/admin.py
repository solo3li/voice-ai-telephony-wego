from django.contrib import admin
from .models import EmployeeProfile, CallQueue, QueueMembership

class QueueMembershipInline(admin.TabularInline):
    model = QueueMembership
    extra = 1
    fields = ('employee', 'order', 'is_active', 'created_at')
    readonly_fields = ('created_at',)

@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'extension', 'display_name', 'department', 'user', 'status', 'is_active', 'created_at')
    list_filter = ('status', 'department', 'is_active')
    search_fields = ('extension', 'display_name', 'department', 'user__username')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(CallQueue)
class CallQueueAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'code', 'user', 'strategy', 'ring_timeout_seconds', 'total_timeout_seconds', 'is_active', 'members_count')
    list_filter = ('strategy', 'is_active', 'user')
    search_fields = ('name', 'code', 'user__username')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [QueueMembershipInline]

    def members_count(self, obj):
        return obj.memberships.count()
    members_count.short_description = "عدد الأعضاء"

@admin.register(QueueMembership)
class QueueMembershipAdmin(admin.ModelAdmin):
    list_display = ('id', 'queue', 'employee', 'order', 'is_active', 'created_at')
    list_filter = ('is_active', 'queue')
    search_fields = ('queue__name', 'employee__display_name', 'employee__extension')
    readonly_fields = ('created_at',)
