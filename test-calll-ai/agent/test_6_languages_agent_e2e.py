#!/usr/bin/env python3
import sys
import os

from prompts.builder import generate_welcome_greeting
from prompts.dialects import (
    LANGUAGE_SWITCH_OFFERS_MAP,
    get_language_switch_offer,
    build_language_lock_instruction,
    DIALECT_RULES_MAP,
    DIALECT_TO_LANG_FAMILY,
)

def run_agent_language_tests():
    print("=" * 60)
    print("🤖 RUNNING VOICE AI AGENT 6-LANGUAGE VERIFICATION")
    print("=" * 60)

    # 1. Proactive Greetings in 6 Languages
    print("\n[1] Proactive Default Greetings in 6 Languages:")
    test_profiles = [
        {"name": "سارة", "language": "arabic", "dialect": "egyptian", "expected": "أهلاً بحضرتك يا فندم"},
        {"name": "خالد", "language": "arabic", "dialect": "saudi", "expected": "يا هلا والله"},
        {"name": "Alex", "language": "english", "dialect": "english_us", "expected": "Hello! This is Alex from customer support"},
        {"name": "Elif", "language": "turkish", "dialect": "turkish_tr", "expected": "Merhaba! Ben müşteri hizmetlerinden Elif"},
        {"name": "Camille", "language": "french", "dialect": "french_fr", "expected": "Bonjour ! C'est Camille du service client"},
        {"name": "Lukas", "language": "german", "dialect": "german_de", "expected": "Hallo! Hier ist Lukas vom Kundenservice"},
        {"name": "Sofia", "language": "spanish", "dialect": "spanish_es", "expected": "¡Hola! Le habla Sofia de atención al cliente"},
    ]
    for prof in test_profiles:
        greeting = generate_welcome_greeting(prof)
        assert prof["expected"].lower() in greeting.lower(), f"Greeting for {prof['language']}/{prof['dialect']} expected '{prof['expected']}', got: '{greeting}'"
        print(f"  [+] Greeting for {prof['language']} ({prof['dialect']}): '{greeting[:45]}...'")

    # 2. Returning Customer Greetings in 6 Languages
    print("\n[2] Returning Recognized Customer Greetings in 6 Languages:")
    customer_tests = [
        {"prof": {"name": "Alex", "language": "english", "dialect": "english_us"}, "user": "John", "expected": "Hello John! Welcome back"},
        {"prof": {"name": "Elif", "language": "turkish", "dialect": "turkish_tr"}, "user": "Ahmet", "expected": "Merhaba Sayın Ahmet! Tekrar hoş geldiniz"},
        {"prof": {"name": "Camille", "language": "french", "dialect": "french_fr"}, "user": "Pierre", "expected": "Bonjour Pierre ! Ravi de vous retrouver"},
        {"prof": {"name": "Lukas", "language": "german", "dialect": "german_de"}, "user": "Klaus", "expected": "Hallo Herr/Frau Klaus! Schön, dass Sie wieder da sind"},
        {"prof": {"name": "Sofia", "language": "spanish", "dialect": "spanish_es"}, "user": "Carlos", "expected": "¡Hola Carlos! Qué gusto saludarle de nuevo"},
        {"prof": {"name": "سارة", "language": "arabic", "dialect": "saudi"}, "user": "فيصل", "expected": "يا هلا والله أستاذ فيصل"},
    ]
    for ct in customer_tests:
        ret_greeting = generate_welcome_greeting(ct["prof"], customer_name=ct["user"])
        assert ct["expected"].lower() in ret_greeting.lower(), f"Returning greeting failed for {ct['user']}: {ret_greeting}"
        print(f"  [+] Returning customer for {ct['prof']['language']}: '{ret_greeting[:50]}...'")

    # 3. Outbound Campaign Greetings in 6 Languages
    print("\n[3] Outbound Campaign Greetings in 6 Languages:")
    outbound_tests = [
        {"prof": {"name": "Alex", "language": "english", "dialect": "english_us"}, "campaign": "Follow up", "expected": "Hello, this is Alex. I'm calling regarding Follow up"},
        {"prof": {"name": "Elif", "language": "turkish", "dialect": "turkish_tr"}, "campaign": "Yenileme", "expected": "Merhaba, ben Elif. Sizi Yenileme ile ilgili arıyorum"},
        {"prof": {"name": "Camille", "language": "french", "dialect": "french_fr"}, "campaign": "Offre spéciale", "expected": "Bonjour, ici Camille. Je vous appelle concernant Offre spéciale"},
        {"prof": {"name": "Lukas", "language": "german", "dialect": "german_de"}, "campaign": "Vertrag", "expected": "Hallo, hier ist Lukas. Ich rufe Sie bezüglich Vertrag an"},
        {"prof": {"name": "Sofia", "language": "spanish", "dialect": "spanish_es"}, "campaign": "Suscripción", "expected": "Hola, le habla Sofia. Me comunico con usted con respecto a Suscripción"},
    ]
    for ot in outbound_tests:
        out_greeting = generate_welcome_greeting(ot["prof"], is_outbound=True, outbound_context={"call_goal": ot["campaign"]})
        assert ot["expected"].lower() in out_greeting.lower(), f"Outbound greeting failed for {ot['campaign']}: {out_greeting}"
        print(f"  [+] Outbound campaign for {ot['prof']['language']}: '{out_greeting[:55]}...'")

    # 4. Dialect & Polite Language Switch Offers Map
    print("\n[4] Polite Language Switch Offers Map & Aliases:")
    expected_switch_langs = ['english', 'en', 'french', 'fr', 'turkish', 'tr', 'german', 'de', 'spanish', 'es']
    for slang in expected_switch_langs:
        offer = get_language_switch_offer(slang)
        assert offer, f"Missing switch offer for '{slang}'!"
        print(f"  [+] Language switch offer for '{slang}': '{offer}'")

    # 5. Language Lock Instructions
    print("\n[5] Language Lock Instruction generation:")
    for lang in ['english', 'french', 'german', 'spanish', 'turkish', 'arabic']:
        instruction = build_language_lock_instruction(lang)
        assert instruction, f"Failed to build language lock instruction for {lang}"
        print(f"  [+] Lock instruction for {lang}: length={len(instruction)} chars")

    print("\n" + "=" * 60)
    print("✅ VOICE AI AGENT 6-LANGUAGE SUITE PASSED 100%!")
    print("=" * 60)

if __name__ == "__main__":
    run_agent_language_tests()
