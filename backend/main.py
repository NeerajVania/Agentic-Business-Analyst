"""
backend/main.py
================
FastAPI application entry point.
"""

from __future__ import annotations

import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from backend.api import (
    routes_analyze,
    routes_auth,
    routes_evaluation,
    routes_forecast,
    routes_chat,
    routes_rag,
    routes_report,
    routes_upload,
)
from backend.utils.security import get_current_active_user
from config.settings import get_settings
from database.session import get_db_mode, init_db
from memory.redis_memory import get_memory

settings = get_settings()
redis_store = get_memory()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Agentic Data Analyst API — env={}", settings.app_env)
    settings.ensure_directories()
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as exc:
        logger.warning("Database initialization skipped or failed: {}", exc)
    yield
    logger.info("Shutting down API")


app = FastAPI(
    title="Agentic Data Analyst",
    description="Autonomous Business Intelligence System powered by Mistral AI + LangGraph",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allows Streamlit frontend (default :8501) to call the API.
# Tighten allow_origins in production (e.g. ["http://localhost:8501"]).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(routes_auth.router, prefix="/auth", tags=["Authentication"])

protected_dependencies = [Depends(get_current_active_user)] if settings.require_auth else []

app.include_router(routes_upload.router,     prefix="/upload",          tags=["Upload"],      dependencies=protected_dependencies)
app.include_router(routes_analyze.router,    prefix="/analyze",         tags=["Analysis"],    dependencies=protected_dependencies)
app.include_router(routes_chat.router,       prefix="/chat",            tags=["Chat"],        dependencies=protected_dependencies)
app.include_router(routes_report.router,     prefix="/generate-report", tags=["Reports"],     dependencies=protected_dependencies)
app.include_router(routes_rag.router,        prefix="/rag",             tags=["RAG"],         dependencies=protected_dependencies)
app.include_router(routes_forecast.router,   prefix="/forecast",        tags=["Forecast"],    dependencies=protected_dependencies)
app.include_router(routes_evaluation.router, prefix="/evaluate",        tags=["Evaluation"],  dependencies=protected_dependencies)


@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "app": settings.app_name}


@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "healthy",
        "env": settings.app_env,
        "use_in_memory_fallback": settings.use_in_memory_fallback,
        "services": {
            "redis": "connected" if redis_store.available else "fallback",
            "database": get_db_mode(),
        },
    }