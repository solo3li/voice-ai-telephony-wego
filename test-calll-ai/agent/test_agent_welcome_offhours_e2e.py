#!/usr/bin/env python3
"""
Test prompt builder and off-hours session in voice_agent container.
"""
import sys
import os

from agent.prompts.builder import build_dynamic_system_instruction, generate_welcome_greeting
from agent.session.off_hours_session import run_off_hours_session

def test_prompts():
    print("\n--- Testing Agent Dynamic Prompt Builder ---")
    # Case 1: Welcome Enabled with custom text
    prof_enabled = {
        "name": "سارة",
        "gender": "female",
        "dialect": "egyptian",
        "persona_role": "خدمة عملاء",
        "speaking_style": "ودود ومرح",
        "verbosity": "balanced",
        "welcome_message": "أهلاً بحضرتك يا فندم في متجرنا!",
        "is_welcome_message_enabled": True
    }
    prompt_1 = build_dynamic_system_instruction(prof_enabled)
    assert "أهلاً بحضرتك يا فندم في متجرنا!" in prompt_1
    assert "رسالة الترحيب المحددة لك لبدء الحديث" in prompt_1
    print("✓ Prompt with custom welcome message PASSED")

    # Case 2: Welcome Disabled
    prof_disabled = {
        "name": "سارة",
        "gender": "female",
        "dialect": "egyptian",
        "persona_role": "خدمة عملاء",
        "speaking_style": "ودود ومرح",
        "verbosity": "balanced",
        "welcome_message": "رسالة لن تظهر",
        "is_welcome_message_enabled": False
    }
    prompt_2 = build_dynamic_system_instruction(prof_disabled)
    assert "رسالة الترحيب الافتتاحية معطلة لهذا البروفايل" in prompt_2
    assert "التزم الصمت التام وانتظر المتصل البشري حتى يتكلم أولاً" in prompt_2
    assert "رسالة لن تظهر" not in prompt_2
    print("✓ Prompt with disabled welcome message PASSED")

    # Case 3: generate_welcome_greeting
    greeting_1 = generate_welcome_greeting(prof_enabled)
    assert greeting_1 == "أهلاً بحضرتك يا فندم في متجرنا!"
    print("✓ generate_welcome_greeting PASSED")

    # Case 4: Verify run_off_hours_session is callable
    assert callable(run_off_hours_session)
    print("✓ run_off_hours_session callable PASSED")

if __name__ == '__main__':
    test_prompts()
    print("\nALL AGENT TESTS PASSED! 🚀")
