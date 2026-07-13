"""
agents/llm_cache.py

A tiny in-memory cache for LLM responses keyed by prompt/messages.
This helps speed up repeated identical requests during development and testing.
Not intended as a production cache.
"""
from __future__ import annotations

import time
import threading
from typing import Any, Optional

_LOCK = threading.Lock()
_CACHE: dict[str, tuple[float, Any]] = {}
_TTL = 60 * 60  # 1 hour


def cache_get(key: str) -> Optional[Any]:
    with _LOCK:
        entry = _CACHE.get(key)
        if not entry:
            return None
        ts, val = entry
        if ts + _TTL < time.time():
            del _CACHE[key]
            return None
        return val


def cache_set(key: str, value: Any) -> None:
    with _LOCK:
        _CACHE[key] = (time.time(), value)


def cache_clear() -> None:
    with _LOCK:
        _CACHE.clear()
