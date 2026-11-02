# SPDX-License-Identifier: Apache-2.0
"""
Platform Voice Catalog & Server-Side Abstraction Engine.
Authoritative white-label mapping between human personas and underlying engine voices.
Strictly isolates underlying provider voice names from frontend clients and public APIs.
"""
from typing import Dict, Any, List, Optional

PLATFORM_VOICES = [
    # Female Personas (15)
    {
        "id": "nourhan",
        "name": "نورهان (Nourhan)",
        "gender": "female",
        "style": "نشيطة وسريعة (خدمة عملاء ومبيعات)",
        "tag": "افتراضي",
        "engine_voice": "Aoede",
    },
    {
        "id": "mariam",
        "name": "مريم (Mariam)",
        "gender": "female",
        "style": "واثقة وحازمة (حجوزات واستشارات)",
        "tag": "استشارات",
        "engine_voice": "Kore",
    },
    {
        "id": "sarah",
        "name": "سارة (Sarah)",
        "gender": "female",
        "style": "شابة وودودة (تسويق ومطاعم)",
        "tag": "تسويق",
        "engine_voice": "Leda",
    },
    {
        "id": "laila",
        "name": "ليلى (Laila)",
        "gender": "female",
        "style": "دافئة ومريحة (عيادات ورعاية)",
        "tag": "رعاية",
        "engine_voice": "Callisto",
    },
    {
        "id": "huda",
        "name": "هدى (Huda)",
        "gender": "female",
        "style": "رقيقة وواضحة (دعم فني وتعليم)",
        "tag": "دعم فني",
        "engine_voice": "Sulafat",
    },
    {
        "id": "yasmin",
        "name": "ياسمين (Yasmin)",
        "gender": "female",
        "style": "مشرقة ومتحمسة (عروض ترويجية)",
        "tag": "ترويج",
        "engine_voice": "Autonoe",
    },
    {
        "id": "salma",
        "name": "سلمى (Salma)",
        "gender": "female",
        "style": "هادئة ومطمئنة (خدمات VIP وبنوك)",
        "tag": "VIP",
        "engine_voice": "Achernar",
    },
    {
        "id": "dina",
        "name": "دينا (Dina)",
        "gender": "female",
        "style": "رنانة ومتمكنة (مكاتب إدارة وتنفيذية)",
        "tag": "إداري",
        "engine_voice": "Erinome",
    },
    {
        "id": "fatima",
        "name": "فاطمة (Fatima)",
        "gender": "female",
        "style": "تفاعلية وتعبيرية (تجارة إلكترونية)",
        "tag": "تجارة",
        "engine_voice": "Laomedeia",
    },
    {
        "id": "reema",
        "name": "ريما (Reema)",
        "gender": "female",
        "style": "مرحبة ومضيافة (فنادق وضيافة)",
        "tag": "ضيافة",
        "engine_voice": "Gacrux",
    },
    {
        "id": "nadine",
        "name": "نادين (Nadine)",
        "gender": "female",
        "style": "أنيقة وراقية (عقارات ومجوهرات)",
        "tag": "عقارات",
        "engine_voice": "Vindemiatrix",
    },
    {
        "id": "shahd",
        "name": "شهد (Shahd)",
        "gender": "female",
        "style": "واضحة ومباشرة (استعلامات وسنترال)",
        "tag": "سنترال",
        "engine_voice": "Despina",
    },
    {
        "id": "hind",
        "name": "هند (Hind)",
        "gender": "female",
        "style": "نقية وأنيقة (خدمة عملاء راقية)",
        "tag": "راقي",
        "engine_voice": "Galatea",
    },
    {
        "id": "mona",
        "name": "منى (Mona)",
        "gender": "female",
        "style": "لطيفة ومبهجة (خدمات عامة وأفراد)",
        "tag": "عام",
        "engine_voice": "Larissa",
    },
    {
        "id": "nour",
        "name": "نور (Nour)",
        "gender": "female",
        "style": "طبيعية وسلسة (مساعدة شخصية وسكرتارية)",
        "tag": "سكرتارية",
        "engine_voice": "Naiad",
    },

    # Male Personas (15)
    {
        "id": "omar",
        "name": "عمر (Omar)",
        "gender": "male",
        "style": "مرح وحيوي (مبيعات ومطاعم وتوصيل)",
        "tag": "افتراضي",
        "engine_voice": "Puck",
    },
    {
        "id": "tarek",
        "name": "طارق (Tarek)",
        "gender": "male",
        "style": "هادئ ووقور (استشارات وشركات مالية)",
        "tag": "استشارات",
        "engine_voice": "Charon",
    },
    {
        "id": "khaled",
        "name": "خالد (Khaled)",
        "gender": "male",
        "style": "عميق وجهوري (بنوك ومؤسسات رسمية)",
        "tag": "رسمي",
        "engine_voice": "Fenrir",
    },
    {
        "id": "ziad",
        "name": "زياد (Ziad)",
        "gender": "male",
        "style": "منعش ومشرق (تسويق وتطبيقات ذكية)",
        "tag": "تسويق",
        "engine_voice": "Zephyr",
    },
    {
        "id": "youssef",
        "name": "يوسف (Youssef)",
        "gender": "male",
        "style": "حازم ومباشر (دعم تقني ومصانع)",
        "tag": "دعم فني",
        "engine_voice": "Orus",
    },
    {
        "id": "karim",
        "name": "كريم (Karim)",
        "gender": "male",
        "style": "تلقائي وعفوي (خدمات شبابية وتجزئة)",
        "tag": "شبابي",
        "engine_voice": "Umbriel",
    },
    {
        "id": "ahmed",
        "name": "أحمد (Ahmed)",
        "gender": "male",
        "style": "واضح ورصين (عقارات ومقاولات)",
        "tag": "عقارات",
        "engine_voice": "Schedar",
    },
    {
        "id": "sameh",
        "name": "سامح (Sameh)",
        "gender": "male",
        "style": "عملي وسريع (لوجستيات ومستودعات)",
        "tag": "لوجستيات",
        "engine_voice": "Achird",
    },
    {
        "id": "faisal",
        "name": "فيصل (Faisal)",
        "gender": "male",
        "style": "متفاعل وحيوي (فعاليات وحجوزات)",
        "tag": "فعاليات",
        "engine_voice": "Sadachbia",
    },
    {
        "id": "majed",
        "name": "ماجد (Majed)",
        "gender": "male",
        "style": "واقعي وبسيط (خدمات عامة وصيانة)",
        "tag": "صيانة",
        "engine_voice": "Zubenelgenubi",
    },
    {
        "id": "hossam",
        "name": "حسام (Hossam)",
        "gender": "male",
        "style": "مطمئن ومتزن (قطاع طبي وتأمين)",
        "tag": "طبي",
        "engine_voice": "Thalassa",
    },
    {
        "id": "wael",
        "name": "وائل (Wael)",
        "gender": "male",
        "style": "ديناميكي ومتمكن (إدارة مبيعات)",
        "tag": "مبيعات",
        "engine_voice": "Proteus",
    },
    {
        "id": "seif",
        "name": "سيف (Seif)",
        "gender": "male",
        "style": "شاب وتقني (برمجيات وتقنية)",
        "tag": "تقني",
        "engine_voice": "Neso",
    },
    {
        "id": "rami",
        "name": "رامي (Rami)",
        "gender": "male",
        "style": "مهذب وسلس (استقبال وفنادق)",
        "tag": "استقبال",
        "engine_voice": "Halimede",
    },
    {
        "id": "ali",
        "name": "علي (Ali)",
        "gender": "male",
        "style": "مختصر وموجز (استعلامات وبلاغات فورية)",
        "tag": "موجز",
        "engine_voice": "Sao",
    },
]

# Fast lookup tables
ID_TO_ENGINE: Dict[str, str] = {v["id"].lower(): v["engine_voice"] for v in PLATFORM_VOICES}
ENGINE_TO_ID: Dict[str, str] = {v["engine_voice"].lower(): v["id"] for v in PLATFORM_VOICES}

# Allow engine voice names directly
for v in PLATFORM_VOICES:
    ID_TO_ENGINE[v["engine_voice"].lower()] = v["engine_voice"]
    ENGINE_TO_ID[v["id"].lower()] = v["id"]

# Allow display names as lookup
for v in PLATFORM_VOICES:
    ID_TO_ENGINE[v["name"].lower()] = v["engine_voice"]
    ENGINE_TO_ID[v["name"].lower()] = v["id"]


def resolve_engine_voice(voice_key: Optional[str]) -> str:
    """
    Maps persona ID ('nourhan', 'omar') or raw engine voice ('Aoede', 'Puck')
    to the underlying valid Gemini Live engine voice model name.
    Defaults to 'Aoede' if unknown or empty.
    """
    if not voice_key:
        return "Aoede"
    key = str(voice_key).strip().lower()
    return ID_TO_ENGINE.get(key, "Aoede")


def resolve_display_voice_id(engine_voice: Optional[str]) -> str:
    """
    Maps engine voice ('Aoede', 'Puck') or persona ID to the human persona ID ('nourhan', 'omar').
    Defaults to 'nourhan' if unknown or empty.
    """
    if not engine_voice:
        return "nourhan"
    key = str(engine_voice).strip().lower()
    return ENGINE_TO_ID.get(key, "nourhan")


def resolve_display_voice_name(voice_key: Optional[str]) -> str:
    """Returns the full human display name (e.g. 'نورهان (Nourhan)')."""
    vid = resolve_display_voice_id(voice_key)
    for v in PLATFORM_VOICES:
        if v["id"] == vid:
            return v["name"]
    return "نورهان (Nourhan)"


def get_public_voices() -> List[Dict[str, Any]]:
    """
    Returns public catalog of 30 human personas WITHOUT exposing underlying engine_voice.
    Guarantees strict server-side abstraction and white-label isolation.
    """
    return [
        {
            "id": v["id"],
            "name": v["name"],
            "gender": v["gender"],
            "style": v["style"],
            "tag": v["tag"],
        }
        for v in PLATFORM_VOICES
    ]


def get_voice_by_id(voice_id: str) -> Optional[Dict[str, Any]]:
    """Returns the platform voice definition by persona ID or engine voice."""
    vid = resolve_display_voice_id(voice_id)
    for v in PLATFORM_VOICES:
        if v["id"] == vid:
            return v
    return None
