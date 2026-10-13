from django.urls import path
from . import views

app_name = 'agents'

urlpatterns = [
    # Voice, Dialect & Persona Profiles APIs
    path('profiles/', views.list_profiles, name='list_profiles'),
    path('profiles/create/', views.create_profile, name='create_profile'),
    path('profiles/<int:profile_id>/activate/', views.activate_profile, name='activate_profile'),
    path('profiles/<int:profile_id>/update/', views.update_profile, name='update_profile'),
    path('profiles/<int:profile_id>/delete/', views.delete_profile, name='delete_profile'),

    # AI Industry Roles & Custom Roles Library
    path('roles/catalog/', views.api_roles_catalog, name='roles_catalog'),
    path('roles/custom/', views.api_custom_roles_list_create, name='custom_roles_list_create'),
    path('roles/custom/<int:role_id>/', views.api_custom_role_detail, name='custom_role_detail'),


    # External FastMCP Server APIs
    path('mcp/', views.get_mcp_server, name='get_mcp_server'),
    path('mcp/save/', views.save_mcp_server, name='save_mcp_server'),
    path('mcp/sync/', views.sync_mcp_server, name='sync_mcp_server'),
    path('mcp/toggle/', views.toggle_mcp_server, name='toggle_mcp_server'),
    path('mcp/delete/', views.delete_mcp_server, name='delete_mcp_server'),
    path('mcp/test-connection/', views.test_mcp_connection_view, name='test_mcp_connection'),
    path('mcp/test-tool/', views.test_mcp_tool_view, name='test_mcp_tool'),

    # Internal AI Agent Session Bootstrap API
    path('internal/bootstrap/', views.api_internal_agent_bootstrap, name='api_internal_agent_bootstrap'),
    path('internal/whatsapp/send/', views.api_internal_agent_whatsapp_send, name='api_internal_agent_whatsapp_send'),

    # Structured Live Context (Fast In-Memory Cache)
    path('context/', views.api_user_live_context_web, name='user_live_context_web'),
    path('context/preview/', views.api_user_live_context_preview_web, name='user_live_context_preview_web'),
]

