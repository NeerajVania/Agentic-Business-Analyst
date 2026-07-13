"""
agents/insight_agent.py
========================

Converts raw statistical results into clear, executive-level business
insights using the Mistral API.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from loguru import logger
try:
    from mistralai.client import Mistral
except ImportError:
    try:
        from mistralai import Mistral
    except ImportError:
        Mistral = None
from agents.llm_cache import cache_get, cache_set

from agents.state import AgentState


SYSTEM_PROMPT = (
    "You are a senior business analyst. Analyze the data and return a JSON object with two keys:\n"
    "1. \"insights\": list of 2-4 executive-level business insights. Be specific with numbers. "
    "Explain WHY patterns occurred, not just what happened. Each insight: 1-2 sentences.\n"
    "2. \"trends\": list of 2-4 observable trends in the data (rising, falling, cyclical, seasonal). "
    "Format each trend as: '<Metric> <direction> — <brief explanation with numbers>'. Each trend: 1 sentence.\n"
    "Return ONLY valid JSON: {\"insights\": [\"...\"], \"trends\": [\"...\"]}"
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


def _normalize_insights(text: str) -> list[str]:
    if isinstance(text, list):
        return [str(item).strip() for item in text if str(item).strip()]
    parsed = (text or "").strip()
    if not parsed:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", parsed) if p.strip()]
    insights = []
    for paragraph in paragraphs:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", paragraph) if s.strip()]
        if sentences:
            insights.append(" ".join(sentences[:2]))
        elif paragraph:
            insights.append(paragraph)
        if len(insights) >= 3:
            break

    if insights:
        return insights

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", parsed) if s.strip()]
    return [" ".join(sentences[:3])] if sentences else [parsed]


def insight_agent(state: AgentState) -> dict:
    question = state.get("question") or state.get("user_query", "")
    analysis = state.get("analysis_results", {}) or state.get("analysis_result", {})
    rag = state.get("rag_context", "")

    # Trim analysis to key stats only — avoids large context and speeds up LLM
    trimmed: dict = {}
    for ds_name, ds_data in (analysis.items() if isinstance(analysis, dict) else {}.items()):
        if not isinstance(ds_data, dict):
            continue
        trimmed[ds_name] = {
            "shape": ds_data.get("shape"),
            "descriptive_stats": ds_data.get("descriptive_stats"),
            "top_correlations": ds_data.get("top_correlations"),
            "categorical_stats": ds_data.get("categorical_stats"),
            "date_stats": ds_data.get("date_stats"),
        }

    user_parts = [f"Question: {question}", "Analysis result:\n" + json.dumps(trimmed, default=str, indent=2)[:6000]]
    if rag:
        user_parts.append("Company context: " + (rag if isinstance(rag, str) else json.dumps(rag)[:1000]))

    user_msg = "\n\n".join(user_parts)

    try:
        # Prefer the app settings (reads .env via Pydantic); fall back to os.environ
        try:
            from config.settings import get_settings
            api_key = get_settings().mistral_api_key
        except Exception:
            api_key = os.environ.get("MISTRAL_API_KEY")

        if not api_key:
            logger.error("[InsightAgent] MISTRAL_API_KEY not set")
            return {"insights": _normalize_insights("Insight generation failed: 'MISTRAL_API_KEY'"), "error": "MISTRAL_API_KEY not set"}

        client = Mistral(api_key=api_key)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]
        key = json.dumps(messages, sort_keys=True, default=str)
        cached = cache_get(key)
        if cached is not None:
            text = _strip_fences(cached)
        else:
            resp = client.chat.complete(model="mistral-small-latest", messages=messages)
            content = resp.choices[0].message.content
            text = _strip_fences(content)
            cache_set(key, content)
        # Try to parse as JSON with insights + trends
        try:
            parsed_json = json.loads(text)
            raw_insights = parsed_json.get("insights", [])
            raw_trends   = parsed_json.get("trends", [])
            insights = [str(i).strip() for i in raw_insights if str(i).strip()]
            trends   = [str(t).strip() for t in raw_trends   if str(t).strip()]
            if insights:
                return {"insights": insights, "trends": trends}
        except (json.JSONDecodeError, AttributeError):
            pass

        # Fallback: treat as plain text insights, no trends
        return {"insights": _normalize_insights(text), "trends": []}

    except Exception as exc:
        logger.error("[InsightAgent] error: %s", exc)
        return {"insights": _normalize_insights(f"Insight generation failed: {exc}"), "trends": []}