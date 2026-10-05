import logging
import inngest
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from common.inngest_client import inngest_client
from .models import AgentToolCallLog
from crm.models import CallSession

logger = logging.getLogger(__name__)


@inngest_client.create_function(
    fn_id="log-agent-tool-call",
    name="Log Agent Tool Call Execution",
    trigger=inngest.TriggerEvent(event="agent/tool.executed"),
)
async def fn_log_agent_tool_call(ctx: inngest.Context) -> dict:
    data = ctx.event.data or {}
    user_id = data.get("user_id")
    room_name = data.get("room_name") or ""
    tool_name = data.get("tool_name") or "unknown"
    status = data.get("status") or "success"

    logger.info(f"[Inngest Tool Log] Processing tool call log: {tool_name} [{status}] in room {room_name}")

    def _save_log():
        # 1. Resolve User
        user = None
        if user_id:
            user = User.objects.filter(id=user_id).first()
        if not user and room_name:
            session = CallSession.objects.filter(room_name=room_name).first()
            if session:
                user = session.user

        if not user:
            logger.warning(f"[Inngest Tool Log] Could not resolve user for tool log: {tool_name} (user_id={user_id})")
            return None

        # 2. Resolve matching CallSession if room_name provided
        call_session = None
        if room_name:
            call_session = CallSession.objects.filter(room_name=room_name).order_by("-started_at").first()

        # 3. Create AgentToolCallLog
        log_obj = AgentToolCallLog.objects.create(
            user=user,
            call_session=call_session,
            room_name=room_name,
            caller_phone=data.get("caller_phone") or (call_session.caller_phone if call_session else ""),
            tool_name=tool_name,
            tool_type=data.get("tool_type") or "mcp",
            server_name=data.get("server_name") or "",
            server_url=data.get("server_url") or "",
            arguments=data.get("arguments") or {},
            status=status,
            error_type=data.get("error_type") or "none",
            error_message=data.get("error_message") or "",
            response_preview=data.get("response_preview") or "",
            raw_response=data.get("raw_response") or {},
            execution_time_ms=int(data.get("execution_time_ms") or 0)
        )
        return log_obj.id

    log_id = await sync_to_async(_save_log)()
    if log_id:
        logger.info(f"[Inngest Tool Log] Successfully saved AgentToolCallLog #{log_id} for {tool_name}")
        return {"status": "created", "log_id": log_id, "tool_name": tool_name}
    return {"status": "skipped", "reason": "user_not_found"}


all_agent_inngest_functions = [fn_log_agent_tool_call]
