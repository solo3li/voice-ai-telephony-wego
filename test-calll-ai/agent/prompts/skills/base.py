"""Base class and interface for modular AI agent skills."""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class Skill:
    """Represents a domain or behavioral skill that can be dynamically plugged into an agent."""
    id: str
    name: str
    description: str
    prompt_instruction: str = ""
    required_tools: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def render(self, context: Optional[Dict[str, Any]] = None) -> str:
        """Render the skill prompt instructions."""
        return self.prompt_instruction.strip()
