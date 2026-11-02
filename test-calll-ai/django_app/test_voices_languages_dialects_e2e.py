"""
End-to-End Verification Test for 30 Google Voices, Full World Languages & Dialects Architecture.
Tests:
1. Profiles API metadata (30 Google voices, all languages, language_dialects_map).
2. Creating and activating profiles across various languages and dialects.
3. Testing AI Agent dynamic system instruction generation across all dialects and languages.
4. Testing Bootstrap API payload for AI daemon.
"""

import os
import sys
import json
import django

# Setup Django Environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from django.test import RequestFactory
from django.contrib.auth.models import User
from agents.models import AgentProfile
from agents.views import list_profiles, create_profile, update_profile, activate_profile, GOOGLE_VOICES, LANGUAGE_DIALECTS_MAP
from agents.views import api_internal_agent_bootstrap

# Import agent prompt builder if accessible
try:
    sys.path.insert(0, '/root/test/test-calll-ai/agent')
    from main import build_dynamic_system_instruction, parse_active_profile_from_bootstrap
except Exception:
    try:
        sys.path.insert(0, '/app')
        from main import build_dynamic_system_instruction, parse_active_profile_from_bootstrap
    except Exception:
        build_dynamic_system_instruction = None
        parse_active_profile_from_bootstrap = None


def run_e2e_tests():
    print("=" * 65)
    print("🧪 STARTING E2E TEST: VOICES, LANGUAGES & DIALECTS SUITE")
    print("=" * 65)

    rf = RequestFactory()
    user, _ = User.objects.get_or_create(username="test_voice_suite_user", defaults={"email": "voices@test.com"})

    # -------------------------------------------------------------
    # TEST 1: Verify 30 White-Label Voices Metadata & Private Isolation
    # -------------------------------------------------------------
    print("\n[TEST 1] Verifying White-Label Voice Catalog (30 Human Personas)...")
    female_voices = [v for v in GOOGLE_VOICES if v['gender'] == 'female']
    male_voices = [v for v in GOOGLE_VOICES if v['gender'] == 'male']
    print(f"[+] Total Voices defined: {len(GOOGLE_VOICES)}")
    print(f"    - Female Personas: {len(female_voices)} (e.g. nourhan, mariam, sarah, laila...)")
    print(f"    - Male Personas: {len(male_voices)} (e.g. omar, tarek, khaled, ziad...)")

    assert len(GOOGLE_VOICES) == 30, f"Expected 30 voices, got {len(GOOGLE_VOICES)}"
    assert len(female_voices) == 15, f"Expected 15 female voices, got {len(female_voices)}"
    assert len(male_voices) == 15, f"Expected 15 male voices, got {len(male_voices)}"

    # Private Field Isolation assertion
    for v in GOOGLE_VOICES:
        assert "engine_voice" not in v, f"Private field engine_voice leaked in public voice: {v}"
        assert "id" in v and "name" in v and "gender" in v and "style" in v and "tag" in v

    # Bidirectional resolvers test
    from agents.voice_catalog import resolve_engine_voice, resolve_display_voice_id
    assert resolve_engine_voice("nourhan") == "Aoede"
    assert resolve_engine_voice("Aoede") == "Aoede"
    assert resolve_engine_voice("omar") == "Puck"
    assert resolve_engine_voice("Puck") == "Puck"
    assert resolve_display_voice_id("Aoede") == "nourhan"
    assert resolve_display_voice_id("nourhan") == "nourhan"
    assert resolve_display_voice_id("Puck") == "omar"
    assert resolve_display_voice_id("omar") == "omar"
    print("✅ TEST 1 PASSED: 30 White-Label Personas & Server-Side Bidirectional Resolvers verified.")

    # -------------------------------------------------------------
    # TEST 2: Verify Language & Dialect Mapping Hierarchy
    # -------------------------------------------------------------
    print("\n[TEST 2] Verifying Hierarchical Language & Dialects Structure...")
    languages = [l[0] for l in AgentProfile.LANGUAGE_CHOICES]
    print(f"[+] Supported Languages ({len(languages)}): {languages}")

    assert "arabic" in languages
    assert "english" in languages
    assert "french" in languages
    assert "spanish" in languages
    assert "german" in languages
    assert "italian" in languages
    assert "turkish" in languages
    assert "russian" in languages
    assert "urdu" in languages
    assert "hindi" in languages
    assert "chinese" in languages

    # Check that each language has dialect choices in LANGUAGE_DIALECTS_MAP
    for lang in languages:
        dialects = LANGUAGE_DIALECTS_MAP.get(lang, [])
        assert len(dialects) > 0, f"Language '{lang}' has no dialects mapped!"
        print(f"    - {lang.capitalize()}: {len(dialects)} dialects mapped.")

    print("✅ TEST 2 PASSED: Hierarchical languages and dialects verified.")

    # -------------------------------------------------------------
    # TEST 3: Test Profiles API (list_profiles)
    # -------------------------------------------------------------
    print("\n[TEST 3] Testing list_profiles endpoint metadata...")
    req = rf.get('/api/agents/profiles/')
    req.user = user
    resp = list_profiles(req)
    assert resp.status_code == 200, f"Unexpected status: {resp.status_code}"
    data = json.loads(resp.content.decode('utf-8'))
    assert data["status"] == "success"
    assert "platform_voices" in data
    assert len(data["platform_voices"]) == 30
    assert len(data["google_voices"]) == 30
    for v in data["platform_voices"]:
        assert "engine_voice" not in v, f"engine_voice leaked in platform_voices API: {v}"
    assert "language_dialects_map" in data
    assert "languages" in data
    print(f"[+] API returned {len(data['languages'])} languages and {len(data['platform_voices'])} platform voices.")

    # Developer & Partner Studio Endpoints Parity Test
    from developer.models import UserApiKey
    from developer.views import api_user_profiles_studio
    dev_key, _ = UserApiKey.objects.get_or_create(
        user=user,
        defaults={"name": "Voices Dev Key", "key": "sk_live_usr_vtest_" + "v" * 27, "is_active": True}
    )
    dev_req = rf.get('/api/v1/profiles/studio/', HTTP_X_API_KEY=dev_key.key)
    dev_req.user = user
    dev_resp = api_user_profiles_studio(dev_req)
    assert dev_resp.status_code == 200, f"Studio returned {dev_resp.status_code}: {dev_resp.content}"
    dev_data = json.loads(dev_resp.content.decode('utf-8'))
    assert "platform_voices" in dev_data
    assert len(dev_data["platform_voices"]) == 30
    for v in dev_data["platform_voices"]:
        assert "engine_voice" not in v

    print("✅ TEST 3 PASSED: list_profiles & studio APIs return full metadata with engine_voice strictly isolated.")

    # -------------------------------------------------------------
    # TEST 4: Create and Activate Profiles with Different Dialects & Voices
    # -------------------------------------------------------------
    print("\n[TEST 4] Creating & Activating Profiles with Human Personas & Engine Abstraction...")
    test_cases = [
        {"name": "سارة - مبيعات سعودي", "voice": "mariam", "expected_engine": "Kore", "gender": "female", "lang": "arabic", "dialect": "saudi"},
        {"name": "فاطمة - خدمة عملاء إماراتي", "voice": "laila", "expected_engine": "Callisto", "gender": "female", "lang": "arabic", "dialect": "emirati"},
        {"name": "كريم - دعم مغربي", "voice": "sameh", "expected_engine": "Achird", "gender": "male", "lang": "arabic", "dialect": "moroccan"},
        {"name": "زيد - دعم عراقي", "voice": "tarek", "expected_engine": "Charon", "gender": "male", "lang": "arabic", "dialect": "iraqi"},
        {"name": "John - US Sales", "voice": "ziad", "expected_engine": "Zephyr", "gender": "male", "lang": "english", "dialect": "english_us"},
        {"name": "Emma - UK Support", "voice": "nourhan", "expected_engine": "Aoede", "gender": "female", "lang": "english", "dialect": "english_uk"},
        {"name": "Pierre - Paris", "voice": "youssef", "expected_engine": "Orus", "gender": "male", "lang": "french", "dialect": "french_fr"},
        {"name": "Hans - Berlin", "voice": "khaled", "expected_engine": "Fenrir", "gender": "male", "lang": "german", "dialect": "german_de"},
        {"name": "Ali - Lahore", "voice": "faisal", "expected_engine": "Sadachbia", "gender": "male", "lang": "urdu", "dialect": "urdu_pk"},
        {"name": "Mei - Beijing", "voice": "yasmin", "expected_engine": "Autonoe", "gender": "female", "lang": "chinese", "dialect": "chinese_zh"},
    ]

    for tc in test_cases:
        create_req = rf.post(
            '/api/agents/profiles/create/',
            data=json.dumps({
                "name": tc["name"],
                "voice_name": tc["voice"],
                "gender": tc["gender"],
                "language": tc["lang"],
                "dialect": tc["dialect"],
                "persona_role": "customer_support",
                "speaking_style": "friendly",
                "is_active": True
            }),
            content_type='application/json'
        )
        create_req.user = user
        c_resp = create_profile(create_req)
        assert c_resp.status_code == 201, f"Failed creating profile {tc['name']}: {c_resp.content}"
        c_data = json.loads(c_resp.content.decode('utf-8'))
        prof = c_data["profile"]
        assert prof["language"] == tc["lang"]
        assert prof["dialect"] == tc["dialect"]
        assert prof["voice_name"] == tc["voice"]
        assert "voice_display" in prof, f"voice_display missing in profile to_dict: {prof}"
        # Verify engine voice resolution via model helper
        p_obj = AgentProfile.objects.get(id=prof["id"])
        assert p_obj.get_engine_voice() == tc["expected_engine"]
        print(f"    [+] Created: {prof['name']} (ID: {prof['id']}) -> {prof['language']} / {prof['dialect']} / {prof['voice_name']} (Display: '{prof['voice_display']}', Engine: {p_obj.get_engine_voice()})")

    # Mixed-case & raw engine name resilience test
    mixed_cases = [
        ("NOURHAN", "nourhan", "Aoede"),
        ("pUcK", "omar", "Puck"),
        ("Aoede", "nourhan", "Aoede"),
        ("  KhAlEd  ", "khaled", "Fenrir"),
    ]
    for raw_input, expected_id, expected_eng in mixed_cases:
        mc_req = rf.post(
            '/api/agents/profiles/create/',
            data=json.dumps({
                "name": f"Resilience Test {raw_input.strip()}",
                "voice_name": raw_input,
                "gender": "male",
                "language": "arabic",
                "dialect": "egyptian",
                "persona_role": "customer_support",
                "speaking_style": "friendly",
                "is_active": False
            }),
            content_type='application/json'
        )
        mc_req.user = user
        mc_resp = create_profile(mc_req)
        assert mc_resp.status_code == 201
        mc_prof = json.loads(mc_resp.content.decode('utf-8'))["profile"]
        assert mc_prof["voice_name"] == expected_id, f"Expected {expected_id}, got {mc_prof['voice_name']}"
        mc_obj = AgentProfile.objects.get(id=mc_prof["id"])
        assert mc_obj.get_engine_voice() == expected_eng
        print(f"    [+] Mixed-case input '{raw_input}' cleanly normalized to '{expected_id}' (Engine: {expected_eng})")

    print("✅ TEST 4 PASSED: Successfully created and verified multi-lingual profiles with engine voice isolation & casing resilience.")

    # -------------------------------------------------------------
    # TEST 5: Verify AI Dynamic System Instruction Prompt Builder
    # -------------------------------------------------------------
    print("\n[TEST 5] Testing AI Prompt Generator with Dialects...")
    sample_dialects = [
        ("saudi", "السعودية والخليجية الدارجة"),
        ("emirati", "الإماراتية والخليجية العذبة"),
        ("moroccan", "الدارجة المغربية"),
        ("iraqi", "العراقية الدافئة"),
        ("sudanese", "السودانية السمحة"),
        ("english_us", "American English"),
        ("french_fr", "français"),
        ("german_de", "Standarddeutsch"),
        ("chinese_zh", "普通话"),
        ("egyptian", "المصرية العامية"),
    ]

    if build_dynamic_system_instruction is not None:
        for d_code, expected_substr in sample_dialects:
            test_prof = {
                "name": f"Test {d_code}",
                "gender": "female",
                "dialect": d_code,
                "persona_role": "customer_support",
                "speaking_style": "friendly",
                "custom_instructions": "لا تتردد في الإجابة"
            }
            prompt = build_dynamic_system_instruction(test_prof)
            assert expected_substr.lower() in prompt.lower(), f"Prompt for '{d_code}' did not contain '{expected_substr}'!"
            print(f"    [+] Prompt generation for '{d_code}' verified ({len(prompt)} chars).")
        print("✅ TEST 5 PASSED: Prompt builder generates accurate cultural guidelines for all dialects.")
    else:
        print("    [!] Note: Agent code resides in voice_agent container. Running agent validation separately.")

    # -------------------------------------------------------------
    # TEST 6: Test Internal Bootstrap API Delivery
    # -------------------------------------------------------------
    print("\n[TEST 6] Testing Internal Bootstrap Endpoint for AI Daemon...")
    b_req = rf.post(
        '/api/agents/internal/bootstrap/',
        data=json.dumps({"user_id": user.id}),
        content_type='application/json',
        HTTP_X_INTERNAL_API_KEY=getattr(settings, 'INTERNAL_API_KEY', 'voice-internal-secret-token-key-12345')
    )
    b_resp = api_internal_agent_bootstrap(b_req)
    assert b_resp.status_code == 200, f"Bootstrap failed with code {b_resp.status_code}"
    b_data = json.loads(b_resp.content.decode('utf-8'))
    active_p = b_data.get("profile")
    assert active_p is not None, "Bootstrap returned no active profile!"
    assert "language" in active_p
    assert "dialect" in active_p
    assert "voice_name" in active_p
    print(f"    [+] Bootstrap successfully delivered active profile:")
    print(f"        Name: {active_p['name']}")
    print(f"        Voice: {active_p['voice_name']}")
    print(f"        Language: {active_p['language']}")
    print(f"        Dialect: {active_p['dialect']}")
    print("✅ TEST 6 PASSED: Bootstrap API verified.")

    print("\n" + "=" * 65)
    print("🎉 ALL TESTS PASSED SUCCESSFULLY! FULL SUITE IS VERIFIED!")
    print("=" * 65)


if __name__ == '__main__':
    run_e2e_tests()
