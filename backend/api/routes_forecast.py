"""
backend/api/routes_forecast.py
================================
Time-series forecasting endpoint.

  POST /forecast

Frontend consumer
-----------------
  07_forecast.py  →  POST /forecast
    Payload:  {
                dataset_id, date_column, target_column,
                periods, method ("prophet"|"arima"), session_id
              }
    Expects:  ForecastResponse:
                {
                  session_id, target_column, method,
                  forecast: list[dict],   ← rendered as pd.DataFrame + download CSV
                  chart: dict|None,       ← Plotly JSON dict → go.Figure(chart)
                  summary: str            ← shown in "Forecast Summary" card
                }

    Frontend also reads:
      • result["model_metrics"]  (optional) → diagnostics tab key/value grid
      • result["errors"]         (optional) → pipeline warnings expander

Schema keys expected from 07_forecast.py
-----------------------------------------
  schema["columns"]         — all column names
  schema["date_columns"]    — pre-detected date cols (fallback: heuristic filter)
  schema["numeric_columns"] — pre-detected numeric cols

  Ensure analytics/data_processor.load_dataset() populates these keys.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from loguru import logger

from backend.api.routes_upload import get_dataset_registry
from backend.models.schemas import ForecastRequest, ForecastResponse
from analytics.forecasting import run_forecast

router = APIRouter()


@router.post("", response_model=ForecastResponse)
async def forecast(request: ForecastRequest) -> ForecastResponse:
    """
    Run Prophet or ARIMA forecasting on an uploaded dataset column.

    Validates that the dataset, date column, and target column all exist
    before passing the DataFrame to analytics/forecasting.py.
    """
    registry = get_dataset_registry()

    if request.dataset_id not in registry:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found. Upload it first via POST /upload/multi.",
        )

    meta = registry[request.dataset_id]
    df = meta["df"]

    if request.target_column not in df.columns:
        raise HTTPException(
            status_code=422,
            detail=f"Column '{request.target_column}' not found in dataset.",
        )
    if request.date_column not in df.columns:
        raise HTTPException(
            status_code=422,
            detail=f"Date column '{request.date_column}' not found in dataset.",
        )

    try:
        result = run_forecast(
            df=df,
            date_col=request.date_column,
            target_col=request.target_column,
            periods=request.periods,
            method=request.method,
        )
        logger.info(
            "Forecast complete: method={} target={} periods={}",
            request.method, request.target_column, request.periods,
        )
        return ForecastResponse(
            session_id=request.session_id,
            target_column=request.target_column,
            method=request.method,
            forecast=result["forecast"],        # list[dict] with "ds"/"yhat"/CI keys
            chart=result.get("chart"),          # Plotly JSON dict or None
            summary=result.get("summary", ""),
            model_metrics=result.get("model_metrics"),
            errors=result.get("errors", []),
        )
    except Exception as exc:
        logger.error("Forecast failed: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc))