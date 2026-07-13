"""
database/session.py
====================
SQLAlchemy async session factory and ORM models.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import AsyncGenerator, Any

from loguru import logger
from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config.settings import get_settings

settings = get_settings()

_db_available = True


class NullResult:
    """Minimal result object for no-op DB fallback."""

    def scalars(self) -> "NullResult":
        return self

    def first(self) -> Any:
        return None

    def all(self) -> list[Any]:
        return []

    def one_or_none(self) -> Any:
        return None

    async def scalar(self) -> Any:
        return None

    async def scalar_one(self) -> Any:
        return None


class NullAsyncSession:
    """AsyncSession fallback that ignores writes and returns empty query results."""

    async def __aenter__(self) -> "NullAsyncSession":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def execute(self, *args: Any, **kwargs: Any) -> NullResult:
        return NullResult()

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    async def refresh(self, instance: Any, attribute_names: Any = None, with_for_update: Any = None) -> None:
        return None

    def add(self, instance: Any) -> None:
        return None

    def delete(self, instance: Any) -> None:
        return None

    async def close(self) -> None:
        return None


def is_db_available() -> bool:
    return _db_available and not settings.use_in_memory_fallback


def get_db_mode() -> str:
    if settings.use_in_memory_fallback or not _db_available:
        return "fallback"
    return "connected"

# ── Engine ────────────────────────────────────────────────────────────────────
engine = None
AsyncSessionLocal = None

if not settings.use_in_memory_fallback:
    try:
        engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            connect_args={},
        )
        AsyncSessionLocal = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    except Exception as exc:
        logger.warning("Could not create DB engine at startup: {}", exc)


# ── Dependency ────────────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if settings.use_in_memory_fallback or not _db_available or AsyncSessionLocal is None:
        logger.warning(
            "Database session fallback active — returning in-memory fallback session"
        )
        yield NullAsyncSession()
        return

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    global _db_available
    if settings.use_in_memory_fallback:
        _db_available = False
        logger.info(
            "USE_IN_MEMORY_FALLBACK=true — database persistence disabled and using in-memory fallback"
        )
        return

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        _db_available = True
    except Exception as exc:
        _db_available = False
        logger.warning(
            "Database initialization skipped or failed, metadata persistence disabled: {}",
            exc,
        )


# ── ORM Models ────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class SessionModel(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserModel(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(150), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="user", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(String, nullable=True)
    metadata_ = Column("metadata", JSONB, default=dict)


class DatasetModel(Base):
    __tablename__ = "datasets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), nullable=True)
    filename = Column(String, nullable=False)
    rows = Column(Integer)
    columns = Column(Integer)
    schema_ = Column("schema", JSONB, default=dict)
    uploaded_at = Column(DateTime, default=datetime.utcnow)


class AnalysisModel(Base):
    __tablename__ = "analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), nullable=True)
    query = Column(Text, nullable=False)
    execution_plan = Column(JSONB, default=list)
    insights = Column(JSONB, default=list)
    recommendations = Column(JSONB, default=list)
    kpi_summary = Column(JSONB, default=dict)
    anomaly_count = Column(Integer, default=0)
    report_path = Column(String, nullable=True)
    processing_sec = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)