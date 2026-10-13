"""Official LiveKit Agents Worker for AI Voice Telephony.

Utilizes LiveKit Agents 1.8+ with Gemini 3.8 Multimodal Live API, Native Agent Dispatch,
multi-tenant knowledge RAG, customer memory, dynamic MCP tools, and real-time Centrifugo monitoring.
"""
import asyncio
import json
import os
import sys
import time
import re
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
    AgentFalseInterruptionEvent,
    ErrorEvent,
)
from livekit.plugins.google.realtime import RealtimeModel
from google.genai import types as genai_types

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
    send_whatsapp_message_async,
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

    # If user_id wasn't in metadata, check Redis cache set by dispatch_agent_to_room for SIP/inbound calls
    if not user_id:
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(REDIS_URL, decode_responses=True)
            cached_meta = await r.get(f"room_job_meta:{room_name}")
            if cached_meta:
                cached_data = json.loads(cached_meta)
                user_id = cached_data.get("user_id") or user_id
                if not profile_data:
                    profile_data = cached_data.get("profile")
                if not caller_phone or caller_phone == "web_dashboard":
                    caller_phone = cached_data.get("caller_phone") or caller_phone
            await r.aclose()
        except Exception as r_err:
            logger.debug(f"Redis room_job_meta lookup skipped: {r_err}")

    caller_ext = None
    if "__" in room_name:
        try:
            cand = room_name.split("__", 1)[1].split("_")[0]
            if cand:
                caller_ext = cand
        except Exception:
            pass

    # Fallback: extract from room pattern (strictly excluding 999 service extension)
    if not user_id and "_" in room_name:
        parts = room_name.split("_")
        for part in parts:
            if part.isdigit() and len(part) <= 6 and part != "999":
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
    try:
        bootstrap = await fetch_agent_bootstrap_async(
            user_id=user_id,
            caller_phone=caller_phone,
            room_name=room_name,
            caller_extension=caller_ext or ""
        )
        if not user_id and bootstrap.get("user_id"):
            user_id = bootstrap.get("user_id")
            logger.info(f"[LiveKit Agent] Auto-resolved user_id={user_id} from Django bootstrap for room '{room_name}'")
    except Exception as err:
        logger.error(f"Failed to fetch agent bootstrap for room '{room_name}': {err}")

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

    # Discover available tools metadata for the dynamic system instruction manifest
    available_tools_meta: List[Dict[str, Any]] = [
        {
            "name": "search_knowledge_base",
            "description": "البحث الدلالي الموثوق في مستندات وقاعدة معرفة المنشأة الرسمية عند ورود أي سؤال عن خدمات أو أسعار أو سياسات غير مذكورة في الذاكرة اللحظية."
        },
        {
            "name": "lookup_customer_memory",
            "description": "استرجاع ملف وبيانات وسجل العميل وتفضيلاته بالاسم أو برقم هاتفه لمساعدته بشكل مخصص."
        },
        {
            "name": "send_whatsapp_message",
            "description": "إرسال رسالة نصية أو رابط المنيو أو تفاصيل الطلب أو أي معلومات يطلبها العميل على الواتساب أثناء المكالمة لرقم هاتفه تلقائياً."
        }
    ]
    if call_queues:
        available_tools_meta.append({
            "name": "transfer_to_queue",
            "description": "تحويل المكالمة لطابور خدمة العملاء البشري عند طلب العميل التحدث مع موظف بشري أو قسم معين."
        })

    mcp_servers_list = parse_mcp_servers_from_bootstrap(bootstrap) if user_id else []
    for s in mcp_servers_list:
        for t in s.get("tools", []):
            if t.get("name"):
                available_tools_meta.append({
                    "name": t["name"],
                    "description": t.get("description", f"تنفيذ إجراء {t['name']}")
                })

    # Build system instruction prompt
    system_instruction_text = build_dynamic_system_instruction(
        active_profile,
        memory_card_text,
        queue_context=None,
        outbound_context=outbound_context,
        call_queues=call_queues,
        live_context=live_context,
        knowledge_manifest=knowledge_manifest,
        available_tools=available_tools_meta,
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
        off_hours_agent = Agent(instructions="You are an automated phone receptionist answering outside business hours. Apologize politely to the caller in Arabic and speak the provided message clearly.")
        await off_hours_session.start(off_hours_agent, room=ctx.room)
        try:
            handle = off_hours_session.generate_reply(
                instructions=f"انطق رسالة الاعتذار التالية للمتصل خارج أوقات العمل بدقة ولطف واختم: '{ai_msg}'"
            )
            await handle
        except Exception as e:
            logger.error(f"Error speaking off-hours greeting: {e}")
        await asyncio.sleep(4.0)
        await ctx.room.disconnect()
        return

    # 6. Build LLM Tools
    tools: List[Any] = []

    # Tool 1: Semantic Knowledge Base Search
    @llm.function_tool(
        description="البحث الدلالي الموثوق في قاعدة المعرفة والمستندات الرسمية للمنشأة. استدعِ هذه الأداة فوراً عند ورود أي سؤال عن خدمات أو سياسات أو أسعار أو معلومات عمل مذكورة في المستندات لاستخراج الإجابة الحقيقية الدقيقة."
    )
    async def search_knowledge_base(query: str) -> str:
        """Search tenant knowledge base documents.

        Args:
            query: موضوع أو سؤال البحث في المستندات.
        """
        if not user_id:
            return "لا تتوفر مستندات مسجلة لهذا الحساب."
        search_query = str(query or "").strip()
        if not search_query:
            return "يرجى تحديد موضوع السؤال للبحث في المستندات."
        asyncio.create_task(notify_centrifugo_async(channel_name, "agent_tool_executing", f"جاري البحث في المستندات عن: {search_query}"))
        try:
            results = await asyncio.wait_for(
                query_knowledge_base_async(query=search_query, user_id=user_id),
                timeout=4.5
            )
            txt = "\n\n".join(results) if isinstance(results, list) else str(results)
            asyncio.create_task(notify_centrifugo_async(channel_name, "agent_tool_done", f"تم العثور على معلومات ذات صلة بـ: {search_query}"))
            return txt or "لم يتم العثور على نصوص مطابقة في قاعدة المعرفة."
        except asyncio.TimeoutError:
            logger.warning(f"Timeout querying knowledge base for '{search_query}'")
            return "جاري استكمال البحث في المستندات، تفضل بسؤالك التالي."
        except Exception as e:
            logger.error(f"Error querying knowledge base: {e}")
            return "لم يتم العثور على معلومات مطابقة في قاعدة المعرفة حالياً."

    tools.append(search_knowledge_base)

    # Tool 2: Customer Memory Lookup
    @llm.function_tool(
        description="البحث في سجل وذاكرة العملاء بالاسم أو برقم الهاتف لاسترجاع بيانات العميل وتفضيلاته وعنوانه وسجل تواصله السابق مع المؤسسة لمساعدته بشكل مخصص."
    )
    async def lookup_customer_memory(identifier: str) -> str:
        """Lookup customer memory profile.

        Args:
            identifier: اسم العميل أو رقم هاتفه.
        """
        if not user_id:
            return "سجل العملاء غير مفعل."
        search_id = str(identifier or "").strip()
        if not search_id:
            return "يرجى تحديد اسم العميل أو رقم هاتفه للبحث."
        asyncio.create_task(notify_centrifugo_async(channel_name, "agent_tool_executing", f"جاري استرجاع بيانات العميل: {search_id}"))
        try:
            mem = await asyncio.wait_for(
                lookup_customer_memory_async(user_id=user_id, query=search_id),
                timeout=4.0
            )
            card = mem.get("card_text") or "لا توجد بيانات سابقة مسجلة لهذا العميل."
            asyncio.create_task(notify_centrifugo_async(channel_name, "agent_tool_done", "تم استرجاع ملف العميل بنجاح"))
            return card
        except asyncio.TimeoutError:
            logger.warning(f"Timeout looking up customer memory for '{search_id}'")
            return "لا توجد بيانات سابقة مسجلة لهذا العميل."
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
        async def transfer_to_queue(queue_code: str, reason: str = "") -> str:
            """Transfer caller to human department queue.

            Args:
                queue_code: كود القسم المطلوب تحويل المكالمة إليه.
                reason: سبب تحويل المكالمة.
            """
            q_code = str(queue_code or "").strip()
            r_reason = str(reason or "").strip()
            asyncio.create_task(notify_centrifugo_async(channel_name, "agent_tool_executing", f"جاري تحويل المكالمة إلى قسم ({q_code})..."))
            try:
                await asyncio.wait_for(
                    execute_ai_transfer_and_hold(
                        room_name=ctx.room.name,
                        user_id=user_id or 1,
                        queue_code=q_code,
                        reason=r_reason,
                        caller_phone=caller_phone,
                    ),
                    timeout=4.0
                )
                asyncio.create_task(notify_centrifugo_async(channel_name, "agent_transferring", f"تم تحويل المكالمة بنجاح إلى قسم ({q_code})"))
                return "تم تحويل المكالمة بنجاح، جاري وضع العميل على الانتظار وتحويله لممثل القسم."
            except asyncio.TimeoutError:
                logger.warning(f"Timeout transferring call to queue {q_code}")
                return "جاري إتمام التحويل، يرجى الانتظار لحظات."
            except Exception as e:
                logger.error(f"Error transferring call to queue {q_code}: {e}")
                return "تعذر إتمام التحويل حالياً، يرجى المحاولة لاحقاً."

        tools.append(transfer_to_queue)

    # Tool 4: Send WhatsApp Message to Caller
    @llm.function_tool(
        description=(
            "إرسال رسالة نصية أو رابط المنيو أو تفاصيل الطلب أو أي معلومات يطلبها العميل على الواتساب أثناء المكالمة. "
            "إذا لم يحدد العميل رقماً آخر صراحة، يتم الإرسال تلقائياً إلى رقم هاتفه المتصل منه. "
            "أخبر العميل فوراً بعد استدعاء الأداة بأن الرسالة أو الرابط وصله الآن على الواتساب."
        )
    )
    async def send_whatsapp_message(message: str, phone: Optional[str] = None) -> str:
        """Send a WhatsApp message or link to caller.

        Args:
            message: نص الرسالة أو الرابط المراد إرساله للعميل على الواتساب.
            phone: رقم هاتف العميل (اختياري، إن لم يُحدد يتم الإرسال تلقائياً لرقم المتصل).
        """
        if not user_id:
            return "تعذر إرسال الرسالة، حساب المنشأة غير محدد."
        target_phone = str(phone or "").strip() or str(caller_phone or "").strip()
        digits = re.sub(r"\D", "", target_phone)
        if len(digits) < 7:
            return (
                "لم يتوفر رقم هاتف محمول صالح للعميل لإرسال الواتساب إليه. "
                "اطلب من العميل بلباقة أن يمليك رقم الواتساب أو رقم الجوال الخاص به لترسل له رابط المنيو فوراً."
            )

        if digits.startswith("01") and len(digits) == 11:
            target_phone = "20" + digits[1:]
        elif digits.startswith("05") and len(digits) == 10:
            target_phone = "966" + digits[1:]
        elif digits.startswith("00"):
            target_phone = digits[2:]
        else:
            target_phone = digits

        clean_msg = str(message or "").strip()
        if not clean_msg:
            return "نص الرسالة فارغ، يرجى تحديد ما تريد إرساله."

        # Ensure digital menu link is included if user requested menu
        d_menu_url = (live_context.get("digital_menu_url") or "").strip() if live_context else ""
        if d_menu_url and ("منيو" in clean_msg or "قائمة" in clean_msg or "menu" in clean_msg.lower()) and "http" not in clean_msg:
            clean_msg += f"\nرابط قائمة الطعام الإلكترونية:\n{d_menu_url}"

        asyncio.create_task(notify_centrifugo_async(channel_name, "agent_tool_executing", f"جاري إرسال رسالة واتساب إلى ({target_phone})..."))
        try:
            res = await asyncio.wait_for(
                send_whatsapp_message_async(user_id=user_id, phone=target_phone, message=clean_msg),
                timeout=6.0
            )
            if not res or res.get("status") == "error" or not res.get("ok"):
                err_msg = res.get("error") or res.get("message") or "تعذر الإرسال"
                logger.error(f"Failed to send WhatsApp message to {target_phone}: {err_msg}")
                return f"حدث خطأ أثناء محاولة إرسال رسالة الواتساب إلى ({target_phone}): {err_msg}. اعتذر للعميل واطلب منه التأكد من صحة رقم الواتساب."

            asyncio.create_task(notify_centrifugo_async(channel_name, "agent_tool_done", "تم إرسال رسالة الواتساب بنجاح"))
            return f"تم إرسال الرسالة بنجاح إلى رقم الواتساب ({target_phone}). أخبر العميل بأن الرسالة وصلته الآن على الواتساب."
        except asyncio.TimeoutError:
            logger.warning(f"Timeout sending WhatsApp message to {target_phone}")
            return f"جاري إرسال الرسالة للرقم ({target_phone}) وستصل للعميل خلال لحظات."
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {e}")
            return f"حدث خطأ أثناء محاولة إرسال رسالة الواتساب: {e}"

    tools.append(send_whatsapp_message)

    # Tool 5: Dynamic Tenant MCP Tools
    mcp_servers_list = parse_mcp_servers_from_bootstrap(bootstrap) if user_id else []
    for s in mcp_servers_list:
        s_url = s.get("server_url")
        s_token = s.get("auth_token", "")
        for t in s.get("tools", []):
            t_name = t.get("name")
            t_desc = t.get("description", "")
            t_schema = t.get("parameters") or t.get("inputSchema") or {}
            if not t_name:
                continue

            def make_mcp_wrapper(name: str, url: str, token: str, desc: str, input_schema: Any):
                param_dict = input_schema if isinstance(input_schema, dict) and input_schema.get("type") == "object" else {"type": "object", "properties": {}}
                raw_schema = {
                    "name": name,
                    "description": desc or f"Execute tool {name}",
                    "parameters": param_dict
                }
                @llm.function_tool(raw_schema=raw_schema)
                async def mcp_tool(raw_arguments: dict) -> str:
                    raw_args = dict(raw_arguments) if isinstance(raw_arguments, dict) else {}
                    if caller_phone and caller_phone != "web_dashboard" and isinstance(raw_args, dict):
                        props = (param_dict.get("properties") or {}) if isinstance(param_dict, dict) else {}
                        for p_key in ("phone", "customer_phone", "phone_number"):
                            if p_key in props and not raw_args.get(p_key):
                                raw_args[p_key] = caller_phone
                                break
                    asyncio.create_task(notify_centrifugo_async(channel_name, "agent_tool_executing", f"جاري تنفيذ الإجراء ({name})..."))
                    try:
                        res = await asyncio.wait_for(
                            execute_mcp_tool_call(server_url=url, auth_token=token, tool_name=name, arguments=raw_args),
                            timeout=10.0
                        )
                        asyncio.create_task(notify_centrifugo_async(channel_name, "agent_tool_done", f"تم إكمال الإجراء ({name})"))
                        if isinstance(res, dict):
                            if "result" in res and res.get("result"):
                                if res.get("is_error"):
                                    err_msg = res.get("error_message") or res.get("result")
                                    return f"تعذر تنفيذ الإجراء ({name}): {err_msg}"
                                return str(res.get("result"))
                            return json.dumps(res, ensure_ascii=False)
                        return str(res)
                    except asyncio.TimeoutError:
                        logger.warning(f"Timeout executing MCP tool {name}")
                        return f"استغرق تنفيذ الإجراء ({name}) وقتاً أطول من المتوقع، جاري متابعته مع الفرع."
                    except Exception as ex:
                        logger.error(f"Error calling MCP tool {name}: {ex}")
                        return f"خطأ أثناء استدعاء الأداة {name}: {ex}"

                return mcp_tool

            tools.append(make_mcp_wrapper(t_name, s_url, s_token, t_desc, t_schema))

    logger.info(f"[LiveKit Agent] Initialized {len(tools)} tools for room '{room_name}'")

    # 7. Setup RealtimeModel with Gemini 3.8 Live API, Session Resumption, and Sliding Window Compression
    resumption_cfg = genai_types.SessionResumptionConfig(transparent=True)
    compression_cfg = genai_types.ContextWindowCompressionConfig(
        trigger_tokens=25000,
        sliding_window=genai_types.SlidingWindow(target_tokens=15000),
    )
    input_transcription_cfg = genai_types.AudioTranscriptionConfig()
    output_transcription_cfg = genai_types.AudioTranscriptionConfig()

    model = RealtimeModel(
        model=chosen_model,
        api_key=active_api_key,
        voice=chosen_voice,
        instructions=system_instruction_text,
        session_resumption=resumption_cfg,
        context_window_compression=compression_cfg,
        input_audio_transcription=input_transcription_cfg,
        output_audio_transcription=output_transcription_cfg,
    )

    session = AgentSession(
        llm=model,
        use_tts_aligned_transcript=False,
        turn_handling={
            "interruption": {
                "enabled": True,
                "min_duration": 0.3,
                "min_words": 0,
                "resume_false_interruption": True,
            }
        },
    )
    agent = Agent(instructions=system_instruction_text, tools=tools)

    # 8. Transcripts & Conversation State Tracking
    conversation_history: List[Dict[str, str]] = []
    call_start_time = time.time()
    call_active = True

    turn_tracker = {
        "pending_reply": False,
        "last_user_turn_ts": 0.0,
        "last_user_text": "",
        "assistant_spoke_in_turn": False,
    }

    def on_user_transcript(ev: UserInputTranscribedEvent):
        if ev.is_final and ev.transcript:
            text = ev.transcript.strip()
            if text:
                turn_tracker["pending_reply"] = True
                turn_tracker["last_user_turn_ts"] = time.time()
                turn_tracker["last_user_text"] = text
                turn_tracker["assistant_spoke_in_turn"] = False

                # Quiet in-memory tracking for end-of-call memory distillation (Zero live network/Event Loop overhead)
                conversation_history.append({"role": "user", "text": text})

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
                turn_tracker["pending_reply"] = False
                turn_tracker["assistant_spoke_in_turn"] = True
                # Quiet in-memory tracking for end-of-call memory distillation (Zero live network/Event Loop overhead)
                conversation_history.append({"role": "assistant", "text": text})

    def on_agent_state(ev: AgentStateChangedEvent):
        st = str(getattr(ev, "new_state", getattr(ev, "state", ""))).lower()
        if "speaking" in st:
            turn_tracker["pending_reply"] = False
            turn_tracker["assistant_spoke_in_turn"] = True
            asyncio.create_task(notify_centrifugo_async(channel_name, "agent_speaking", "المساعدة الصوتية تتحدث الآن"))
        elif "thinking" in st:
            asyncio.create_task(notify_centrifugo_async(channel_name, "agent_thinking", "المساعدة الصوتية تفكر..."))
        elif "listening" in st or "idle" in st:
            asyncio.create_task(notify_centrifugo_async(channel_name, "agent_listening", "المساعدة الصوتية تستمع إليك"))

    def on_false_interruption(ev: AgentFalseInterruptionEvent):
        logger.info(f"[LiveKit Agent] False interruption detected in room '{room_name}'. Audio playback restored.")

    def on_agent_error(ev: ErrorEvent):
        logger.warning(f"[LiveKit Agent] Voice agent error event in room '{room_name}': {ev}")

    session.on("user_input_transcribed", on_user_transcript)
    session.on("conversation_item_added", on_conversation_item)
    session.on("agent_state_changed", on_agent_state)
    session.on("agent_false_interruption", on_false_interruption)
    session.on("error", on_agent_error)

    # Background Watchdog: Recovers from empty model responses / silent drops on barge-in
    async def silent_drop_watchdog():
        while call_active:
            await asyncio.sleep(0.5)
            if not turn_tracker.get("pending_reply"):
                continue
            idle_delta = time.time() - turn_tracker.get("last_user_turn_ts", time.time())
            current_st = str(getattr(session, "agent_state", "")).lower()
            if idle_delta >= 3.8 and ("idle" in current_st or "listening" in current_st) and not turn_tracker.get("assistant_spoke_in_turn"):
                logger.warning(f"[Watchdog] Detected silent drop/empty response after {idle_delta:.1f}s for '{turn_tracker.get('last_user_text')}'. Nudging agent...")
                turn_tracker["pending_reply"] = False
                turn_tracker["assistant_spoke_in_turn"] = True

                dialect = str(active_profile.get("dialect", "egyptian")).lower()
                recovery_nudge = "معاك يا فندم، سامعك اتفضل."
                if "saudi" in dialect or "gulf" in dialect:
                    recovery_nudge = "سمّ آمرني طال عمرك، أسمعك تفضل."
                elif "levantine" in dialect:
                    recovery_nudge = "معك يا غالي، عم بسمعك تفضل."

                try:
                    handle = session.generate_reply(
                        instructions=f"قل للمتصل بنبرة هادئة ومؤدبة: '{recovery_nudge}'"
                    )
                    await handle
                except Exception as ex:
                    logger.debug(f"[Watchdog] Failed to generate recovery nudge: {ex}")

    watchdog_task = asyncio.create_task(silent_drop_watchdog())

    # 9. Register Call Cleanup & Memory Distillation Callback
    async def cleanup_and_distill():
        nonlocal call_active
        call_active = False
        watchdog_task.cancel()
        duration = round(time.time() - call_start_time, 2)
        logger.info(f"[LiveKit Agent] Room '{room_name}' ending. Duration: {duration}s, Turns: {len(conversation_history)}")
        await notify_centrifugo_async(channel_name, "agent_stopped", "انتهت المكالمة الصوتية وجاري حفظ ملخص الجلسة...")

        if user_id:
            dialogue_messages = [
                {"speaker": "user" if item.get("role") == "user" else "assistant", "text": item.get("text", "")}
                for item in conversation_history
            ]
            try:
                await asyncio.wait_for(
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
                    ),
                    timeout=6.0,
                )
            except asyncio.TimeoutError:
                logger.warning(f"[LiveKit Agent] Memory distillation timed out for room '{room_name}'. Saving basic session in Django...")
                lines = [f"{m['speaker']}: {m['text']}" for m in dialogue_messages]
                await save_call_session_and_update_memory_async(
                    user_id=user_id,
                    room_name=room_name,
                    started_at=call_start_time,
                    transcript_text="\n".join(lines),
                    summary=f"مكالمة صوتية مكتملة ({len(dialogue_messages)} ردود، المدة: {int(duration)} ثانية).",
                    updated_profile=dict(memory_data.get("card_data") or active_profile or {}),
                    caller_phone=caller_phone,
                    outbound_context=outbound_context,
                    duration_seconds=int(duration),
                )
            except Exception as dist_err:
                logger.error(f"[LiveKit Agent] Error finalizing call memory for room '{room_name}': {dist_err}")

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
            handle = session.generate_reply(
                instructions=f"ابدأ المكالمة فوراً بالترحيب بالعميل بنبرة ودودة وواضحة والتزم بالتحية التالية: {greeting_text}"
            )
            await handle
    except Exception as e:
        logger.warning(f"Proactive greeting wait ended or participant already connected: {e}")
        try:
            handle = session.generate_reply(
                instructions=f"ابدأ المكالمة فوراً بالترحيب بالعميل بنبرة ودودة وواضحة والتزم بالتحية التالية: {greeting_text}"
            )
            await handle
        except Exception as e2:
            logger.debug(f"Proactive fallback greeting failed: {e2}")


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
