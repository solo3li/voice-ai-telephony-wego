from django.urls import path
from . import views

urlpatterns = [
    # Platform UI endpoints (for authenticated user dashboard in room.html)
    path('apply/', views.apply_partner, name='partner_apply'),
    path('dashboard/', views.get_partner_dashboard, name='partner_dashboard'),
    path('settings/', views.update_partner_settings, name='partner_settings'),
    path('settings/test-webhook/', views.test_partner_webhook, name='partner_test_webhook'),
    path('clients/cap/', views.update_client_cap, name='partner_client_cap'),

    path('docs/', views.api_partner_docs, name='partner_docs'),
    path('docs/openapi.json', views.api_partner_openapi_spec, name='partner_openapi_spec'),
    path('docs/scalar/', views.api_partner_docs_scalar, name='partner_docs_scalar'),

    # Headless REST API v1 for Partner SaaS Server-to-Server Integrations
    path('studio/', views.api_partner_studio, name='api_partner_studio'),
    path('wallet/', views.api_partner_wallet, name='api_partner_wallet'),
    path('transactions/', views.api_partner_transactions, name='api_partner_transactions'),

    path('clients/register/', views.api_partner_register_client, name='api_partner_register_client'),
    path('clients/', views.api_partner_list_clients, name='api_partner_list_clients'),
    path('clients/<int:client_id>/calls/', views.api_partner_client_calls, name='api_partner_client_calls'),
    path('clients/<int:client_id>/calls/dial/', views.api_partner_client_call_dial, name='api_partner_client_calls_dial'),
    path('clients/<int:client_id>/calls/hangup/', views.api_partner_client_call_hangup, name='api_partner_client_call_hangup'),
    path('clients/<int:client_id>/calls/<str:call_id>/', views.api_partner_client_call_detail, name='api_partner_client_call_detail'),

    path('clients/<int:client_id>/profiles/', views.api_partner_client_profile, name='api_partner_client_profile'),
    path('clients/<int:client_id>/profiles/studio/', views.api_partner_studio, name='api_partner_client_studio'),
    path('clients/<int:client_id>/profiles/<int:profile_id>/', views.api_partner_client_profile_detail, name='api_partner_client_profile_detail'),
    path('clients/<int:client_id>/profiles/<int:profile_id>/activate/', views.api_partner_client_profile_activate, name='api_partner_client_profile_activate'),

    path('clients/<int:client_id>/memory/', views.api_partner_client_memory, name='api_partner_client_memory'),
    path('clients/<int:client_id>/memory/<int:memory_id>/', views.api_partner_client_memory_detail, name='api_partner_client_memory_detail'),
    path('clients/<int:client_id>/crm/customers/', views.api_partner_client_crm_customers, name='api_partner_client_crm_customers'),
    path('clients/<int:client_id>/crm/customers/<str:phone>/', views.api_partner_client_crm_customer_detail, name='api_partner_client_crm_customer_detail'),

    path('clients/<int:client_id>/documents/', views.api_partner_client_documents, name='api_partner_client_documents'),
    path('clients/<int:client_id>/rag/query/', views.api_partner_client_rag_query, name='api_partner_client_rag_query'),

    path('clients/<int:client_id>/telephony/', views.api_partner_client_telephony, name='api_partner_client_telephony'),
    path('clients/<int:client_id>/telephony/numbers/', views.api_partner_client_numbers, name='api_partner_client_numbers'),
    path('clients/<int:client_id>/telephony/pbx-trunks/', views.api_partner_client_pbx_trunks, name='api_partner_client_pbx_trunks'),
    path('clients/<int:client_id>/telephony/pbx-trunks/<int:trunk_id>/', views.api_partner_client_pbx_trunk_detail, name='api_partner_client_pbx_trunk_detail'),
    path('clients/<int:client_id>/telephony/<str:trunk_type>/<int:trunk_id>/', views.api_partner_client_telephony_detail, name='api_partner_client_telephony_detail'),

    path('clients/<int:client_id>/employees/', views.api_partner_client_employees, name='api_partner_client_employees'),
    path('clients/<int:client_id>/employees/<int:employee_id>/', views.api_partner_client_employee_detail, name='api_partner_client_employee_detail'),
    path('clients/<int:client_id>/employees/calls/', views.api_partner_client_employee_calls, name='api_partner_client_employee_calls'),

    path('clients/<int:client_id>/queues/', views.api_partner_client_queues, name='api_partner_client_queues'),
    path('clients/<int:client_id>/queues/<int:queue_id>/', views.api_partner_client_queue_detail, name='api_partner_client_queue_detail'),
    path('clients/<int:client_id>/queues/<int:queue_id>/members/', views.api_partner_client_queue_members, name='api_partner_client_queue_members'),

    path('clients/<int:client_id>/mcp/', views.api_partner_client_mcp, name='api_partner_client_mcp'),
    path('clients/<int:client_id>/mcp/test/', views.api_partner_client_mcp_test, name='api_partner_client_mcp_test'),
    path('clients/<int:client_id>/mcp/test-tool/', views.api_partner_client_mcp_test_tool, name='api_partner_client_mcp_test_tool_generic'),
    path('clients/<int:client_id>/mcp/<int:mcp_id>/', views.api_partner_client_mcp_detail, name='api_partner_client_mcp_detail'),
    path('clients/<int:client_id>/mcp/<int:mcp_id>/sync/', views.api_partner_client_mcp_sync, name='api_partner_client_mcp_sync'),
    path('clients/<int:client_id>/mcp/<int:mcp_id>/test-tool/', views.api_partner_client_mcp_test_tool, name='api_partner_client_mcp_test_tool'),

    # Managed Client Campaigns (Inngest Powered)
    path('clients/<int:client_id>/campaigns/', views.api_partner_client_campaigns, name='api_partner_client_campaigns'),
    path('clients/<int:client_id>/campaigns/<int:campaign_id>/', views.api_partner_client_campaign_detail, name='api_partner_client_campaign_detail'),
    path('clients/<int:client_id>/campaigns/<int:campaign_id>/start/', views.api_partner_client_campaign_start, name='api_partner_client_campaign_start'),
    path('clients/<int:client_id>/campaigns/<int:campaign_id>/pause/', views.api_partner_client_campaign_pause, name='api_partner_client_campaign_pause'),
    path('clients/<int:client_id>/campaigns/<int:campaign_id>/reset/', views.api_partner_client_campaign_reset, name='api_partner_client_campaign_reset'),
    path('clients/<int:client_id>/campaigns/<int:campaign_id>/export/', views.api_partner_client_campaign_export, name='api_partner_client_campaign_export'),
    path('clients/<int:client_id>/campaigns/<int:campaign_id>/contacts/<int:contact_id>/', views.api_partner_client_campaign_contact_detail, name='api_partner_client_campaign_contact_detail'),
    path('clients/<int:client_id>/campaigns/<int:campaign_id>/contacts/<int:contact_id>/dial/', views.api_partner_client_campaign_contact_dial, name='api_partner_client_campaign_contact_dial'),

    # Managed Client Business Hours & Off-Hours Schedule
    path('clients/<int:client_id>/business-hours/', views.api_partner_client_business_hours, name='api_partner_client_business_hours'),

    # Managed Client Structured Live Context API (Real-time in-memory cache)
    path('clients/<int:client_id>/context/', views.api_partner_client_live_context, name='api_partner_client_live_context'),
]


