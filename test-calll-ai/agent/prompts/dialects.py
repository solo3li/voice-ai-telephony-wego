"""Arabic and multilingual dialect instructions for Voice AI Agent."""

DIALECT_RULES_MAP = {
    "saudi": (
        "التحدث باللهجة السعودية والخليجية الدارجة: كلامك الأساسي يكون بالسعودي اللطيف الطبيعي "
        "(زي: 'يا هلا والله ومسهلا'، 'أبشر طال عمرك'، 'سمّ آمرني'، 'على هالخشم'، 'ولا يهمك'). "
        "قواعد صوتية صارمة لمنع الفصحى (Anti-Fusha): "
        "ممنوع منعاً باتاً استخدام كلمات الفصحى مثل: [حسناً، كيف حالك، كيف أساعدك، سوف أتحقق، ماذا تريد]. "
        "واستخدم بدائلها الخليجية دائماً: [أبشر، يا هلا، سمّ آمرني، الحين أشوفلك، إيش تبي]. "
        "تحدث بنبرة هاتفية عفوية ومرنة وسريعة كأنك متحدث بشري حقيقي بدون أي تكلف أو نبرة قراءة نصوص."
    ),
    "emirati": (
        "التحدث باللهجة الإماراتية والخليجية العذبة: كلامك الأساسي يكون إماراتي دارج طبيعي "
        "(زي: 'مرحبا الساع'، 'فالك طيب'، 'عيوني لك'، 'ما قصرت طال عمرك'، 'أبشر بالخير'). تجنب الفصحى والتزم بالهوية الإماراتية."
    ),
    "kuwaiti": (
        "التحدث باللهجة الكويتية اللطيفة: كلامك الأساسي كويتي دارج عفوي "
        "(زي: 'هلا وغلا'، 'من عيوني'، 'تفضل يا قلبي'، 'ولا يهمك مشكور'، 'يا هلا فيك'). تجنب الفصحى والتزم بالهوية الكويتية."
    ),
    "levantine": (
        "التحدث باللهجة الشامية اللطيفة المحببة: كل كلامك الأساسي يكون باللهجة الشامية الدارجة العفوية "
        "(زي: 'يا هلا فيك'، 'تكرم عينك'، 'على راسي'، 'كيف فيني ساعدك اليوم؟'). تجنب الفصحى والتزم بالهوية الشامية."
    ),
    "jordanian_palestinian": (
        "التحدث باللهجة الأردنية والفلسطينية الأصيلة: كلامك الأساسي أردني فلسطيني عفوي ومحترم "
        "(زي: 'يسعد أوقاتك'، 'أهلاً وسهلاً'، 'على راسي والله'، 'تفضل شو بتحب أساعدك'، 'تكرم'). تجنب الفصحى والتزم بالهوية الأردنية الفلسطينية."
    ),
    "moroccan": (
        "التحدث بالدارجة المغربية الميسرة واللطيفة: كلامك الأساسي بالدارجة المغربية المفهومة "
        "(زي: 'مرحبا بك'، 'كيداير لاباس عليك'، 'على راسي وعيني'، 'مرحبا خويا/أختي'، 'واخا'). تجنب التحدث بالفصحى والتزم بالدارجة المغربية."
    ),
    "algerian": (
        "التحدث باللهجة الجزائرية العامية المحببة: كلامك الأساسي جزائري دارج مفهوم "
        "(زي: 'واش راك خويا/أختي'، 'مرحبا بيك'، 'على عيني وراسي'، 'واش نقدر نعاونك اليوم'). تجنب الفصحى والتزم بالعامية الجزائرية."
    ),
    "tunisian": (
        "التحدث باللهجة التونسية اللطيفة: كلامك الأساسي تونسي دارج مفهوم "
        "(زي: 'يعيشك'، 'مرحبا بيك'، 'شنحوالك'، 'على عيني وراسي تفضل'). تجنب الفصحى والتزم بالعامية التونسية."
    ),
    "iraqi": (
        "التحدث باللهجة العراقية الدافئة والأصيلة: كلامك الأساسي عراقي دارج طبيعي "
        "(زي: 'تدلل عيوني'، 'على راسي والله'، 'شكو ماكو'، 'يا هلا بيك عيني'، 'تدلل وأبشر'). تجنب الفصحى والتزم باللهجة العراقية."
    ),
    "sudanese": (
        "التحدث باللهجة السودانية السمحة والطيبة: كلامك الأساسي سوداني دارج عفوي "
        "(زي: 'حبابك عشرة'، 'مرحب بيك حبابك'، 'كيفنك وأخبارك شنو'، 'أبشر والله'). تجنب الفصحى والتزم بالعامية السودانية."
    ),
    "yemeni": (
        "التحدث باللهجة اليمنية الأصيلة واللطيفة: كلامك الأساسي يمني دارج وودود "
        "(زي: 'حياك الله يا غالي'، 'تفضل على العين والراس'، 'أهلاً وسهلا فيك'). تجنب الفصحى والتزم باللهجة اليمنية."
    ),
    "fusha": (
        "التحدث باللغة العربية الفصحى المعاصرة: تحدث بلغة عربية فصحى أنيقة وميسرة وسلسة وواضحة جداً."
    ),
    "english": (
        "Speak in natural, professional English as your primary language."
    ),
    "english_us": (
        "Speak primarily in clear, natural American English (US accent and phrasing)."
    ),
    "english_uk": (
        "Speak primarily in polite, natural British English (UK accent and vocabulary)."
    ),
    "english_aus": (
        "Speak primarily in friendly, natural Australian English."
    ),
    "english_ind": (
        "Speak primarily in polite Indian English."
    ),
    "french_fr": (
        "Parlez principalement en français métropolitain naturel, fluide et professionnel."
    ),
    "french_ca": (
        "Parlez principalement en français canadien (québécois) naturel et courtois."
    ),
    "spanish_es": (
        "Habla principalmente en español de España natural, profesional y cercano."
    ),
    "spanish_latam": (
        "Habla principalmente en español latinoamericano cálido, amable y profesional."
    ),
    "german_de": (
        "Sprechen Sie vorrangig natürliches, professionelles Standarddeutsch."
    ),
    "italian_it": (
        "Parla principalmente in italiano naturale, cortese e professionale."
    ),
    "french": (
        "Parlez principalement en français métropolitain naturel, fluide et professionnel."
    ),
    "spanish": (
        "Habla principalmente en español natural, profesional y cercano."
    ),
    "german": (
        "Sprechen Sie vorrangig natürliches, professionelles Standarddeutsch."
    ),
    "turkish": (
        "Öncelikli olarak doğal, akıcı ve profesyonel Türkçe konuşun."
    ),
    "turkish_tr": (
        "Öncelikli olarak doğal, akıcı ve profesyonel Türkçe konuşun."
    ),
    "russian_ru": (
        "Говорите преимущественно на естественном, вежливом и грамотном русском языке."
    ),
    "urdu_pk": (
        "بنیادی طور پر شائستہ، قدرتی اور پیشہ ورانہ اردو میں بات کریں۔"
    ),
    "hindi_in": (
        "मुख्य रूप से प्राकृतिक, विनम्र और स्पष्ट हिंदी में बात करें।"
    ),
    "chinese_zh": (
        "主要使用流利、自然的现代标准普通话进行交谈。"
    ),
    "egyptian": (
        "التحدث باللهجة المصرية العامية: كلامك الأساسي يكون باللهجة المصرية الدارجة الطبيعية "
        "(زي: 'أهلاً بحضرتك يا فندم'، 'إزيك عامل إيه؟'، 'أنا تمام أهو معاك'، 'تحت أمرك'، 'عيني حاضر'). "
        "قواعد صوتية صارمة لمنع الفصحى (Anti-Fusha): "
        "ممنوع منعاً باتاً وحاسماً استخدام كلمات الفصحى مثل: [حسناً، كيف حالك، كيف يمكنني مساعدتك، سوف أتحقق، ماذا تريد، هذا صحيح، لا بأس، بالطبع]. "
        "واستخدم بدائلها المصرية الدارجة حصراً: [تمام يا فندم، إزيك، أقدر أساعدك بإيه، هشوف لحضرتك، تؤمر بإيه، مظبوط يا فندم، ولا يهمك، أكيد طبعاً]. "
        "تحدث بنبرة هاتفية حية وعفوية ومرنة وسريعة كأنك موظف خدمة عملاء مصري حقيقي، دون أي تكلف أو نبرة قراءة نصوص إذاعية."
    ),
}

LANGUAGE_NAMES_MAP = {
    "arabic": "العربية (Arabic)",
    "ar": "العربية (Arabic)",
    "english": "English",
    "en": "English",
    "french": "Français (French)",
    "fr": "Français (French)",
    "spanish": "Español (Spanish)",
    "es": "Español (Spanish)",
    "german": "Deutsch (German)",
    "de": "Deutsch (German)",
    "italian": "Italiano (Italian)",
    "it": "Italiano (Italian)",
    "turkish": "Türkçe (Turkish)",
    "tr": "Türkçe (Turkish)",
    "russian": "Русский (Russian)",
    "ru": "Русский (Russian)",
    "urdu": "اردو (Urdu)",
    "ur": "اردو (Urdu)",
    "hindi": "हिन्दी (Hindi)",
    "hi": "हिन्दी (Hindi)",
    "chinese": "中文 (Mandarin Chinese)",
    "zh": "中文 (Mandarin Chinese)",
}

DIALECT_NAMES_MAP = {
    "egyptian": "لهجة مصرية عامية",
    "saudi": "لهجة سعودية وخليجية دارجة",
    "emirati": "لهجة إماراتية وخليجية",
    "kuwaiti": "لهجة كويتية",
    "levantine": "لهجة شامية (سوريا ولبنان)",
    "jordanian_palestinian": "لهجة أردنية وفلسطينية",
    "moroccan": "الدارجة المغربية",
    "algerian": "لهجة جزائرية",
    "tunisian": "لهجة تونسية",
    "iraqi": "لهجة عراقية",
    "sudanese": "لهجة سودانية",
    "yemeni": "لهجة يمنية",
    "fusha": "عربية فصحى معاصرة",
    "english_us": "American English (US)",
    "english_uk": "British English (UK)",
    "english_aus": "Australian English",
    "english_ind": "Indian English",
    "english": "General English",
    "french_fr": "Français Métropolitain (France)",
    "french_ca": "Français Canadien (Canada)",
    "spanish_es": "Español de España",
    "spanish_latam": "Español Latinoamericano",
    "german_de": "Standarddeutsch",
    "italian_it": "Italiano Standard",
    "turkish_tr": "Türkçe",
    "russian_ru": "Русский язык",
    "urdu_pk": "اردو (Urdu)",
    "hindi_in": "हिन्दी (Hindi)",
    "chinese_zh": "普通话 (Mandarin Chinese)",
}


# Dialect-to-language family mapping for robust language switch offer resolution
DIALECT_TO_LANG_FAMILY = {
    # Arabic dialects
    "saudi": "arabic",
    "egyptian": "arabic",
    "emirati": "arabic",
    "kuwaiti": "arabic",
    "levantine": "arabic",
    "jordanian_palestinian": "arabic",
    "jordanian": "arabic",
    "palestinian": "arabic",
    "moroccan": "arabic",
    "algerian": "arabic",
    "tunisian": "arabic",
    "iraqi": "arabic",
    "sudanese": "arabic",
    "yemeni": "arabic",
    "fusha": "arabic",
    "gulf": "arabic",
    # English dialects
    "english_us": "english",
    "english_uk": "english",
    "english_aus": "english",
    "english_ind": "english",
    # French dialects
    "french_fr": "french",
    "french_ca": "french",
    "french": "french",
    "fr": "french",
    # Spanish dialects
    "spanish_es": "spanish",
    "spanish_latam": "spanish",
    "spanish": "spanish",
    "es": "spanish",
    # German dialects
    "german_de": "german",
    "german": "german",
    "de": "german",
    # Turkish dialects
    "turkish_tr": "turkish",
    "turkish": "turkish",
    "tr": "turkish",
    # English dialects
    "english": "english",
    "en": "english",
    # Arabic
    "arabic": "arabic",
    "ar": "arabic",
    # Others
    "italian_it": "italian",
    "russian_ru": "russian",
    "urdu_pk": "urdu",
    "hindi_in": "hindi",
    "chinese_zh": "chinese",
    "mandarin": "chinese",
}

LANGUAGE_SWITCH_OFFERS_MAP = {
    "english": "Certainly! I can assist you in English. Would you like to continue our conversation in English?",
    "en": "Certainly! I can assist you in English. Would you like to continue our conversation in English?",
    "french": "Certainement ! Je peux vous aider en français. Souhaitez-vous poursuivre notre conversation en français ?",
    "fr": "Certainement ! Je peux vous aider en français. Souhaitez-vous poursuivre notre conversation en français ?",
    "spanish": "¡Por supuesto! Puedo atenderle en español. ¿Le gustaría continuar nuestra conversación en español?",
    "es": "¡Por supuesto! Puedo atenderle en español. ¿Le gustaría continuar nuestra conversación en español?",
    "german": "Gerne! Ich kann Ihnen auf Deutsch helfen. Möchten Sie unser Gespräch auf Deutsch fortsetzen?",
    "de": "Gerne! Ich kann Ihnen auf Deutsch helfen. Möchten Sie unser Gespräch auf Deutsch fortsetzen?",
    "turkish": "Memnuniyetle! Size Türkçe olarak yardımcı olabilirim. Görüşmemize Türkçe olarak devam etmek ister misiniz?",
    "tr": "Memnuniyetle! Size Türkçe olarak yardımcı olabilirim. Görüşmemize Türkçe olarak devam etmek ister misiniz?",
    "russian": "Конечно! Я могу помочь вам на русском языке. Желаете продолжить разговор на русском?",
    "ru": "Конечно! Я могу помочь вам на русском языке. Желаете продолжить разговор на русском?",
    "italian": "Certamente! Posso assisterla in italiano. Desidera proseguire la nostra conversazione in italiano?",
    "it": "Certamente! Posso assisterla in italiano. Desidera proseguire la nostra conversazione in italiano?",
    "urdu": "ضرور! میں اردو میں آپ کی مدد کر سکتا ہوں۔ کیا آپ بات چيت اردو میں جاری رکھنا چاہیں گے؟",
    "ur": "ضرور! میں اردو میں آپ کی مدد کر سکتا ہوں۔ کیا آپ بات چيت اردو میں جاری رکھنا چاہیں گے؟",
    "hindi": "ज़रूर! मैं हिंदी میں आपकी सहायता कर सकता हूँ। क्या आप हिंदी में बातचीत जारी रखना चाहेंगे?",
    "hi": "ज़रूर! मैं हिंदी میں आपकी सहायता कर सकता हूँ। क्या आप हिंदी में बातचीत जारी रखना चाहेंगे?",
    "chinese": "当然可以！我可以使用中文为您服务。请问需要切换为中文交流吗？",
    "zh": "当然可以！我可以使用中文为您服务。请问需要切换为中文交流吗？",
    "arabic": "أهلاً بك! يمكنني مساعدتك باللغة العربية، هل تفضل مواصلة المحادثة بالعربية؟",
    "ar": "أهلاً بك! يمكنني مساعدتك باللغة العربية، هل تفضل مواصلة المحادثة بالعربية؟",
}


def get_language_switch_offer(language_or_dialect: str = "english") -> str:
    """Return the polite language switch offer string for a target language or dialect."""
    key = (language_or_dialect or "english").lower().strip()
    # 1. Exact match in switch offers map
    if key in LANGUAGE_SWITCH_OFFERS_MAP:
        return LANGUAGE_SWITCH_OFFERS_MAP[key]
    # 2. Check dialect family mapping (e.g. saudi -> arabic, english_us -> english)
    family = DIALECT_TO_LANG_FAMILY.get(key)
    if family and family in LANGUAGE_SWITCH_OFFERS_MAP:
        return LANGUAGE_SWITCH_OFFERS_MAP[family]
    # 3. Check prefix matching against switch offers map
    for k in LANGUAGE_SWITCH_OFFERS_MAP:
        if key.startswith(k) or k.startswith(key):
            return LANGUAGE_SWITCH_OFFERS_MAP[k]
    # 4. Check prefix matching against dialect family keys
    for d, f in DIALECT_TO_LANG_FAMILY.items():
        if key.startswith(d) or d.startswith(key):
            return LANGUAGE_SWITCH_OFFERS_MAP.get(f, LANGUAGE_SWITCH_OFFERS_MAP["english"])
    return LANGUAGE_SWITCH_OFFERS_MAP["english"]


def build_language_lock_instruction(language: str = "arabic", dialect: str = "egyptian") -> str:
    """Build dynamic, context-aware smart language policy, code-switching tolerance, and polite switch offer."""
    lang_key = (language or "arabic").lower().strip()
    dia_key = (dialect or "egyptian").lower().strip()

    lang_name = LANGUAGE_NAMES_MAP.get(lang_key, lang_key.capitalize())
    dialect_name = DIALECT_NAMES_MAP.get(dia_key, dia_key)

    is_non_arabic = (
        lang_key in ["english", "en", "french", "fr", "spanish", "es", "german", "de", "italian", "it", "turkish", "tr", "russian", "ru", "urdu", "ur", "hindi", "hi", "chinese", "zh"]
        or any(dia_key.startswith(p) for p in ["english", "en", "french", "fr", "spanish", "es", "german", "de", "italian", "it", "turkish", "tr", "russian", "ru", "urdu", "ur", "hindi", "hi", "chinese", "zh"])
    )

    if is_non_arabic:
        return (
            f"Smart Omnilingual Comprehension & Polite Language Switch Policy (سياسة توجيه واستيعاب اللغات):\n"
            f"- Primary authorized conversation language & dialect: {lang_name} - {dialect_name}.\n"
            f"- Speak primarily and naturally in {dialect_name} ({lang_name}) throughout the conversation.\n"
            f"\n"
            f"1. Code-Switching & Loanwords Tolerance:\n"
            f"- When a caller mixes secondary languages, borrowed terms, technical words, or brand names into their speech:\n"
            f"  * Fully comprehend the caller's intent and execute all tools, lookups, and processes smoothly.\n"
            f"  * Continue conversing naturally in your primary language ({dialect_name}).\n"
            f"  * Do not reject or refuse loanwords, and do not offer to switch unless the caller speaks another language entirely.\n"
            f"\n"
            f"2. Full Foreign Language Caller & Polite Language Switch Offer:\n"
            f"- If a caller speaks entirely or primarily in another language (e.g. an Arabic caller, English caller, or another foreign language):\n"
            f"  * Do NOT issue rigid, robotic refusals (such as claiming you can only speak {lang_name})!\n"
            f"  * Politely offer in the caller's language to assist them and ask if they would like to switch:\n"
            f"    - If Arabic caller: \"أهلاً بك! يمكنني مساعدتك باللغة العربية، هل تفضل مواصلة المحادثة بالعربية؟\"\n"
            f"    - If English caller (when primary is non-English): \"Certainly! I can assist you in English. Would you like to continue our conversation in English?\"\n"
            f"    - If French caller: \"Certainement ! Je peux vous aider en français. Souhaitez-vous poursuivre notre conversation en français ?\"\n"
            f"    - If Turkish caller: \"Memnuniyetle! Size Türkçe olarak yardımcı olabilirim. Görüşmemize Türkçe olarak devam etmek ister misiniz?\"\n"
            f"    - If German caller: \"Gerne! Ich kann Ihnen auf Deutsch helfen. Möchten Sie unser Gespräch auf Deutsch fortsetzen?\"\n"
            f"    - If Spanish caller: \"¡Por supuesto! Puedo atenderle en español. ¿Le gustaría continuar nuestra conversación en español?\"\n"
            f"    - (Or the polite equivalent offer in the caller's spoken language).\n"
            f"  * Once the caller confirms (e.g., 'Yes', 'Sure', 'نعم تفضل', 'Oui'): seamlessly switch to that language to assist them through all tools, inquiries, and services without requiring human transfer.\n"
            f"  * If the caller declines or prefers your primary language, continue smoothly in {dialect_name}."
        )
    else:
        return (
            f"سياسة توجيه اللغة واللهجة واستيعاب اللغات (Smart Omnilingual Comprehension & Polite Language Switch Policy):\n"
            f"- لغة ولهجة الحوار الأساسية المعتمدة للمنشأة: {lang_name} ({dialect_name}).\n"
            f"- تحدث بلهجتك الأساسية المعتمدة ({dialect_name}) طوال المكالمة بنبرة بشرية طبيعية وودودة.\n"
            f"\n"
            f"1. استيعاب الخلط اللغوي والمصطلحات الدخيلة (Code-Switching & Loanwords Tolerance):\n"
            f"- عندما يتحدث العميل باللغة العربية مدمجة بمصطلحات أو كلمات أجنبية شائعة أو تقنية (مثل: 'cancel', 'order', 'check-in', 'Wi-Fi', 'app', 'online', 'discount', 'merci', أو أسماء المنتجات والخدمات والعلامات التجارية):\n"
            f"  * افهم واستوعب قصد ومطلوب المتصل بالكامل ونفذ الأدوات والعمليات المطلوبة بمرونة ودقة وسرعة.\n"
            f"  * تابع الحوار بلهجتك الأساسية المعتمدة ({dialect_name}) بتدفق وسلاسة طبيعية.\n"
            f"  * يُحظر تماماً الاعتذار أو إظهار عدم الفهم أو رفض هذه المصطلحات الدخيلة، ولا تعرض التبديل طالما أن حديث العميل الأساسي بالعربية.\n"
            f"\n"
            f"2. التعامل مع المتصل الأجنبي بالكامل والعرض اللبق للتبديل (Full Foreign Language Caller - Polite Switch Offer):\n"
            f"- إذا تحدث المتصل بالكامل أو بشكل رئيسي بلغة أجنبية (مثل متصل أو سائح يتحدث بالإنجليزية أو الفرنسية أو التركية أو غيرها):\n"
            f"  * يُمنع منعاً باتاً الرفض الجاف أو إعلان العجز (مثل ادعاء عدم دعم اللغة أو رفض التحدث بلغة العميل)، ولا ترفض تقديم الخدمة إطلاقاً!\n"
            f"  * بادر بلباقة واستئذان بعرض المساعدة بلغته الأجنبية وسؤاله عما إذا كان يفضل متابعة الحوار بتلك اللغة:\n"
            f"    - إذا تحدث بالإنجليزية (English): \"Certainly! I can assist you in English. Would you like to continue our conversation in English?\"\n"
            f"    - إذا تحدث بالفرنسية (Français): \"Certainement ! Je peux vous aider en français. Souhaitez-vous poursuivre notre conversation en français ?\"\n"
            f"    - إذا تحدث بالتركية (Türkçe): \"Memnuniyetle! Size Türkçe olarak yardımcı olabilirim. Görüşmemize Türkçe olarak devam etmek ister misiniz?\"\n"
            f"    - إذا تحدث بالألمانية (Deutsch): \"Gerne! Ich kann Ihnen auf Deutsch helfen. Möchten Sie unser Gespräch auf Deutsch fortsetzen?\"\n"
            f"    - إذا تحدث بالإسبانية (Español): \"¡Por supuesto! Puedo atenderle en español. ¿Le gustaría continuar nuestra conversación en español?\"\n"
            f"    - (أو العبارة اللبقة المقابلة باللغة الأجنبية التي تحدث بها العميل مثل الروسية أو الإيطالية).\n"
            f"  * بمجرد تأكيد المتصل وموافقته (مثل: 'Yes please', 'Sure', 'Oui', 'Yes', 'Okay', 'Evet'): تحول فوراً وسلساً للتحدث بلغته، وقدم له كافة الخدمات واستدعاء الأدوات والمعلومات المطلوبة باحترافية كاملة ودون الحاجة لتحويله لموظف بشري.\n"
            f"  * إذا رفض العميل التبديل أو فضل الاستمرار بالعربية، واصل خدمته بلهجتك المعتمدة بكل رحابة صدر."
        )


