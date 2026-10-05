import asyncio
import time
import json
import logging
import concurrent.futures

logger = logging.getLogger(__name__)


def _run_sync(coro):
    """Safely run an async coroutine from synchronous Django views or worker threads."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


async def test_mcp_connection_async(server_url: str, auth_token: str = "", timeout: float = 6.0) -> dict:
    """
    Connect to external MCP SSE server, perform handshake initialization,
    and discover available tools with schema validation.
    """
    server_url = (server_url or "").strip()
    auth_token = (auth_token or "").strip()

    if not server_url:
        return {
            "ok": False,
            "error_type": "invalid_url",
            "latency_ms": 0,
            "error_message": "رابط الخادم (server_url) مطلوب.",
            "tools_count": 0,
            "tools": []
        }

    if not (server_url.startswith("http://") or server_url.startswith("https://")):
        return {
            "ok": False,
            "error_type": "invalid_url",
            "latency_ms": 0,
            "error_message": "يجب أن يبدأ رابط الخادم بـ http:// أو https://",
            "tools_count": 0,
            "tools": []
        }

    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    start_time = time.perf_counter()

    try:
        from mcp import ClientSession
        from mcp.client.sse import sse_client

        async def _connect_and_list():
            async with sse_client(server_url, headers=headers) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tool_list = await session.list_tools()
                    parsed_tools = []
                    for t in (tool_list.tools or []):
                        schema = getattr(t, 'input_schema', None) or getattr(t, 'inputSchema', None) or {}
                        if not isinstance(schema, dict):
                            schema = {}
                        properties = schema.get('properties', {}) if isinstance(schema, dict) else {}
                        required = schema.get('required', []) if isinstance(schema, dict) else []
                        parsed_tools.append({
                            "name": t.name,
                            "description": t.description or "",
                            "parameters": schema,
                            "required_params": required,
                            "params_count": len(properties) if isinstance(properties, dict) else 0
                        })
                    return parsed_tools

        tools = await asyncio.wait_for(_connect_and_list(), timeout=timeout)
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return {
            "ok": True,
            "status": "success",
            "latency_ms": latency_ms,
            "tools_count": len(tools),
            "tools": tools,
            "message": f"تم الاتصال بنجاح بالخادم خلال {latency_ms}ms واكتشاف {len(tools)} أداة متاحة."
        }

    except asyncio.TimeoutError:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        err_msg = f"انتهت المهلة الزمنية ({timeout} ثوانٍ) أثناء محاولة الاتصال بالخادم."
        logger.warning(f"MCP Connection timeout for {server_url} after {latency_ms}ms")
        return {
            "ok": False,
            "status": "error",
            "error_type": "timeout",
            "latency_ms": latency_ms,
            "error_message": err_msg,
            "tools_count": 0,
            "tools": []
        }
    except Exception as ex:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        raw_msg = str(ex)
        err_lower = raw_msg.lower()

        if "401" in err_lower or "403" in err_lower or "unauthorized" in err_lower or "forbidden" in err_lower:
            err_type = "auth_error"
            user_msg = "فشل التحقق من صلاحيات الدخول (401/403): تأكد من صحة الـ Bearer Token."
        elif "connection refused" in err_lower or "cannot connect" in err_lower or "nodename nor servname" in err_lower or "temporary failure in name resolution" in err_lower or "errno -3" in err_lower:
            err_type = "connection_error"
            user_msg = f"تعذر الوصول للخادم: تأكد من تشغيل خادم الـ SSE وصحة الرابط على الشبكة ({raw_msg})."
        else:
            err_type = "handshake_error"
            user_msg = f"فشل تهيئة بروتوكول MCP مع الخادم: {raw_msg}"

        logger.warning(f"MCP Connection error for {server_url}: {err_type} - {raw_msg}")
        return {
            "ok": False,
            "status": "error",
            "error_type": err_type,
            "latency_ms": latency_ms,
            "error_message": user_msg,
            "raw_error": raw_msg,
            "tools_count": 0,
            "tools": []
        }


def test_mcp_connection_sync(server_url: str, auth_token: str = "", timeout: float = 6.0) -> dict:
    """Synchronous wrapper for test_mcp_connection_async."""
    return _run_sync(test_mcp_connection_async(server_url, auth_token=auth_token, timeout=timeout))


async def test_mcp_tool_async(
    server_url: str,
    auth_token: str = "",
    tool_name: str = "",
    arguments: dict = None,
    timeout: float = 8.0
) -> dict:
    """
    Execute a test call on a specific tool on the remote MCP SSE server,
    capturing latency, output, and application/protocol errors.
    """
    server_url = (server_url or "").strip()
    auth_token = (auth_token or "").strip()
    tool_name = (tool_name or "").strip()
    if arguments is None:
        arguments = {}

    if not server_url:
        return {
            "ok": False,
            "error_type": "invalid_url",
            "execution_time_ms": 0,
            "error_message": "رابط الخادم (server_url) مطلوب."
        }

    if not tool_name:
        return {
            "ok": False,
            "error_type": "invalid_tool",
            "execution_time_ms": 0,
            "error_message": "اسم الأداة (tool_name) مطلوب لتنفيذ الاختبار."
        }

    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    start_time = time.perf_counter()

    try:
        from mcp import ClientSession
        from mcp.client.sse import sse_client

        async def _call_tool():
            async with sse_client(server_url, headers=headers) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments=arguments)
                    out_texts = []
                    for c in getattr(result, 'content', []):
                        if hasattr(c, "text"):
                            out_texts.append(c.text)
                        else:
                            out_texts.append(str(c))
                    raw_text = "\n".join(out_texts) if out_texts else "{}"
                    is_err = getattr(result, "is_error", False)
                    return raw_text, is_err

        raw_text, is_err = await asyncio.wait_for(_call_tool(), timeout=timeout)
        exec_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

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

        return {
            "ok": not is_err,
            "status": "success" if not is_err else "error",
            "execution_time_ms": exec_time_ms,
            "tool_name": tool_name,
            "arguments": arguments,
            "result": raw_text,
            "is_error": is_err,
            "error_type": error_type,
            "error_message": error_msg,
            "message": "تم تنفيذ الأداة بنجاح." if not is_err else f"فشل تنفيذ الأداة: {error_msg}"
        }

    except asyncio.TimeoutError:
        exec_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
        err_msg = f"انتهت المهلة الزمنية ({timeout} ثوانٍ) أثناء تنفيذ الأداة '{tool_name}'."
        logger.warning(f"MCP Tool execution timeout for '{tool_name}' after {exec_time_ms}ms")
        return {
            "ok": False,
            "status": "error",
            "error_type": "timeout",
            "execution_time_ms": exec_time_ms,
            "tool_name": tool_name,
            "arguments": arguments,
            "is_error": True,
            "error_message": err_msg,
            "result": err_msg
        }
    except Exception as ex:
        exec_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
        raw_msg = str(ex)
        logger.warning(f"MCP Tool execution error for '{tool_name}': {raw_msg}")
        return {
            "ok": False,
            "status": "error",
            "error_type": "connection_error",
            "execution_time_ms": exec_time_ms,
            "tool_name": tool_name,
            "arguments": arguments,
            "is_error": True,
            "error_message": f"حدث خطأ أثناء استدعاء الأداة: {raw_msg}",
            "result": raw_msg
        }


def test_mcp_tool_sync(
    server_url: str,
    auth_token: str = "",
    tool_name: str = "",
    arguments: dict = None,
    timeout: float = 8.0
) -> dict:
    """Synchronous wrapper for test_mcp_tool_async."""
    return _run_sync(test_mcp_tool_async(
        server_url=server_url,
        auth_token=auth_token,
        tool_name=tool_name,
        arguments=arguments,
        timeout=timeout
    ))
