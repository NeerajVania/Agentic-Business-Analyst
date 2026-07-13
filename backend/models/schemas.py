"""
backend/models/schemas.py
==========================
Pydantic request / response models for all API endpoints.

Field alignment with frontend pages
-------------------------------------
UploadResponse
  • dataset_id, filename, rows, columns  — used by 01_upload.py dataset_card()
  • schema                               — stored in st.session_state.uploaded_datasets[id]
                                           07_forecast.py reads:
                                             schema["columns"], schema["date_columns"],
                                             schema["numeric_columns"]

MultiUploadResponse
  • datasets        — list of UploadResponse
  • join_suggestions — displayed in 01_upload.py join cards

AnalysisResponse
  • kpi_summary               — kpi_row() in 02_analyze.py / 03_dashboard.py
  • active_agents             — agent_badges() in 02_analyze.py
  • insights, trends          — insight_list(kind="insight")
  • recommendations           — insight_list(kind="rec")
  • anomaly_count, anomaly_explanations — insight_list(kind="anomaly")
  • chart_count, charts       — go.Figure(chart) in 02_analyze.py / 03_dashboard.py
  • generated_sql             — st.code(language="sql")
  • generated_pandas          — st.code(language="python")
  • executive_summary         — prose card
  • report_markdown           — preview in 05_reports.py
  • processing_time_seconds   — summary bar
  • rag_citations             — citation expander
  • errors                    — pipeline errors expander

ChatResponse
  • response      — message["content"] bubble
  • rag_citations — citation chips (message["citations"])

ForecastResponse
  • forecast      — pd.DataFrame(forecast) + CSV download
  • chart         — go.Figure(chart) Plotly JSON
  • summary       — forecast summary card
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


# ── Upload ────────────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    dataset_id: str
    filename: str
    rows: int
    columns: int
    schema_: Dict[str, Any] = Field(default_factory=dict, alias="schema")

    model_config = {"populate_by_name": True}


class MultiUploadResponse(BaseModel):
    datasets: List[UploadResponse]
    join_suggestions: List[Dict[str, Any]] = Field(default_factory=list)


# ── Analysis ──────────────────────────────────────────────────────────────────

class AnalysisRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Natural language business question")
    dataset_ids: List[str] = Field(..., min_length=1)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    include_rag: bool = Field(True, description="Whether to inject RAG context into the pipeline")


class AnalysisResponse(BaseModel):
    session_id: str
    query: str
    execution_plan: List[str] = Field(default_factory=list)
    active_agents: List[str] = Field(default_factory=list)
    insights: List[str] = Field(default_factory=list)
    trends: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    anomaly_count: int = 0
    anomaly_explanations: List[str] = Field(default_factory=list)
    chart_count: int = 0
    # Each element is a Plotly JSON dict — frontend calls go.Figure(chart)
    charts: List[Dict[str, Any]] = Field(default_factory=list)
    generated_sql: Optional[str] = None
    generated_pandas: Optional[str] = None
    kpi_summary: Dict[str, Any] = Field(default_factory=dict)
    executive_summary: str = ""
    report_markdown: str = ""
    rag_citations: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    processing_time_seconds: float = 0.0
    explainability: Dict[str, Any] = Field(default_factory=dict)
    evaluation_metrics: Dict[str, Any] = Field(default_factory=dict)


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class ChatResponse(BaseModel):
    response: str
    session_id: str
    # Returned as message["citations"] in 06_chat.py for citation chips
    rag_citations: List[str] = Field(default_factory=list)


# ── Report ────────────────────────────────────────────────────────────────────

class ReportRequest(BaseModel):
    session_id: str
    format: str = Field("html", pattern="^(html|markdown|pdf)$")


class ReportResponse(BaseModel):
    session_id: str
    format: str
    # HTML and Markdown reports return content inline for preview.
    # PDF reports return only file_path (streamed via /download endpoint).
    content: Optional[str] = None
    file_path: Optional[str] = None


# ── RAG ───────────────────────────────────────────────────────────────────────

class RAGUploadResponse(BaseModel):
    filename: str
    chunks_stored: int
    collection: str


class RAGQueryRequest(BaseModel):
    query: str
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    top_k: int = Field(5, ge=1, le=20)


class RAGQueryResponse(BaseModel):
    answer: str
    # Displayed as source list in 04_rag.py with insight-item CSS class
    citations: List[str] = Field(default_factory=list)
    session_id: str


# ── Forecast ─────────────────────────────────────────────────────────────────

class ForecastRequest(BaseModel):
    dataset_id: str
    target_column: str
    date_column: str
    periods: int = Field(30, ge=1, le=365)
    method: str = Field("prophet", pattern="^(prophet|arima)$")
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class ForecastResponse(BaseModel):
    session_id: str
    target_column: str
    method: str
    # list of dicts with keys: ds, yhat, yhat_lower, yhat_upper (Prophet)
    # or: date, value (ARIMA) — frontend handles both via df.columns
    forecast: List[Dict[str, Any]] = Field(default_factory=list)
    # Plotly JSON dict for go.Figure(chart) in 07_forecast.py
    chart: Optional[Dict[str, Any]] = None
    summary: str = ""
    # Optional model diagnostics displayed in the diagnostics tab
    model_metrics: Optional[Dict[str, Any]] = None
    errors: List[str] = Field(default_factory=list)


# ── Evaluation ────────────────────────────────────────────────────────────────

class EvaluationResponse(BaseModel):
    session_id: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    notes: List[str] = Field(default_factory=list)
    last_analysis: Dict[str, Any] = Field(default_factory=dict)
    evaluation_metrics: Dict[str, Any] = Field(default_factory=dict)


# ── Dashboard (convenience schema for future /dashboard endpoint) ─────────────

class DashboardResponse(BaseModel):
    session_id: str
    kpis: Dict[str, Any] = Field(default_factory=dict)
    charts: List[Dict[str, Any]] = Field(default_factory=list)
    insights: List[str] = Field(default_factory=list)
    anomaly_count: int = 0
    dataset_count: int = 0


# ── Authentication ─────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: str = Field("user")


class UserProfile(BaseModel):
    username: str
    email: EmailStr
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    email: str
    role: str