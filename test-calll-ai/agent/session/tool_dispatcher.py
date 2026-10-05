import time
from typing import Dict, Any, List, Optional, Tuple
from google.genai import types
from agent.config import logger
from agent.clients.centrifugo_client import notify_centrifugo_async
from agent.clients.django_client import query_knowledge_base_async, lookup_customer_memory_async
from agent.clients.mcp_client import execute_mcp_tool_call
from agent.clients.inngest_client import dispatch_tool_log_to_inngest


def clean_gemini_schema(raw):
    """
    Recursively sanitize any JSON Schema (from FastMCP, Pydantic, OpenAPI, etc.)
    into a strict Gemini Live API compliant Schema dictionary.
    Gemini Live API strictly permits only: type, properties, required, items, description, enum, nullable.
    Any extra fields (e.g. additionalProperties, additional_properties, title, default, $schema) cause error 1007.
    """
    if not isinstance(raw, dict):
        return raw

    cleaned = {}

    # 1. Handle anyOf / oneOf (unwrap Optional[T])
    any_of = raw.get("anyOf") or raw.get("any_of") or raw.get("oneOf") or raw.get("one_of")
    if any_of and isinstance(any_of, list):
        non_null_schemas = [s for s in any_of if isinstance(s, dict) and s.get("type") not in ("null", "NULL")]
        has_null = any(isinstance(s, dict) and s.get("type") in ("null", "NULL") for s in any_of)
        
        if non_null_schemas:
            primary = clean_gemini_schema(non_null_schemas[0])
            if isinstance(primary, dict):
                cleaned.update(primary)
        if has_null:
            cleaned["nullable"] = True

    # 2. Extract and normalize type
    schema_type = raw.get("type")
    if schema_type:
        if isinstance(schema_type, str):
            st_upper = schema_type.upper()
            if st_upper in ("STRING", "INTEGER", "NUMBER", "BOOLEAN", "OBJECT", "ARRAY"):
                cleaned["type"] = st_upper
            elif st_upper in ("FLOAT", "DOUBLE"):
                cleaned["type"] = "NUMBER"
            elif st_upper in ("INT", "LONG"):
                cleaned["type"] = "INTEGER"
            elif st_upper in ("BOOL",):
                cleaned["type"] = "BOOLEAN"
            else:
                cleaned["type"] = st_upper
        elif isinstance(schema_type, list):
            non_null_types = [t for t in schema_type if str(t).lower() != "null"]
            if non_null_types:
                cleaned["type"] = str(non_null_types[0]).upper()
            if any(str(t).lower() == "null" for t in schema_type):
                cleaned["nullable"] = True

    if "type" not in cleaned:
        if "properties" in raw:
            cleaned["type"] = "OBJECT"
        elif "items" in raw:
            cleaned["type"] = "ARRAY"

    if "description" in raw and isinstance(raw["description"], str):
        cleaned["description"] = raw["description"]

    if "nullable" in raw:
        cleaned["nullable"] = bool(raw["nullable"])

    if "enum" in raw and isinstance(raw["enum"], list):
        cleaned["enum"] = [str(e) for e in raw["enum"]]

    if "properties" in raw and isinstance(raw["properties"], dict):
        cleaned_props = {}
        for prop_name, prop_schema in raw["properties"].items():
            cleaned_props[prop_name] = clean_gemini_schema(prop_schema)
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

    # Safety Firewall for Gemini Live: OBJECT types in arrays MUST have properties defined
    if cleaned.get("type") == "ARRAY" and isinstance(cleaned.get("items"), dict):
        item_dict = cleaned["items"]
        if item_dict.get("type") == "OBJECT" and not item_dict.get("properties"):
            item_dict["properties"] = {
                "name": {"type": "STRING", "description": "اسم العنصر أو الصنف"},
                "quantity": {"type": "INTEGER", "description": "الكمية"}
            }
            item_dict["required"] = ["name"]

    return cleaned


def build_gemini_tools(mcp_tools: Dict[str, Any], call_queues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build the function declarations list for Gemini Live connect config."""
    rag_decl = {
        "name": "search_knowledge_base",
        "description": (
            "البحث الدلالي الذكي في قاعدة المعرفة والمستندات والبيانات المعتمدة للمؤسسة أو النشاط للإجابة على استفسارات المتصل بدقة وموثوقية."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "نص السؤال أو الاستفسار أو الكلمات المفتاحية للبحث عنها في المستندات"
                }
            },
            "required": ["query"]
        }
    }

    memory_decl = {
        "name": "lookup_customer_memory",
        "description": (
            "البحث في سجل وذاكرة العملاء بالاسم أو برقم الهاتف لاسترجاع بيانات العميل وتفضيلاته وعنوانه وسجل تواصله السابق مع المؤسسة لمساعدته بشكل مخصص."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "identifier": {
                    "type": "STRING",
                    "description": "رقم هاتف العميل (مثل 01108124794) أو اسمه للبحث عنه في سجلات المنشأة"
                }
            },
            "required": ["identifier"]
        }
    }

    func_decls = [rag_decl, memory_decl]

    # Add external MCP tools from all active servers with clean Gemini schemas
    for t_name, t_info in mcp_tools.items():
        decl = {
            "name": t_name,
            "description": t_info.get("description", "")
        }
        params = t_info.get("parameters")
        if params and isinstance(params, dict):
            cleaned_params = clean_gemini_schema(params)
            if cleaned_params and isinstance(cleaned_params, dict):
                decl["parameters"] = cleaned_params
        func_decls.append(decl)

    if mcp_tools:
        logger.info(f"Loaded {len(mcp_tools)} total MCP tools: {list(mcp_tools.keys())}")

    # Add tenant call_queues transfer tool if tenant has active queues
    if call_queues:
        q_codes = [str(q["code"]) for q in call_queues]
        q_desc_parts = []
        for q in call_queues:
            detail = f" [الاختصاص: {q['description']}]" if q.get("description") else ""
            q_desc_parts.append(f"{q['name']} ({q['code']}){detail}")
        q_descriptions = " | ".join(q_desc_parts)
        transfer_decl = {
            "name": "transfer_to_queue",
            "description": f"تحويل المكالمة الجارية إلى أحد طوابير الموظفين البشريين التابعة للمؤسسة. الأقسام واختصاصاتها: [{q_descriptions}]. ممنوع استدعاء هذه الأداة فوراً دون سؤال العميل أولاً عن مشكلته، لكن بمجرد تكرار طلبه أو ذكر القسم استدعِ الأداة فوراً مع كتابة ملخص ما قاله العميل كاملاً في حقل reason.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "queue_code": {
                        "type": "STRING",
                        "description": f"كود الطابور المراد التحويل إليه حصراً من بين: {q_codes}"
                    },
                    "reason": {
                        "type": "STRING",
                        "description": "ملخص وافٍ لسبب التحويل وما قاله العميل والمشكلة لتمريره لممثلي القسم"
                    }
                },
                "required": ["queue_code"]
            }
        }
        func_decls.append(transfer_decl)
        logger.info(f"Loaded transfer_to_queue tool with {len(call_queues)} tenant queues: {q_codes}")

    return [{"function_declarations": func_decls}]


async def handle_gemini_tool_call(
    fc,
    user_id: Optional[int],
    room_name: str,
    channel_name: str,
    mcp_tools: Dict[str, Any],
    call_queues: List[Dict[str, Any]],
    genai_client = None,
    session_state: Optional[Any] = None
) -> Tuple[types.FunctionResponse, Optional[Dict[str, Any]]]:
    """Execute a single function call from Gemini Live and return (response, pending_transfer)."""
    pending_transfer = None
    start_t = time.monotonic()
    caller_phone = getattr(session_state, "caller_phone", "") if session_state else ""

    if fc.name == "search_knowledge_base":
        await notify_centrifugo_async(channel_name, "agent_searching_rag", "جاري البحث الدلالي في مستنداتك...")
        query_text = fc.args.get("query", "") if fc.args else ""
        logger.info(f"Executing search_knowledge_base for user_id={user_id}, query='{query_text}'")
        search_result = await query_knowledge_base_async(query_text, user_id, genai_client)
        logger.info(f"Search result retrieved: {search_result[:100]}...")
        elapsed_ms = int((time.monotonic() - start_t) * 1000)

        dispatch_tool_log_to_inngest({
            "user_id": user_id,
            "room_name": room_name,
            "caller_phone": caller_phone,
            "tool_name": "search_knowledge_base",
            "tool_type": "rag",
            "server_name": "نظام البحث الدلالي (RAG)",
            "arguments": {"query": query_text},
            "status": "success",
            "error_type": "none",
            "error_message": "",
            "response_preview": search_result[:300],
            "execution_time_ms": elapsed_ms
        })

        return types.FunctionResponse(
            id=fc.id,
            name=fc.name,
            response={"result": search_result}
        ), None

    elif fc.name == "lookup_customer_memory":
        identifier = str(fc.args.get("identifier", "")).strip() if fc.args else ""
        await notify_centrifugo_async(channel_name, "agent_action_executing", f"جاري فحص سجل العميل '{identifier}'...")
        logger.info(f"Executing lookup_customer_memory for user_id={user_id}, identifier='{identifier}'")
        res = await lookup_customer_memory_async(user_id, identifier)
        elapsed_ms = int((time.monotonic() - start_t) * 1000)

        if res.get("found"):
            mem = res.get("memory") or {}
            c_name = mem.get("customer_name") or ""
            phone = res.get("phone_number")
            prof = mem.get("permanent_profile") or {}
            summary = mem.get("last_interaction_summary") or ""

            if session_state and phone:
                session_state.caller_phone = phone
                caller_phone = phone
                logger.info(f"Dynamically updated session_state.caller_phone to '{phone}' from memory lookup")

            result_msg = "تم العثور على سجل العميل في النظام بنجاح:\n"
            if c_name:
                result_msg += f"- اسم العميل: {c_name}\n"
            if phone:
                result_msg += f"- رقم الهاتف: {phone}\n"
            if prof.get("address") or prof.get("city"):
                result_msg += f"- العنوان/المدينة: {prof.get('address') or prof.get('city')}\n"
            if prof.get("preferences"):
                prefs = prof['preferences']
                if isinstance(prefs, list):
                    prefs = "، ".join(str(p) for p in prefs)
                result_msg += f"- التفضيلات والاهتمامات: {prefs}\n"
            if summary:
                result_msg += f"- ملخص آخر تواصل: {summary}\n"
            result_msg += "وظف هذه المعلومات للترحيب بالعميل ومتابعة طلبه ومساعدته بذكاء وعفوية."

            dispatch_tool_log_to_inngest({
                "user_id": user_id,
                "room_name": room_name,
                "caller_phone": caller_phone,
                "tool_name": "lookup_customer_memory",
                "tool_type": "memory",
                "server_name": "ذاكرة العملاء (CRM)",
                "arguments": {"identifier": identifier},
                "status": "success",
                "error_type": "none",
                "error_message": "",
                "response_preview": result_msg[:300],
                "execution_time_ms": elapsed_ms
            })

            return types.FunctionResponse(
                id=fc.id,
                name=fc.name,
                response={"result": result_msg}
            ), None
        else:
            not_found_msg = f"لم يتم العثور على سجل سابق للعميل بالمعرف '{identifier}'. تعامل معه كعميل جديد بلباقة وسجل بياناته عند الحاجة."
            dispatch_tool_log_to_inngest({
                "user_id": user_id,
                "room_name": room_name,
                "caller_phone": caller_phone,
                "tool_name": "lookup_customer_memory",
                "tool_type": "memory",
                "server_name": "ذاكرة العملاء (CRM)",
                "arguments": {"identifier": identifier},
                "status": "failed",
                "error_type": "not_found",
                "error_message": f"لا يوجد سجل للعميل '{identifier}'",
                "response_preview": not_found_msg[:300],
                "execution_time_ms": elapsed_ms
            })

            return types.FunctionResponse(
                id=fc.id,
                name=fc.name,
                response={"result": not_found_msg}
            ), None

    elif fc.name in mcp_tools:
        mcp_info = mcp_tools[fc.name]
        desc = mcp_info["description"][:30] if mcp_info.get("description") else fc.name
        s_name = mcp_info.get("server_name", "FastMCP")
        s_url = mcp_info.get("server_url", "")
        await notify_centrifugo_async(channel_name, "agent_action_executing", f"جاري استدعاء أداة {s_name}: {desc}...")
        act_args = dict(fc.args or {})
        logger.info(f"Executing MCP tool '{fc.name}' with args {act_args} on [{s_name}] {s_url}")
        action_result = await execute_mcp_tool_call(
            s_url,
            mcp_info["auth_token"],
            fc.name,
            act_args
        )
        elapsed_ms = int((time.monotonic() - start_t) * 1000)

        is_error = False
        error_msg = ""
        error_type = "none"
        raw_output = ""

        if isinstance(action_result, dict):
            is_error = bool(action_result.get("is_error"))
            error_msg = str(action_result.get("error_message") or action_result.get("result") or "")
            error_type = str(action_result.get("error_type") or "tool_error")
            raw_output = str(action_result.get("result") or "")
        else:
            raw_output = str(action_result)
            if "حدث خطأ" in raw_output or "استغرق نظام" in raw_output or "validation error" in raw_output.lower():
                is_error = True
                error_msg = raw_output
                error_type = "tool_error"

        # Dispatch log event to Inngest
        dispatch_tool_log_to_inngest({
            "user_id": user_id,
            "room_name": room_name,
            "caller_phone": caller_phone,
            "tool_name": fc.name,
            "tool_type": "mcp",
            "server_name": s_name,
            "server_url": s_url,
            "arguments": act_args,
            "status": "failed" if is_error else "success",
            "error_type": error_type if is_error else "none",
            "error_message": error_msg if is_error else "",
            "response_preview": (error_msg if is_error else raw_output)[:300],
            "raw_response": action_result if isinstance(action_result, dict) else {"result": raw_output},
            "execution_time_ms": elapsed_ms
        })

        if is_error:
            logger.warning(f"MCP tool '{fc.name}' failed: type={error_type}, msg={error_msg[:100]}")
            # Notify Centrifugo of tool failure for live dashboard tracking
            await notify_centrifugo_async(
                channel_name,
                "agent_action_failed",
                f"فشل تنفيذ أداة {fc.name}: {error_msg[:80]}",
                {
                    "tool_name": fc.name,
                    "server_name": s_name,
                    "error": error_msg,
                    "error_type": error_type
                }
            )

            available_queues_hint = ""
            if call_queues:
                q_names = " أو ".join([f"قسم {q['name']}" for q in call_queues if q.get("name")])
                if q_names:
                    available_queues_hint = f" واعرض على المتصل تحويله إلى {q_names} إذا رغب."

            error_instruction = (
                f"تنبيه حاسم للمساعد الصوتي: فشلت هذه الأداة ({fc.name}) في التنفيذ ولم تكتمل العملية المطلوبة. "
                f"يجب أن تعتذر للمتصل فوراً وتوضح له سبب التعذر بلباقة بناءً على سبب الخطأ: ({error_msg}). "
                f"يُمنع منعاً باتاً وحاسماً أن تدّعي نجاح العملية أو تقول 'تم تأكيد طلبك' أو 'تم التسجيل' أو تؤلف بيانات وهمية! "
                f"اقترح على المتصل إعادة المحاولة لاحقاً،{available_queues_hint}"
            )

            return types.FunctionResponse(
                id=fc.id,
                name=fc.name,
                response={
                    "status": "error",
                    "error": True,
                    "error_type": error_type,
                    "error_message": error_msg,
                    "instruction": error_instruction
                }
            ), None
        else:
            logger.info(f"MCP tool '{fc.name}' response: {raw_output[:150]}")
            await notify_centrifugo_async(
                channel_name,
                "agent_action_success",
                f"تم تنفيذ أداة {fc.name} بنجاح",
                {"tool_name": fc.name}
            )
            return types.FunctionResponse(
                id=fc.id,
                name=fc.name,
                response={
                    "status": "success",
                    "result": raw_output
                }
            ), None

    elif fc.name == "transfer_to_queue":
        q_code = str(fc.args.get("queue_code", "")).strip() if fc.args else ""
        reason = str(fc.args.get("reason", "")).strip() if fc.args else ""
        matched_q = next((q for q in call_queues if str(q.get("code")) == q_code), None)
        q_name = matched_q.get("name", "القسم المطلوب") if matched_q else f"طابور {q_code}"
        elapsed_ms = int((time.monotonic() - start_t) * 1000)
        logger.info(f"AI requested transfer_to_queue in room {room_name}: queue_code={q_code}, queue_name={q_name}, reason={reason}")

        dispatch_tool_log_to_inngest({
            "user_id": user_id,
            "room_name": room_name,
            "caller_phone": caller_phone,
            "tool_name": "transfer_to_queue",
            "tool_type": "transfer",
            "server_name": "نظام طوابير الكول سنتر",
            "arguments": {"queue_code": q_code, "reason": reason},
            "status": "success",
            "error_type": "none",
            "error_message": "",
            "response_preview": f"تحويل إلى {q_name}: {reason}",
            "execution_time_ms": elapsed_ms
        })

        await notify_centrifugo_async(channel_name, "agent_transferring", f"جاري تحويلك إلى {q_name}...")
        pending_transfer = {
            "queue_code": q_code,
            "queue_name": q_name,
            "reason": reason
        }
        return types.FunctionResponse(
            id=fc.id,
            name=fc.name,
            response={
                "status": "success",
                "target_queue": q_name
            }
        ), pending_transfer

    else:
        logger.warning(f"Unknown tool requested by Gemini: {fc.name}")
        elapsed_ms = int((time.monotonic() - start_t) * 1000)
        dispatch_tool_log_to_inngest({
            "user_id": user_id,
            "room_name": room_name,
            "caller_phone": caller_phone,
            "tool_name": fc.name,
            "tool_type": "mcp",
            "server_name": "غير معرف",
            "arguments": dict(fc.args or {}),
            "status": "failed",
            "error_type": "unknown_tool",
            "error_message": f"الأداة '{fc.name}' غير معرفة في النظام",
            "execution_time_ms": elapsed_ms
        })

        return types.FunctionResponse(
            id=fc.id,
            name=fc.name,
            response={"result": "عذراً، هذه الأداة غير معرفة."}
        ), None
