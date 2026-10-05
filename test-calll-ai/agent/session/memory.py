"""Background customer memory distillation and profile persistence."""
import asyncio
import json
from typing import Dict, Any, List, Optional
from google.genai import types
from agent.config import logger, GEMINI_FLASH_MODEL
from agent.clients.django_client import save_call_session_and_update_memory_async


async def distill_and_update_memory(
    user_id: int,
    room_name: str,
    started_at: float,
    messages: List[Dict[str, Any]],
    current_profile: Dict[str, Any],
    caller_phone: str = "web_dashboard",
    genai_client = None,
    outbound_context: Optional[Dict[str, Any]] = None
):
    """Background task to extract permanent profile facts and distill short-term episode summary."""
    try:
        user_msgs = [m for m in messages if m.get("speaker") == "user"]
        if not user_msgs or len(messages) < 2:
            logger.info(f"Call in room {room_name} had insufficient speech turns ({len(messages)}). Skipping memory distillation.")
            return

        lines = []
        for m in messages:
            speaker_label = "العميل" if m.get("speaker") == "user" else "المساعد"
            lines.append(f"{speaker_label}: {m.get('text', '')}")
        transcript_text = "\n".join(lines)

        distillation_prompt = f"""أنت محلل ذكاء اصطناعي متخصص في استخلاص ذاكرة العملاء لمساعد صوتي ذكي.
المطلوب منك تحليل نص هذه المكالمة الصوتية واستخراج نقطتين فقط بدقة وإيجاز شديد:
1. "summary": ملخص دقيق ومركز جداً في سطرين فقط (لا يتعدى 50 كلمة) لما دار في المكالمة، والأسئلة أو المنتجات التي سأل عنها العميل، وموقفه وحالة طلبه.
   - قاعدة حاسمة وإلزامية: يُمنع منعاً باتاً تسجيل أي عبارات مثل 'عطل في السيستم' أو 'مشكلة فنية' أو 'تهنيج' في الملخص! ركز فقط على احتياجات العميل وما طلبه (مثال: 'طلب العميل شاي كرك وبانتظار تأكيد الطلب والتوصيل لمدينة الشروق').
2. "new_permanent_facts": أي حقائق دائمة جديدة ذكرها العميل صراحةً (اسمه، هاتفه، عنوانه/مدينته، اهتمامات وتفضيلات محددة بالمنتجات، ملاحظات). إذا لم يذكر أي حقيقة جديدة، اترك الحقل فارغاً.

البروفايل الدائم الحالي للعميل:
{json.dumps(current_profile, ensure_ascii=False)}

نص المكالمة:
{transcript_text}

أجب بصيغة JSON فقط بهذا الشكل:
{{
  "summary": "...",
  "new_permanent_facts": {{
    "customer_name": "...",
    "phone": "...",
    "address": "...",
    "preferences": ["..."],
    "notes": "..."
  }}
}}"""

        response = await genai_client.aio.models.generate_content(
            model=GEMINI_FLASH_MODEL,
            contents=distillation_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        resp_text = response.text or "{}"
        data = json.loads(resp_text)
        summary = data.get("summary", "").strip()
        new_facts = data.get("new_permanent_facts", {})

        updated_profile = dict(current_profile or {})
        if new_facts and isinstance(new_facts, dict):
            for k in ["customer_name", "phone", "address", "notes"]:
                val = new_facts.get(k)
                if val and str(val).strip() and str(val).strip().lower() not in ["null", "none", "..."]:
                    updated_profile[k] = str(val).strip()

            if new_facts.get("preferences") and isinstance(new_facts["preferences"], list):
                existing_prefs = list(updated_profile.get("preferences") or [])
                for p in new_facts["preferences"]:
                    p_str = str(p).strip()
                    if p_str and p_str not in existing_prefs:
                        existing_prefs.append(p_str)
                updated_profile["preferences"] = existing_prefs[:6]

        # Dynamic binding: if caller was anonymous/web but explicitly stated their phone number in the call
        extracted_phone = updated_profile.get("phone")
        final_phone = caller_phone
        if extracted_phone and str(extracted_phone).strip() and caller_phone in ['web_dashboard', 'anonymous', 'unknown', '']:
            final_phone = str(extracted_phone).strip()
            logger.info(f"Dynamically bound call in room {room_name} to extracted phone '{final_phone}'")

        logger.info(f"Distillation complete for ({user_id}, {final_phone}). Summary: {summary[:80]}...")

        await save_call_session_and_update_memory_async(
            user_id=user_id,
            room_name=room_name,
            started_at=started_at,
            transcript_text=transcript_text,
            summary=summary,
            updated_profile=updated_profile,
            caller_phone=final_phone,
            outbound_context=outbound_context
        )
    except Exception as e:
        logger.error(f"Error in distill_and_update_memory for user {user_id}: {e}", exc_info=True)
