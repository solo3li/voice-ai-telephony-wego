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
    path('campaigns/contacts/<int:contact_id>/whatsapp/', campaign_views.api_send_single_contact_whatsapp, name='api_send_single_contact_whatsapp'),

    # Evolution API WhatsApp & Omnichannel Endpoints
    path('whatsapp/status/', views.api_whatsapp_status, name='api_whatsapp_status'),
    path('whatsapp/connect/', views.api_whatsapp_connect, name='api_whatsapp_connect'),
    path('whatsapp/disconnect/', views.api_whatsapp_disconnect, name='api_whatsapp_disconnect'),
    path('whatsapp/messages/', views.api_whatsapp_messages, name='api_whatsapp_messages'),
    path('whatsapp/conversations/', views.api_whatsapp_conversations, name='api_whatsapp_conversations'),
    path('whatsapp/conversations/<path:phone_number>/messages/', views.api_whatsapp_conversation_messages, name='api_whatsapp_conversation_messages'),
    path('whatsapp/conversations/<path:phone_number>/reply/', views.api_whatsapp_conversation_reply, name='api_whatsapp_conversation_reply'),
    path('whatsapp/conversations/<path:phone_number>/toggle-ai/', views.api_whatsapp_conversation_toggle_ai, name='api_whatsapp_conversation_toggle_ai'),
    path('whatsapp/conversations/<path:phone_number>/update-contact/', views.api_whatsapp_conversation_update_contact, name='api_whatsapp_conversation_update_contact'),
    path('whatsapp/sync/', views.api_whatsapp_sync, name='api_whatsapp_sync'),
    path('whatsapp/send-test/', views.api_whatsapp_send_test, name='api_whatsapp_send_test'),
    path('whatsapp/trigger-followup/', views.api_whatsapp_trigger_followup, name='api_whatsapp_trigger_followup'),
    path('whatsapp/webhook/', views.api_whatsapp_webhook, name='api_whatsapp_webhook'),
]
