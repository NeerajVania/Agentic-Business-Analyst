"""
agents/data_analysis_agent.py
==============================
Data Analysis Agent — pure Python (Pandas + NumPy + SciPy + DuckDB).

Responsibilities:
  • Descriptive statistics (mean, median, std, variance, skewness, kurtosis)
  • Correlation matrix + top correlated pairs
  • Shapiro-Wilk normality tests
  • Distribution analysis for categorical columns
  • Groupby aggregations for KPI extraction
  • Missing-value analysis
  • Cross-dataset join suggestion via DuckDB
  • dashboard_config generation for Streamlit frontend
"""

from __future__ import annotations

import math
from typing import Any

import duckdb
import numpy as np
import pandas as pd
from scipy import stats
from loguru import logger

from agents.state import AgentState


# ── Agent node ────────────────────────────────────────────────────────────────

def data_analysis_agent(state: AgentState) -> AgentState:
    """
    LangGraph node: Data Analysis Agent.

    Reads:  dataframes, dataset_schemas
    Writes: analysis_results, kpi_summary, dashboard_config
    """
    logger.info("[DataAnalysisAgent] Starting analysis")

    dataframes: dict[str, pd.DataFrame] = state.get("dataframes", {})
    if not dataframes:
        return {
            "errors": state.get("errors", []) + ["DataAnalysisAgent: No dataframes found"],
        }

    analysis_results: dict[str, Any] = {}
    kpi_summary: dict[str, Any] = {}

    for name, df in dataframes.items():
        logger.info("[DataAnalysisAgent] Analysing '{}'  ({} rows × {} cols)", name, *df.shape)
        try:
            analysis_results[name] = _sanitize(_analyse_dataframe(df, name))
            kpi_summary[name] = _extract_kpis(df)
        except Exception as exc:
            logger.error("[DataAnalysisAgent] Failed on '{}': {}", name, exc)
            analysis_results[name] = {"error": str(exc)}

    # Cross-dataset analysis when multiple datasets exist
    if len(dataframes) > 1:
        try:
            analysis_results["cross_dataset"] = _sanitize(_cross_dataset_analysis(dataframes))
        except Exception as exc:
            logger.warning("[DataAnalysisAgent] Cross-dataset analysis failed: {}", exc)

    dashboard_config = _build_dashboard_config(dataframes, kpi_summary, analysis_results)

    return {
        "analysis_results": analysis_results,
        "kpi_summary": kpi_summary,
        "dashboard_config": dashboard_config,
    }


# ── Analysis helpers ──────────────────────────────────────────────────────────

def _analyse_dataframe(df: pd.DataFrame, name: str) -> dict[str, Any]:
    """Run comprehensive analysis on a single dataframe."""
    result: dict[str, Any] = {"dataset": name}

    result["shape"] = {"rows": int(len(df)), "columns": int(len(df.columns))}
    result["dtypes"] = {str(k): str(v) for k, v in df.dtypes.items()}
    result["missing_values"] = {str(k): int(v) for k, v in df.isnull().sum().items()}
    result["missing_pct"] = {
        str(k): round(float(v), 2)
        for k, v in (df.isnull().sum() / max(len(df), 1) * 100).items()
    }

    # ── Numeric columns ──────────────────────────────────────────────────
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if numeric_cols:
        desc = df[numeric_cols].describe()
        result["descriptive_stats"] = {
            col: {stat: _safe_float(val) for stat, val in col_stats.items()}
            for col, col_stats in desc.to_dict().items()
        }
        result["variance"] = {str(k): _safe_float(v) for k, v in df[numeric_cols].var().items()}
        result["skewness"] = {str(k): _safe_float(v) for k, v in df[numeric_cols].skew().items()}
        result["kurtosis"] = {str(k): _safe_float(v) for k, v in df[numeric_cols].kurtosis().items()}

        if len(numeric_cols) > 1:
            corr = df[numeric_cols].corr().round(4)
            result["correlation_matrix"] = {
                str(col_a): {str(col_b): _safe_float(val) for col_b, val in row.items()}
                for col_a, row in corr.to_dict().items()
            }
            result["top_correlations"] = _top_correlations(df[numeric_cols])

        normality: dict[str, dict] = {}
        for col in numeric_cols[:5]:
            series = df[col].dropna()
            if len(series) < 3:
                continue
            sample = series.sample(min(500, len(series)), random_state=42)
            stat, p = stats.shapiro(sample)
            normality[col] = {
                "statistic": round(float(stat), 4),
                "p_value": round(float(p), 4),
                "is_normal": bool(p > 0.05),
            }
        result["normality_tests"] = normality

    # ── Categorical columns ──────────────────────────────────────────────
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    if cat_cols:
        cat_stats: dict[str, Any] = {}
        for col in cat_cols[:10]:
            vc = df[col].value_counts()
            mode_val = df[col].mode()
            cat_stats[col] = {
                "unique_values": int(df[col].nunique()),
                "top_5": {str(k): int(v) for k, v in vc.head(5).items()},
                "mode": str(mode_val.iloc[0]) if not mode_val.empty else None,
                "null_count": int(df[col].isnull().sum()),
            }
        result["categorical_stats"] = cat_stats

    # ── Date/time columns ────────────────────────────────────────────────
    date_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()
    if date_cols:
        date_stats: dict[str, Any] = {}
        for col in date_cols:
            min_d, max_d = df[col].min(), df[col].max()
            date_stats[col] = {
                "min": str(min_d),
                "max": str(max_d),
                "range_days": int((max_d - min_d).days) if pd.notna(min_d) and pd.notna(max_d) else None,
            }
        result["date_stats"] = date_stats

    return result


def _safe_float(val: Any) -> Any:
    """Convert a value to Python float, replacing NaN/Inf with None."""
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 6)
    except (TypeError, ValueError):
        return None


def _extract_kpis(df: pd.DataFrame) -> dict[str, Any]:
    """
    Extract numeric columns that are likely KPIs based on column name keywords.
    """
    kpis: dict[str, Any] = {}
    kpi_keywords = [
        "revenue", "sales", "profit", "amount", "price",
        "count", "qty", "quantity", "cost", "income",
        "spend", "budget", "margin", "value", "total",
    ]

    for col in df.select_dtypes(include=[np.number]).columns:
        if any(kw in col.lower() for kw in kpi_keywords):
            series = df[col].dropna()
            kpis[col] = {
                "total": round(float(series.sum()), 2),
                "mean":  round(float(series.mean()), 2),
                "max":   round(float(series.max()), 2),
                "min":   round(float(series.min()), 2),
                "median": round(float(series.median()), 2),
                "std":   round(float(series.std()), 2),
            }
    return kpis


def _top_correlations(
    df_numeric: pd.DataFrame,
    top_n: int = 10,
    min_abs_corr: float = 0.3,
) -> list[dict]:
    """
    Return top-N correlation pairs (excluding self-correlations and weak pairs).
    All values converted to Python native types.
    """
    corr = df_numeric.corr().abs()
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
    pairs = (
        upper.stack()
        .reset_index()
        .rename(columns={"level_0": "col_a", "level_1": "col_b", 0: "correlation"})
    )
    pairs = (
        pairs[pairs["correlation"] >= min_abs_corr]
        .sort_values("correlation", ascending=False)
        .head(top_n)
    )
    # Explicitly convert to Python native types
    result = []
    for _, row in pairs.iterrows():
        result.append({
            "col_a": str(row["col_a"]),
            "col_b": str(row["col_b"]),
            "correlation": round(float(row["correlation"]), 4),
        })
    return result


def _cross_dataset_analysis(dataframes: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """
    Use DuckDB to detect common columns across datasets and validate joins.
    """
    result: dict[str, Any] = {}
    con = duckdb.connect()

    safe_names: dict[str, str] = {}
    for name, df in dataframes.items():
        safe = name.replace("-", "_").replace(" ", "_")
        con.register(safe, df)
        safe_names[name] = safe

    all_columns = {
        name: set(df.columns.str.lower())
        for name, df in dataframes.items()
    }

    names = list(all_columns.keys())
    join_suggestions = []

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            common = all_columns[names[i]] & all_columns[names[j]]
            if not common:
                continue

            join_col = next(iter(common))
            a_safe = safe_names[names[i]]
            b_safe = safe_names[names[j]]

            probe_count = None
            try:
                probe_sql = (
                    f'SELECT COUNT(*) AS n FROM "{a_safe}" a '
                    f'JOIN "{b_safe}" b ON a."{join_col}" = b."{join_col}"'
                )
                probe_count = int(con.execute(probe_sql).fetchone()[0])
            except Exception as exc:
                logger.debug("[DataAnalysisAgent] Join probe failed: {}", exc)

            join_suggestions.append({
                "dataset_a": names[i],
                "dataset_b": names[j],
                "common_columns": sorted(common),
                "suggested_join": f"JOIN ON {', '.join(sorted(common))}",
                "join_row_count": probe_count,
                "confidence": (
                    "high" if any(k in common for k in ("id", "key", "code"))
                    else "medium"
                ),
            })

    result["join_suggestions"] = join_suggestions
    con.close()
    return result


def _build_dashboard_config(
    dataframes: dict[str, pd.DataFrame],
    kpi_summary: dict[str, Any],
    analysis_results: dict[str, Any],
) -> dict[str, Any]:
    """Build a Streamlit dashboard configuration spec."""
    kpi_cards = []
    for dataset, kpis in kpi_summary.items():
        for metric, values in kpis.items():
            kpi_cards.append({
                "label": f"{metric} ({dataset})",
                "value": values.get("total", 0),
                "delta": None,
            })

    filter_cols: list[dict] = []
    for name, df in dataframes.items():
        for col in df.select_dtypes(include=["object", "category"]).columns:
            if df[col].nunique() <= 30:
                filter_cols.append({"dataset": name, "column": col})

    chart_order = ["bar", "line", "heatmap", "histogram", "box", "scatter"]

    return {
        "kpi_cards": kpi_cards,
        "filter_columns": filter_cols,
        "chart_order": chart_order,
        "dataset_count": int(len(dataframes)),
        "layout": "wide",
    }


def _sanitize(val: Any) -> Any:
    """Recursively convert numpy/pandas types to JSON-serialisable Python types."""
    if val is None:
        return None
    if isinstance(val, dict):
        return {str(k): _sanitize(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_sanitize(v) for v in val]
    if isinstance(val, np.integer):
        return int(val)
    if isinstance(val, np.floating):
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(val, np.bool_):
        return bool(val)
    if isinstance(val, np.ndarray):
        return _sanitize(val.tolist())
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    return val
