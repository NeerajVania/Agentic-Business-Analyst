"""
analytics/data_processor.py
=============================
Dataset ingestion, schema inference, type detection, and join suggestions.
"""

from __future__ import annotations

import io
import math
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from loguru import logger


# ── Public API ────────────────────────────────────────────────────────────────

def load_dataset(content: bytes, filename: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Load raw file bytes into a DataFrame and infer its schema.

    Supports: CSV, Excel (.xlsx/.xls), JSON

    Returns:
        (df, schema_dict)
    """
    ext = filename.rsplit(".", 1)[-1].lower()

    if ext == "csv":
        df = pd.read_csv(io.BytesIO(content))
    elif ext in ("xlsx", "xls"):
        df = pd.read_excel(io.BytesIO(content))
    elif ext == "json":
        df = pd.read_json(io.BytesIO(content))
    else:
        raise ValueError(f"Unsupported file extension: .{ext}")

    df = _clean_dataframe(df)
    schema = _infer_schema(df, filename)

    logger.info("Loaded '{}': {} rows × {} cols", filename, len(df), len(df.columns))
    return df, schema


def suggest_joins(schemas: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Identify potential join keys across multiple dataset schemas.

    Returns a list of join suggestions with common column names.
    """
    suggestions = []
    names = list(schemas.keys())

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            cols_a = set(c.lower() for c in schemas[names[i]].get("columns", []))
            cols_b = set(c.lower() for c in schemas[names[j]].get("columns", []))
            common = cols_a & cols_b

            if common:
                suggestions.append({
                    "dataset_a": names[i],
                    "dataset_b": names[j],
                    "common_columns": sorted(common),
                    "suggested_join": f"JOIN ON {', '.join(sorted(common))}",
                    "confidence": "high" if any(k in common for k in ("id", "key", "code")) else "medium",
                })

    return suggestions


# ── Internal helpers ──────────────────────────────────────────────────────────

def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise column names and attempt datetime parsing."""
    df.columns = [str(c).strip() for c in df.columns]

    for col in df.columns:
        if any(kw in col.lower() for kw in ("date", "time", "dt", "timestamp")):
            try:
                df[col] = pd.to_datetime(df[col], errors="coerce")
            except Exception:
                pass

    return df


def _infer_schema(df: pd.DataFrame, filename: str) -> Dict[str, Any]:
    """Build a schema dictionary from a DataFrame, with all values sanitized to Python native types."""
    dtypes = {str(k): str(v) for k, v in df.dtypes.items()}
    missing = {str(k): int(v) for k, v in df.isnull().sum().items()}
    missing_pct = {
        str(k): round(float(v), 2)
        for k, v in (df.isnull().sum() / max(len(df), 1) * 100).items()
    }

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    date_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()

    pk_candidates = [
        col for col in df.columns
        if df[col].nunique() == len(df) and "id" in col.lower()
    ]

    sample_records = _sanitize(df.head(3).to_dict(orient="records"))

    return {
        "filename": str(filename),
        "rows": int(len(df)),
        "columns_count": int(len(df.columns)),
        "columns": [str(c) for c in df.columns.tolist()],
        "dtypes": dtypes,
        "numeric_columns": [str(c) for c in numeric_cols],
        "categorical_columns": [str(c) for c in categorical_cols],
        "date_columns": [str(c) for c in date_cols],
        "missing_values": missing,
        "missing_pct": missing_pct,
        "primary_key_candidates": [str(c) for c in pk_candidates],
        "sample": sample_records,
    }


def _sanitize(val: Any) -> Any:
    """
    Recursively convert numpy/pandas types to JSON-serialisable Python types.
    Replaces NaN / Inf with None so they can be serialised to JSON.
    """
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
    # Handle pandas Timestamp / NaT
    if hasattr(val, "isoformat"):
        try:
            return val.isoformat()
        except Exception:
            return str(val)
    if hasattr(val, "_value") and val is pd.NaT:
        return None
    return val
