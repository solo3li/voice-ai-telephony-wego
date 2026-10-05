"""Voice AI Agent package."""
import os
import sys
import types

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
for p in [current_dir, parent_dir]:
    if p and p not in sys.path:
        sys.path.insert(0, p)

if "agent" not in sys.modules:
    agent_pkg = types.ModuleType("agent")
    agent_pkg.__path__ = [current_dir]
    sys.modules["agent"] = agent_pkg
