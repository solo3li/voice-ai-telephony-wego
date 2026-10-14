"""Core prompt modules for Universal Voice & Omnichannel AI."""
from .universal_voice import build_universal_voice_rules
from .channel_adapter import build_channel_instructions
from .tool_contract import build_tool_contract_rules

__all__ = [
    "build_universal_voice_rules",
    "build_channel_instructions",
    "build_tool_contract_rules",
]
