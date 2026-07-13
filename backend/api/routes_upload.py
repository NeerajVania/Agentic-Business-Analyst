"""
backend/api/routes_upload.py
=============================
Dataset upload endpoints.

  POST   /upload          — single file upload
  POST   /upload/multi    — multiple files (used by frontend 01_upload.py)
  GET    /upload/datasets — list loaded datasets
  DELETE /upload/{id}     — remove a dataset

Frontend consumers
------------------
  01_upload.py  →  POST /upload/multi
                   Sends List[UploadFile] as multipart "files"
                   Expects MultiUploadResponse:
                     { datasets: [UploadResponse], join_suggestions: [...] }

  07_forecast.py reads schema.columns, schema.date_columns, schema.numeric_columns
                 from the UploadResponse stored in st.session_state.uploaded_datasets.
                 Make sure load_dataset() populates those keys in the schema dict.
"""

from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile
from loguru import logger

from analytics.data_processor import load_dataset, suggest_joins
from backend.models.schemas import MultiUploadResponse, UploadResponse
from config.settings import get_settings

settings = get_settings()

router = APIRouter()

# In-memory dataset registry — keyed by dataset_id (UUID string).
# Each entry: {"df": pd.DataFrame, "schema": dict, "filename": str, "rows": int, "columns": int}
# Replace with Redis / DB persistence in production.
_datasets: dict[str, dict] = {}


def get_dataset_registry() -> dict[str, dict]:
    """Return the global in-memory dataset registry.

    Imported by routes_analyze.py and routes_forecast.py to access uploaded DataFrames.
    """
    return _datasets


# ── Single upload ─────────────────────────────────────────────────────────────

@router.post("", response_model=UploadResponse)
async def upload_single(file: UploadFile = File(...)) -> UploadResponse:
    """Upload a single CSV / Excel / JSON dataset."""
    _validate_extension(file.filename)
    try:
        content = await file.read()
        _validate_file_size(content, file.filename)
        df, schema = load_dataset(content, file.filename)

        dataset_id = str(uuid.uuid4())
        _datasets[dataset_id] = {
            "df": df,
            "schema": schema,
            "filename": file.filename,
            "rows": schema["rows"],
            "columns": schema["columns_count"],
        }

        logger.info("Uploaded '{}' → id={}", file.filename, dataset_id)
        return UploadResponse(
            dataset_id=dataset_id,
            filename=file.filename,
            rows=schema["rows"],
            columns=schema["columns_count"],
            schema=schema,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Upload failed for '{}': {}", file.filename, exc)
        raise HTTPException(status_code=422, detail=str(exc))


# ── Multi-file upload ─────────────────────────────────────────────────────────

@router.post("/multi", response_model=MultiUploadResponse)
async def upload_multiple(files: List[UploadFile] = File(...)) -> MultiUploadResponse:
    """
    Upload multiple datasets simultaneously.

    Called by frontend/pages/01_upload.py:
        requests.post(f"{API_BASE}/upload/multi", files=files)

    Returns join suggestions so the frontend can display cross-dataset
    relationship hints.
    """
    responses: List[UploadResponse] = []
    schemas: dict[str, dict] = {}

    for file in files:
        try:
            _validate_extension(file.filename)
            content = await file.read()
            _validate_file_size(content, file.filename)
            df, schema = load_dataset(content, file.filename)

            dataset_id = str(uuid.uuid4())
            _datasets[dataset_id] = {
                "df": df,
                "schema": schema,
                "filename": file.filename,
                "rows": schema["rows"],
                "columns": schema["columns_count"],
            }

            name = file.filename.rsplit(".", 1)[0]
            schemas[name] = schema

            responses.append(UploadResponse(
                dataset_id=dataset_id,
                filename=file.filename,
                rows=schema["rows"],
                columns=schema["columns_count"],
                schema=schema,
            ))
            logger.info("Multi-upload: '{}' → id={}", file.filename, dataset_id)
        except Exception as exc:
            logger.warning("Skipping '{}' in multi-upload: {}", file.filename, exc)

    if not responses:
        raise HTTPException(status_code=422, detail="No files could be processed.")

    join_suggestions = suggest_joins(schemas)
    return MultiUploadResponse(datasets=responses, join_suggestions=join_suggestions)


# ── Dataset list ──────────────────────────────────────────────────────────────

@router.get("/datasets")
async def list_datasets() -> dict:
    """List all uploaded datasets (metadata only, no DataFrames)."""
    return {
        ds_id: {
            "filename": meta["filename"],
            "rows": meta["schema"]["rows"],
            "columns": meta["schema"]["columns_count"],
        }
        for ds_id, meta in _datasets.items()
    }


# ── Delete dataset ────────────────────────────────────────────────────────────

@router.delete("/{dataset_id}")
async def delete_dataset(dataset_id: str) -> dict:
    """Remove a dataset from the registry."""
    if dataset_id not in _datasets:
        raise HTTPException(status_code=404, detail="Dataset not found")
    del _datasets[dataset_id]
    logger.info("Deleted dataset id={}", dataset_id)
    return {"message": f"Dataset {dataset_id} deleted"}


# ── Helpers ───────────────────────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json"}


def _validate_extension(filename: str) -> None:
    ext = "." + filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext}'. Allowed: {ALLOWED_EXTENSIONS}",
        )


def _validate_file_size(content: bytes, filename: str) -> None:
    limit = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"File '{filename}' exceeds the {settings.max_upload_size_mb} MB limit.",
        )