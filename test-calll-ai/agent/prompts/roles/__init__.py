"""Roles package for Agent Personas and Archetypes."""
from .archetypes import ARCHETYPES, get_archetype_behavior
from .registry import ROLE_REGISTRY, resolve_role_text, get_role_default_skills

__all__ = [
    "ARCHETYPES",
    "get_archetype_behavior",
    "ROLE_REGISTRY",
    "resolve_role_text",
    "get_role_default_skills",
]
