"""
agents/visualization_agent.py
==============================
Visualization Agent — Plotly chart generation.

Responsibilities:
  • Intelligently select the best chart type based on data characteristics
  • Generate Plotly figure specifications
  • Handle bar, line, scatter, pie, heatmap, histogram, box, correlation plots

Performance note: large datasets are sampled to CHART_SAMPLE_SIZE rows
before chart generation to keep chart specs manageable.
"""

from __future__ import annotations

from typing import Any

import json
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from loguru import logger

from agents.state import AgentState

CHART_SAMPLE_SIZE = 5_000
MAX_CATEGORIES = 15


# ── Agent node ────────────────────────────────────────────────────────────────

def visualization_agent(state: AgentState) -> AgentState:
    """
    LangGraph node: Visualization Agent.
    Reads `dataframes`, `analysis_results`, `query_results`, `user_query`.
    Writes `chart_specs`, `chart_types_chosen`.
    """
    logger.info("[VisualizationAgent] Generating charts")

    dataframes: dict[str, pd.DataFrame] = state.get("dataframes", {})
    query_results = state.get("query_results", [])

    charts = []
    chart_types = []

    for name, df in dataframes.items():
        # Sample large datasets for performance
        if len(df) > CHART_SAMPLE_SIZE:
            logger.info(
                "[VisualizationAgent] Sampling {} → {} rows for '{}'",
                len(df), CHART_SAMPLE_SIZE, name,
            )
            df = df.sample(CHART_SAMPLE_SIZE, random_state=42).reset_index(drop=True)

        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
        date_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()

        # 1. KPI bar chart
        if numeric_cols and cat_cols:
            try:
                fig = _bar_chart(df, cat_cols[0], numeric_cols[0], name)
                charts.append(fig)
                chart_types.append("bar")
                logger.info("[VisualizationAgent] Stored bar chart for '{}'", name)
            except Exception as exc:
                logger.warning("[VisualizationAgent] Bar chart failed for '{}': {}", name, exc)

        # 2. Time series if dates exist
        if date_cols and numeric_cols:
            try:
                fig = _line_chart(df, date_cols[0], numeric_cols[0], name)
                charts.append(fig)
                chart_types.append("line")
                logger.info("[VisualizationAgent] Stored line chart for '{}'", name)
            except Exception as exc:
                logger.warning("[VisualizationAgent] Line chart failed for '{}': {}", name, exc)

        # 3. Correlation heatmap
        if len(numeric_cols) > 2:
            try:
                corr_fig = _correlation_heatmap(df[numeric_cols], name)
                charts.append(corr_fig)
                chart_types.append("heatmap")
                logger.info("[VisualizationAgent] Stored heatmap for '{}'", name)
            except Exception as exc:
                logger.warning("[VisualizationAgent] Heatmap failed for '{}': {}", name, exc)

        # 4. Distribution histograms for top 2 numeric cols
        for col in numeric_cols[:2]:
            try:
                fig = _histogram(df, col, name)
                charts.append(fig)
                chart_types.append("histogram")
                logger.info("[VisualizationAgent] Stored histogram for '{}' on {}", name, col)
            except Exception as exc:
                logger.warning("[VisualizationAgent] Histogram failed for col '{}': {}", col, exc)

        # 5. Box plots for outlier visibility (limit categories)
        if numeric_cols and cat_cols:
            try:
                fig = _box_plot(df, cat_cols[0], numeric_cols[0], name)
                charts.append(fig)
                chart_types.append("box")
                logger.info("[VisualizationAgent] Stored box plot for '{}'", name)
            except Exception as exc:
                logger.warning("[VisualizationAgent] Box plot failed for '{}': {}", name, exc)

        # 6. Scatter: top 2 numeric correlation
        if len(numeric_cols) >= 2:
            try:
                fig = _scatter_plot(df, numeric_cols[0], numeric_cols[1], name)
                charts.append(fig)
                chart_types.append("scatter")
                logger.info("[VisualizationAgent] Stored scatter chart for '{}'", name)
            except Exception as exc:
                logger.warning("[VisualizationAgent] Scatter failed for '{}': {}", name, exc)

    # 7. Query result chart (if applicable)
    if query_results and isinstance(query_results, list):
        try:
            qr_df = pd.DataFrame(query_results)
            if not qr_df.empty:
                qr_chart = _auto_chart(qr_df, "Query Result")
                if qr_chart:
                    charts.append(qr_chart)
                    chart_types.append("auto")
                    logger.info(
                        "[VisualizationAgent] Created auto chart for query results"
                    )
        except Exception as exc:
            logger.warning("[VisualizationAgent] Query result chart failed: {}", exc)

    # Anomaly overlay (if anomalies detected)
    anomalies = state.get("anomalies", [])
    if anomalies:
        for name, df in state.get("dataframes", {}).items():
            try:
                if len(df) > CHART_SAMPLE_SIZE:
                    df = df.sample(CHART_SAMPLE_SIZE, random_state=42).reset_index(drop=True)
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                if numeric_cols:
                    fig = _anomaly_chart(df, numeric_cols[0], anomalies, name)
                    charts.append(fig)
                    chart_types.append("anomaly_scatter")
            except Exception as exc:
                logger.warning("[VisualizationAgent] Anomaly chart failed: {}", exc)

    if not charts:
        logger.warning("[VisualizationAgent] No charts generated for current state")
    else:
        logger.info(
            "[VisualizationAgent] Generated {} charts and stored them in state",
            len(charts),
        )

    return {
        "chart_specs": charts,
        "chart_types_chosen": chart_types,
    }


# ── Chart builders ─────────────────────────────────────────────────────────────

def _serialize_fig(fig: go.Figure) -> dict:
    """Serialize a Plotly figure to a JSON-safe dict for LangGraph state."""
    return json.loads(fig.to_json())


def _bar_chart(df: pd.DataFrame, x: str, y: str, title: str) -> dict:
    # Limit categories
    grouped = df.groupby(x)[y].sum().reset_index().sort_values(y, ascending=False).head(MAX_CATEGORIES)
    fig = px.bar(
        grouped, x=x, y=y,
        title=f"{title} — {y} by {x}",
        color=y, color_continuous_scale="Blues",
        template="plotly_dark",
    )
    fig.update_layout(showlegend=False)
    return _serialize_fig(fig)


def _line_chart(df: pd.DataFrame, x: str, y: str, title: str) -> dict:
    df_sorted = df.sort_values(x)
    fig = px.line(
        df_sorted, x=x, y=y,
        title=f"{title} — {y} over time",
        template="plotly_dark",
        markers=True,
    )
    return _serialize_fig(fig)


def _correlation_heatmap(df_numeric: pd.DataFrame, title: str) -> dict:
    corr = df_numeric.corr().round(2)
    z_values = corr.values.tolist()  # Convert to Python list
    fig = go.Figure(
        data=go.Heatmap(
            z=z_values,
            x=corr.columns.tolist(),
            y=corr.index.tolist(),
            colorscale="RdBu",
            zmid=0,
            text=[[round(v, 2) for v in row] for row in z_values],
            texttemplate="%{text}",
        )
    )
    fig.update_layout(
        title=f"{title} — Correlation Matrix",
        template="plotly_dark",
    )
    return _serialize_fig(fig)


def _histogram(df: pd.DataFrame, col: str, title: str) -> dict:
    fig = px.histogram(
        df, x=col,
        title=f"{title} — Distribution of {col}",
        nbins=30,
        template="plotly_dark",
        color_discrete_sequence=["#00d4ff"],
    )
    return _serialize_fig(fig)


def _box_plot(df: pd.DataFrame, x: str, y: str, title: str) -> dict:
    # Limit number of categories shown in box plot
    top_cats = df[x].value_counts().head(MAX_CATEGORIES).index
    df_filtered = df[df[x].isin(top_cats)]
    fig = px.box(
        df_filtered, x=x, y=y,
        title=f"{title} — {y} distribution by {x}",
        template="plotly_dark",
        color=x,
    )
    return _serialize_fig(fig)


def _scatter_plot(df: pd.DataFrame, x: str, y: str, title: str) -> dict:
    # Try with OLS trendline, fall back to plain scatter
    try:
        fig = px.scatter(
            df, x=x, y=y,
            title=f"{title} — {x} vs {y}",
            template="plotly_dark",
            trendline="ols",
            opacity=0.7,
        )
    except Exception:
        fig = px.scatter(
            df, x=x, y=y,
            title=f"{title} — {x} vs {y}",
            template="plotly_dark",
            opacity=0.7,
        )
    return _serialize_fig(fig)


def _auto_chart(df: pd.DataFrame, title: str) -> dict | None:
    """Automatically pick a chart for a query result dataframe."""
    numeric = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical = df.select_dtypes(include=["object"]).columns.tolist()

    if not numeric:
        return None

    if categorical:
        fig = px.bar(df.head(MAX_CATEGORIES), x=categorical[0], y=numeric[0], title=title, template="plotly_dark")
    else:
        fig = px.line(df, y=numeric[0], title=title, template="plotly_dark")

    return _serialize_fig(fig)


def _anomaly_chart(
    df: pd.DataFrame,
    col: str,
    anomalies: list[dict],
    title: str,
) -> dict:
    """Scatter plot highlighting anomaly points."""
    df = df.reset_index(drop=True)
    fig = px.scatter(
        df, x=df.index, y=col,
        title=f"{title} — Anomalies in {col}",
        template="plotly_dark",
        opacity=0.5,
    )
    anomaly_indices = [a.get("index", 0) for a in anomalies if "index" in a and isinstance(a.get("index"), int)]
    if anomaly_indices:
        valid_idx = [i for i in anomaly_indices if i < len(df)]
        if valid_idx:
            anomaly_df = df.iloc[valid_idx]
            fig.add_scatter(
                x=list(anomaly_df.index),
                y=list(anomaly_df[col]),
                mode="markers",
                marker=dict(color="red", size=10, symbol="x"),
                name="Anomaly",
            )
    return _serialize_fig(fig)
