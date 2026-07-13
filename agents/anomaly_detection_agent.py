"""
agents/anomaly_detection_agent.py
==================================
Anomaly Detection Agent — ML-based outlier detection.

Techniques:
  • Isolation Forest
  • Z-score (|z| > 3)
  • IQR (1.5 × IQR rule)

Each detected anomaly includes:
  • Row index
  • Column affected
  • Value
  • Detection method
  • Severity (low / medium / high)

Performance note: large datasets are sampled to MAX_SAMPLE rows before
detection.  Total anomalies are capped at MAX_ANOMALIES to keep the
state payload manageable.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from loguru import logger

from agents.state import AgentState

MAX_SAMPLE = 10_000
MAX_ANOMALIES = 150


# ── Agent node ────────────────────────────────────────────────────────────────

def anomaly_detection_agent(state: AgentState) -> AgentState:
    """
    LangGraph node: Anomaly Detection Agent.
    Reads `dataframes`.
    Writes `anomalies`, `anomaly_explanations`.
    """
    logger.info("[AnomalyDetectionAgent] Detecting anomalies")

    dataframes: dict[str, pd.DataFrame] = state.get("dataframes", {})
    all_anomalies: list[dict] = []
    all_explanations: list[str] = []

    for name, df in dataframes.items():
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if not numeric_cols:
            continue

        # Sample large datasets for performance
        if len(df) > MAX_SAMPLE:
            logger.info(
                "[AnomalyDetectionAgent] Sampling {} → {} rows for '{}'",
                len(df), MAX_SAMPLE, name,
            )
            df_sample = df.sample(MAX_SAMPLE, random_state=42).reset_index(drop=True)
        else:
            df_sample = df.copy()

        z_anomalies = _zscore_detection(df_sample, numeric_cols, name)
        all_anomalies.extend(z_anomalies)

        iqr_anomalies = _iqr_detection(df_sample, numeric_cols, name)
        all_anomalies.extend(iqr_anomalies)

        if len(numeric_cols) >= 2:
            iso_anomalies = _isolation_forest_detection(df_sample, numeric_cols, name)
            all_anomalies.extend(iso_anomalies)

        # Cap total anomalies early to avoid huge payloads
        if len(all_anomalies) >= MAX_ANOMALIES:
            all_anomalies = all_anomalies[:MAX_ANOMALIES]
            logger.info("[AnomalyDetectionAgent] Capped anomalies at {}", MAX_ANOMALIES)
            break

    # Generate explanations AFTER the loop so the break doesn't skip them
    for name in dataframes:
        explanations = _generate_explanations(all_anomalies, name)
        all_explanations.extend(explanations)

    # Final cap
    all_anomalies = all_anomalies[:MAX_ANOMALIES]
    all_explanations = all_explanations[:MAX_ANOMALIES]

    logger.info("[AnomalyDetectionAgent] Found {} anomalies", len(all_anomalies))

    return {
        "anomalies": all_anomalies,
        "anomaly_explanations": all_explanations,
    }


# ── Detection methods ─────────────────────────────────────────────────────────

def _zscore_detection(
    df: pd.DataFrame, cols: list[str], dataset: str
) -> list[dict]:
    """Flag rows where |z-score| > 3 in any numeric column."""
    anomalies = []
    threshold = 3.0

    for col in cols:
        series = df[col].dropna()
        if len(series) < 10:
            continue
        z_scores = np.abs((series - series.mean()) / series.std())
        outlier_idx = z_scores[z_scores > threshold].index

        for idx in outlier_idx[:30]:  # cap per column
            z = float(z_scores.loc[idx])
            anomalies.append({
                "dataset": dataset,
                "index": int(idx),
                "column": col,
                "value": float(df.loc[idx, col]),
                "method": "z-score",
                "score": round(z, 3),
                "severity": _severity_from_zscore(z),
            })

    return anomalies


def _iqr_detection(
    df: pd.DataFrame, cols: list[str], dataset: str
) -> list[dict]:
    """Flag rows outside [Q1 - 1.5*IQR, Q3 + 1.5*IQR]."""
    anomalies = []

    for col in cols:
        series = df[col].dropna()
        if len(series) < 10:
            continue
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        mask = (df[col] < lower) | (df[col] > upper)
        col_anomalies = []
        for idx in df[mask].index:
            val = float(df.loc[idx, col])
            col_anomalies.append({
                "dataset": dataset,
                "index": int(idx),
                "column": col,
                "value": val,
                "method": "iqr",
                "bounds": {"lower": round(float(lower), 3), "upper": round(float(upper), 3)},
                "severity": "medium" if abs(val - float(series.mean())) / float(series.std()) < 4 else "high",
            })
        anomalies.extend(col_anomalies[:30])  # cap per column

    return anomalies


def _isolation_forest_detection(
    df: pd.DataFrame, cols: list[str], dataset: str, contamination: float = 0.05
) -> list[dict]:
    """Multivariate anomaly detection using Isolation Forest."""
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    anomalies = []

    X = df[cols].dropna()
    if len(X) < 20:
        return anomalies

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    clf = IsolationForest(contamination=contamination, random_state=42, n_estimators=100)
    preds = clf.fit_predict(X_scaled)
    scores = clf.score_samples(X_scaled)

    outlier_mask = preds == -1
    count = 0
    for i, (idx, is_outlier) in enumerate(zip(X.index, outlier_mask)):
        if is_outlier and count < 50:  # cap isolation forest anomalies
            anomalies.append({
                "dataset": dataset,
                "index": int(idx),
                "column": "multivariate",
                "value": {col: float(df.loc[idx, col]) for col in cols},
                "method": "isolation_forest",
                "score": round(float(scores[i]), 4),
                "severity": "high" if scores[i] < -0.15 else "medium",
            })
            count += 1

    return anomalies


# ── Explanation generator ─────────────────────────────────────────────────────

def _generate_explanations(anomalies: list[dict], dataset: str) -> list[str]:
    """Generate human-readable anomaly explanations."""
    explanations = []
    for a in anomalies:
        if a["dataset"] != dataset:
            continue
        method = a["method"]
        col = a["column"]
        val = a["value"]
        sev = a.get("severity", "medium")
        idx = a["index"]

        if method == "z-score":
            z = a["score"]
            if isinstance(val, float):
                explanations.append(
                    f"[{sev.upper()}] Row {idx} in `{dataset}`: `{col}` = {val:.2f} "
                    f"is {z:.1f} standard deviations from the mean (z-score anomaly)."
                )
        elif method == "iqr":
            bounds = a.get("bounds", {})
            if isinstance(val, float):
                explanations.append(
                    f"[{sev.upper()}] Row {idx} in `{dataset}`: `{col}` = {val:.2f} "
                    f"falls outside expected range [{bounds.get('lower')}, {bounds.get('upper')}] (IQR anomaly)."
                )
        elif method == "isolation_forest":
            score = a["score"]
            explanations.append(
                f"[{sev.upper()}] Row {idx} in `{dataset}` is a multivariate outlier "
                f"(Isolation Forest score: {score:.3f})."
            )

    return explanations


def _severity_from_zscore(z: float) -> str:
    if z > 5:
        return "high"
    elif z > 4:
        return "medium"
    return "low"
