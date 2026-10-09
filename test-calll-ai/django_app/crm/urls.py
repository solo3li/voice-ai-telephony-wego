from django.urls import path
from . import views
from . import campaign_views

app_name = 'crm'

urlpatterns = [
    path('customers/', views.list_customers_memory, name='list_customers_memory'),
    path('calls/', views.list_all_calls, name='list_all_calls'),
    path('memory/', views.get_customer_memory, name='get_customer_memory'),
    path('memory/reset/', views.reset_customer_memory, name='reset_customer_memory'),
    path('internal/memory/', views.api_internal_get_customer_memory, name='api_internal_get_customer_memory'),
    path('internal/complete-call/', views.api_internal_save_call_session_and_memory, name='api_internal_save_call_session_and_memory'),
    path('internal/save-session-and-memory/', views.api_internal_save_call_session_and_memory, name='api_internal_save_session_and_memory_alias'),

    # Outbound Campaigns & CRM Leads Engine
    path('campaigns/', campaign_views.api_list_campaigns, name='api_list_campaigns'),
    path('campaigns/upload/', campaign_views.api_upload_and_create_campaign, name='api_upload_and_create_campaign'),
    path('campaigns/<int:campaign_id>/', campaign_views.api_get_campaign_detail, name='api_get_campaign_detail'),
    path('campaigns/<int:campaign_id>/start/', campaign_views.api_start_campaign, name='api_start_campaign'),
    path('campaigns/<int:campaign_id>/pause/', campaign_views.api_pause_campaign, name='api_pause_campaign'),
    path('campaigns/<int:campaign_id>/reset/', campaign_views.api_reset_campaign_contacts, name='api_reset_campaign_contacts'),
    path('campaigns/<int:campaign_id>/export/', campaign_views.api_export_campaign_contacts, name='api_export_campaign_contacts'),
    path('campaigns/contacts/<int:contact_id>/dial/', campaign_views.api_dial_single_contact, name='api_dial_single_contact'),

    # Digital Coworker, Approval Gates & Omnichannel
    path('coworker/config/', views.api_coworker_config, name='api_coworker_config'),
    path('coworker/approvals/', views.api_coworker_approvals_list, name='api_coworker_approvals_list'),
    path('coworker/approvals/decide/', views.api_coworker_approval_action, name='api_coworker_approval_action'),
    path('coworker/tool/execute/', views.api_execute_coworker_tool, name='api_execute_coworker_tool'),
    path('whatsapp/send/', views.api_whatsapp_send, name='api_whatsapp_send'),
    path('whatsapp/qr/', views.api_whatsapp_qr, name='api_whatsapp_qr'),
    path('telegram/webhook/', views.api_telegram_webhook, name='api_telegram_webhook'),
    path('omnichannel/messages/', views.api_omnichannel_messages_list, name='api_omnichannel_messages_list'),
]

