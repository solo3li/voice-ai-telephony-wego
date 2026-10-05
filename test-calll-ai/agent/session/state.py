"""Session state tracking for active Voice Agent calls."""
import asyncio
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set


@dataclass
class AgentSessionState:
    room_name: str
    user_id: Optional[int]
    caller_phone: str
    channel_name: str
    started_at: float
    dialogue_turns: List[Dict[str, str]] = field(default_factory=list)
    is_agent_speaking: bool = False
    turn_complete: bool = True
    agent_last_audio_time: float = 0.0
    interrupted: bool = False
    pending_transfer: Optional[Dict[str, Any]] = None
    background_tasks: Set[asyncio.Task] = field(default_factory=set)

    def track_task(self, task: asyncio.Task) -> asyncio.Task:
        """Retain a strong reference to background task so Python 3.11 GC does not destroy it."""
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
        return task

    async def cancel_all_tasks(self):
        """Cancel and cleanly await all remaining background tasks."""
        if not self.background_tasks:
            return
        tasks = list(self.background_tasks)
        for t in tasks:
            if not t.done():
                t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.background_tasks.clear()
