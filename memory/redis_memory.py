"""
memory/redis_memory.py
=======================
Redis-backed conversation and analysis memory.

Stores:
  • Conversation history (per session)
  • Previous analysis summaries
  • User preferences
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, List, Optional

import redis
from loguru import logger

from config.settings import get_settings

settings = get_settings()

# TTL in seconds (24 hours)
DEFAULT_TTL = 86400


class RedisMemory:
    """Thread-safe Redis memory store for conversation sessions."""

    def __init__(self):
        self._fallback: dict[str, Any] = {}
        if settings.use_in_memory_fallback:
            self._available = False
            logger.info(
                "USE_IN_MEMORY_FALLBACK=true — Redis memory using in-memory fallback store"
            )
            return

        try:
            self._client = redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=3,
            )
            self._client.ping()
            self._available = True
            logger.info("Redis memory connected: {}", settings.redis_url)
        except (redis.ConnectionError, redis.TimeoutError, redis.RedisError) as exc:
            logger.warning(
                "Redis unavailable ({}) — falling back to in-memory store",
                exc,
            )
            self._available = False

    # ── Conversation history ──────────────────────────────────────────────────

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Append a message to the conversation history."""
        key = f"conversation:{session_id}"
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if self._available:
            self._client.rpush(key, json.dumps(message))
            self._client.expire(key, DEFAULT_TTL)
        else:
            self._fallback.setdefault(key, []).append(message)

    def get_history(self, session_id: str, limit: int = 20) -> List[dict]:
        """Retrieve the last `limit` messages for a session."""
        key = f"conversation:{session_id}"

        if self._available:
            raw_messages = self._client.lrange(key, -limit, -1)
            return [json.loads(m) for m in raw_messages]
        else:
            return self._fallback.get(key, [])[-limit:]

    def clear_history(self, session_id: str) -> None:
        """Clear conversation history for a session."""
        key = f"conversation:{session_id}"
        if self._available:
            self._client.delete(key)
        else:
            self._fallback.pop(key, None)

    # ── Generic key/value compatibility for LangGraph memory ────────────────

    def get(self, key: str) -> Optional[Any]:
        """Get a generic key from the store."""
        if self._available:
            raw = self._client.get(key)
            if raw is None:
                return None
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return raw
        return self._fallback.get(key)

    def set(self, key: str, value: Any) -> None:
        """Set a generic key in the store."""
        if self._available:
            payload = json.dumps(value, default=str)
            self._client.set(key, payload)
        else:
            self._fallback[key] = value

    def delete(self, key: str) -> None:
        """Delete a generic key from the store."""
        if self._available:
            self._client.delete(key)
        else:
            self._fallback.pop(key, None)

    @property
    def available(self) -> bool:
        return self._available

    @property
    def fallback_mode(self) -> bool:
        return not self._available

    # ── Analysis cache ────────────────────────────────────────────────────────

    def save_analysis(self, session_id: str, analysis_summary: dict) -> None:
        """Store a compressed analysis summary."""
        key = f"analysis:{session_id}"
        entry = {
            **analysis_summary,
            "saved_at": datetime.utcnow().isoformat(),
        }

        if self._available:
            # Keep last 10 analyses per session (LPUSH + LTRIM)
            self._client.lpush(key, json.dumps(entry, default=str))
            self._client.ltrim(key, 0, 9)
            self._client.expire(key, DEFAULT_TTL)
        else:
            lst = self._fallback.setdefault(key, [])
            lst.insert(0, entry)
            self._fallback[key] = lst[:10]

    def get_analyses(self, session_id: str) -> List[dict]:
        """Retrieve previous analyses for a session."""
        key = f"analysis:{session_id}"
        if self._available:
            raw = self._client.lrange(key, 0, -1)
            return [json.loads(r) for r in raw]
        return self._fallback.get(key, [])

    # ── User preferences ──────────────────────────────────────────────────────

    def save_preference(self, session_id: str, key: str, value: Any) -> None:
        """Save a user preference."""
        pref_key = f"prefs:{session_id}"
        if self._available:
            self._client.hset(pref_key, key, json.dumps(value))
            self._client.expire(pref_key, DEFAULT_TTL * 7)  # 7 days
        else:
            self._fallback.setdefault(pref_key, {})[key] = value

    def get_preference(self, session_id: str, key: str) -> Optional[Any]:
        """Retrieve a user preference."""
        pref_key = f"prefs:{session_id}"
        if self._available:
            raw = self._client.hget(pref_key, key)
            return json.loads(raw) if raw else None
        return self._fallback.get(pref_key, {}).get(key)


# ── Singleton ──────────────────────────────────────────────────────────────────

_memory_instance: Optional[RedisMemory] = None


def get_memory() -> RedisMemory:
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = RedisMemory()
    return _memory_instance