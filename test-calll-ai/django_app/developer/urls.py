from django.urls import path
from . import views

urlpatterns = [
    # Developer Key Management (for logged-in UI dashboard)
    path('keys/', views.get_developer_keys, name='developer_keys'),
    path('keys/rotate/', views.rotate_developer_key, name='developer_keys_rotate'),

    # Interactive Scalar Docs & OpenAPI spec
    path('docs/', views.api_user_docs, name='developer_docs'),
    path('docs/openapi.json', views.api_user_openapi_spec, name='developer_openapi_spec'),

    # Direct User REST API Endpoints (authenticated via X-API-Key or Bearer sk_live_usr_...)
    path('account/', views.api_user_account, name='developer_account'),
    
    # Billing & Wallet CRUD
    path('billing/wallet/', views.api_user_billing_wallet, name='developer_billing_wallet'),
    path('billing/transactions/', views.api_user_billing_transactions, name='developer_billing_transactions'),

    path('profiles/', views.api_user_profiles, name='developer_profiles'),
    path('profiles/studio/', views.api_user_profiles_studio, name='developer_profiles_studio'),
    path('profiles/<int:profile_id>/', views.api_user_profile_detail, name='developer_profile_detail'),
    path('profiles/<int:profile_id>/activate/', views.api_user_profile_activate, name='developer_profile_activate'),

    path('memory/', views.api_user_memory, name='developer_memory'),
    path('memory/<int:memory_id>/', views.api_user_memory_detail, name='developer_memory_detail'),

    # CRM Customers CRUD
    path('crm/customers/', views.api_user_crm_customers, name='developer_crm_customers'),
    path('crm/customers/<str:phone>/', views.api_user_crm_customer_delete, name='developer_crm_customer_delete'),

    path('documents/', views.api_user_documents, name='developer_documents'),
    path('rag/query/', views.api_user_rag_query, name='developer_rag_query'),

    path('mcp/', views.api_user_mcp, name='developer_mcp'),
    path('mcp/test/', views.api_user_mcp_test, name='developer_mcp_test'),
    path('mcp/test-tool/', views.api_user_mcp_test_tool, name='developer_mcp_test_tool_generic'),
    path('mcp/<int:mcp_id>/', views.api_user_mcp_detail, name='developer_mcp_detail'),
    path('mcp/<int:mcp_id>/sync/', views.api_user_mcp_sync, name='developer_mcp_sync'),
    path('mcp/<int:mcp_id>/test-tool/', views.api_user_mcp_test_tool, name='developer_mcp_test_tool'),

    # Telephony & SIP Trunks
    path('telephony/', views.api_user_telephony, name='developer_telephony'),
    path('telephony/numbers/', views.api_user_numbers, name='developer_numbers'),
    path('telephony/pbx-trunks/', views.api_user_pbx_trunks, name='developer_pbx_trunks'),
    path('telephony/pbx-trunks/<int:trunk_id>/', views.api_user_pbx_trunk_detail, name='developer_pbx_trunk_detail'),

    # Employee Management & Call Logs
    path('employees/', views.api_user_employees, name='developer_employees'),
    path('employees/<int:employee_id>/', views.api_user_employee_detail, name='developer_employee_detail'),
    path('employees/calls/', views.api_user_employee_calls, name='developer_employee_calls'),

    path('queues/', views.api_user_queues, name='developer_queues'),
    path('queues/<int:queue_id>/', views.api_user_queue_detail, name='developer_queue_detail'),
    path('queues/<int:queue_id>/members/', views.api_user_queue_members, name='developer_queue_members'),

    path('calls/', views.api_user_calls, name='developer_calls'),
    path('calls/dial/', views.api_user_call_dial, name='developer_calls_dial'),
    path('calls/hangup/', views.api_user_call_hangup, name='developer_calls_hangup'),
    path('calls/<str:call_id>/', views.api_user_call_detail, name='developer_call_detail'),
    path('webhooks/', views.api_user_webhooks, name='developer_webhooks'),

    # Campaigns & Outbound Calling (Inngest Powered)
    path('campaigns/', views.api_user_campaigns, name='developer_campaigns'),
    path('campaigns/<int:campaign_id>/', views.api_user_campaign_detail, name='developer_campaign_detail'),
    path('campaigns/<int:campaign_id>/start/', views.api_user_campaign_start, name='developer_campaign_start'),
    path('campaigns/<int:campaign_id>/pause/', views.api_user_campaign_pause, name='developer_campaign_pause'),
    path('campaigns/<int:campaign_id>/reset/', views.api_user_campaign_reset, name='developer_campaign_reset'),
    path('campaigns/<int:campaign_id>/export/', views.api_user_campaign_export, name='developer_campaign_export'),
    path('campaigns/<int:campaign_id>/contacts/<int:contact_id>/', views.api_user_campaign_contact_detail, name='developer_campaign_contact_detail'),
    path('campaigns/<int:campaign_id>/contacts/<int:contact_id>/dial/', views.api_user_campaign_contact_dial, name='developer_campaign_contact_dial'),

    # Business Hours & Off-Hours Schedule
    path('business-hours/', views.api_user_business_hours, name='developer_business_hours'),

    # Structured Live Context API (Real-time in-memory cache)
    path('context/', views.api_user_live_context, name='developer_live_context'),
]


