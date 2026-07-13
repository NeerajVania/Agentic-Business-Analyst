"""
agents/planner_agent.py
=======================

Planner Agent using the mistralai Python client.

This node accepts an AgentState and produces a short execution plan
containing analytical subtasks. It returns a minimal plan structure
expected by the graph: {"plan": [...], "current_task": "..."}.
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

from agents.llm_cache import cache_get, cache_set

from agents.state import AgentState


SYSTEM_PROMPT = (
    "You are a data analyst. Given a business question and dataset schema, "
    "break the question into 3-6 analytical subtasks. Return ONLY valid JSON: "
    '{"tasks": ["task1", "task2", ...], "reasoning": "why these tasks"}'
)


def _strip_fences(text: str) -> str:
    text = (text or "").strip().lstrip("\ufeff")
    if text.startswith("```"):
        # drop fences like ``` or ```json
        lines = text.splitlines()
        # remove first line and last if it's a fence
        if lines and lines[-1].strip() == "```":
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        return "\n".join(lines).strip()
    return text


def planner_agent(state: AgentState) -> dict:
    """LangGraph node: produce a short task plan from question + schema."""
    question = state.get("question") or state.get("user_query") or ""
    schema = state.get("dataset_schema", {})

    user_payload = {
        "question": question,
        "dataset_schema": schema,
    }

    try:
        api_key = os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            logger.error("[PlannerAgent] MISTRAL_API_KEY not set")
            fallback = [
                "Perform exploratory data analysis",
                "Generate SQL and Pandas queries",
                "Create visualizations and initial insights",
            ]
            return {"plan": fallback, "current_task": fallback[0], "error": "MISTRAL_API_KEY not set"}
        client = Mistral(api_key=api_key)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, indent=2)},
        ]
        key = json.dumps(messages, sort_keys=True, default=str)
        cached = cache_get(key)
        if cached is not None:
            content = cached
        else:
            resp = client.chat.complete(model="mistral-small-latest", messages=messages)
            content = resp.choices[0].message.content
            cache_set(key, content)
        raw = _strip_fences(content)
        result = json.loads(raw)

        tasks = result.get("tasks") or []
        if not isinstance(tasks, list) or len(tasks) == 0:
            raise ValueError("No tasks returned")

        return {"plan": tasks, "current_task": tasks[0]}

    except Exception as exc:  # JSON errors, client issues, KeyError, etc.
        logger.warning("[PlannerAgent] failed to parse LLM response: %s", exc)
        fallback = [
            "Perform exploratory data analysis",
            "Generate SQL and Pandas queries",
            "Create visualizations and initial insights",
        ]
        return {"plan": fallback, "current_task": fallback[0], "error": str(exc)}