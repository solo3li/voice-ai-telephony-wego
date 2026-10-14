"""Dynamic Skill Loader supporting Built-in, Custom, and External Claude/MCP Skills."""
import logging
from typing import List, Dict, Any, Optional
from .base import Skill
from .delivery_address import DELIVERY_ADDRESS_SKILL

logger = logging.getLogger(__name__)

# Built-in Skills Registry
SKILLS_REGISTRY: Dict[str, Skill] = {
    "delivery_address": DELIVERY_ADDRESS_SKILL,
    "whatsapp_summary": Skill(
        id="whatsapp_summary",
        name="تأكيد ومتابعة الواتساب بعد المكالمة",
        description="إرسال ملخص الطلب ورابط التتبع المباشر وطلب تقييم الخدمة عبر الواتساب.",
        prompt_instruction="إرسال الواتساب أثناء المكالمة (أداة send_whatsapp_message): إذا طلب العميل إرسال المنيو، أو لوكيشن، أو تفاصيل الطلب، أو أي معلومة على الواتساب، استدعِ أداة [send_whatsapp_message] فوراً مع نص الرسالة المطلوب لتصل لرقم هاتفه أثناء المكالمة.",
        required_tools=["send_whatsapp_message"],
        tags=["whatsapp", "omnichannel"]
    ),
    "lead_qualification": Skill(
        id="lead_qualification",
        name="تأهيل العميل البيعي (BANT Qualification)",
        description="استكشاف الميزانية، الإطار الزمني، الحاجة، والقدرة على اتخاذ القرار قبل تقديم العروض.",
        prompt_instruction="قواعد تأهيل العميل البيعي:\n1. استكشف بلباقة الميزانية التقريبية التي يفضلها العميل.\n2. حدد موعد الانتقال أو التنفيذ المستهدف.\n3. تحقق عما إذا كان هناك شركاء أو أفراد عائلة يشاركونه القرار لتقديم العرض الأنسب لهم جميعاً.",
        tags=["sales", "real_estate"]
    ),
    "troubleshooting_triage": Skill(
        id="troubleshooting_triage",
        name="تشخيص الأعطال وفرز التذاكر",
        description="اتباع شجرة تشخيص منظمة واستخراج كود الخطأ وفتح تذكرة دعم.",
        prompt_instruction="قواعد تشخيص الأعطال والدعم:\n1. اسأل العميل عن رسالة الخطأ الظاهرة لديه وسلوك الجهاز.\n2. اطلب منه بهدوء تجربة الإجراء الأولي البسيط (إعادة التشغيل أو فحص الكابلات).\n3. إن لم يُحل العطل فوراً، افتح تذكرة دعم فني وزوده برقم التذكرة والوقت المتوقع للمعالجة.",
        tags=["tech_support", "it"]
    )
}


def register_skill(skill: Skill) -> None:
    """Register or overwrite a skill in the global registry."""
    SKILLS_REGISTRY[skill.id] = skill


def load_custom_skills_from_profile(profile: Dict[str, Any]) -> List[Skill]:
    """
    Extracts custom or external skills defined directly in the agent's profile.
    Supports Claude/MCP style skill manifests:
    - dict with keys: 'id' or 'name', 'instructions', 'tools', etc.
    """
    custom_skills: List[Skill] = []
    raw_custom = profile.get("custom_skills") or []
    if isinstance(raw_custom, list):
        for idx, item in enumerate(raw_custom):
            if isinstance(item, Skill):
                custom_skills.append(item)
            elif isinstance(item, dict):
                s_id = str(item.get("id") or item.get("name") or f"custom_skill_{idx+1}").strip()
                s_name = str(item.get("name") or s_id).strip()
                s_desc = str(item.get("description") or "").strip()
                s_prompt = str(item.get("instructions") or item.get("prompt_instruction") or item.get("prompt") or "").strip()
                s_tools = item.get("tools") or item.get("required_tools") or []
                if s_prompt:
                    custom_skills.append(Skill(
                        id=s_id,
                        name=s_name,
                        description=s_desc,
                        prompt_instruction=s_prompt,
                        required_tools=s_tools,
                        tags=["custom", "external"]
                    ))
    return custom_skills


def resolve_active_skills(
    profile: Dict[str, Any],
    role_key: Optional[str] = None,
    available_tools: Optional[List[Dict[str, Any]]] = None
) -> List[Skill]:
    """
    Determines all active skills for an agent, combining:
    1. Explicitly enabled skills (if specified in profile)
    2. Role-based default skills (if no explicit list)
    3. Tool-driven fallback (e.g. food delivery address skill if order tools exist)
    4. Custom/External skills defined in the profile
    """
    active_skills: Dict[str, Skill] = {}

    # Check available tool names for automatic detection
    tool_names = set()
    if available_tools:
        for t in available_tools:
            name = t.get("name") if isinstance(t, dict) else getattr(t, "name", None)
            if name:
                tool_names.add(str(name).strip())

    # 1. Explicitly enabled skills in profile
    enabled_keys = profile.get("enabled_skills")
    if enabled_keys is not None and isinstance(enabled_keys, list):
        for key in enabled_keys:
            k_clean = str(key).strip()
            if k_clean in SKILLS_REGISTRY:
                active_skills[k_clean] = SKILLS_REGISTRY[k_clean]
    else:
        # Default behavior: Inspect role and available tools for backward compatibility
        clean_role = str(role_key or profile.get("persona_role") or "").strip()
        from agent.prompts.roles.registry import get_role_default_skills
        default_keys = get_role_default_skills(clean_role)
        for dk in default_keys:
            if dk in SKILLS_REGISTRY:
                active_skills[dk] = SKILLS_REGISTRY[dk]

        # Automatic tool-driven skill activation:
        # If order creation tools or menu lookups are present, activate delivery address skill
        order_tool_indicators = {"create_callcenter_order", "preview_callcenter_order", "search_knowledge_base"}
        if tool_names.intersection(order_tool_indicators) and clean_role in ["restaurant_orders", "delivery_dispatch", ""]:
            active_skills["delivery_address"] = DELIVERY_ADDRESS_SKILL

    # 2. Append custom / external skills
    for cs in load_custom_skills_from_profile(profile):
        active_skills[cs.id] = cs

    return list(active_skills.values())
