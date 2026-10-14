"""Prompts package for Voice & Omnichannel AI Agent."""
from .dialects import DIALECT_RULES_MAP, build_language_lock_instruction
from .verbosity import VERBOSITY_INSTRUCTIONS
from .builder import build_dynamic_system_instruction, generate_welcome_greeting
from .live_context import format_live_context_for_prompt
from .roles.registry import ROLE_REGISTRY, resolve_role_text, get_role_default_skills
from .roles.archetypes import ARCHETYPES, get_archetype_behavior
from .skills.custom_loader import SKILLS_REGISTRY, resolve_active_skills, register_skill
from .core.channel_adapter import build_channel_instructions
from .core.universal_voice import build_universal_voice_rules

__all__ = [
    "DIALECT_RULES_MAP",
    "VERBOSITY_INSTRUCTIONS",
    "build_dynamic_system_instruction",
    "generate_welcome_greeting",
    "format_live_context_for_prompt",
    "build_language_lock_instruction",
    "ROLE_REGISTRY",
    "resolve_role_text",
    "get_role_default_skills",
    "ARCHETYPES",
    "get_archetype_behavior",
    "SKILLS_REGISTRY",
    "resolve_active_skills",
    "register_skill",
    "build_channel_instructions",
    "build_universal_voice_rules",
]
