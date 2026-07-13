"""
agents/query_generation_agent.py
=================================
Query Generation Agent using the Mistral client. Produces DuckDB SQL
and equivalent Pandas code. Validates SQL via a dry-run EXPLAIN in DuckDB
and retries once if there is a syntax/parse error.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import duckdb
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
    "You are an expert SQL and Pandas developer. Given a dataset schema and a question, "
    "write both a SQL query (DuckDB-compatible) and equivalent Pandas code. Return ONLY valid JSON: "
    '{"sql": "...", "pandas": "...", "explanation": "..."}'
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


def _format_schema_for_prompt(schemas: dict[str, Any]) -> str:
    if not schemas:
        return "No datasets available."
    out = []
    for name, schema in schemas.items():
        cols = schema.get("columns", [])
        dtypes = schema.get("dtypes", {})
        cols_fmt = ", ".join(f"{c}: {dtypes.get(c, 'unknown')}" for c in cols[:50])
        out.append(f"Table: {name}\nColumns: {cols_fmt}")
    return "\n\n".join(out)


def query_generation_agent(state: AgentState) -> dict:
    question = state.get("question") or state.get("user_query", "")
    schemas = state.get("dataset_schema", {}) or {}
    schema_text = _format_schema_for_prompt(schemas)

    user_text = f"Question: {question}\n\n{schema_text}"

    try:
        api_key = os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            logger.error("[QueryGenerationAgent] MISTRAL_API_KEY not set")
            return {"sql_query": "", "pandas_code": "", "error": "MISTRAL_API_KEY not set"}
        client = Mistral(api_key=api_key)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
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
        parsed = json.loads(raw)

        sql = parsed.get("sql", "")
        pandas_code = parsed.get("pandas", "")

        # Validate SQL using EXPLAIN as a dry-run
        try:
            duckdb.query(f"EXPLAIN {sql}")
        except Exception as err:
            logger.warning("[QueryGen] SQL validation failed: %s — retrying once", err)
            # Retry once with the error appended to the prompt
            retry_text = user_text + f"\n\nThe previous SQL had this error: {err}. Fix it."
            resp2 = client.chat.complete(model="mistral-small-latest", messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": retry_text},
            ])
            content2 = resp2.choices[0].message.content
            raw2 = _strip_fences(content2)
            parsed2 = json.loads(raw2)
            sql = parsed2.get("sql", sql)
            pandas_code = parsed2.get("pandas", pandas_code)

        return {
            "sql_query": sql,
            "pandas_code": pandas_code,
            "generated_sql": sql,
            "generated_pandas": pandas_code,
        }

    except Exception as exc:
        logger.error("[QueryGenerationAgent] error: %s", exc)
        return {
            "sql_query": "",
            "pandas_code": "",
            "generated_sql": "",
            "generated_pandas": "",
            "error": str(exc),
        }