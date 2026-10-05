import json
import logging
from typing import Dict, Any
from agents.models import SystemSetting

logger = logging.getLogger(__name__)

SCORING_PROMPT_TEMPLATE = """
أنت خبير تحليل مكالمات وتقييم عملاء (Lead Qualification & CRM Specialist).
مهمتك تحليل تفريغ المكالمة الصوتية التالية بين المساعد الصوتي والعميل، واستخراج النتائج بدقة بالغة وفقاً لهدف وسيناريو الحملة.

هدف وسيناريو الحملة المطلوب تحقيقه:
\"\"\"{call_prompt}\"\"\"

بيانات العميل المتاحة:
- الاسم: {customer_name}
- بيانات إضافية من الشيت: {attributes_json}

تفريغ المحادثة الصوتية:
\"\"\"{transcript}\"\"\"

المطلوب:
حلل المحادثة واستخرج النتيجة بصيغة JSON حصراً بالشكل التالي دون أي نصوص إضافية:
{{
    "interest_level": "hot" | "warm" | "cold" | "callback" | "unreached",
    "call_summary": "ملخص واضح ومركز لما حدث في المكالمة في سطرين",
    "customer_intent": "ما يريده العميل بالضبط أو سبب رفضه / قبوله",
    "extracted_data": {{
        "key_answers": "الإجابات الرئيسية للأسئلة المحددة في سيناريو الحملة",
        "action_required": "الإجراء المطلوب من فريق العمل إن وجد (مثل: إرسال عرض، حجز موعد، إلخ)",
        "preferred_time": "الوقت المناسب للتواصل إن طلبه العميل"
    }}
}}

معايير تصنيف interest_level بدقة:
- "hot": العميل مهتم جداً، متفاعل، وافق على العرض أو حجز موعداً أو طلب بدء الإجراءات.
- "warm": العميل مهتم لكن لديه استفسارات، يحتاج تفكيراً، أو طلب تفاصيل عبر واتساب / اتصال لاحق.
- "cold": العميل غير مهتم صراحة، رفض العرض، أو قال لا يتناسب معه.
- "callback": العميل طلب الاتصال به في وقت آخر لأنه مشغول الآن.
- "unreached": لم يتم التحدث مع العميل فعلياً أو المكالمة انقطعت قبل البدء.
"""

def score_and_extract_lead(call_prompt: str, transcript: str, customer_name: str = "", attributes: dict = None) -> Dict[str, Any]:
    """
    Uses Google Gemini (via centrally configured API key in SystemSetting)
    to classify the lead interest level and extract structured insights based on the campaign's custom prompt.
    """
    if not transcript or len(transcript.strip()) < 10:
        return {
            "interest_level": "unreached",
            "call_summary": "المكالمة انتهت دون محادثة واضحة أو تعذر الاستماع.",
            "customer_intent": "غير محدد",
            "extracted_data": {}
        }

    api_key = SystemSetting.get_gemini_api_key()
    if not api_key:
        logger.warning("Gemini API key is not configured for lead scoring. Using heuristic fallback.")
        return {
            "interest_level": "warm" if len(transcript) > 50 else "uncontacted",
            "call_summary": transcript[:200] + "...",
            "customer_intent": "غير محدد (مفتاح Gemini غير مضبوط)",
            "extracted_data": {}
        }

    try:
        from google import genai
        client = genai.Client(api_key=api_key)

        prompt = SCORING_PROMPT_TEMPLATE.format(
            call_prompt=call_prompt or "تقييم اهتمام العميل وتلخيص طلبه",
            customer_name=customer_name or "عميل",
            attributes_json=json.dumps(attributes or {}, ensure_ascii=False),
            transcript=transcript
        )

        response = client.models.generate_content(
            model='gemini-3.8-flash',
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )

        text = response.text.strip()
        data = json.loads(text)
        return {
            "interest_level": data.get("interest_level", "warm"),
            "call_summary": data.get("call_summary", ""),
            "customer_intent": data.get("customer_intent", ""),
            "extracted_data": data.get("extracted_data", {})
        }
    except Exception as e:
        logger.error(f"Error in score_and_extract_lead: {e}", exc_info=True)
        return {
            "interest_level": "warm",
            "call_summary": "مكالمة تمت بنجاح (حدث خطأ أثناء الفرز الذكي).",
            "customer_intent": "",
            "extracted_data": {"error": str(e)}
        }
