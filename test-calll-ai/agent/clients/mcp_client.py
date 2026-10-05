import asyncio
from config import logger
from .django_client import fetch_agent_bootstrap_sync, parse_mcp_servers_from_bootstrap

def fetch_user_mcp_servers_sync(user_id: int, bootstrap: dict = None) -> list:
    """Fetch all active external MCP servers and cached tools for user via Django API."""
    if bootstrap is not None:
        return parse_mcp_servers_from_bootstrap(bootstrap)
    if not user_id:
        return []
    try:
        b = fetch_agent_bootstrap_sync(user_id)
        return parse_mcp_servers_from_bootstrap(b)
    except Exception as e:
        logger.error(f"Error fetching MCP servers for user {user_id}: {e}")
        return []

# Backwards compatibility alias
fetch_user_mcp_server_sync = fetch_user_mcp_servers_sync

import json

class MCPToolResult(dict):
    """
    Structured result of an MCP tool call.
    Inherits from dict and overrides __str__ so it can seamlessly be used as either
    a dict (res['is_error'], res['error_message']) or a string (str(res)).
    """
    def __init__(self, success: bool, is_error: bool, result: str, error_message: str = "", error_type: str = "none"):
        super().__init__(
            success=success,
            is_error=is_error,
            result=result,
            error_message=error_message,
            error_type=error_type
        )

    def __str__(self) -> str:
        return self.get("result", "")


async def execute_mcp_tool_call(server_url: str, auth_token: str, tool_name: str, arguments: dict) -> MCPToolResult:
    """Execute tool call on external MCP SSE server with strict timeout and comprehensive error detection."""
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    logger.info(f"Connecting to MCP SSE at {server_url} to call '{tool_name}' with {arguments}")
    try:
        async def _call():
            async with sse_client(server_url, headers=headers) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments=arguments)
                    out_texts = []
                    for c in result.content:
                        if hasattr(c, "text"):
                            out_texts.append(c.text)
                        else:
                            out_texts.append(str(c))
                    raw_text = "\n".join(out_texts) if out_texts else "{}"
                    is_err = getattr(result, "is_error", False)
                    return raw_text, is_err

        raw_text, is_err = await asyncio.wait_for(_call(), timeout=4.0)

        # Inspect raw_text for application-level error payloads
        error_msg = ""
        error_type = "none"

        if is_err:
            error_type = "tool_error"
            error_msg = raw_text
        elif "validation error" in raw_text.lower() or "missing required argument" in raw_text.lower():
            is_err = True
            error_type = "validation_error"
            error_msg = raw_text
        else:
            try:
                parsed = json.loads(raw_text)
                if isinstance(parsed, dict):
                    if parsed.get("ok") is False or parsed.get("success") is False:
                        is_err = True
                        error_type = "tool_error"
                        error_msg = str(parsed.get("error") or parsed.get("message") or parsed.get("detail") or raw_text)
                    elif str(parsed.get("status", "")).lower() in ("error", "failed", "failure"):
                        is_err = True
                        error_type = "tool_error"
                        error_msg = str(parsed.get("error") or parsed.get("message") or parsed.get("detail") or raw_text)
                    elif "error" in parsed and parsed.get("error") and not parsed.get("ok"):
                        is_err = True
                        error_type = "tool_error"
                        error_msg = str(parsed.get("error"))
            except Exception:
                pass

        if is_err and not error_msg:
            error_msg = raw_text

        return MCPToolResult(
            success=not is_err,
            is_error=is_err,
            result=raw_text,
            error_message=error_msg,
            error_type=error_type
        )
    except asyncio.TimeoutError:
        logger.warning(f"MCP tool '{tool_name}' timed out after 4.0s")
        timeout_msg = "استغرق خادم أداة المتجر وقتاً أطول من المتوقع للرد (انتهت المهلة الزمنية)."
        return MCPToolResult(
            success=False,
            is_error=True,
            result=timeout_msg,
            error_message=timeout_msg,
            error_type="timeout"
        )
    except Exception as ex:
        logger.error(f"Error calling MCP tool '{tool_name}' on {server_url}: {ex}", exc_info=True)
        conn_msg = f"تعذر الاتصال بخادم الأداة: {str(ex)}"
        return MCPToolResult(
            success=False,
            is_error=True,
            result=conn_msg,
            error_message=conn_msg,
            error_type="connection"
        )
