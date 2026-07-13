"""
agents/graph.py
===============
LangGraph multi-agent workflow orchestration.

Graph structure:
  START
    → planner
    → router
    → [data_analysis | query_generation | anomaly_detection | visualization | insight | recommendation | report]
    → insight
    → recommendation
    → report
    → END
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

try:
    from loguru import logger
except ImportError:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("agents.graph")

try:
    from langgraph.graph import StateGraph, START, END
except ImportError:
    StateGraph = None  # type: ignore[assignment]
    START = None
    END = None

from agents.state import AgentState, safe_state_value

try:
    from langgraph.checkpointer import MemorySaver
except Exception:
    # langgraph.checkpointer may not be available in all environments
    # Use None so `graph.compile(checkpointer=...)` falls back to no checkpointer.
    MemorySaver = None


def _timed(node_fn, node_name: str):
    def wrapper(state: AgentState) -> dict:
        t0 = time.perf_counter()
        try:
            output = node_fn(state) or {}
            if not isinstance(output, dict):
                raise ValueError(f"{node_name} returned non-dict output: {type(output).__name__}")
            output = {key: safe_state_value(value) for key, value in output.items()}
        except Exception as exc:
            logger.exception("[Graph] %s failed", node_name)
            elapsed = round(time.perf_counter() - t0, 3)
            logger.info("[Graph] %s failed in %.3fs", node_name, elapsed)
            return {
                "errors": [f"{node_name} failed: {exc}"],
                "active_agents": [node_name],
            }

        elapsed = round(time.perf_counter() - t0, 3)
        logger.info("[Graph] %s completed in %.3fs", node_name, elapsed)

        # Only return this node's contribution — the Annotated reducer merges across branches
        if node_name not in (output.get("active_agents") or []):
            output["active_agents"] = [node_name]

        return output

    wrapper.__name__ = node_fn.__name__
    return wrapper


def planner(state: AgentState) -> dict:
    from agents.planner_agent import planner_agent
    return planner_agent(state)


def data_analysis(state: AgentState) -> dict:
    from agents.data_analysis_agent import data_analysis_agent
    return data_analysis_agent(state)


def query_generation(state: AgentState) -> dict:
    from agents.query_generation_agent import query_generation_agent
    return query_generation_agent(state)


def anomaly_detection(state: AgentState) -> dict:
    from agents.anomaly_detection_agent import anomaly_detection_agent
    return anomaly_detection_agent(state)


def visualization(state: AgentState) -> dict:
    from agents.visualization_agent import visualization_agent
    return visualization_agent(state)


def insight(state: AgentState) -> dict:
    from agents.insight_agent import insight_agent
    return insight_agent(state)


def recommendation(state: AgentState) -> dict:
    from agents.recommendation_agent import recommendation_agent
    return recommendation_agent(state)


def report(state: AgentState) -> dict:
    from agents.report_agent import report_agent
    return report_agent(state)


def router(state: AgentState) -> str:
    plan: List[str] = state.get("plan", []) or []
    completed: List[str] = state.get("completed_tasks", []) or []

    next_task: Optional[str] = None
    for task in plan:
        if task not in completed:
            next_task = task
            break

    if not next_task:
        return END

    normalized = next_task.lower()
    if any(keyword in normalized for keyword in ("analyze", "statistics")):
        return "data_analysis"
    if any(keyword in normalized for keyword in ("sql", "query")):
        return "query_generation"
    if any(keyword in normalized for keyword in ("anomaly", "outlier")):
        return "anomaly_detection"
    if any(keyword in normalized for keyword in ("visual", "chart")):
        return "visualization"
    if "insight" in normalized:
        return "insight"
    if "recommend" in normalized:
        return "recommendation"
    if "report" in normalized:
        return "report"

    return "data_analysis"


ROUTING_MAP: Dict[str, str] = {
    "data_analysis": "data_analysis",
    "query_generation": "query_generation",
    "anomaly_detection": "anomaly_detection",
    "visualization": "visualization",
    "insight": "insight",
    "recommendation": "recommendation",
    "report": "report",
    END: END,
}


def build_agent_graph() -> StateGraph:
    if StateGraph is None or START is None or END is None:
        raise RuntimeError("LangGraph is not installed or unavailable")

    graph = StateGraph(AgentState)

    graph.add_node("planner", _timed(planner, "planner"))
    graph.add_node("data_analysis", _timed(data_analysis, "data_analysis"))
    graph.add_node("query_generation", _timed(query_generation, "query_generation"))
    graph.add_node("anomaly_detection", _timed(anomaly_detection, "anomaly_detection"))
    graph.add_node("visualization", _timed(visualization, "visualization"))
    graph.add_node("insight", _timed(insight, "insight"))
    graph.add_node("recommendation", _timed(recommendation, "recommendation"))
    graph.add_node("report", _timed(report, "report"))

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "data_analysis")
    # Fan-out: run query_generation, anomaly_detection, visualization in parallel
    graph.add_edge("data_analysis", "query_generation")
    graph.add_edge("data_analysis", "anomaly_detection")
    graph.add_edge("data_analysis", "visualization")
    # Fan-in: all three feed into insight
    graph.add_edge("query_generation", "insight")
    graph.add_edge("anomaly_detection", "insight")
    graph.add_edge("visualization", "insight")
    graph.add_edge("insight", "recommendation")
    graph.add_edge("recommendation", "report")
    graph.add_edge("report", END)

    checkpointer = MemorySaver() if callable(MemorySaver) else None
    compiled = graph.compile(checkpointer=checkpointer)
    logger.info("[Graph] Agent graph compiled — nodes: %s", list(graph.nodes))
    return compiled


_graph: Optional[StateGraph] = None


def get_agent_graph() -> Optional[StateGraph]:
    global _graph
    if _graph is None:
        try:
            _graph = build_agent_graph()
        except Exception as exc:
            logger.warning("[Graph] LangGraph unavailable or failed to compile: %s", exc)
            _graph = None
    return _graph


def _merge_state(base: AgentState, update: dict) -> AgentState:
    merged = dict(base)
    merged_errors = list(base.get("errors", []) or [])
    if "errors" in update:
        merged_errors += [e for e in update.get("errors", []) or []]
    if merged_errors:
        merged["errors"] = merged_errors
    # merge active_agents arrays while preserving order
    active_agents = list(dict.fromkeys((base.get("active_agents", []) or []) + (update.get("active_agents", []) or [])))
    if active_agents:
        merged["active_agents"] = active_agents
    merged.update({k: v for k, v in update.items() if k not in ("errors", "active_agents")})
    return merged


def _run_fallback_pipeline(initial_state: AgentState) -> AgentState:
    logger.warning("[Graph] Falling back to manual sequential pipeline")
    import concurrent.futures
    state: AgentState = dict(initial_state)

    # Sequential: planner → data_analysis
    for node in [planner, data_analysis]:
        output = _timed(node, node.__name__)(state) or {}
        state = _merge_state(state, output)

    # Parallel: query_generation + anomaly_detection + visualization
    parallel_nodes = [query_generation, anomaly_detection, visualization]
    state_snapshot = dict(state)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futures = {ex.submit(_timed(n, n.__name__), state_snapshot): n.__name__ for n in parallel_nodes}
        for fut in concurrent.futures.as_completed(futures):
            try:
                output = fut.result() or {}
                state = _merge_state(state, output)
            except Exception as exc:
                logger.error("[Graph] Parallel node failed: %s", exc)

    # Sequential: insight → recommendation → report
    for node in [insight, recommendation, report]:
        output = _timed(node, node.__name__)(state) or {}
        state = _merge_state(state, output)

    return state


async def run_agent_pipeline(initial_state: AgentState) -> AgentState:
    """Execute the agent pipeline. Uses the optimised fallback pipeline (ThreadPoolExecutor
    for the parallel fan-out step) which is faster and more predictable than the compiled
    LangGraph StateGraph for synchronous IO-bound agents."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run_fallback_pipeline, initial_state)
