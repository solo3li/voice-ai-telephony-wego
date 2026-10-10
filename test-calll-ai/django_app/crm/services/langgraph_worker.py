"""
LangGraph Autonomous Omnichannel Employee Worker (24/7 WhatsApp & Cross-Channel AI).

Features:
1. Full 24/7 Conversational WhatsApp Agent (Multi-turn Chat) with Gemini tool calling.
2. Direct Knowledge Base (RAG) search in uploaded documents.
3. Live MCP Tools execution (from UserMCPServer) for orders, branches, menus, CRM, etc.
4. Unified Customer Memory:
   - Call Memory (what happened on the phone)
   - WhatsApp Memory (what happened in the chat)
5. Cross-Channel Continuity: Voice Agent and WhatsApp Agent share the same brain and context.
"""
import logging
import json
import time
from typing import TypedDict, Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone

from langgraph.graph import StateGraph, END
from google import genai
from google.genai import types

from crm.models import CustomerMemory, OmnichannelMessage
from crm.services.evolution_client import send_whatsapp_message
from agents.models import SystemSetting, AgentProfile, UserMCPServer, AgentToolCallLog
from agents.mcp_service import test_mcp_tool_sync

logger = logging.getLogger(__name__)


class FollowupState(TypedDict):
    user_id: int
    phone_number: str
    customer_name: str
    trigger_type: str  # "inbound_whatsapp" | "post_call" | "scheduled_followup"
    call_transcript: Optional[str]
    call_summary: Optional[str]
    inbound_message: Optional[str]
    call_memory: Dict[str, Any]
    whatsapp_memory: Dict[str, Any]
    should_send: bool
    message_text: str
    reason: str
    customer_stage: str
    next_followup_hours: Optional[int]
    tools_invoked: list
    is_sent: bool
    error: Optional[str]


# ==================== Schema Cleaner for Gemini ====================

def clean_gemini_schema(raw: Any) -> Any:
    """Normalize arbitrary JSON Schema into strict Gemini Schema format."""
    if not isinstance(raw, dict):
        return {"type": "OBJECT", "properties": {}}

    cleaned: Dict[str, Any] = {}

    if "type" in raw:
        st = raw["type"]
        if isinstance(st, str):
            st_upper = st.upper()
            if st_upper in ("STRING", "INTEGER", "NUMBER", "BOOLEAN", "ARRAY", "OBJECT"):
                cleaned["type"] = st_upper
        elif isinstance(st, list):
            non_null = [t for t in st if str(t).lower() != "null"]
            if non_null:
                cleaned["type"] = str(non_null[0]).upper()
            if any(str(t).lower() == "null" for t in st):
                cleaned["nullable"] = True

    if "type" not in cleaned:
        if "properties" in raw:
            cleaned["type"] = "OBJECT"
        elif "items" in raw:
            cleaned["type"] = "ARRAY"
        else:
            cleaned["type"] = "STRING"

    if "description" in raw and isinstance(raw["description"], str):
        cleaned["description"] = raw["description"]

    if "enum" in raw and isinstance(raw["enum"], list):
        cleaned["enum"] = [str(e) for e in raw["enum"]]

    if "properties" in raw and isinstance(raw["properties"], dict):
        cleaned_props = {}
        for p_name, p_schema in raw["properties"].items():
            cleaned_props[p_name] = clean_gemini_schema(p_schema)
        cleaned["properties"] = cleaned_props

    if "required" in raw and isinstance(raw["required"], list):
        if "properties" in cleaned:
            cleaned["required"] = [f for f in raw["required"] if f in cleaned["properties"]]
        else:
            cleaned["required"] = list(raw["required"])

    if "items" in raw:
        if isinstance(raw["items"], dict):
            cleaned["items"] = clean_gemini_schema(raw["items"])
        elif isinstance(raw["items"], list) and raw["items"]:
            cleaned["items"] = clean_gemini_schema(raw["items"][0])

    if cleaned.get("type") == "ARRAY" and isinstance(cleaned.get("items"), dict):
        item_dict = cleaned["items"]
        if item_dict.get("type") == "OBJECT" and not item_dict.get("properties"):
            item_dict["properties"] = {
                "name": {"type": "STRING", "description": "اسم العنصر"},
                "value": {"type": "STRING", "description": "القيمة"}
            }
            item_dict["required"] = ["name"]

    return cleaned


# ==================== Tool Execution Helpers ====================

def execute_knowledge_base_search(user_id: int, query: str, top_k: int = 4) -> str:
    """Semantic pgvector + hybrid keyword search in uploaded enterprise documents."""
    from knowledge.models import DocumentChunk
    from pgvector.django import CosineDistance

    api_key = SystemSetting.get_gemini_api_key()
    if not api_key:
        return "قاعدة المعرفة غير مهيأة حالياً (مفتاح API غير متوفر)."

    try:
        client = genai.Client(api_key=api_key)
        embed_res = client.models.embed_content(
            model="gemini-embedding-001",
            contents=query,
            config=types.EmbedContentConfig(output_dimensionality=768)
        )
        query_vec = embed_res.embeddings[0].values if embed_res and embed_res.embeddings else None

        chunks = []
        if query_vec:
            chunks = list(
                DocumentChunk.objects.filter(user_id=user_id)
                .annotate(distance=CosineDistance('embedding', query_vec))
                .filter(distance__lte=0.65)
                .order_by('distance')[:top_k]
            )

        # Keyword fallback
        if not chunks:
            from django.db.models import Q
            stopwords = {'ما', 'هو', 'هي', 'هل', 'من', 'عن', 'في', 'إلى', 'على', 'مع', 'لو', 'عندكم', 'أنا', 'عاوز', 'عايز', 'إيه', 'ليه', 'كام', 'فين'}
            clean_words = [w for w in query.replace('؟', ' ').replace('،', ' ').split() if len(w) >= 3 and w.lower() not in stopwords]
            if clean_words:
                kw_q = Q()
                for word in clean_words[:5]:
                    kw_q |= Q(content__icontains=word)
                chunks = list(DocumentChunk.objects.filter(user_id=user_id).filter(kw_q)[:top_k])

        if not chunks:
            return "لم يتم العثور على أي معلومات متعلقة بهذا السؤال في مستندات المنشأة المرفوعة."

        return "المعلومات الموثقة المستخرجة من مستندات المنشأة:\n" + "\n---\n".join([c.content for c in chunks])
    except Exception as e:
        logger.error(f"Error executing knowledge base search: {e}")
        return f"تعذر البحث في المستندات حالياً: {e}"


def execute_customer_memory_lookup(user_id: int, identifier: str) -> str:
    """Look up customer CRM profile, call memory, and whatsapp history."""
    mem = CustomerMemory.objects.filter(user_id=user_id, phone_number=identifier).first()
    if not mem:
        clean = "".join(ch for ch in identifier if ch.isdigit())
        if len(clean) >= 7:
            mem = CustomerMemory.objects.filter(user_id=user_id, phone_number__endswith=clean[-8:]).first()
    if not mem:
        return f"لم يتم العثور على سجل سابق للعميل بالرقم/الاسم '{identifier}'."
    return mem.format_for_system_instruction()


def load_user_mcp_tools(user_id: int) -> Tuple[List[types.FunctionDeclaration], Dict[str, Dict[str, Any]]]:
    """Discover all active MCP tools for this user."""
    servers = UserMCPServer.objects.filter(user_id=user_id, is_active=True)
    decls = []
    tool_map = {}

    for srv in servers:
        tools = srv.cached_tools or []
        for t in tools:
            name = t.get("name")
            if not name:
                continue
            desc = t.get("description", "")
            raw_schema = t.get("input_schema") or t.get("inputSchema") or t.get("parameters") or {}
            cleaned = clean_gemini_schema(raw_schema)
            decl = types.FunctionDeclaration(
                name=name,
                description=desc,
                parameters=cleaned
            )
            decls.append(decl)
            tool_map[name] = {
                "server_url": srv.server_url,
                "auth_token": srv.auth_token,
                "server_name": srv.name
            }

    return decls, tool_map


def load_assistant_persona(user_id: int) -> str:
    """Load the user's active AgentProfile to maintain unified voice and chat persona."""
    prof = AgentProfile.objects.filter(user_id=user_id, is_active=True).first()
    if not prof:
        prof = AgentProfile.objects.filter(user_id=user_id).first()

    if not prof:
        return "أنت ممثل خدمة عملاء محترف ولبق، تتحدث باللهجة المصرية الطبيعية وتساعد العملاء بدقة وسرعة."

    dialect_rules_map = {
        "egyptian": "تحدث باللهجة المصرية العامية الطبيعية والمريحة، بأسلوب ودي وسلس (مثال: 'تمام يا فندم'، 'تحت أمرك'، 'عنيا ليك').",
        "saudi": "تحدث باللهجة السعودية الخليجية الطبيعية والمهذبة (مثال: 'أهلاً يا طويل العمر'، 'أبشر'، 'تحت أمرك').",
        "emirati": "تحدث باللهجة الإماراتية الخليجية الودية والراقية (مثال: 'مرحبا الساع'، 'طال عمرك'، 'فالك طيب').",
        "kuwaiti": "تحدث باللهجة الكويتية الودية المحترمة (مثال: 'هلا وغلا'، 'حياك الله').",
        "levantine": "تحدث باللهجة الشامية اللبنانية/السورية اللطيفة (مثال: 'تكرم عينك'، 'أهلاً وسهلاً').",
        "fusha": "تحدث باللغة العربية الفصحى المعاصرة السلسة والواضحة.",
    }
    dialect_rule = dialect_rules_map.get(prof.dialect, dialect_rules_map["egyptian"])

    instructions = [
        f"أنت الموظف الذكي الموحد للمنشأة. اسمك أو صفتك: {prof.name}.",
        f"دورك: {getattr(prof, 'persona_role', '') or getattr(prof, 'role', '') or 'خدمة العملاء والدعم والمبيعات'}.",
        f"أسلوبك ونبرتك: {getattr(prof, 'speaking_style', '') or 'ودود، محترف، سريع البديهة'}.",
        f"قواعد اللهجة: {dialect_rule}",
        "قواعد المحادثة في شات الواتساب:",
        "1. تحدث بشكل طبيعي وإنساني وواضح ومريح للقراءة في الواتساب.",
        "2. ⛔ حظر قاطع للرسائل التمهيدية: ممنوع تماماً ونهائياً إرسال أي رسائل تمهيدية أو وعود مثل: 'هبحثلك في المستندات'، 'لحظة واحدة وهجيبلك التفاصيل'، 'ثواني أشوفلك'، 'عشان أقدر أديلك أسعار هشوف النظام'. هذا شات، والعميل ينتظر الإجابة الشافية مباشرة، ولا تذكر له خطوات بحثك الداخلية أو أنك تبحث في مستندات إطلاقاً.",
        "3. استدعِ أداة البحث في المستندات (search_knowledge_base) أو الأدوات البرمجية فوراً في صمت وبشكل آلي دون إرسال أي نص تمهيدي، ثم قدّم الإجابة المباشرة والنهائية الكاملة والشافية في ردك.",
        "4. الذاكرة الموحدة: أنت تعرف كل ما دار بين العميل وبيننا في المكالمات الهاتفية والشات، أكمل معه الحوار بسلاسة دون أن تطلب منه إعادة الكلام.",
    ]
    if prof.custom_instructions:
        instructions.append(f"توجيهات إضافية خاصة بالمنشأة:\n{prof.custom_instructions}")

    return "\n".join(instructions)


# ==================== LangGraph Nodes ====================

def evaluate_context_node(state: FollowupState) -> FollowupState:
    """Step 1: Load customer profile, call memory, and whatsapp history."""
    user_id = state.get("user_id")
    phone = state.get("phone_number", "").strip()

    try:
        mem_obj, _ = CustomerMemory.objects.get_or_create(
            user_id=user_id,
            phone_number=phone,
            defaults={"customer_name": state.get("customer_name") or ""}
        )
        state["call_memory"] = mem_obj.call_memory or {}
        state["whatsapp_memory"] = mem_obj.whatsapp_memory or {}
        if mem_obj.customer_name and not state.get("customer_name"):
            state["customer_name"] = mem_obj.customer_name
    except Exception as e:
        logger.warning(f"Error loading CustomerMemory in LangGraph: {e}")
        state["call_memory"] = state.get("call_memory") or {}
        state["whatsapp_memory"] = state.get("whatsapp_memory") or {}

    state["tools_invoked"] = []
    return state


def decision_and_drafting_node(state: FollowupState) -> FollowupState:
    """
    Step 2: Dual Mode Execution:
    - Mode A: Inbound WhatsApp Interactive Chat (Full Multi-turn Chatbot with Tools & MCPs).
    - Mode B: Post-Call Follow-up Evaluation & Drafting.
    """
    trigger_type = state.get("trigger_type", "inbound_whatsapp")
    user_id = state.get("user_id")
    phone = state.get("phone_number", "")
    c_name = state.get("customer_name") or "العميل"
    inbound_msg = state.get("inbound_message", "")
    call_mem = state.get("call_memory") or {}
    wa_mem = state.get("whatsapp_memory") or {}

    api_key = SystemSetting.get_gemini_api_key()
    if not api_key:
        state["should_send"] = False
        state["error"] = "No Gemini API key configured"
        return state

    client = genai.Client(api_key=api_key)
    persona_prompt = load_assistant_persona(user_id)

    # ---------------- Mode A: Inbound WhatsApp Interactive Employee ----------------
    if trigger_type == "inbound_whatsapp":
        # Send typing indicator (composing) immediately so customer sees "يكتب الآن..." on WhatsApp
        try:
            from .evolution_client import send_whatsapp_presence
            instance_name = f"user_{user_id}"
            send_whatsapp_presence(phone, "composing", delay_ms=2500, instance_name=instance_name)
        except Exception as p_err:
            logger.debug(f"Could not send typing presence: {p_err}")

        # 1. Build Tools (RAG + Memory + MCP Tools)
        mcp_decls, mcp_tool_map = load_user_mcp_tools(user_id)

        rag_decl = types.FunctionDeclaration(
            name="search_knowledge_base",
            description="البحث الدلالي الموثوق في مستندات وقاعدة معرفة المنشأة الرسمية. استدعِ هذه الأداة فوراً عند ورود أي سؤال عن خدمات أو أسعار أو سياسات مذكورة في المستندات.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "query": {"type": "STRING", "description": "نص السؤال الدقيق أو الموضوع المراد استخراجه من المستندات"}
                },
                "required": ["query"]
            }
        )

        memory_decl = types.FunctionDeclaration(
            name="lookup_customer_memory",
            description="البحث في سجل وذاكرة العميل بالاسم أو برقم الهاتف لمعرفة ما تم الاتفاق عليه سابقاً هاتفياً أو في الشات.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "identifier": {"type": "STRING", "description": "رقم هاتف العميل أو اسمه"}
                },
                "required": ["identifier"]
            }
        )

        all_decls = [rag_decl, memory_decl] + mcp_decls
        tools_config = [types.Tool(function_declarations=all_decls)] if all_decls else None

        # 2. Build Memory Context for Prompt
        call_sum = call_mem.get("last_call_summary", "")
        agreed = call_mem.get("agreed_next_steps", "")
        memory_context = ""
        if call_sum or agreed:
            memory_context = f"\n[ذاكرة المكالمات الهاتفية السابقة للعميل]: {call_sum}. ما تم الاتفاق عليه هاتفياً: {agreed}.\n"

        system_instruction = (
            f"{persona_prompt}\n"
            f"{memory_context}\n"
            f"أنت تتحدث الآن مع العميل عبر الواتساب (رقمه: {phone}، اسمه: {c_name}).\n"
            f"⛔ تنبيه حاسم وصارم: ممنوع منعاً باتاً ونهائياً إرسال أي رسائل تمهيدية أو وعود للعميل (مثل: 'هبحثلك في المستندات' أو 'لحظة واحدة وهجيبلك التفاصيل' أو 'ثواني أشوفلك'). هذا تطبيق شات، والعميل ينتظر الإجابة المباشرة ولا تذكر له خطوات بحثك الداخلية أو أنك تبحث في مستندات إطلاقاً.\n"
            f"إذا كان سؤال العميل يتطلب معرفة أسعار أو باقات أو خدمات أو أي تفاصيل من قاعدة المعرفة: يجب عليك استدعاء أداة (search_knowledge_base) فوراً وبصمت تام في نفس اللحظة بدون إرسال أي نص تمهيدي.\n"
            f"قدّم الإجابة المباشرة الشافية الكاملة للعميل بعد استخراج البيانات من الأداة مباشرة في رسالة واحدة."
        )

        # 3. Build Rich Conversation History (Last 25 messages for deep conversational context)
        contents = []
        db_history = list(
            OmnichannelMessage.objects.filter(user_id=user_id, phone_number=phone)
            .order_by('-created_at')[:25]
        )
        db_history.reverse()

        for m in db_history:
            txt = m.message_text.strip()
            if not txt:
                continue
            # Skip if it is the current incoming message at the end
            if m.direction == "inbound":
                if txt == inbound_msg and m == db_history[-1]:
                    continue
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=txt)]))
            else:
                contents.append(types.Content(role="model", parts=[types.Part.from_text(text=txt)]))

        # Add the current user message
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=inbound_msg)]))

        # 4. Multi-turn Tool Calling Execution Loop (up to 3 turns)
        tools_invoked = []
        final_answer = ""

        try:
            for turn in range(3):
                gen_config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.4
                )
                if tools_config:
                    gen_config.tools = tools_config

                resp = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=contents,
                    config=gen_config
                )

                if not resp.candidates or not resp.candidates[0].content:
                    break

                cand_content = resp.candidates[0].content
                contents.append(cand_content)

                # Check if Gemini wants to call tools
                if resp.function_calls:
                    for fc in resp.function_calls:
                        t_name = fc.name
                        t_args = fc.args or {}
                        tools_invoked.append({"name": t_name, "args": t_args})
                        logger.info(f"LangGraph WhatsApp Agent calling tool '{t_name}' with args: {t_args}")

                        t_output = ""
                        start_tool_time = time.perf_counter()
                        is_err = False

                        if t_name == "search_knowledge_base":
                            q = str(t_args.get("query", inbound_msg))
                            t_output = execute_knowledge_base_search(user_id, q)
                        elif t_name == "lookup_customer_memory":
                            ident = str(t_args.get("identifier", phone))
                            t_output = execute_customer_memory_lookup(user_id, ident)
                        elif t_name in mcp_tool_map:
                            srv_info = mcp_tool_map[t_name]
                            mcp_res = test_mcp_tool_sync(
                                server_url=srv_info["server_url"],
                                auth_token=srv_info["auth_token"],
                                tool_name=t_name,
                                arguments=t_args,
                                timeout=8.0
                            )
                            t_output = mcp_res.get("result") or mcp_res.get("error_message") or "{}"
                            is_err = not mcp_res.get("ok", True)
                        else:
                            t_output = f"Unknown tool: {t_name}"
                            is_err = True

                        exec_ms = round((time.perf_counter() - start_tool_time) * 1000, 2)

                        # Log tool call into AgentToolCallLog
                        try:
                            AgentToolCallLog.objects.create(
                                user_id=user_id,
                                tool_name=t_name,
                                arguments=t_args,
                                result={"output": t_output[:1000]},
                                is_error=is_err,
                                error_message="" if not is_err else t_output[:255],
                                execution_time_ms=exec_ms
                            )
                        except Exception as log_ex:
                            logger.debug(f"Could not log tool call: {log_ex}")

                        # Append tool response part
                        contents.append(types.Content(
                            role="tool",
                            parts=[types.Part.from_function_response(
                                name=t_name,
                                response={"result": t_output}
                            )]
                        ))
                    # Continue loop to let Gemini generate answer using tool outputs
                    continue
                else:
                    # Model produced text answer
                    candidate_text = resp.text.strip() if resp.text else ""

                    # Intercept any filler promises to search documents
                    filler_triggers = [
                        "هبحثلك", "أبحثلك", "سأبحث", "هبحث في", "ابحث في", "سأقوم بالبحث",
                        "المستندات الرسمية", "المستندات بتاعتنا", "مستندات المنشأة",
                        "لحظة واحدة وهجيبلك", "ثواني وهجيبلك", "لحظة وهشوفلك", "ثواني أشوفلك",
                        "لحظة واحدة من فضلك وهجيبلك", "عشان أقدر أديلك تفاصيل دقيقة", "هجيبلك كل المعلومات"
                    ]
                    is_filler = any(trig in candidate_text for trig in filler_triggers)

                    if is_filler and turn < 2:
                        logger.warning(f"Intercepted filler research promise from Gemini: '{candidate_text[:80]}'. Executing silent RAG search...")
                        t_output = execute_knowledge_base_search(user_id, inbound_msg)
                        tools_invoked.append({"name": "search_knowledge_base", "args": {"query": inbound_msg}, "auto_intercepted": True})

                        # Feed the knowledge result back to Gemini with a strict directive for direct final answer
                        contents.append(types.Content(
                            role="user",
                            parts=[types.Part.from_text(
                                text=(
                                    f"[توجيه فوري للنظام]: ممنوع إرسال رسائل تمهيدية أو وعود للعميل. هذه نتائج المستندات الرسمية الموثقة:\n"
                                    f"{t_output}\n"
                                    f"المطلوب: أجب العميل الآن فوراً بالإجابة النهائية المباشرة الكاملة والشافية عن سؤاله بالأسلوب المصري الطبيعي، دون ذكر أنك قمت بالبحث ودون أي عبارات تمهيدية."
                                )
                            )]
                        ))
                        continue
                    else:
                        final_answer = candidate_text
                        break

            if not final_answer:
                final_answer = "أهلاً بك يا فندم! تحت أمرك، تحب أساعدك في إيه؟"

            state["should_send"] = True
            state["message_text"] = final_answer
            state["reason"] = "inbound_conversational_reply"
            state["customer_stage"] = "active_chat"
            state["tools_invoked"] = tools_invoked

        except Exception as err:
            logger.error(f"Error in WhatsApp conversational tool loop: {err}", exc_info=True)
            state["should_send"] = False
            state["error"] = str(err)

        return state

    # ---------------- Mode B: Post-Call Follow-up Evaluation ----------------
    call_sum = state.get("call_summary") or call_mem.get("last_call_summary", "")
    system_prompt = (
        f"{persona_prompt}\n"
        "مهمتك: بعد انتهاء مكالمة هاتفية مع العميل، اتخذ قراراً هل يلزم إرسال رسالة متابعة على الواتساب أم لا.\n"
        "القواعد:\n"
        "1. إذا اتفق العميل في المكالمة على إرسال عروض، باقات، أسعار، أو تفاصيل: ضع should_send = true وصِغ الرسالة بلهجتك.\n"
        "2. إذا كانت المكالمة خطأ أو غير مفيدة أو لا تستدعي متابعة: ضع should_send = false.\n"
        "3. مخرجاتك يجب أن تكون كائن JSON حصراً."
    )

    user_prompt = f"""
بيانات العميل:
- الاسم: {c_name}
- الهاتف: {phone}
- ملخص المكالمة المنتهية: "{call_sum}"
- ما تم الاتفاق عليه: "{call_mem.get('agreed_next_steps', '')}"

المطلوب:
أخرج النتيجة ككائن JSON بالصيغة:
{{
  "should_send": true,
  "message_text": "نص الرسالة بأسلوب المساعد...",
  "reason": "post_call_followup",
  "customer_stage": "contacted",
  "next_followup_hours": 24
}}
"""
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json"
            )
        )
        data = json.loads(response.text.strip())
        state["should_send"] = bool(data.get("should_send", True))
        state["message_text"] = str(data.get("message_text", "")).strip()
        state["reason"] = str(data.get("reason", "post_call_followup")).strip()
        state["customer_stage"] = str(data.get("customer_stage", "contacted")).strip()
        state["next_followup_hours"] = data.get("next_followup_hours")
    except Exception as e:
        logger.error(f"Error in LangGraph post-call decision node: {e}", exc_info=True)
        state["should_send"] = False
        state["error"] = str(e)

    return state


def execute_action_node(state: FollowupState) -> FollowupState:
    """Step 3: Dispatch WhatsApp message and synchronize customer memory."""
    if not state.get("should_send") or not state.get("message_text"):
        state["is_sent"] = False
        return state

    phone = state.get("phone_number", "")
    text = state.get("message_text", "")
    user_id = state.get("user_id")
    c_name = state.get("customer_name") or ""
    reason = state.get("reason", "followup")

    # 1. Send via Evolution API
    instance_name = f"user_{user_id}" if user_id else "default_workspace"
    send_res = send_whatsapp_message(phone, text, instance_name=instance_name)
    state["is_sent"] = send_res.get("ok", False)

    # 2. Record OmnichannelMessage log
    try:
        OmnichannelMessage.objects.create(
            user_id=user_id,
            phone_number=phone,
            customer_name=c_name,
            channel="whatsapp",
            direction="outbound_ai",
            message_text=text,
            is_followup=(state.get("trigger_type") == "post_call"),
            followup_reason=reason,
            metadata={
                "send_result": send_res,
                "trigger_type": state.get("trigger_type"),
                "tools_invoked": state.get("tools_invoked", []),
                "next_followup_hours": state.get("next_followup_hours")
            }
        )
    except Exception as log_err:
        logger.warning(f"Failed to record OmnichannelMessage: {log_err}")

    # 3. Synchronize CustomerMemory (whatsapp_memory)
    try:
        mem_obj = CustomerMemory.objects.filter(user_id=user_id, phone_number=phone).first()
        if mem_obj:
            wm = mem_obj.whatsapp_memory or {}
            wm["last_interaction_at"] = datetime.now(timezone.utc).isoformat()
            wm["customer_stage"] = state.get("customer_stage", "active_chat")
            wm["last_sent_message"] = text

            # Maintain last 10 messages for conversation continuity
            msgs = wm.get("last_messages", [])
            msgs.append({
                "sender": "ai",
                "text": text,
                "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
            })
            wm["last_messages"] = msgs[-10:]

            # Ongoing conversation summary for cross-channel voice agent awareness
            last_cust = state.get("inbound_message") or wm.get("last_received_message", "")
            if state.get("inbound_message"):
                wm["last_received_message"] = state.get("inbound_message")
            wm["conversation_summary"] = (
                f"العميل استفسر عن: '{last_cust[:80]}'، "
                f"وتم الرد عليه بـ: '{text[:80]}'."
            )

            if state.get("next_followup_hours"):
                wm["pending_followup"] = {
                    "reason": reason,
                    "hours": state.get("next_followup_hours"),
                    "status": "scheduled"
                }

            mem_obj.whatsapp_memory = wm
            mem_obj.save(update_fields=["whatsapp_memory", "updated_at"])
    except Exception as mem_err:
        logger.warning(f"Failed to update CustomerMemory in action node: {mem_err}")

    return state


# ==================== LangGraph Graph Compilation ====================

def build_followup_graph():
    """Compile the LangGraph workflow for autonomous 24/7 omnichannel engagement."""
    workflow = StateGraph(FollowupState)

    workflow.add_node("evaluate_context", evaluate_context_node)
    workflow.add_node("decision_and_drafting", decision_and_drafting_node)
    workflow.add_node("execute_action", execute_action_node)

    workflow.set_entry_point("evaluate_context")
    workflow.add_edge("evaluate_context", "decision_and_drafting")
    workflow.add_edge("decision_and_drafting", "execute_action")
    workflow.add_edge("execute_action", END)

    return workflow.compile()


FOLLOWUP_GRAPH_APP = build_followup_graph()


def run_autonomous_followup(
    user_id: int,
    phone_number: str,
    trigger_type: str = "post_call",
    call_transcript: str = "",
    call_summary: str = "",
    inbound_message: str = "",
    customer_name: str = ""
) -> Dict[str, Any]:
    """Execute LangGraph omnichannel engine for a customer event."""
    initial_state: FollowupState = {
        "user_id": user_id,
        "phone_number": phone_number,
        "customer_name": customer_name,
        "trigger_type": trigger_type,
        "call_transcript": call_transcript,
        "call_summary": call_summary,
        "inbound_message": inbound_message,
        "call_memory": {},
        "whatsapp_memory": {},
        "should_send": False,
        "message_text": "",
        "reason": "",
        "customer_stage": "contacted",
        "next_followup_hours": None,
        "tools_invoked": [],
        "is_sent": False,
        "error": None
    }

    try:
        final_state = FOLLOWUP_GRAPH_APP.invoke(initial_state)
        return final_state
    except Exception as e:
        logger.error(f"LangGraph execution failed for {phone_number}: {e}", exc_info=True)
        return {"error": str(e), "is_sent": False}
