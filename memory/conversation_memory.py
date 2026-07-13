"""
memory/conversation_memory.py
==============================
LangGraph-compatible conversation memory wrapper.
Delegates persistence to RedisMemory with a clean interface
for injecting history into agent state.
"""

from __future__ import annotations

from typing import Dict, List

from memory.redis_memory import get_memory


class ConversationMemory:
    """
    Manages per-session conversation context for injection into AgentState.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._store = get_memory()

    def add_user_message(self, content: str) -> None:
        self._store.add_message(self.session_id, "user", content)

    def add_assistant_message(self, content: str) -> None:
        self._store.add_message(self.session_id, "assistant", content)

    def get_history(self, limit: int = 20) -> List[Dict[str, str]]:
        """Return [{role, content}] list for injection into AgentState."""
        return self._store.get_history(self.session_id, limit=limit)

    def get_previous_analyses(self) -> List[Dict]:
        return self._store.get_analyses(self.session_id)

    def clear(self) -> None:
        self._store.clear_history(self.session_id)

    def save_analysis_summary(self, query: str, insights: List[str], datasets: List[str]) -> None:
        self._store.save_analysis(self.session_id, {
            "query": query,
            "insights": insights[:3],
            "datasets": datasets,
        })