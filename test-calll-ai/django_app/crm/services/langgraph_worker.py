"""
LangGraph Autonomous Employee Worker for 24/7 WhatsApp Follow-up & Omnichannel Memory.

Orchestrates multi-step reasoning, cross-channel customer memory enrichment
(Call Memory + WhatsApp Memory), and automated WhatsApp engagement.
"""
import logging
import json
import os
from typing import TypedDict, Dict, Any, Optional
from datetime import datetime, timezone

from langgraph.graph import StateGraph, END
from google import genai
from google.genai import types

from crm.models import CustomerMemory, OmnichannelMessage
from crm.services.evolution_client import send_whatsapp_message
from agents.models import SystemSetting

logger = logging.getLogger(__name__)


class FollowupState(TypedDict):
    user_id: int
    phone_number: str
    customer_name: str
    trigger_type: str  # "post_call" | "inbound_whatsapp" | "scheduled_followup"
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
    is_sent: bool
    error: Optional[str]


def evaluate_context_node(state: FollowupState) -> FollowupState:
    """Step 1: Load and align cross-channel customer memory."""
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

    return state


def decision_and_drafting_node(state: FollowupState) -> FollowupState:
    """Step 2: Deep reasoning using Gemini to decide whether to follow up and draft the message."""
    trigger_type = state.get("trigger_type", "post_call")
    phone = state.get("phone_number", "")
    c_name = state.get("customer_name") or "العميل"
    call_sum = state.get("call_summary") or state.get("call_memory", {}).get("last_call_summary", "")
    inbound_msg = state.get("inbound_message", "")
    wa_mem = state.get("whatsapp_memory", {})

    api_key = SystemSetting.get_gemini_api_key()
    if not api_key:
        state["should_send"] = False
        state["error"] = "No Gemini API key configured"
        return state

    client = genai.Client(api_key=api_key)

    system_prompt = (
        "أنت موظف خدمة عملاء ومتابعة ذكي ومحترف تعمل في منشأة على مدار 24 ساعة.\n"
        "مهمتك هي التواصل والمتابعة التلقائية مع العملاء عبر الواتساب بناءً على سجل مكالماتهم ورسائلهم.\n"
        "القواعد والأسلوب:\n"
        "1. تحدث بلهجة مصرية مهذبة ولطيفة وودودة جداً، باسم العميل.\n"
        "2. كن موجزاً وواضحاً ومفيداً، دون تكلف أو كلام إعلاني مبتذل.\n"
        "3. اربط الحديث بذكاء بما تم الاتفاق عليه أو الحديث بشأنه في المكالمة أو الشات.\n"
        "4. مخرجاتك يجب أن تكون حصراً بصيغة JSON صالحة دون أي نصوص إضافية خارج الـ JSON."
    )

    user_prompt = f"""
بيانات العميل:
- الاسم: {c_name}
- رقم الهاتف: {phone}
- نوع الحدث: {trigger_type}

ذاكرة المكالمات الهاتفية السابقة:
"{call_sum}"

ذاكرة محادثات الواتساب السابقة:
- ملخص الشات السابق: {wa_mem.get('conversation_summary', 'لا يوجد شات سابق')}
- آخر رسائل متبادلة: {json.dumps(wa_mem.get('last_messages', []), ensure_ascii=False)}

الحدث الحالي:
- نص الرسالة الواردة (إن وجدت): "{inbound_msg}"
- ملخص المكالمة المنتهية للتو: "{state.get('call_summary', '')}"

المطلوب:
اتخذ قراراً ذكياً بشأن الخطوة التالية:
1. هل يجب إرسال رسالة واتساب للعميل الآن؟ (true إذا كان يستحق متابعة بعد المكالمة أو رداً على رسالته، false إذا كانت المكالمة خطأ أو غير مفيدة أو لا تحتاج تواصلاً).
2. نص الرسالة المطلوب إرسالها للعميل بأسلوب ودود وموجز ومباشر.
3. سبب المتابعة (مثال: post_call_offer, price_recap, answer_inquiry, courteous_followup).
4. مرحلة العميل (lead, negotiation, contacted, closed).
5. بعد كم ساعة تفضل أن يطمئن الموظف عليه مرة أخرى إذا لم يرد العميل؟ (مثال: 24 ساعة، أو null إذا انتهى الأمر).

أخرج النتيجة ككائن JSON بالصيغة التالية تماماً:
{{
  "should_send": true,
  "message_text": "نص الرسالة...",
  "reason": "سبب الإرسال",
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
        raw_text = response.text.strip()
        data = json.loads(raw_text)

        state["should_send"] = bool(data.get("should_send", True))
        state["message_text"] = str(data.get("message_text", "")).strip()
        state["reason"] = str(data.get("reason", "automated_followup")).strip()
        state["customer_stage"] = str(data.get("customer_stage", "contacted")).strip()
        state["next_followup_hours"] = data.get("next_followup_hours")
    except Exception as e:
        logger.error(f"Error in LangGraph decision node: {e}", exc_info=True)
        state["should_send"] = False
        state["error"] = str(e)

    return state


def execute_action_node(state: FollowupState) -> FollowupState:
    """Step 3: Dispatch WhatsApp message and update omnichannel memory."""
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
            is_followup=True,
            followup_reason=reason,
            metadata={"send_result": send_res, "next_followup_hours": state.get("next_followup_hours")}
        )
    except Exception as log_err:
        logger.warning(f"Failed to record OmnichannelMessage: {log_err}")

    # 3. Update CustomerMemory (whatsapp_memory)
    try:
        mem_obj = CustomerMemory.objects.filter(user_id=user_id, phone_number=phone).first()
        if mem_obj:
            wm = mem_obj.whatsapp_memory or {}
            wm["last_interaction_at"] = datetime.now(timezone.utc).isoformat()
            wm["customer_stage"] = state.get("customer_stage", "contacted")
            wm["last_sent_message"] = text

            # Maintain last 6 messages
            msgs = wm.get("last_messages", [])
            msgs.append({"sender": "ai", "text": text, "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")})
            wm["last_messages"] = msgs[-6:]

            # Summary update
            wm["conversation_summary"] = f"آخر رسالة متابعة أرسلها الذكاء الاصطناعي ({reason}): {text[:100]}"
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


def build_followup_graph():
    """Compile the LangGraph workflow for autonomous 24/7 follow-up."""
    workflow = StateGraph(FollowupState)

    workflow.add_node("evaluate_context", evaluate_context_node)
    workflow.add_node("decision_and_drafting", decision_and_drafting_node)
    workflow.add_node("execute_action", execute_action_node)

    workflow.set_entry_point("evaluate_context")
    workflow.add_edge("evaluate_context", "decision_and_drafting")
    workflow.add_edge("decision_and_drafting", "execute_action")
    workflow.add_edge("execute_action", END)

    return workflow.compile()


# Global compiled app
FOLLOWUP_GRAPH_APP = build_followup_graph()


def run_autonomous_followup(
    user_id: int,
    phone_number: str,
    trigger_type: str = "post_call",
    call_summary: str = "",
    call_transcript: str = "",
    inbound_message: str = "",
    customer_name: str = ""
) -> Dict[str, Any]:
    """Synchronously or asynchronously trigger the LangGraph employee pipeline."""
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
        "customer_stage": "lead",
        "next_followup_hours": None,
        "is_sent": False,
        "error": None
    }

    try:
        final_state = FOLLOWUP_GRAPH_APP.invoke(initial_state)
        return dict(final_state)
    except Exception as e:
        logger.error(f"Error executing LangGraph follow-up workflow: {e}", exc_info=True)
        return {"error": str(e), "is_sent": False}
