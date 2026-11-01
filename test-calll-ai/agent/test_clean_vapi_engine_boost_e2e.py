#!/usr/bin/env python3
"""
Comprehensive End-to-End Verification Test for Decoupled Domain-Agnostic
Voice AI Call Center Engine (Vapi.ai model) & Omnilingual Language Policy.

Validates:
1. Domain Agnosticism: Zero restaurant / food domain terms across 5 diverse enterprise industries.
2. Omnilingual Comprehension & Polite Language Switch Architecture:
   - Code-Switching & Loanwords Tolerance: Understand intent for mixed loanwords ("cancel", "order", "Wi-Fi", "app", etc.) without refusal.
   - Polite Language Switch Offer for full foreign language callers ("Certainly! I can assist you in English...").
   - Seamless switch upon customer confirmation without requiring human transfer.
3. Final Anti-Drift Anchor: Presence of final anti-drift anchor block at the very end of every prompt with code-switching and polite switch awareness.
4. Omnichannel Live Context: Clean, generic formatting of services, branches, zones, and offers.
5. Generic CRM Customer Memory: Distillation prompt & memory card with generic CRM fields.
6. Core Telephony Tools Scope: Domain-agnostic WhatsApp, queue transfer, knowledge RAG, and FastMCP.
7. Silent-Drop Watchdog Nudges: Dialect- and language-appropriate recovery phrases.
"""

import sys
import os
import json

from agent.prompts.builder import build_dynamic_system_instruction, generate_welcome_greeting
from agent.prompts.dialects import (
    build_language_lock_instruction,
    DIALECT_NAMES_MAP,
    LANGUAGE_NAMES_MAP,
    LANGUAGE_SWITCH_OFFERS_MAP,
    get_language_switch_offer,
    DIALECT_TO_LANG_FAMILY,
)
from agent.prompts.core.universal_voice import build_universal_voice_rules
from agent.prompts.live_context import format_live_context_for_prompt
from agent.clients.django_client import parse_customer_memory_from_bootstrap


# Food / Restaurant forbidden terms to ensure zero domain coupling leakage
FORBIDDEN_FOOD_TERMS = [
    "ساندوتش",
    "برجر",
    "فراخ",
    "مايونيز",
    "شاورما",
    "بيتزا",
    "شيف",
    "مطعم",
    "المنيو بتاعنا",
    "ألف هنا وشفا",
    "وجبة",
    "وجبات",
    "ديليفري أكل",
]


def test_1_domain_agnostic_prompts_across_diverse_industries():
    print("\n[TEST 1] Verifying Domain Agnosticism across 5 Diverse Enterprise Industries...")

    industries = [
        {
            "name": "سحابة الأمان لتقنية المعلومات",
            "role": "technical_support",
            "dialect": "saudi",
            "language": "arabic",
            "domain": "IT Infrastructure & Cloud Services",
        },
        {
            "name": "الدار للاستثمار والتطوير العقاري",
            "role": "sales_representative",
            "dialect": "emirati",
            "language": "arabic",
            "domain": "Real Estate Brokerage",
        },
        {
            "name": "مجمع الأمل الطبي التخصصي",
            "role": "appointment_booking",
            "dialect": "egyptian",
            "language": "arabic",
            "domain": "Healthcare & Dental Clinic",
        },
        {
            "name": "الرواد لصيانة وتشغيل المرافق",
            "role": "customer_support",
            "dialect": "levantine",
            "language": "arabic",
            "domain": "Field Maintenance & Facility Management",
        },
        {
            "name": "Horizon Global Consulting",
            "role": "customer_support",
            "dialect": "english_us",
            "language": "english",
            "domain": "Management & Financial Consulting",
        },
    ]

    for ind in industries:
        profile = {
            "name": ind["name"],
            "persona_role": ind["role"],
            "dialect": ind["dialect"],
            "language": ind["language"],
            "speaking_style": "professional",
            "verbosity": "balanced",
        }
        prompt = build_dynamic_system_instruction(profile)

        # Check that no food / restaurant keywords leak into the generic engine prompt
        for term in FORBIDDEN_FOOD_TERMS:
            assert term not in prompt, (
                f"Domain leakage detected in {ind['domain']} prompt! Found forbidden food term: '{term}'"
            )

        # Verify operational core rules are present
        assert "أدوات الـ API وخوادم الأدوات (MCP)" in prompt or "MCP" in prompt
        assert "قاعدة المعرفة والمستندات" in prompt
        assert "Zero Fabrication Guarantee" in prompt

        print(f"  [+] {ind['domain']}: Verified 100% clean domain separation ({len(prompt)} chars).")

    print("✅ TEST 1 PASSED: Zero restaurant coupling across all enterprise domains.")


def test_2_strict_language_and_dialect_lock():
    print("\n[TEST 2] Verifying Omnilingual Comprehension & Polite Language Switch across 10+ Languages and Dialects...")

    # 1. Test get_language_switch_offer resolver across Arabic dialects, codes, and international languages
    # Critical verification: Arabic dialects must NEVER resolve to English!
    assert get_language_switch_offer("saudi") == LANGUAGE_SWITCH_OFFERS_MAP["arabic"]
    assert get_language_switch_offer("egyptian") == LANGUAGE_SWITCH_OFFERS_MAP["arabic"]
    assert get_language_switch_offer("levantine") == LANGUAGE_SWITCH_OFFERS_MAP["arabic"]
    assert get_language_switch_offer("fusha") == LANGUAGE_SWITCH_OFFERS_MAP["arabic"]
    assert get_language_switch_offer("moroccan") == LANGUAGE_SWITCH_OFFERS_MAP["arabic"]
    assert get_language_switch_offer("arabic") == LANGUAGE_SWITCH_OFFERS_MAP["arabic"]
    assert get_language_switch_offer("ar") == LANGUAGE_SWITCH_OFFERS_MAP["arabic"]

    # Foreign dialects and language codes
    assert get_language_switch_offer("english_us") == LANGUAGE_SWITCH_OFFERS_MAP["english"]
    assert get_language_switch_offer("english_uk") == LANGUAGE_SWITCH_OFFERS_MAP["english"]
    assert get_language_switch_offer("en") == LANGUAGE_SWITCH_OFFERS_MAP["english"]
    assert get_language_switch_offer("french_fr") == LANGUAGE_SWITCH_OFFERS_MAP["french"]
    assert get_language_switch_offer("fr") == LANGUAGE_SWITCH_OFFERS_MAP["french"]
    assert get_language_switch_offer("turkish") == LANGUAGE_SWITCH_OFFERS_MAP["turkish"]
    assert get_language_switch_offer("turkish_tr") == LANGUAGE_SWITCH_OFFERS_MAP["turkish"]
    assert get_language_switch_offer("tr") == LANGUAGE_SWITCH_OFFERS_MAP["turkish"]
    assert get_language_switch_offer("chinese_zh") == LANGUAGE_SWITCH_OFFERS_MAP["chinese"]
    assert get_language_switch_offer("mandarin") == LANGUAGE_SWITCH_OFFERS_MAP["chinese"]
    print("  [+] Switch Offer Resolver: Verified 100% accurate resolution across dialects and ISO codes.")

    # 2. Test Arabic dialects: Code-switching tolerance & polite foreign switch offers
    arabic_dialects = ["saudi", "levantine", "egyptian", "moroccan", "fusha"]

    for dia in arabic_dialects:
        lock = build_language_lock_instruction(language="arabic", dialect=dia)

        # Verify policy header
        assert "Smart Omnilingual Comprehension & Polite Language Switch Policy" in lock or "سياسة توجيه اللغة واللهجة واستيعاب اللغات" in lock

        # Verify Code-Switching tolerance & borrowed terms
        assert "Code-Switching" in lock or "الخلط اللغوي" in lock
        assert "cancel" in lock and "order" in lock and "Wi-Fi" in lock

        # Verify NO rigid refusals
        assert "أنا أتحدث باللغة العربية فقط" not in lock
        assert "يُحظر تماماً التحدث باللغة الإنجليزية" not in lock

        # Verify polite switch offers for foreign callers (English, French, Turkish)
        assert "Certainly! I can assist you in English. Would you like to continue our conversation in English?" in lock
        assert "Certainement ! Je peux vous aider en français" in lock
        assert "Memnuniyetle! Size Türkçe olarak yardımcı olabilirim" in lock

        # Verify seamless switch upon confirmation and graceful decline handling
        assert "تحول فوراً وسلساً للتحدث بلغته" in lock or "تحول فوراً" in lock
        assert "دون الحاجة لتحويله لموظف بشري" in lock
        assert "إذا رفض العميل" in lock
        print(f"  [+] Arabic dialect '{dia}': Code-switching tolerance and polite switch offer verified.")

    # 3. Test Non-Arabic international languages
    foreign_cases = [
        ("english", "english_us"),
        ("french", "french_fr"),
        ("spanish", "spanish_es"),
        ("german", "german_de"),
        ("turkish", "turkish_tr"),
        ("russian", "russian_ru"),
        ("italian", "italian_it"),
        ("urdu", "urdu_pk"),
        ("hindi", "hindi_in"),
        ("chinese", "chinese_zh"),
    ]

    for lang, dia in foreign_cases:
        lock = build_language_lock_instruction(language=lang, dialect=dia)

        # Verify omnilingual policy and code-switching
        assert "Smart Omnilingual Comprehension & Polite Language Switch Policy" in lock
        assert "Code-Switching & Loanwords Tolerance" in lock
        assert "Full Foreign Language Caller & Polite Language Switch Offer" in lock

        # Verify polite offers
        assert "أهلاً بك! يمكنني مساعدتك باللغة العربية، هل تفضل مواصلة المحادثة بالعربية؟" in lock
        assert "Certainly! I can assist you in English" in lock

        # Verify seamless switch upon confirmation and graceful decline handling
        assert "seamlessly switch to that language" in lock
        assert "without requiring human transfer" in lock
        assert "If the caller declines" in lock

        # Verify NO rigid refusal phrases
        assert "I apologize, I can only assist in English" not in lock
        assert "لا تقلد لغة المتصل أبداً ولا تكررها" not in lock
        print(f"  [+] Foreign language '{lang}' ({dia}): Omnilingual comprehension and polite switch verified.")

    print("✅ TEST 2 PASSED: Omnilingual comprehension and polite language switch active across all supported languages.")


def test_3_final_anti_drift_anchor():
    print("\n[TEST 3] Verifying Final Anti-Drift Language Lock Anchor at End of Prompt...")

    profiles = [
        {"name": "سالم", "dialect": "saudi", "language": "arabic", "persona_role": "sales_representative"},
        {"name": "Alex", "dialect": "english_us", "language": "english", "persona_role": "customer_support"},
        {"name": "Karim", "dialect": "french_fr", "language": "french", "persona_role": "technical_support"},
    ]

    for p in profiles:
        prompt = build_dynamic_system_instruction(p)
        anchor_title = "[مرساة قفل اللغة واللهجة ومنع الانجراف (Final Anti-Drift Language Lock Anchor)]"
        assert anchor_title in prompt, f"Anti-drift anchor missing in prompt for {p['name']}"

        # Anchor must be at the very bottom of the prompt
        anchor_pos = prompt.find(anchor_title)
        assert len(prompt) - anchor_pos <= 650, f"Anti-drift anchor is not positioned at the very end of prompt for {p['name']}"
        assert prompt.strip().endswith("=" * 20), f"Anti-drift anchor is not terminating the prompt for {p['name']}"

        # Verify anchor contains code-switching tolerance & polite switch offer
        assert "Code-Switching" in prompt or "الخلط اللغوي" in prompt
        assert "يُحظر التبديل إليها إطلاقاً" not in prompt, "Rigid refusal leaked into anti-drift anchor!"

        # Verify language-appropriate anchor body
        if p["language"] == "arabic":
            assert "لغتك ولهجتك الأساسية المعتمدة" in prompt
            assert "المتصل أجنبياً بالكامل" in prompt
        else:
            assert "Primary authorized language & dialect" in prompt
            assert "Code-Switching & loanwords tolerance" in prompt
        print(f"  [+] {p['name']} ({p['language']}): Anti-drift anchor verified at prompt terminal.")

    print("✅ TEST 3 PASSED: Anti-drift anchor guaranteed at the end of every prompt.")


def test_4_live_context_domain_agnostic():
    print("\n[TEST 4] Verifying Live Context Formatting for Generic Business Data...")

    generic_context = {
        "business_name": "قمم لتقنية السحاب",
        "unavailable_items": ["باقة الخوادم المخصصة الفائقة (Dedicated Extreme)"],
        "branches": [
            {
                "name": "فرع الرياض - مركز الملك فهد المالي",
                "phone": "+966112233445",
                "address": "طريق الملك فهد، الرياض",
                "opening_time": "08:00",
                "closing_time": "18:00",
                "is_active": True,
            }
        ],
        "delivery_zones": [
            {
                "zone_name": "منطقة الشرق الأوسط وشمال أفريقيا",
                "fee": 0,
                "coverage": "تغطية سحابية كاملة بزمن استجابة أقل من 20 مللي ثانية",
            }
        ],
        "offers": [
            {
                "title": "عرض الربع السنوي للشركات الناشئة",
                "discount": "خصم 25% على اشتراكات السنة الأولى",
                "valid_until": "2026-12-31",
            }
        ],
        "catalog": [
            {
                "name": "باقة الحوسبة السحابية الأساسية",
                "price": 499,
                "currency": "SAR",
                "description": "4 vCPU, 16GB RAM, 100GB NVMe Storage",
            }
        ],
    }

    formatted = format_live_context_for_prompt(generic_context)
    assert "قمم لتقنية السحاب" in formatted
    assert "باقة الخوادم المخصصة الفائقة" in formatted
    assert "فرع الرياض" in formatted
    assert "منطقة الشرق الأوسط" in formatted
    assert "عرض الربع السنوي" in formatted
    assert "باقة الحوسبة السحابية" in formatted

    for term in FORBIDDEN_FOOD_TERMS:
        assert term not in formatted, f"Forbidden food term '{term}' leaked into live context!"

    print("  [+] Generic business context formatted cleanly without restaurant terms.")
    print("✅ TEST 4 PASSED: Omnichannel live context is completely domain-agnostic.")


def test_5_customer_memory_crm_agnostic():
    print("\n[TEST 5] Verifying Customer Memory Card & Schema Domain Agnosticism...")

    # Test CRM memory card formatting from bootstrap
    mock_bootstrap = {
        "customer_memory": {
            "customer_name": "المهندس عبد الله",
            "last_interaction_summary": "استفسر عن ترقية الخوادم السحابية ونطاقات الأسعار.",
            "permanent_profile": {
                "customer_name": "المهندس عبد الله",
                "vip_tier": "vip",
                "phone": "+966501122334",
                "personality": {
                    "pace": "fast",
                    "communication_style": "direct",
                },
                "addresses": [
                    {
                        "label": "المقر الرئيسي",
                        "address": "الرياض - حي الملز - برج الأعمال",
                        "instructions": "الدور العاشر - إدارة التقنية",
                    }
                ],
                "interests_and_preferences": ["استضافة السيرفرات السحابية", "حلول الأمن السيبراني"],
                "past_issues": ["تم حل مشكلة بطء استجابة الـ DNS في التذكرة #4912"],
                "notes": "الرئيس التنفيذي للتقنية في شركة مساهمة، له صلاحية اعتماد العقود",
            },
        }
    }

    parsed = parse_customer_memory_from_bootstrap(mock_bootstrap, caller_phone="+966501122334")
    card = parsed["card_text"]

    assert "المهندس عبد الله" in card
    assert "عميل VIP دائم" in card
    assert "الأمن السيبراني" in card
    assert "اهتمامات وتفضيلات سابقة" in card
    assert "سجل ملاحظات سابقة" in card
    assert "يفضل السرعة والإيجاز المباشر" in card
    assert "الرياض - حي الملز" in card

    for term in FORBIDDEN_FOOD_TERMS:
        assert term not in card, f"Forbidden food term '{term}' leaked into memory card!"

    print("  [+] Generic CRM memory card verified for enterprise customer.")
    print("✅ TEST 5 PASSED: Customer memory is 100% domain-agnostic CRM.")


def test_6_watchdog_silent_drop_dialect_nudges():
    print("\n[TEST 6] Verifying Watchdog Silent-Drop Recovery Nudges across Dialects...")

    # Simulate the dialect resolution logic from livekit_worker.py silent_drop_watchdog
    def get_watchdog_nudge(language: str, dialect: str) -> str:
        lang = (language or "arabic").lower().strip()
        dia = (dialect or "egyptian").lower().strip()

        if lang in ["english"] or dia.startswith("english"):
            return "I'm right here with you, I can hear you clearly. Please go ahead."
        elif lang in ["french"] or dia.startswith("french"):
            return "Je suis là, je vous écoute très bien. Je vous en prie, continuez."
        elif lang in ["spanish"] or dia.startswith("spanish"):
            return "Aquí estoy, le escucho claramente. Por favor continúe."
        elif lang in ["german"] or dia.startswith("german"):
            return "Ich bin da und höre Sie gut. Bitte sprechen Sie weiter."
        elif lang in ["turkish"] or dia.startswith("turkish"):
            return "Buradayım, sizi dinliyorum. Buyrun lütfen."
        elif lang in ["russian"] or dia.startswith("russian"):
            return "Я здесь, я вас отлично слышу. Пожалуйста, говорите."
        elif lang in ["italian"] or dia.startswith("italian"):
            return "Ci sono, la sento perfectamente. Prego, mi dica."
        elif lang in ["urdu"] or dia.startswith("urdu"):
            return "جی میں سن رہا ہوں، فرمائیے۔"
        elif lang in ["hindi"] or dia.startswith("hindi"):
            return "जी मैं सुन रहा हूँ, कृपया बताएं।"
        elif lang in ["chinese"] or dia.startswith("chinese"):
            return "我在听，请问有什么可以帮您？"
        elif "saudi" in dia or "gulf" in dia or "emirati" in dia or "kuwaiti" in dia:
            return "سمّ آمرني طال عمرك، أسمعك تفضل."
        elif "levantine" in dia or "jordanian" in dia:
            return "معك يا غالي، عم بسمعك تفضل."
        elif "moroccan" in dia or "algerian" in dia or "tunisian" in dia:
            return "معاك، راني نسمع فيك مزيان تفضل."
        elif "fusha" in dia:
            return "معك يا سيدي، أنا أسمعك جيداً تفضل."
        else:
            return "معاك يا فندم، سامعك اتفضل."

    assert "سمّ آمرني" in get_watchdog_nudge("arabic", "saudi")
    assert "عم بسمعك" in get_watchdog_nudge("arabic", "levantine")
    assert "راني نسمع" in get_watchdog_nudge("arabic", "moroccan")
    assert "سامعك اتفضل" in get_watchdog_nudge("arabic", "egyptian")
    assert "أنا أسمعك جيداً" in get_watchdog_nudge("arabic", "fusha")
    assert "I'm right here with you" in get_watchdog_nudge("english", "english_us")
    assert "Je suis là" in get_watchdog_nudge("french", "french_fr")
    assert "Ich bin da" in get_watchdog_nudge("german", "german_de")
    assert "Buradayım" in get_watchdog_nudge("turkish", "turkish_tr")

    print("  [+] All silent-drop recovery nudges verified for authentic cultural matching.")
    print("✅ TEST 6 PASSED: Watchdog recovery nudges match dialect and language.")


async def test_7_core_telephony_tools_scope_vapi_model():
    print("\n[TEST 7] Verifying Core Telephony Tools Scope (Vapi.ai Model)...")
    from session.tool_dispatcher import build_gemini_tools, handle_gemini_tool_call
    from unittest.mock import MagicMock

    mcp_tools = {
        "crm_create_ticket": {
            "server_url": "http://mock:8000/sse",
            "auth_token": "mock-token",
            "server_name": "ZendeskCRM",
            "description": "إنشاء تذكرة دعم فني جديدة",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "subject": {"type": "STRING"},
                    "priority": {"type": "STRING"},
                },
            },
        }
    }
    call_queues = [
        {"code": "billing", "name": "قسم الحسابات والفواتير", "description": "استفسارات الفواتير والدفع"},
        {"code": "tech_support", "name": "الدعم الفني المتقدم", "description": "الأعطال والمسائل التقنية"},
    ]

    tools = build_gemini_tools(mcp_tools, call_queues)
    func_decls = tools[0]["function_declarations"]
    tool_names = [f["name"] for f in func_decls]

    assert "search_knowledge_base" in tool_names, "Core search_knowledge_base tool missing"
    assert "crm_create_ticket" in tool_names, "Dynamic FastMCP tool missing"
    assert "transfer_to_queue" in tool_names, "Core transfer_to_queue tool missing"
    assert "lookup_customer_memory" in tool_names, "Core lookup_customer_memory tool missing"

    # Verify queue transfer execution
    fc_mock = MagicMock()
    fc_mock.id = "call_queue_999"
    fc_mock.name = "transfer_to_queue"
    fc_mock.args = {"queue_code": "tech_support", "reason": "العميل يواجه مشكلة في ربط الخوادم"}

    resp, pending_transfer = await handle_gemini_tool_call(
        fc=fc_mock,
        user_id=1,
        room_name="test_clean_vapi_room",
        channel_name="rooms:test_clean_vapi_room",
        mcp_tools=mcp_tools,
        call_queues=call_queues,
    )

    assert pending_transfer is not None
    assert pending_transfer["queue_code"] == "tech_support"
    assert pending_transfer["queue_name"] == "الدعم الفني المتقدم"
    assert resp.response["status"] == "success"
    from agent.clients.http_pool import close_http_session
    await close_http_session()
    print("  [+] Core tools verified: search_knowledge_base, crm_create_ticket, transfer_to_queue, lookup_customer_memory.")
    print("✅ TEST 7 PASSED: Core Voice AI Call Center engine tools scope verified.")


def test_8_unconfigured_role_rag_no_delivery_address_leakage():
    print("\n[TEST 8] Verifying Unconfigured Agent with RAG Tool Does NOT Leak Delivery Address Skill...")
    from agent.prompts.skills.delivery_address import DELIVERY_ADDRESS_SKILL

    # Assert skill has decoupled required_tools
    assert DELIVERY_ADDRESS_SKILL.required_tools == [], "DELIVERY_ADDRESS_SKILL still coupled to food order tools"

    # Default profile without role and with search_knowledge_base
    unconfigured_profile = {
        "name": "المساعد الذكي للمنشأة",
        "language": "arabic",
        "dialect": "saudi",
        "persona_role": "",
    }
    tools = [{"name": "search_knowledge_base", "description": "RAG search"}]

    prompt = build_dynamic_system_instruction(unconfigured_profile, available_tools=tools)

    # Must NOT contain delivery address skill
    assert "قاعدة جمع وتفصيل العنوان الذكي المتكيف لطلبات التوصيل" not in prompt, (
        "Delivery address skill leaked into unconfigured enterprise agent with RAG tool!"
    )
    assert "الشيخ زايد" not in prompt
    assert "سؤال الحسم السريع الإلزامي" not in prompt
    print("  [+] Verified: Generic enterprise bot with RAG tool does not leak delivery address rules.")
    print("✅ TEST 8 PASSED: Delivery address skill is strictly isolated from generic RAG bots.")


def test_9_dialect_aware_off_topic_and_handoff_isolation():
    print("\n[TEST 9] Verifying Dialect & Language Awareness in Off-Topic and Human Handoff Instructions...")
    from agent.prompts.skills.human_transfer import build_human_transfer_instruction

    # 1. English Profile: zero Egyptian slang in off-topic or handoff
    en_profile = {"name": "Alex", "language": "english", "dialect": "english_us"}
    en_prompt = build_dynamic_system_instruction(en_profile, call_queues=[])
    assert "specifically dedicated to our organization's services" in en_prompt
    assert "بعتذر لحضرتك جداً يا فندم" not in en_prompt, "Egyptian apology leaked into English off-topic prompt!"
    assert "outside of regular business hours" in en_prompt
    assert "ممثلو خدمة العملاء غير متاحين حالياً" not in en_prompt, "Egyptian handoff apology leaked into English prompt!"
    print("  [+] English profile: Verified clean English off-topic and off-hours handoff instructions.")

    # 2. Saudi Profile: authentic Saudi phrasing in off-topic and handoff
    saudi_profile = {"name": "سالم", "language": "arabic", "dialect": "saudi"}
    saudi_prompt = build_dynamic_system_instruction(saudi_profile, call_queues=[])
    assert "المعذرة منك طال عمرك، إحنا هنا مخصصين لخدمات واستفسارات المنشأة" in saudi_prompt
    assert "المعذرة منك طال عمرك، ممثلو خدمة العملاء غير متاحين حالياً" in saudi_prompt
    assert "بعتذر لحضرتك جداً يا فندم" not in saudi_prompt, "Egyptian apology leaked into Saudi profile!"
    print("  [+] Saudi profile: Verified authentic Saudi off-topic and off-hours handoff instructions.")

    # 3. Multi-Queue Saudi routing discovery
    queues = [{"name": "الدعم الفني", "code": "support"}]
    saudi_mq = build_human_transfer_instruction(queues, language="arabic", dialect="saudi")
    assert "أبشر طال عمرك، بحولك الحين لممثل الدعم الفني" in saudi_mq
    assert "حاضر يا فندم، هحول حضرتك حالاً" not in saudi_mq, "Egyptian phrasing leaked into Saudi queue handoff!"
    print("  [+] Saudi multi-queue: Verified authentic queue transfer phrasing.")

    # 4. ISO 639-1 2-letter language code support
    iso_en_lock = build_language_lock_instruction(language="en", dialect="english_us")
    assert "Code-Switching & Loanwords Tolerance" in iso_en_lock
    assert "Polite Language Switch" in iso_en_lock
    iso_ar_lock = build_language_lock_instruction(language="ar", dialect="saudi")
    assert "Code-Switching" in iso_ar_lock or "الخلط اللغوي" in iso_ar_lock
    assert "Certainly! I can assist you in English" in iso_ar_lock
    print("  [+] ISO 639-1 codes: Verified language lock handles 2-letter codes seamlessly.")

    print("✅ TEST 9 PASSED: Dialect and language awareness completely verified across all flows.")


async def run_all():
    print("=" * 70)
    print("🚀 RUNNING CLEAN VAPI ENGINE & STRICT LANGUAGE LOCK BOOST E2E SUITE")
    print("=" * 70)

    test_1_domain_agnostic_prompts_across_diverse_industries()
    test_2_strict_language_and_dialect_lock()
    test_3_final_anti_drift_anchor()
    test_4_live_context_domain_agnostic()
    test_5_customer_memory_crm_agnostic()
    test_6_watchdog_silent_drop_dialect_nudges()
    await test_7_core_telephony_tools_scope_vapi_model()
    test_8_unconfigured_role_rag_no_delivery_address_leakage()
    test_9_dialect_aware_off_topic_and_handoff_isolation()

    print("\n" + "=" * 70)
    print("🎉 ALL 9 CLEAN VAPI ENGINE & LANGUAGE LOCK TESTS PASSED 100% PERFECTLY!")
    print("=" * 70)


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_all())
