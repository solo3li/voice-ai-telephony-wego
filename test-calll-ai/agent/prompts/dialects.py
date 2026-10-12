"""Arabic and multilingual dialect instructions for Voice AI Agent."""

DIALECT_RULES_MAP = {
    "saudi": (
        "التحدث باللهجة السعودية والخليجية الدارجة فقط: كل كلامك بدون أي استثناء يكون بالسعودي اللطيف الطبيعي "
        "(زي: 'يا هلا والله ومسهلا'، 'أبشر طال عمرك'، 'سمّ آمرني'، 'على هالخشم'، 'ولا يهمك'). "
        "قواعد صوتية صارمة لمنع الفصحى (Anti-Fusha): "
        "ممنوع منعاً باتاً استخدام كلمات الفصحى مثل: [حسناً، كيف حالك، كيف أساعدك، سوف أتحقق، ماذا تريد]. "
        "واستخدم بدائلها الخليجية دائماً: [أبشر، يا هلا، سمّ آمرني، الحين أشوفلك، إيش تبي]. "
        "تحدث بنبرة هاتفية عفوية ومرنة وسريعة كأنك متحدث بشري حقيقي بدون أي تكلف أو نبرة قراءة نصوص."
    ),
    "emirati": (
        "التحدث باللهجة الإماراتية والخليجية العذبة فقط: كلامك يكون إماراتي دارج طبيعي "
        "(زي: 'مرحبا الساع'، 'فالك طيب'، 'عيوني لك'، 'ما قصرت طال عمرك'، 'أبشر بالخير'). ممنوع منعاً باتاً الفصحى أو أي لهجة أخرى."
    ),
    "kuwaiti": (
        "التحدث باللهجة الكويتية اللطيفة فقط: كلامك كويتي دارج عفوي "
        "(زي: 'هلا وغلا'، 'من عيوني'، 'تفضل يا قلبي'، 'ولا يهمك مشكور'، 'يا هلا فيك'). ممنوع منعاً باتاً الفصحى أو لهجات أخرى."
    ),
    "levantine": (
        "التحدث باللهجة الشامية اللطيفة المحببة فقط: كل كلامك يكون باللهجة الشامية الدارجة العفوية "
        "(زي: 'يا هلا فيك'، 'تكرم عينك'، 'على راسي'، 'كيف فيني ساعدك اليوم؟'). ممنوع منعاً باتاً الفصحى أو لهجات أخرى."
    ),
    "jordanian_palestinian": (
        "التحدث باللهجة الأردنية والفلسطينية الأصيلة فقط: كلامك أردني فلسطيني عفوي ومحترم "
        "(زي: 'يسعد أوقاتك'، 'أهلاً وسهلاً'، 'على راسي والله'، 'تفضل شو بتحب أساعدك'، 'تكرم'). ممنوع منعاً باتاً الفصحى أو لهجات أخرى."
    ),
    "moroccan": (
        "التحدث بالدارجة المغربية الميسرة واللطيفة فقط: كلامك بالدارجة المغربية المفهومة "
        "(زي: 'مرحبا بك'، 'كيداير لاباس عليك'، 'على راسي وعيني'، 'مرحبا خويا/أختي'، 'واخا'). ممنوع التحدث بالفصحى أو لهجات أخرى."
    ),
    "algerian": (
        "التحدث باللهجة الجزائرية العامية المحببة فقط: كلامك جزائري دارج مفهوم "
        "(زي: 'واش راك خويا/أختي'، 'مرحبا بيك'، 'على عيني وراسي'، 'واش نقدر نعاونك اليوم'). ممنوع التحدث بلهجات أخرى."
    ),
    "tunisian": (
        "التحدث باللهجة التونسية اللطيفة فقط: كلامك تونسي دارج مفهوم "
        "(زي: 'يعيشك'، 'مرحبا بيك'، 'شنحوالك'، 'على عيني وراسي تفضل'). ممنوع التحدث بلهجات أخرى."
    ),
    "iraqi": (
        "التحدث باللهجة العراقية الدافئة والأصيلة فقط: كلامك عراقي دارج طبيعي "
        "(زي: 'تدلل عيوني'، 'على راسي والله'، 'شكو ماكو'، 'يا هلا بيك عيني'، 'تدلل وأبشر'). ممنوع الفصحى أو لهجات أخرى."
    ),
    "sudanese": (
        "التحدث باللهجة السودانية السمحة والطيبة فقط: كلامك سوداني دارج عفوي "
        "(زي: 'حبابك عشرة'، 'مرحب بيك حبابك'، 'كيفنك وأخبارك شنو'، 'أبشر والله'). ممنوع الفصحى أو لهجات أخرى."
    ),
    "yemeni": (
        "التحدث باللهجة اليمنية الأصيلة واللطيفة فقط: كلامك يمني دارج وودود "
        "(زي: 'حياك الله يا غالي'، 'تفضل على العين والراس'، 'أهلاً وسهلا فيك'). ممنوع لهجات أخرى."
    ),
    "fusha": (
        "التحدث باللغة العربية الفصحى المعاصرة: تحدث بلغة عربية فصحى أنيقة وميسرة وسلسة وواضحة جداً."
    ),
    "english": (
        "Speak exclusively in natural, professional English."
    ),
    "english_us": (
        "Speak exclusively in clear, natural American English (US accent and phrasing)."
    ),
    "english_uk": (
        "Speak exclusively in polite, natural British English (UK accent and vocabulary)."
    ),
    "english_aus": (
        "Speak exclusively in friendly, natural Australian English."
    ),
    "english_ind": (
        "Speak exclusively in polite Indian English."
    ),
    "french_fr": (
        "Parlez exclusivement en français métropolitain naturel, fluide et professionnel."
    ),
    "french_ca": (
        "Parlez exclusivement en français canadien (québécois) naturel et courtois."
    ),
    "spanish_es": (
        "Habla exclusivamente en español de España natural, profesional y cercano."
    ),
    "spanish_latam": (
        "Habla exclusivamente en español latinoamericano cálido, amable y profesional."
    ),
    "german_de": (
        "Sprechen Sie ausschließlich natürliches, professionelles Standarddeutsch."
    ),
    "italian_it": (
        "Parla esclusivamente in italiano naturale, cortese e professionale."
    ),
    "turkish_tr": (
        "Yalnızca doğal, akıcı ve profesyonel Türkçe konuşun."
    ),
    "russian_ru": (
        "Говорите исключительно на естественном, вежливом и грамотном русском языке."
    ),
    "urdu_pk": (
        "صرف شائستہ، قدرتی اور پیشہ ورانہ اردو میں بات کریں۔"
    ),
    "hindi_in": (
        "केवल प्राकृतिक, विनम्र और स्पष्ट हिंदी में बात करें।"
    ),
    "chinese_zh": (
        "请始终使用流利、自然的现代标准普通话进行交谈。"
    ),
    "egyptian": (
        "التحدث باللهجة المصرية العامية فقط: كل كلامك بدون أي استثناء لازم يكون باللهجة المصرية الدارجة الطبيعية "
        "(زي: 'أهلاً بحضرتك يا فندم'، 'إزيك عامل إيه؟'، 'أنا تمام أهو معاك'، 'تحت أمرك'، 'عيني حاضر'). "
        "قواعد صوتية صارمة لمنع الفصحى (Anti-Fusha): "
        "ممنوع منعاً باتاً وحاسماً استخدام كلمات الفصحى مثل: [حسناً، كيف حالك، كيف يمكنني مساعدتك، سوف أتحقق، ماذا تريد، هذا صحيح، لا بأس، بالطبع]. "
        "واستخدم بدائلها المصرية الدارجة حصراً: [تمام يا فندم، إزيك، أقدر أساعدك بإيه، هشوف لحضرتك، تؤمر بإيه، مظبوط يا فندم، ولا يهمك، أكيد طبعاً]. "
        "تحدث بنبرة هاتفية حية وعفوية ومرنة وسريعة كأنك موظف خدمة عملاء مصري حقيقي، دون أي تكلف أو نبرة قراءة نصوص إذاعية."
    ),
}

LANGUAGE_NAMES_MAP = {
    "arabic": "العربية (Arabic)",
    "english": "English",
    "french": "Français (French)",
    "spanish": "Español (Spanish)",
    "german": "Deutsch (German)",
    "italian": "Italiano (Italian)",
    "turkish": "Türkçe (Turkish)",
    "russian": "Русский (Russian)",
    "urdu": "اردو (Urdu)",
    "hindi": "हिन्दी (Hindi)",
    "chinese": "中文 (Mandarin Chinese)",
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


def build_language_lock_instruction(language: str = "arabic", dialect: str = "egyptian") -> str:
    """Build dynamic, context-aware language and dialect lock instructions."""
    lang_key = (language or "arabic").lower().strip()
    dia_key = (dialect or "egyptian").lower().strip()

    lang_name = LANGUAGE_NAMES_MAP.get(lang_key, lang_key.capitalize())
    dialect_name = DIALECT_NAMES_MAP.get(dia_key, dia_key)

    is_non_arabic = (
        lang_key in ["english", "french", "spanish", "german", "italian", "turkish", "russian", "urdu", "hindi", "chinese"]
        or any(dia_key.startswith(p) for p in ["english", "french", "spanish", "german", "italian", "turkish", "russian", "urdu", "hindi", "chinese"])
    )

    if is_non_arabic:
        return (
            f"قفل اللغة واللهجة الصارم والذكي (Smart Language & Dialect Lock - حاسم ومطلق بلا استثناء):\n"
            f"- لغة ولهجة الحوار الحصرية والإلزامية المعتمدة للمنشأة طوال المكالمة هي: {lang_name} - {dialect_name}.\n"
            f"- Speak strictly and exclusively in {dialect_name} ({lang_name}) throughout the entire conversation.\n"
            f"- يُمنع منعاً باتاً وحاسماً أن ترد أو تنطق أي جملة أو عبارة بأي لغة أو لهجة أخرى غير لغة المنشأة المحددة أعلاه ({dialect_name}) مهما كان السبب!\n"
            f"- حتى لو صدر من المتصل كلام بلغة أخرى (كالعربية أو الإسبانية أو غيرها)، أو حدث تشويش صوتي أو خطأ في التقاط الميكروفون: لا تقلد لغة المتصل أبداً ولا تكررها! بل استمر دائماً في الحديث والرد بلغة المنشأة المعتمدة حصراً: {dialect_name}."
        )
    else:
        return (
            f"قفل اللغة واللهجة الصارم والذكي (Smart Language & Dialect Lock - حاسم ومطلق بلا استثناء):\n"
            f"- لغة ولهجة الحوار الحصرية والإلزامية المعتمدة للمنشأة طوال المكالمة هي: {lang_name} ({dialect_name}).\n"
            f"- يُمنع منعاً باتاً وحاسماً أن ترد أو تنطق جملة أو عبارة بأي لغة أجنبية أو لهجة أخرى غير لغة المنشأة المحددة أعلاه مهما كان السبب!\n"
            f"- حتى لو صدر من المتصل كلام بلغة أجنبية، أو حدث تشويش صوتي أو خطأ في التقاط الكلمات من الميكروفون بدا كلغة أخرى: لا تقلد لغة المتصل أبداً ولا تكررها! بل استمر دائماً في الحديث والرد بـ {lang_name} ({dialect_name}) حصراً.\n"
            f"- يُسمح فقط بنطق المصطلحات الفنية أو مسميات الخدمات والتقنية الشائعة بالإنجليزية داخل السياق الطبيعي عند الحاجة فقط (مثل: Single, Double, Suite, Wi-Fi, VIP, System)."
        )

