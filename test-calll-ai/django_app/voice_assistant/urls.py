from django.urls import path
from . import views

app_name = 'voice_assistant'

urlpatterns = [
    # Auth Views
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),

    # Voice Assistant Main Room
    path('', views.room_view, name='room'),

    # Real-Time & WebRTC APIs
    path('api/token/', views.get_tokens, name='get_tokens'),
    path('api/livekit/webhook/', views.livekit_webhook, name='livekit_webhook'),

    # Document Management & RAG APIs
    path('api/documents/', views.list_documents, name='list_documents'),
    path('api/documents/upload/', views.upload_document, name='upload_document'),
    path('api/documents/<int:doc_id>/delete/', views.delete_document, name='delete_document'),


    # Voice, Dialect & Persona Profiles APIs
    path('api/profiles/', views.list_profiles, name='list_profiles'),
    path('api/profiles/create/', views.create_profile, name='create_profile'),
    path('api/profiles/<int:profile_id>/activate/', views.activate_profile, name='activate_profile'),
    path('api/profiles/<int:profile_id>/update/', views.update_profile, name='update_profile'),
    path('api/profiles/<int:profile_id>/delete/', views.delete_profile, name='delete_profile'),

    # External MCP Server APIs
    path('api/mcp/', views.get_mcp_server, name='get_mcp_server'),
    path('api/mcp/save/', views.save_mcp_server, name='save_mcp_server'),
    path('api/mcp/sync/', views.sync_mcp_server, name='sync_mcp_server'),
    path('api/mcp/toggle/', views.toggle_mcp_server, name='toggle_mcp_server'),
    path('api/mcp/delete/', views.delete_mcp_server, name='delete_mcp_server'),
    path('api/mcp/test-connection/', views.test_mcp_connection_view, name='test_mcp_connection'),
    path('api/mcp/test-tool/', views.test_mcp_tool_view, name='test_mcp_tool'),

    # Structured Live Context APIs
    path('api/context/', views.api_user_live_context_web, name='api_live_context'),
    path('api/context/preview/', views.api_user_live_context_preview_web, name='api_live_context_preview'),

    # Customer Memory & Call History APIs
    path('api/customers/', views.list_customers_memory, name='list_customers_memory'),
    path('api/memory/', views.get_customer_memory, name='get_customer_memory'),
    path('api/memory/reset/', views.reset_customer_memory, name='reset_customer_memory'),

    # Call Queues & Routing APIs
    path('api/queues/', views.list_call_queues, name='list_call_queues'),
    path('api/queues/create/', views.create_call_queue, name='create_call_queue'),
    path('api/queues/<int:queue_id>/delete/', views.delete_call_queue, name='delete_call_queue'),

    # Generic Outbound SIP Trunk & Calling APIs
    path('api/outbound/trunk/', views.get_outbound_trunk, name='get_outbound_trunk'),
    path('api/outbound/trunk/save/', views.save_outbound_trunk, name='save_outbound_trunk'),
    path('api/outbound/trunk/<int:trunk_id>/delete/', views.delete_outbound_trunk, name='delete_outbound_trunk'),
    path('api/outbound/ai-call/', views.trigger_ai_outbound_call, name='trigger_ai_outbound_call'),
    path('api/telephony/outbound-gateways/', views.list_outbound_gateways, name='list_outbound_gateways'),
    path('api/outbound/gateways/', views.list_outbound_gateways, name='list_outbound_gateways_alt'),
    path('api/pbx-trunks/', views.list_pbx_trunks, name='list_pbx_trunks'),
    path('api/pbx-trunks/save/', views.save_pbx_trunk, name='save_pbx_trunk'),
    path('api/pbx-trunks/<int:trunk_id>/delete/', views.delete_pbx_trunk, name='delete_pbx_trunk'),

    # Employee WebRTC & Auth APIs
    path('api/auth/employee-login/', views.api_employee_login, name='api_employee_login'),
    path('api/auth/me/', views.api_employee_me, name='api_employee_me'),
    path('api/employees/', views.api_list_employees, name='api_list_employees'),
    path('api/employees/create/', views.api_create_employee, name='api_create_employee'),
    path('api/employees/<int:employee_id>/delete/', views.api_delete_employee, name='api_delete_employee'),
    path('api/employees/status/', views.api_update_employee_status, name='api_update_employee_status'),
    path('api/calls/dial/', views.api_dial_call, name='api_dial_call'),
    path('api/calls/token/', views.api_get_call_token, name='api_get_call_token'),
    path('api/calls/hangup/', views.api_hangup_call, name='api_hangup_call'),
    path('api/calls/recordings/<path:filename>', views.stream_call_recording, name='stream_call_recording'),

    # Business Hours Schedule APIs
    path('api/business-hours/', views.get_business_hours, name='get_business_hours'),
    path('api/business-hours/save/', views.save_business_hours, name='save_business_hours'),

    # Dedicated Modular Section Pages
    path('calls/', views.calls_page_view, name='calls_page'),
    path('billing/', views.billing_page_view, name='billing_page'),
    path('crm/', views.crm_page_view, name='crm_page'),
    path('documents/', views.rag_page_view, name='rag_page'),
    path('personas/', views.personas_page_view, name='personas_page'),
    path('campaigns/', views.campaigns_page_view, name='campaigns_page'),
    path('business-hours/', views.business_hours_page_view, name='business_hours_page'),
    path('tools/', views.store_page_view, name='store_page'),
    path('developer/', views.developer_page_view, name='developer_page'),
    path('call-center/', views.callcenter_page_view, name='callcenter_page'),
    path('telephony/', views.telephony_page_view, name='telephony_page'),
    path('partner/', views.partner_page_view, name='partner_page'),
]



