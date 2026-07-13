"""
analytics/statistical_analysis.py
===================================
Reusable statistical helpers used by the Data Analysis Agent and analytics layer.
"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd
from scipy import stats


def descriptive_stats(df: pd.DataFrame) -> Dict[str, Any]:
    """Full descriptive statistics for all numeric columns."""
    numeric = df.select_dtypes(include=[np.number])
    if numeric.empty:
        return {}

    desc = numeric.describe().to_dict()
    desc["variance"] = numeric.var().round(4).to_dict()
    desc["skewness"] = numeric.skew().round(4).to_dict()
    desc["kurtosis"] = numeric.kurtosis().round(4).to_dict()
    return desc


def correlation_matrix(df: pd.DataFrame) -> Dict[str, Any]:
    """Return Pearson correlation matrix for numeric columns."""
    numeric = df.select_dtypes(include=[np.number])
    if numeric.shape[1] < 2:
        return {}
    return numeric.corr().round(4).to_dict()


def normality_tests(df: pd.DataFrame, max_cols: int = 10) -> Dict[str, Dict]:
    """Run Shapiro-Wilk normality test on numeric columns."""
    results = {}
    numeric_cols = df.select_dtypes(include=[np.number]).columns[:max_cols]

    for col in numeric_cols:
        sample = df[col].dropna().sample(min(100, df[col].dropna().shape[0]), random_state=42)
        if len(sample) < 3:
            continue
        stat, p = stats.shapiro(sample)
        results[col] = {
            "statistic": round(float(stat), 4),
            "p_value": round(float(p), 4),
            "is_normal": bool(p > 0.05),
        }
    return results


def groupby_aggregation(
    df: pd.DataFrame,
    group_col: str,
    agg_col: str,
    agg_func: str = "sum",
) -> pd.DataFrame:
    """Generic groupby aggregation."""
    return df.groupby(group_col)[agg_col].agg(agg_func).reset_index()


def missing_value_report(df: pd.DataFrame) -> Dict[str, Any]:
    """Return missing value counts and percentages."""
    total = len(df)
    missing = df.isnull().sum()
    pct = (missing / max(total, 1) * 100).round(2)
    return {
        "counts": missing.to_dict(),
        "percentages": pct.to_dict(),
        "total_rows": total,
        "columns_with_missing": missing[missing > 0].index.tolist(),
    }