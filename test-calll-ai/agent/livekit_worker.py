"""Official LiveKit Agents Worker for AI Voice Telephony.

Utilizes LiveKit Agents 1.8+ with Gemini 3.8 Multimodal Live API, Native Agent Dispatch,
multi-tenant knowledge RAG, customer memory, dynamic MCP tools, and real-time Centrifugo monitoring.
"""
import asyncio
import json
import os
import sys
import time
from typing import Dict, Any, Optional, List

from livekit import api, rtc
from livekit.agents import (
    JobContext,
    JobProcess,
    WorkerOptions,
    WorkerType,
    cli,
    llm,
)
from livekit.agents.voice import (
    AgentSession,
    Agent,
    UserInputTranscribedEvent,
    ConversationItemAddedEvent,
    AgentStateChangedEvent,
)
from livekit.plugins.google.realtime import RealtimeModel

from agent.config import (
    logger,
    LIVEKIT_INTERNAL_URL,
    LIVEKIT_API_KEY,
    LIVEKIT_API_SECRET,
    GEMINI_API_KEY,
    GEMINI_LIVE_MODEL,
    REDIS_URL,
)
from agent.clients.centrifugo_client import notify_centrifugo_async
from agent.clients.django_client import (
    fetch_agent_bootstrap_async,
    parse_mcp_servers_from_bootstrap,
    parse_customer_memory_from_bootstrap,
    parse_active_profile_from_bootstrap,
    query_knowledge_base_async,
    lookup_customer_memory_async,
    save_call_session_and_update_memory_async,
)
from agent.clients.mcp_client import execute_mcp_tool_call
from agent.prompts import build_dynamic_system_instruction, generate_welcome_greeting
from agent.transfer.transfer_bot import execute_ai_transfer_and_hold
from agent.queue_manager import run_queue_session
from agent.session.memory import distill_and_update_memory


async def entrypoint(ctx: JobContext):
    """Entrypoint called for each assigned room / job in an isolated worker process."""
    room_name = ctx.room.name
    channel_name = f"rooms:{room_name}"
    job_id = ctx.job.id if ctx.job else "direct"
    logger.info(f"==> [LiveKit Agent] New Job assigned (job_id={job_id}, room={room_name})")

    # 1. Parse Metadata from Job or Room
    raw_meta = (ctx.job.metadata if ctx.job else "") or (ctx.room.metadata or "")
    payload: Dict[str, Any] = {}
    if raw_meta:
        try:
            payload = json.loads(raw_meta) if isinstance(raw_meta, str) else dict(raw_meta)
        except Exception as e:
            logger.warning(f"Could not parse job metadata as JSON: {e} (raw: {raw_meta})")

    user_id = payload.get("user_id")
    caller_phone = payload.get("caller_phone") or "web_dashboard"
    profile_data = payload.get("profile")
    is_queue = payload.get("is_queue", False)
    queue_data = payload.get("queue_data")
    is_outbound_ai = payload.get("is_outbound_ai", False)
    call_goal = payload.get("call_goal")
    destination_phone = payload.get("destination_phone")
    if is_outbound_ai and destination_phone:
        caller_phone = destination_phone
    is_off_hours = payload.get("is_off_hours", False)
    off_hours_data = payload.get("off_hours_data") or {}

    # If user_id wasn't in metadata, try extracting from room pattern (e.g. room_call_<user_id>_... or ext_<user_id>)
    if not user_id and "_" in room_name:
        parts = room_name.split("_")
        for part in parts:
            if part.isdigit() and len(part) <= 6:
                try:
                    user_id = int(part)
                    break
                except ValueError:
                    pass

    # 2. Check for Queue Session delegation
    if is_queue:
        logger.info(f"[LiveKit Agent] Delegating room '{room_name}' to queue manager...")
        await run_queue_session(
            room_name=room_name,
            user_id=user_id,
            caller_phone=caller_phone,
            queue_data=queue_data,
        )
        return

    # Notify dashboard of initialization
    await notify_centrifugo_async(
        channel_name,
        "agent_starting",
        "جاري تهيئة المساعدة الصوتية وتجهيز قاعدة المستندات والإجراءات عبر LiveKit Agents...",
    )

    # 3. Fetch unified Bootstrap bundle from Django
    bootstrap: Dict[str, Any] = {}
    if user_id:
        try:
            bootstrap = await fetch_agent_bootstrap_async(user_id, caller_phone)
        except Exception as err:
            logger.error(f"Failed to fetch agent bootstrap for user {user_id}: {err}")

    # Resolve active Gemini API key: prioritize Django SystemSetting from bootstrap, fallback to .env
    active_api_key = (bootstrap.get("gemini_api_key") or "").strip() or GEMINI_API_KEY
    if not active_api_key or active_api_key.startswith("your_"):
        err = "GEMINI_API_KEY is not configured in Django Admin (SystemSetting) or .env"
        logger.error(err)
        await notify_centrifugo_async(channel_name, "agent_error", err)
        return

    # Parse profile & voice settings
    active_profile = None
    if profile_data and isinstance(profile_data, dict):
        active_profile = profile_data
    elif user_id:
        active_profile = parse_active_profile_from_bootstrap(bootstrap)
    if not active_profile:
        active_profile = parse_active_profile_from_bootstrap({})

    chosen_voice = active_profile.get("voice_name") or "Aoede"
    chosen_model = os.getenv("GEMINI_LIVE_MODEL", GEMINI_LIVE_MODEL) or "gemini-3.8-live"

    logger.info(
        f"[LiveKit Agent] Using Gemini model '{chosen_model}', voice '{chosen_voice}', "
        f"language '{active_profile.get('language', 'arabic')}' for user {user_id}"
    )

    # Parse memory & knowledge
    memory_data = parse_customer_memory_from_bootstrap(bootstrap, caller_phone) if user_id else {}
    memory_card_text = memory_data.get("card_text", "")
    call_queues = bootstrap.get("call_queues", []) if bootstrap else []
    knowledge_manifest = bootstrap.get("knowledge_manifest", []) if bootstrap else []
    live_context = bootstrap.get("live_context") or {}

    outbound_context = None
    if is_outbound_ai and call_goal:
        outbound_context = {
            "call_goal": call_goal,
            "destination_phone": destination_phone or caller_phone,
        }

    # Build system instruction prompt
    system_instruction_text = build_dynamic_system_instruction(
        active_profile,
        memory_card_text,
        queue_context=None,
        outbound_context=outbound_context,
        call_queues=call_queues,
        live_context=live_context,
        knowledge_manifest=knowledge_manifest,
    )

    # 4. Connect to Room
    await ctx.connect()
    logger.info(f"[LiveKit Agent] Connected to LiveKit room '{room_name}'")

    # 5. Handle Off-Hours if applicable
    if is_off_hours:
        logger.info(f"[LiveKit Agent] Handling off-hours call for room '{room_name}'")
        ai_msg = off_hours_data.get("ai_message") or "مرحباً بك، نتأسف لاتصالك خارج أوقات العمل الرسمية. نسعد بتواصلك معنا مجدداً خلال أوقات العمل."
        await notify_centrifugo_async(
            channel_name,
            "off_hours_call",
            "المكالمة واردة خارج أوقات العمل الرسمية للمنشأة. جاري تطبيق خطة الرد المحددة...",
        )
        # Initialize basic model and speak message
        off_hours_model = RealtimeModel(
            model=chosen_model,
            api_key=active_api_key,
            voice=chosen_voice,
        )
        off_hours_session = AgentSession(llm=off_hours_model)
        off_hours_agent = Agent(instructions="Speak the provided off-hours greeting politely.")
        await off_hours_session.start(off_hours_agent, room=ctx.room)
        await off_hours_session.say(ai_msg)
        await asyncio.sleep(4.0)
        await ctx.room.disconnect()
        return

    # 6. Build LLM Tools
    tools: List[Any] = []

    # Tool 1: Semantic Knowledge Base Search
    @llm.function_tool(
        description="البحث الدلالي الموثوق في قاعدة المعرفة والمستندات الرسمية للمنشأة. استدعِ هذه الأداة فوراً عند ورود أي سؤال عن خدمات أو سياسات أو أسعار أو معلومات عمل مذكورة في المستندات لاستخراج الإجابة الحقيقية الدقيقة."
    )
    async def search_knowledge_base(query: str = "", **kwargs) -> str:
        """Search tenant knowledge base documents."""
        search_query = str(query or kwargs.get("search_query") or kwargs.get("q") or kwargs.get("question") or "").strip()
        if not user_id:
            return "لا تتوفر مستندات مسجلة لهذا الحساب."
        if not search_query:
            return "يرجى تحديد موضوع السؤال للبحث في المستندات."
        await notify_centrifugo_async(channel_name, "agent_tool_executing", f"جاري البحث في المستندات عن: {search_query}")
        try:
            results = await query_knowledge_base_async(query=search_query, user_id=user_id)
            txt = "\n\n".join(results) if isinstance(results, list) else str(results)
            await notify_centrifugo_async(channel_name, "agent_tool_done", f"تم العثور على معلومات ذات صلة بـ: {search_query}")
            return txt or "لم يتم العثور على نصوص مطابقة في قاعدة المعرفة."
        except Exception as e:
            logger.error(f"Error querying knowledge base: {e}")
            return "لم يتم العثور على معلومات مطابقة في قاعدة المعرفة حالياً."

    tools.append(search_knowledge_base)

    # Tool 2: Customer Memory Lookup
    @llm.function_tool(
        description="البحث في سجل وذاكرة العملاء بالاسم أو برقم الهاتف لاسترجاع بيانات العميل وتفضيلاته وعنوانه وسجل تواصله السابق مع المؤسسة لمساعدته بشكل مخصص."
    )
    async def lookup_customer_memory(identifier: str = "", **kwargs) -> str:
        """Lookup customer memory profile."""
        search_id = str(identifier or kwargs.get("phone") or kwargs.get("phone_number") or kwargs.get("name") or kwargs.get("query") or "").strip()
        if not user_id:
            return "سجل العملاء غير مفعل."
        if not search_id:
            return "يرجى تحديد اسم العميل أو رقم هاتفه للبحث."
        await notify_centrifugo_async(channel_name, "agent_tool_executing", f"جاري استرجاع بيانات العميل: {search_id}")
        try:
            mem = await lookup_customer_memory_async(user_id=user_id, query=search_id)
            card = mem.get("card_text") or "لا توجد بيانات سابقة مسجلة لهذا العميل."
            await notify_centrifugo_async(channel_name, "agent_tool_done", "تم استرجاع ملف العميل بنجاح")
            return card
        except Exception as e:
            logger.error(f"Error looking up customer memory: {e}")
            return "لا توجد بيانات سابقة مسجلة لهذا العميل."

    tools.append(lookup_customer_memory)

    # Tool 3: Department Transfer (if tenant has call queues)
    if call_queues:
        q_codes = [str(q["code"]) for q in call_queues]
        q_descriptions = " | ".join(
            [f"{q['name']} ({q['code']})" for q in call_queues]
        )

        @llm.function_tool(
            description=f"تحويل المكالمة الجارية إلى أحد طوابير الموظفين البشريين التابعة للمؤسسة. الأقسام المتاحة: [{q_descriptions}]. الأكواد المتاحة: {q_codes}. استدعِ الأداة مع كتابة ملخص سبب التحويل في حقل reason."
        )
        async def transfer_to_queue(queue_code: str = "", reason: str = "", **kwargs) -> str:
            """Transfer caller to human department queue."""
            q_code = str(queue_code or kwargs.get("queue") or kwargs.get("code") or kwargs.get("department") or "").strip()
            r_reason = str(reason or kwargs.get("note") or kwargs.get("summary") or "").strip()
            await notify_centrifugo_async(channel_name, "agent_tool_executing", f"جاري تحويل المكالمة إلى قسم ({q_code})...")
            try:
                await execute_ai_transfer_and_hold(
                    room_name=ctx.room.name,
                    user_id=user_id or 1,
                    queue_code=q_code,
                    reason=r_reason,
                    caller_phone=caller_phone,
                )
                await notify_centrifugo_async(channel_name, "agent_transferring", f"تم تحويل المكالمة بنجاح إلى قسم ({q_code})")
                return "تم تحويل المكالمة بنجاح، جاري وضع العميل على الانتظار وتحويله لممثل القسم."
            except Exception as e:
                logger.error(f"Error transferring call to queue {q_code}: {e}")
                return "تعذر إتمام التحويل حالياً، يرجى المحاولة لاحقاً."

        tools.append(transfer_to_queue)

    # Tool 4: Dynamic Tenant MCP Tools
    mcp_servers_list = parse_mcp_servers_from_bootstrap(bootstrap) if user_id else []
    for s in mcp_servers_list:
        s_url = s.get("server_url")
        s_token = s.get("auth_token", "")
        for t in s.get("tools", []):
            t_name = t.get("name")
            t_desc = t.get("description", "")
            if not t_name:
                continue

            def make_mcp_wrapper(name: str, url: str, token: str, desc: str):
                @llm.function_tool(name=name, description=desc)
                async def mcp_tool(**kwargs) -> str:
                    await notify_centrifugo_async(channel_name, "agent_tool_executing", f"جاري تنفيذ الإجراء ({name})...")
                    try:
                        res = await execute_mcp_tool_call(server_url=url, auth_token=token, tool_name=name, arguments=kwargs)
                        await notify_centrifugo_async(channel_name, "agent_tool_done", f"تم إكمال الإجراء ({name})")
                        return json.dumps(res, ensure_ascii=False) if isinstance(res, (dict, list)) else str(res)
                    except Exception as ex:
                        logger.error(f"Error calling MCP tool {name}: {ex}")
                        return f"خطأ أثناء استدعاء الأداة {name}: {ex}"

                return mcp_tool

            tools.append(make_mcp_wrapper(t_name, s_url, s_token, t_desc))

    logger.info(f"[LiveKit Agent] Initialized {len(tools)} tools for room '{room_name}'")

    # 7. Setup RealtimeModel with Gemini 3.8 Live API
    model = RealtimeModel(
        model=chosen_model,
        api_key=active_api_key,
        voice=chosen_voice,
        instructions=system_instruction_text,
    )

    session = AgentSession(llm=model)
    agent = Agent(instructions=system_instruction_text, tools=tools)

    # 8. Transcripts & Conversation State Tracking
    conversation_history: List[Dict[str, str]] = []
    call_start_time = time.time()

    def on_user_transcript(ev: UserInputTranscribedEvent):
        if ev.is_final and ev.transcript:
            text = ev.transcript.strip()
            if text:
                conversation_history.append({"role": "user", "text": text})
                asyncio.create_task(
                    notify_centrifugo_async(
                        channel_name,
                        "user_transcript",
                        text,
                        extra={"is_final": True, "created_at": time.time()}
                    )
                )

    def _extract_item_text(item) -> str:
        if not item:
            return ""
        text = getattr(item, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()
        content = getattr(item, "content", None)
        if isinstance(content, str):
            return content.strip()
        elif isinstance(content, list):
            parts = []
            for c in content:
                if isinstance(c, str):
                    parts.append(c)
                elif hasattr(c, "text") and isinstance(c.text, str):
                    parts.append(c.text)
                elif isinstance(c, dict) and "text" in c:
                    parts.append(str(c["text"]))
            return " ".join(parts).strip()
        return ""

    def on_conversation_item(ev: ConversationItemAddedEvent):
        item = getattr(ev, "item", None)
        if item:
            role = getattr(item, "role", "")
            text = _extract_item_text(item)
            if role == "assistant" and text:
                conversation_history.append({"role": "assistant", "text": text})
                asyncio.create_task(
                    notify_centrifugo_async(
                        channel_name,
                        "agent_transcript",
                        text,
                        extra={"is_final": True, "created_at": time.time()}
                    )
                )

    def on_agent_state(ev: AgentStateChangedEvent):
        st = str(getattr(ev, "new_state", getattr(ev, "state", ""))).lower()
        if "speaking" in st:
            asyncio.create_task(notify_centrifugo_async(channel_name, "agent_speaking", "المساعدة الصوتية تتحدث الآن"))
        elif "thinking" in st:
            asyncio.create_task(notify_centrifugo_async(channel_name, "agent_thinking", "المساعدة الصوتية تفكر..."))
        elif "listening" in st or "idle" in st:
            asyncio.create_task(notify_centrifugo_async(channel_name, "agent_listening", "المساعدة الصوتية تستمع إليك"))

    session.on("user_input_transcribed", on_user_transcript)
    session.on("conversation_item_added", on_conversation_item)
    session.on("agent_state_changed", on_agent_state)

    # 9. Register Call Cleanup & Memory Distillation Callback
    async def cleanup_and_distill():
        duration = round(time.time() - call_start_time, 2)
        logger.info(f"[LiveKit Agent] Room '{room_name}' ending. Duration: {duration}s, Turns: {len(conversation_history)}")
        await notify_centrifugo_async(channel_name, "agent_stopped", "انتهت المكالمة الصوتية وجاري حفظ ملخص الجلسة...")

        if user_id:
            dialogue_messages = [
                {"speaker": "user" if item.get("role") == "user" else "assistant", "text": item.get("text", "")}
                for item in conversation_history
            ]
            asyncio.create_task(
                distill_and_update_memory(
                    user_id=user_id,
                    room_name=room_name,
                    started_at=call_start_time,
                    messages=dialogue_messages,
                    current_profile=memory_data.get("card_data") or active_profile or {},
                    caller_phone=caller_phone,
                    genai_client=None,
                    outbound_context=outbound_context,
                    api_key=active_api_key,
                )
            )

    ctx.add_shutdown_callback(cleanup_and_distill)

    # 10. Start Session inside LiveKit Room
    await session.start(agent, room=ctx.room)
    logger.info(f"[LiveKit Agent] AgentSession active for room '{room_name}'")
    await notify_centrifugo_async(
        channel_name,
        "agent_ready",
        "المساعدة الصوتية وقاعدة المستندات جاهزة للاستماع إليك الآن!",
    )

    # 11. Proactive Welcome Greeting
    greeting_text = generate_welcome_greeting(active_profile, memory_card_text)
    try:
        # Wait for human caller to connect (up to 15 seconds)
        participant = await ctx.wait_for_participant()
        if participant:
            logger.info(f"[LiveKit Agent] Human participant '{participant.identity}' joined. Speaking greeting: {greeting_text}")
            await session.say(greeting_text)
    except Exception as e:
        logger.debug(f"Proactive greeting wait ended or participant already connected: {e}")
        try:
            await session.say(greeting_text)
        except Exception:
            pass


def prewarm(proc: JobProcess):
    """Preload heavy dependencies in worker processes to eliminate latency stalls on call dispatch."""
    try:
        import livekit.agents.llm.async_toolset  # noqa: F401
        from livekit.plugins.google.realtime import RealtimeModel  # noqa: F401
    except Exception as e:
        logger.debug(f"Prewarm import note: {e}")


def main():
    """Main worker server process runner using LiveKit cli."""
    logger.info("==========================================================")
    logger.info("   Starting Official LiveKit Agents Worker Daemon        ")
    logger.info(f"   Model: {os.getenv('GEMINI_LIVE_MODEL', GEMINI_LIVE_MODEL)} (Audio-to-Audio)  ")
    logger.info(f"   LiveKit Internal URL: {LIVEKIT_INTERNAL_URL}          ")
    logger.info("   Worker Pool: Multi-Process Isolated (Native Pool)      ")
    logger.info("==========================================================")

    # Default to 'start' CLI command if no subcommand provided
    if len(sys.argv) == 1:
        sys.argv.append("start")

    # Force internal container URL for worker server connection
    os.environ["LIVEKIT_URL"] = LIVEKIT_INTERNAL_URL

    opts = WorkerOptions(
        entrypoint_fnc=entrypoint,
        prewarm_fnc=prewarm,
        agent_name="ai-agent",
        worker_type=WorkerType.ROOM,
        ws_url=LIVEKIT_INTERNAL_URL,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET,
    )
    cli.run_app(opts)


if __name__ == "__main__":
    main()
