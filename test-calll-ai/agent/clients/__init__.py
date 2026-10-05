"""Clients package for Centrifugo, Django, and MCP services."""
from .http_pool import get_http_session, close_http_session
from .centrifugo_client import notify_centrifugo, notify_centrifugo_async
from .django_client import (
    fetch_agent_bootstrap_sync,
    fetch_agent_bootstrap_async,
    query_knowledge_base_sync,
    query_knowledge_base_async,
    trigger_ai_transfer_sync,
    trigger_ai_transfer_async,
    save_call_session_and_update_memory_sync,
    save_call_session_and_update_memory_async,
    parse_mcp_servers_from_bootstrap,
    parse_customer_memory_from_bootstrap,
    parse_active_profile_from_bootstrap,
    fetch_user_active_profile_sync,
    fetch_customer_memory_sync,
    lookup_customer_memory_async,
    lookup_customer_memory_sync,
)
from .mcp_client import execute_mcp_tool_call, fetch_user_mcp_servers_sync

fetch_user_mcp_server_sync = fetch_user_mcp_servers_sync

__all__ = [
    "get_http_session",
    "close_http_session",
    "notify_centrifugo",
    "notify_centrifugo_async",
    "fetch_agent_bootstrap_sync",
    "fetch_agent_bootstrap_async",
    "query_knowledge_base_sync",
    "query_knowledge_base_async",
    "trigger_ai_transfer_sync",
    "trigger_ai_transfer_async",
    "save_call_session_and_update_memory_sync",
    "save_call_session_and_update_memory_async",
    "parse_mcp_servers_from_bootstrap",
    "parse_customer_memory_from_bootstrap",
    "parse_active_profile_from_bootstrap",
    "fetch_user_active_profile_sync",
    "fetch_customer_memory_sync",
    "lookup_customer_memory_async",
    "lookup_customer_memory_sync",
    "execute_mcp_tool_call",
    "fetch_user_mcp_servers_sync",
    "fetch_user_mcp_server_sync",
]
