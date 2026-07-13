"""
agents/state.py
===============
Shared state object passed between every node in the LangGraph multi-agent
workflow.
"""

from __future__ import annotations

from typing import Annotated, Any, Optional
try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict


def add_messages(a: list | None, b: list) -> list:
    """Reducer used for merging annotated message lists in AgentState.

    LangGraph expects reducers with signature (existing, incoming) -> merged.
    This merges two lists by concatenation, preserving order and handling None.
    """
    if a is None:
        a = []
    if b is None:
        b = []
    return list(a) + list(b)


def merge_active_agents(a: list | None, b: list | None) -> list:
    """Reducer for active_agents — merges parallel branch updates without duplicates."""
    if a is None:
        a = []
    if b is None:
        b = []
    return list(dict.fromkeys(list(a) + list(b)))


def merge_errors(a: list | None, b: list | None) -> list:
    """Reducer for errors — concatenates error lists from parallel branches."""
    if a is None:
        a = []
    if b is None:
        b = []
    return list(a) + list(b)


def safe_state_value(value: Any) -> Any:
    """Convert complex objects to JSON-safe values before storing in state."""
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, dict):
        return {str(key): safe_state_value(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [safe_state_value(item) for item in value]

    cls_name = value.__class__.__name__
    if cls_name in ("DataFrame", "Series"):
        try:
            return value.reset_index().to_dict(orient="records")
        except Exception:
            return str(value)

    if cls_name in ("Figure", "PlotlyFigure"):
        try:
            return value.to_dict()
        except Exception:
            return str(value)

    return str(value)


class AgentState(TypedDict, total=False):
    # User input and session
    user_query: str
    question: str
    session_id: str
    
    # Datasets
    dataset_ids: list[str]
    dataframes: dict[str, Any]
    dataset_schema: dict[str, Any]
    dataset_schemas: dict[str, Any]
    dataframe_summary: str
    
    # Planning and routing
    plan: list[str]
    current_task: str
    completed_tasks: list[str]
    execution_plan: list[str]
    active_agents: Annotated[list[str], merge_active_agents]
    
    # Analysis outputs
    analysis_result: dict[str, Any]
    analysis_results: dict[str, Any]
    kpi_summary: dict[str, Any]
    dashboard_config: dict[str, Any]
    
    # Queries
    sql_query: str
    pandas_code: str
    generated_sql: str
    generated_pandas: str
    query_results: list[dict[str, Any]]
    
    # Visualizations and insights
    chart_json: str
    chart_specs: list[dict[str, Any]]
    chart_types_chosen: list[str]
    insights: Any
    trends: list[dict[str, Any]]
    recommendations: list[str]
    anomalies: list[dict[str, Any]]
    anomaly_explanations: list[str]
    
    # Reports and documentation
    report_markdown: str
    report_html: str
    report_pdf_path: str
    final_response: str
    
    # RAG and context
    rag_context: str
    rag_citations: list[str]
    conversation_history: list[dict[str, Any]]
    previous_analyses: list[dict[str, Any]]
    
    # Explainability and evaluation
    explainability: dict[str, Any]
    metadata: dict[str, Any]
    
    # Error tracking
    error: Optional[str]
    errors: Annotated[list[str], merge_errors]
    messages: Annotated[list[dict[str, Any]], add_messages]
