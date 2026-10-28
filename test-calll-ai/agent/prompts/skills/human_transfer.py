"""Smart Human Handoff Skill supporting Multi-Tenant Dynamic Queues and Omnichannel routing."""
from typing import List, Dict, Any, Optional
from .base import Skill


def build_human_transfer_instruction(
    call_queues: Optional[List[Dict[str, Any]]] = None,
    channel: str = "voice",
    language: str = "arabic",
    dialect: str = "egyptian"
) -> str:
    """
    Constructs adaptive human handoff instruction based on the tenant's live queues,
    the interaction medium (Voice call vs WhatsApp chat), and the profile dialect/language.
    Supports 3 distinct multi-tenant operational states:
    1. Multi-Queue Tenant: Intent-based semantic matching and routing
    2. Single-Queue Tenant: Direct warm handoff without department friction
    3. Zero-Queue / Off-Hours Tenant: Intelligent containment and callback capture
    """
    ch = str(channel or "voice").lower().strip()
    is_whatsapp = ch in ["whatsapp", "wa", "text"]
    lang_key = (language or "arabic").lower().strip()
    dia_key = (dialect or "egyptian").lower().strip()

    is_non_arabic = (
        lang_key in ["english", "en", "french", "fr", "spanish", "es", "german", "de", "italian", "it", "turkish", "tr", "russian", "ru", "urdu", "ur", "hindi", "hi", "chinese", "zh"]
        or any(dia_key.startswith(p) for p in ["english", "en", "french", "fr", "spanish", "es", "german", "de", "italian", "it", "turkish", "tr", "russian", "ru", "urdu", "ur", "hindi", "hi", "chinese", "zh"])
    )

    # Dialect-appropriate execution and discovery phrasing
    if is_non_arabic:
        discovery_phrase = '"May I know what your inquiry or issue is specifically so I can assist you or route you to the appropriate department?"'
        voice_multi_exec = (
            "In voice call: Say a reassuring, concise transfer phrase in your configured language:\n"
            '"Certainly, I am transferring you right now to [Department Name], please stay on the line..."\n'
            "and immediately call [transfer_to_queue] with the department code and reason summary in 'reason'."
        )
    elif "saudi" in dia_key or "gulf" in dia_key or "emirati" in dia_key or "kuwaiti" in dia_key:
        discovery_phrase = "«سمّ طال عمرك، إيش المشكلة أو الاستفسار بالتحديد عشان أقدر أخدمك أو أوجهك للقسم المختص؟»"
        voice_multi_exec = (
            "في المكالمة الصوتية: انطق جملة تمهيدية مطمئنة وموجزة بلهجتك الطبيعية:\n"
            "«أبشر طال عمرك، بحولك الحين لقسم [اسم القسم]، ثواني معي...»\n"
            "واستدعِ أداة [transfer_to_queue] فوراً بكود القسم المحدد وتمرير ملخص المشكلة في 'reason'.\n"
            "ويُمنع منعاً باتاً قراءة أي معطيات تقنية أو أكواد للمتصل."
        )
    elif "levantine" in dia_key or "jordanian" in dia_key or "palestinian" in dia_key:
        discovery_phrase = "«تكرم عينك، شو المشكلة أو الاستفسار بالتحديد حتى أقدر ساعدك أو وجهك للقسم المختص؟»"
        voice_multi_exec = (
            "في المكالمة الصوتية: انطق جملة تمهيدية مطمئنة وموجزة بلهجتك الطبيعية:\n"
            "«تكرم عينك، عم حول حضرتك لقسم [اسم القسم]، لحظة معي...»\n"
            "واستدعِ أداة [transfer_to_queue] فوراً بكود القسم المحدد وتمرير ملخص المشكلة في 'reason'.\n"
            "ويُمنع منعاً باتاً قراءة أي معطيات تقنية أو أكواد للمتصل."
        )
    elif "moroccan" in dia_key or "algerian" in dia_key or "tunisian" in dia_key:
        discovery_phrase = "«على راسي، شنو المشكل أو الاستفسار بالضبط باش نقدر نعاونك ولا نوجهك للقسم المختص؟»"
        voice_multi_exec = (
            "في المكالمة الصوتية: انطق جملة تمهيدية مطمئنة وموجزة بلهجتك الطبيعية:\n"
            "«واخا، غادي نحولك دابا لقسم [اسم القسم]، ثواني معايا...»\n"
            "واستدعِ أداة [transfer_to_queue] فوراً بكود القسم المحدد وتمرير ملخص المشكلة في 'reason'.\n"
            "ويُمنع منعاً باتاً قراءة أي معطيات تقنية أو أكواد للمتصل."
        )
    elif "fusha" in dia_key:
        discovery_phrase = "«تحت أمرك يا سيدي، ما هي المشكلة أو الاستفسار بالتحديد لأتمكن من مساعدتك أو توجيهك للقسم المختص؟»"
        voice_multi_exec = (
            "في المكالمة الصوتية: انطق جملة تمهيدية مطمئنة وموجزة:\n"
            "«بالتأكيد يا سيدي، سأقوم بتحويلك فوراً إلى قسم [اسم القسم]، لحظات معي...»\n"
            "واستدعِ أداة [transfer_to_queue] فوراً بكود القسم المحدد وتمرير ملخص المشكلة في 'reason'.\n"
            "ويُمنع منعاً باتاً قراءة أي معطيات تقنية أو أكواد للمتصل."
        )
    else:
        # Egyptian default
        discovery_phrase = "«تحت أمرك يا فندم، إيه المشكلة أو الاستفسار بالتحديد عشان أقدر أساعدك أو أوجهك للقسم المختص؟»"
        voice_multi_exec = (
            "في المكالمة الصوتية: انطق جملة تمهيدية مطمئنة وموجزة بلهجتك الطبيعية:\n"
            "«حاضر يا فندم، هحول حضرتك حالاً لقسم [اسم القسم]، ثواني معايا...»\n"
            "واستدعِ أداة [transfer_to_queue] فوراً بكود القسم المحدد وتمرير ملخص المشكلة في 'reason'.\n"
            "ويُمنع منعاً باتاً قراءة أي معطيات تقنية أو أكواد للمتصل."
        )

    # Action verbs & tool names depending on medium
    if is_whatsapp:
        exec_instruction = (
            "في محادثة الواتساب: أبلغ العميل فوراً برسالة نصية واضحة:\n"
            "«تم تحويل محادثتك الآن لممثل خدمة العملاء في قسم [اسم القسم]، وسيقوم بالرد على حضرتك هنا في الشات فوراً.»\n"
            "واستدعِ أداة [handover_to_human_agent] بكود القسم والسبب لتوجيه الشات للموظف وتعطيل ردود البوت مؤقتاً."
        )
    else:
        exec_instruction = voice_multi_exec

    # State 1: Multi-Queue Tenant
    if call_queues and len(call_queues) > 1:
        q_lines = []
        for q in call_queues:
            name = q.get("name", "خدمة العملاء")
            code = q.get("code", "general")
            desc = f" - اختصاصاته وشروط التحويل إليه: {q['description']}" if q.get("description") else ""
            q_lines.append(f"- قسم {name} [كود التحويل: {code}]{desc}")
        q_list_str = "\n".join(q_lines)

        return f"""[مهارة التوجيه والتحويل البشري الذكي (Smart Human Handoff Skill)]:
أقسام وطوابير خدمة العملاء المتاحة حصراً في هذه المنشأة:
{q_list_str}

بروتوكول التحويل الذكي والتسليم الدافئ (Warm Handoff Protocol):
1. استكشاف المشكلة والمطابقة الدلالية للقسم (Discovery & Semantic Matching):
   - عندما يطلب العميل التحويل لأول مرة: اسأله بلطف واختصار شديد: {discovery_phrase}.
   - طابق مشكلة واحتياج العميل فوراً مع القسم الأنسب من قائمة أقسام المنشأة أعلاه بناءً على اختصاصات كل قسم.
2. التحويل السريع لامتصاص الغضب الشديد (Fast-Track De-escalation):
   - إذا رصدت في نبرة المتصل غضباً حاداً، أو حالة طارئة، أو أصر بحزم على التحدث مع موظف: تجاوز الأسئلة فوراً وبادر بالتحويل للقسم الأنسب دون مماطلة أو جدال لحماية رضا العميل!
3. التسليم الدافئ الشامل (Warm Handoff Summary):
   - عند تنفيذ التحويل، مرر في خانة (reason) ملخصاً وافياً وموجزاً للموظف البشري: [اسم العميل + ملخص المشكلة بالتحديد + درجة الإلحاح]، حتى تظهر للموظف فور استلامه للمحادثة ولا يضطر العميل لإعادة شرح مشكلته من البداية.
4. تنفيذ التحويل عبر القناة المناسبة:
   - {exec_instruction}
5. الالتزام بالأقسام الرسمية:
   - يُمنع منعاً باتاً اختراع أي أقسام أو أرقام طوابير غير الموجودة في القائمة أعلاه."""

    # State 2: Single-Queue Tenant
    elif call_queues and len(call_queues) == 1:
        q = call_queues[0]
        q_name = q.get("name", "خدمة العملاء")
        q_code = q.get("code", "general")
        q_desc = f" ({q['description']})" if q.get("description") else ""

        if is_whatsapp:
            single_exec = (
                f"في محادثة الواتساب: أبلغ العميل: «تم تحويلك لممثل {q_name} وسيقوم بالرد على حضرتك مباشرة» "
                f"واستدعِ [handover_to_human_agent] بكود '{q_code}' مع ملخص المشكلة."
            )
        else:
            if is_non_arabic:
                single_phrase = f'"Certainly, I am transferring you right now to a {q_name} representative, please stay on the line..."'
            elif "saudi" in dia_key or "gulf" in dia_key or "emirati" in dia_key or "kuwaiti" in dia_key:
                single_phrase = f"«أبشر طال عمرك، بحولك الحين لممثل {q_name}، ثواني معي...»"
            elif "levantine" in dia_key or "jordanian" in dia_key or "palestinian" in dia_key:
                single_phrase = f"«تكرم عينك، عم حولك لممثل {q_name}، لحظة معي...»"
            elif "moroccan" in dia_key or "algerian" in dia_key or "tunisian" in dia_key:
                single_phrase = f"«واخا، غادي نحولك دابا لممثل {q_name}، ثواني معايا...»"
            elif "fusha" in dia_key:
                single_phrase = f"«بالتأكيد يا سيدي، سأقوم بتحويلك فوراً إلى ممثل {q_name}، لحظات معي...»"
            else:
                single_phrase = f"«حاضر يا فندم، هحول حضرتك حالاً لممثل {q_name}، ثواني معايا...»"

            single_exec = (
                f"في المكالمة الصوتية: انطق: {single_phrase} "
                f"واستدعِ [transfer_to_queue] بكود '{q_code}' مع ملخص المشكلة."
            )

        return f"""[مهارة التوجيه والتحويل البشري الذكي (Smart Human Handoff Skill)]:
طابور خدمة العملاء المتاح للمنشأة:
- قسم {q_name} [كود التحويل: {q_code}]{q_desc}

بروتوكول التحويل المباشر للطابور الموحد:
1. استكشاف المشكلة: افهم مشكلة العميل باختصار دون سؤاله عن تحديد القسم (نظراً لوجود طابور عام موحد).
2. التسليم الدافئ: مرر ملخص المشكلة واحتياج العميل في 'reason' ليطلع عليه الموظف البشري فور الرد.
3. تنفيذ التحويل:
   - {single_exec}
4. تحويل الغضب الطارئ: إذا كان العميل منفعلاً جداً أو كرر طلبه، حوله فوراً دون تأخير."""

    # State 3: Zero-Queue / Off-Hours Tenant
    else:
        if is_whatsapp:
            if is_non_arabic:
                apology_text = '"I apologize, our customer service representatives are currently offline outside of regular business hours. However, I am available 24/7 and fully equipped to assist with all your questions and requests. How can I help you today?"'
                callback_text = '"I would be glad to log a ticket with your inquiry, and our team will follow up with you as soon as business hours resume."'
            else:
                apology_text = "«بعتذر لحضرتك جداً يا فندم، ممثلو خدمة العملاء غير متاحين حالياً في الشات نظراً لانتهاء ساعات العمل الرسمية، لكن أنا معاك على مدار الساعة وتحت أمرك أقدر أساعدك في كل استفساراتك وتنفيذ طلبك بالكامل، تحب أساعدك في إيه؟»"
                callback_text = "«تحت أمرك يا فندم، ممكن أسجل لحضرتك تذكرة باستفسارك وتفاصيل طلبك، وأول ما يبدأ دوام العمل الصباحي سيتواصل معك أحد مسؤولينا هنا فوراً؟»"
        else:
            if is_non_arabic:
                apology_text = '"I apologize, customer service representatives are currently unavailable outside of regular business hours. However, I am right here with you and fully equipped to assist with all your questions and requests. How may I help you today?"'
                callback_text = '"I would be glad to register a callback ticket with your inquiry and contact information, and our team will follow up with you as soon as business hours open."'
            elif "saudi" in dia_key or "gulf" in dia_key or "emirati" in dia_key or "kuwaiti" in dia_key:
                apology_text = "«المعذرة منك طال عمرك، ممثلو خدمة العملاء غير متاحين حالياً لانتهاء ساعات العمل الرسمية، لكن أنا معك وجاهز أخدمك في كل استفساراتك وتنفيذ طلبك بالكامل، تفضل إيش أقدر أساعدك؟»"
                callback_text = "«أبشر، أقدر أسجل لك تذكرة بمشكلتك ورقم جوالك، وأول ما يبدأ دوام الصباح بيتواصل معك فريق العمل فوراً بإذن الله؟»"
            elif "levantine" in dia_key or "jordanian" in dia_key or "palestinian" in dia_key:
                apology_text = "«بعتذر من حضرتك، ممثلو خدمة العملاء غير متاحين حالياً لانتهاء ساعات العمل الرسمية، لكن أنا معك وتحت أمرك ساعدك بكل استفساراتك وطلبك، تفضل شو بتحب ساعدك؟»"
                callback_text = "«تكرم عينك، بقدر سجل لحضرتك تذكرة باستفسارك ورقم هاتفك، وأول ما يبدأ دوام الصباح بيتواصل معك فريق العمل فوراً؟»"
            elif "moroccan" in dia_key or "algerian" in dia_key or "tunisian" in dia_key:
                apology_text = "«كنعتذر منك، ممثلو خدمة العملاء غير متاحين دابا لانتهاء ساعات العمل الرسمية، ولكن أنا معاك نقدر نعاونك فكل استفساراتك، تفضل كيفاش نقدر نعاونك؟»"
                callback_text = "«واخا، نقدر نسجل ليك تذكرة بالمشكل ديالك ورقم التيليفون، ومع بداية العمل فالصباح غادي يتواصل معاك الفريق ديالنا فوراً؟»"
            elif "fusha" in dia_key:
                apology_text = "«أعتذر منك يا سيدي، ممثلو خدمة العملاء غير متاحين حالياً نظراً لانتهاء ساعات العمل الرسمية، لكنني معك ومستعد لمساعدتك في كافة استفساراتك وتنفيذ طلبك، تفضل كيف يمكنني مساعدتك؟»"
                callback_text = "«تحت أمرك يا سيدي، هل ترغب في أن أسجل لك تذكرة باستفسارك ورقم هاتفك، وسيتواصل معك فريق العمل فور بدء ساعات العمل الرسمية؟»"
            else:
                apology_text = "«بعتذر لحضرتك جداً يا فندم، ممثلو خدمة العملاء غير متاحين حالياً نظراً لانتهاء ساعات العمل الرسمية، لكن أنا معاك وتحت أمرك أقدر أساعدك في كل استفساراتك وتنفيذ طلبك بالكامل، تحب أساعدك في إيه؟»"
                callback_text = "«تحت أمرك يا فندم، ممكن أسجل لحضرتك تذكرة بمشكلتك ورقم تليفونك، وأول ما فريق العمل يبدأ دوام الصباح هيتواصلوا مع حضرتك فوراً؟»"

        return f"""[مهارة التوجيه والتحويل البشري الذكي - بروتوكول الاحتواء خارج أوقات العمل (Off-Hours & Zero-Queue Fallback)]:
- لا تتوفر أي طوابير انتظار أو موظفون بشريون متاحون للتحويل حالياً في هذه المنشأة (نظراً لانتهاء ساعات العمل الرسمية أو لعدم توفر موظفي خدمة عملاء بشريين).
- إذا طلب العميل التحدث مع موظف بشري أو خدمة العملاء أو الدعم الفني:
  1. الاعتذار اللبق وطمأنة العميل:
     اعتذر له بلطف ولباقة: {apology_text}.
  2. الاحتواء وتسجيل بيانات المتابعة (Callback Capture):
     إذا أصر العميل على التحدث مع ممثل بشري، اعرض عليه تسجيل طلبه ورقم هاتفه للمتابعة:
     {callback_text}.
  3. حظر الأعطال الوهمية:
     يُمنع منعاً باتاً الادعاء بوجود عطل فني في السيستم، أو البحث في المستندات (RAG) عن أدوات تحويل وهمية."""


class HumanTransferSkill(Skill):
    """Adaptive Human Transfer Skill that renders dynamic queues and omnichannel rules."""
    def render(self, context: Optional[Dict[str, Any]] = None) -> str:
        ctx = context or {}
        call_queues = ctx.get("call_queues")
        channel = ctx.get("channel", "voice")
        language = ctx.get("language", "arabic")
        dialect = ctx.get("dialect", "egyptian")
        return build_human_transfer_instruction(call_queues=call_queues, channel=channel, language=language, dialect=dialect)


HUMAN_TRANSFER_SKILL = HumanTransferSkill(
    id="human_transfer",
    name="التوجيه والتحويل البشري الذكي والتسليم الدافئ",
    description="توجيه العملاء دلالياً للأقسام المختصة، التسليم الدافئ للموظف، والاحتواء الذكي خارج أوقات العمل عبر الهاتف والواتساب.",
    prompt_instruction="بروتوكول التحويل البشري الذكي والتسليم الدافئ حسب طوابير المنشأة وقناة التواصل.",
    required_tools=["transfer_to_queue", "handover_to_human_agent"],
    tags=["escalation", "queues", "omnichannel"]
)

