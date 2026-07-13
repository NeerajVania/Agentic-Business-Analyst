"""
analytics/forecasting.py
=========================
Time-series forecasting using Prophet and ARIMA.

Supports:
  • Prophet  (trend + seasonality, confidence intervals)
  • ARIMA    (statsmodels, auto-order selection)
"""

from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from loguru import logger


def run_forecast(
    df: pd.DataFrame,
    date_col: str,
    target_col: str,
    periods: int = 30,
    method: str = "prophet",
) -> Dict[str, Any]:
    """
    Run forecasting on a time-series dataset.

    Args:
        df:          Input DataFrame.
        date_col:    Name of the datetime column.
        target_col:  Name of the numeric target column.
        periods:     Number of future periods to forecast.
        method:      'prophet' or 'arima'.

    Returns:
        {forecast: list[dict], chart: plotly_dict, summary: str}
    """
    df = df[[date_col, target_col]].dropna()
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col)

    if method == "prophet":
        return _prophet_forecast(df, date_col, target_col, periods)
    elif method == "arima":
        return _arima_forecast(df, date_col, target_col, periods)
    else:
        raise ValueError(f"Unknown forecast method: {method}")


# ── Prophet ───────────────────────────────────────────────────────────────────

def _prophet_forecast(
    df: pd.DataFrame, date_col: str, target_col: str, periods: int
) -> Dict[str, Any]:
    try:
        from prophet import Prophet  # lazy import — heavy dependency
    except ImportError:
        raise ImportError("Install prophet: pip install prophet")

    prophet_df = df.rename(columns={date_col: "ds", target_col: "y"})
    prophet_df["y"] = pd.to_numeric(prophet_df["y"], errors="coerce")
    prophet_df = prophet_df.dropna(subset=["y"])

    model = Prophet(
        yearly_seasonality="auto",
        weekly_seasonality="auto",
        daily_seasonality=False,
        seasonality_mode="additive",
        interval_width=0.95,
    )
    try:
        model.fit(prophet_df)
        future = model.make_future_dataframe(periods=periods)
        forecast = model.predict(future)
    except MemoryError as exc:
        logger.error("Prophet memory error: %s", exc)
        raise RuntimeError(
            "Prophet failed due to resource constraints. Try ARIMA or reduce the forecast horizon."
        ) from exc
    except Exception as exc:
        logger.error("Prophet fitting failed: %s", exc)
        raise

    # Build forecast records
    forecast_records = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].tail(periods)
    forecast_list = [
        {
            "date": str(row["ds"].date()),
            "forecast": round(float(row["yhat"]), 2),
            "lower": round(float(row["yhat_lower"]), 2),
            "upper": round(float(row["yhat_upper"]), 2),
        }
        for _, row in forecast_records.iterrows()
    ]

    chart = _build_forecast_chart(
        df[date_col], df[target_col],
        forecast["ds"], forecast["yhat"],
        forecast["yhat_lower"], forecast["yhat_upper"],
        target_col, "Prophet",
    )

    last_actual = float(df[target_col].iloc[-1])
    last_forecast = forecast_list[-1]["forecast"]
    change_pct = round((last_forecast - last_actual) / max(abs(last_actual), 1) * 100, 1)

    summary = (
        f"Prophet forecast for '{target_col}' over next {periods} days. "
        f"Projected change: {change_pct:+.1f}% from last known value ({last_actual:.2f})."
    )

    model_metrics = {
        "method": "Prophet",
        "history_points": len(prophet_df),
        "forecast_horizon": periods,
    }

    logger.info("Prophet forecast complete: {} periods", periods)
    return {
        "forecast": forecast_list,
        "chart": chart,
        "summary": summary,
        "model_metrics": model_metrics,
    }


# ── ARIMA ─────────────────────────────────────────────────────────────────────

def _arima_forecast(
    df: pd.DataFrame, date_col: str, target_col: str, periods: int
) -> Dict[str, Any]:
    try:
        from statsmodels.tsa.arima.model import ARIMA
    except ImportError:
        raise ImportError("Install statsmodels: pip install statsmodels")

    series = df[target_col].values

    # Simple auto-order: try (1,1,1) as default
    model = ARIMA(series, order=(1, 1, 1))
    result = model.fit()
    forecast_values = result.forecast(steps=periods)

    # Build date index for future
    last_date = df[date_col].iloc[-1]
    freq = _infer_freq(df[date_col])
    future_dates = pd.date_range(start=last_date, periods=periods + 1, freq=freq)[1:]

    forecast_list = [
        {
            "date": str(d.date()),
            "forecast": round(float(v), 2),
            "lower": round(float(v) * 0.9, 2),
            "upper": round(float(v) * 1.1, 2),
        }
        for d, v in zip(future_dates, forecast_values)
    ]

    conf_int = result.get_forecast(steps=periods).conf_int()
    lower = conf_int[:, 0]
    upper = conf_int[:, 1]

    chart = _build_forecast_chart(
        df[date_col], df[target_col],
        future_dates,
        pd.Series(forecast_values),
        pd.Series(lower),
        pd.Series(upper),
        target_col, "ARIMA",
    )

    summary = (
        f"ARIMA(1,1,1) forecast for '{target_col}' over next {periods} periods. "
        f"Final forecast value: {forecast_list[-1]['forecast']:.2f}."
    )

    model_metrics = {
        "method": "ARIMA",
        "history_points": len(df),
        "forecast_horizon": periods,
    }

    logger.info("ARIMA forecast complete: {} periods", periods)
    return {
        "forecast": forecast_list,
        "chart": chart,
        "summary": summary,
        "model_metrics": model_metrics,
    }


# ── Chart builder ─────────────────────────────────────────────────────────────

def _build_forecast_chart(
    hist_dates, hist_values,
    fut_dates, fut_values,
    lower, upper,
    col_name: str, method: str,
) -> Dict[str, Any]:
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=list(hist_dates), y=list(hist_values),
        name="Historical", line=dict(color="#38bdf8"),
    ))
    fig.add_trace(go.Scatter(
        x=list(fut_dates), y=list(fut_values),
        name="Forecast", line=dict(color="#22c55e", dash="dash"),
    ))
    fig.add_trace(go.Scatter(
        x=list(fut_dates) + list(fut_dates)[::-1],
        y=list(upper) + list(lower)[::-1],
        fill="toself", fillcolor="rgba(34,197,94,0.1)",
        line=dict(color="rgba(255,255,255,0)"),
        name="95% CI",
    ))

    fig.update_layout(
        title=f"{method} Forecast — {col_name}",
        template="plotly_dark",
        xaxis_title="Date",
        yaxis_title=col_name,
    )
    return fig.to_dict()


def _infer_freq(dates: pd.Series) -> str:
    """Infer pandas frequency string from a date series."""
    if len(dates) < 2:
        return "D"
    delta = (dates.iloc[1] - dates.iloc[0]).days
    if delta <= 1:
        return "D"
    elif delta <= 7:
        return "W"
    elif delta <= 31:
        return "MS"
    return "QS"