from django.urls import path
from . import views

app_name = 'call_center'

urlpatterns = [
    # Employee Auth
    path('auth/login/', views.api_employee_login, name='api_employee_login'),
    path('auth/employee-login/', views.api_employee_login, name='api_employee_login_compat'),
    path('auth/me/', views.api_employee_me, name='api_employee_me'),

    # Employees Management & Status
    path('employees/', views.api_list_employees, name='api_list_employees'),
    path('employees/create/', views.api_create_employee, name='api_create_employee'),
    path('employees/<int:employee_id>/delete/', views.api_delete_employee, name='api_delete_employee'),
    path('employees/status/', views.api_update_employee_status, name='api_update_employee_status'),
    path('employees/push-token/', views.api_update_push_token, name='api_update_push_token'),
    path('employees/active-incoming/', views.api_get_active_incoming_call, name='api_get_active_incoming_call'),
    path('employees/heartbeat/', views.api_employee_heartbeat, name='api_employee_heartbeat'),

    # Queues
    path('queues/', views.list_call_queues, name='list_call_queues'),
    path('queues/create/', views.create_call_queue, name='create_call_queue'),
    path('queues/<int:queue_id>/update/', views.update_call_queue, name='update_call_queue'),
    path('queues/<int:queue_id>/delete/', views.delete_call_queue, name='delete_call_queue'),

    # WebRTC Calls
    path('calls/dial/', views.api_dial_call, name='api_dial_call'),
    path('calls/token/', views.api_get_call_token, name='api_get_call_token'),
    path('calls/hangup/', views.api_hangup_call, name='api_hangup_call'),
    path('calls/transfer/', views.api_transfer_call, name='api_transfer_call'),
    path('calls/transfer/cancel/', views.api_transfer_cancel, name='api_transfer_cancel'),
    path('calls/transfer/action/', views.api_transfer_action, name='api_transfer_action'),
    path('calls/logs/', views.api_list_call_logs, name='api_list_call_logs'),
    path('internal/ai-transfer/', views.api_internal_ai_transfer, name='api_internal_ai_transfer'),
    path('internal/asterisk-cdr/', views.api_internal_asterisk_cdr, name='api_internal_asterisk_cdr'),
]
