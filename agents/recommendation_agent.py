"""
agents/recommendation_agent.py
================================
Recommendation Agent using the Mistral client.

Generates 3-5 actionable recommendations referencing specific metrics.
"""

from __future__ import annotations

import json
import os
from typing import Any
from loguru import logger

try:
    from mistralai.client import Mistral
except ImportError:
    try:
        from mistralai import Mistral
    except ImportError:
        Mistral = None

from agents.state import AgentState
from agents.llm_cache import cache_get, cache_set


SYSTEM_PROMPT = (
    "You are a business strategy consultant. Based on data analysis results, generate 3-5 specific, actionable business recommendations. "
    "Each recommendation must reference a specific metric or finding from the data. Return ONLY valid JSON: "
    '{"recommendations": [{"action": "...", "rationale": "...", "metric_referenced": "...", "priority": "high|medium|low"}]}'
)


def _strip_fences(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[-1].strip() == "```":
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        return "\n".join(lines).strip()
    return text


def _format_recommendations(raw_recs: list[dict] | list[str] | Any) -> list[str]:
    formatted = []
    for rec in raw_recs or []:
        if isinstance(rec, dict):
            action = rec.get("action", "").strip()
            rationale = rec.get("rationale", "").strip()
            metric = rec.get("metric_referenced", "").strip()
            priority = rec.get("priority", "").strip()
            parts = []
            if action:
                parts.append(action.rstrip("."))
            if rationale:
                parts.append(f"Why: {rationale.rstrip('.')}")
            if metric:
                parts.append(f"Metric: {metric}")
            if priority:
                parts.append(f"Priority: {priority}")
            formatted.append(" - ".join(parts))
        elif isinstance(rec, str):
            formatted.append(rec.strip())
        else:
            formatted.append(str(rec))
    return [r for r in formatted if r]


def recommendation_agent(state: AgentState) -> dict:
    question = state.get("question") or state.get("user_query", "")
    insights = state.get("insights", "")
    anomalies = state.get("anomalies", [])

    user_payload = {
        "question": question,
        "insights": insights,
        "anomalies": anomalies,
    }

    try:
        api_key = os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            logger.error("[RecommendationAgent] MISTRAL_API_KEY not set")
            return {"recommendations": [], "error": "MISTRAL_API_KEY not set"}
        client = Mistral(api_key=api_key)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, default=str, indent=2)},
        ]
        msg_key = json.dumps(messages, sort_keys=True, default=str)
        cached = cache_get(msg_key)
        if cached is not None:
            content = cached
        else:
            resp = client.chat.complete(model="mistral-small-latest", messages=messages)
            content = resp.choices[0].message.content
            cache_set(msg_key, content)
        raw = _strip_fences(content)
        parsed = json.loads(raw)
        recs = parsed.get("recommendations", [])
        formatted = _format_recommendations(recs)

        return {"recommendations": formatted}

    except Exception as exc:
        logger.error("[RecommendationAgent] error: %s", exc)
        return {"recommendations": [], "error": str(exc)}
