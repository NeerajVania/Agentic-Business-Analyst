"""
backend/models/database.py
===========================
SQLAlchemy ORM models for persisting sessions, datasets, analyses, and reports.

Used by database/session.py for table creation and by routes_auth.py
for user management. The in-memory dataset registry (_datasets dict in
routes_upload.py) is separate from these persistent models — in a
production system you would sync uploaded datasets to the Dataset table.
"""

from datetime import datetime

from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Session(Base):
    """Conversation / analysis session."""
    __tablename__ = "sessions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    user_id = Column(String(255), nullable=True)
    metadata = Column(JSONB, default={})

    datasets  = relationship("Dataset",  back_populates="session", cascade="all, delete-orphan")
    analyses  = relationship("Analysis", back_populates="session", cascade="all, delete-orphan")
    reports   = relationship("Report",   back_populates="session", cascade="all, delete-orphan")


class Dataset(Base):
    """Uploaded dataset metadata (mirrors UploadResponse schema)."""
    __tablename__ = "datasets"

    id         = Column(PG_UUID(as_uuid=True), primary_key=True)
    session_id = Column(PG_UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    filename   = Column(String(255), nullable=False)
    rows       = Column(Integer, nullable=True)
    columns    = Column(Integer, nullable=True)
    schema     = Column(JSONB, default={})
    uploaded_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    session = relationship("Session", back_populates="datasets")


class Analysis(Base):
    """Persisted analysis result (mirrors AnalysisResponse fields)."""
    __tablename__ = "analyses"

    id             = Column(PG_UUID(as_uuid=True), primary_key=True)
    session_id     = Column(PG_UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    query          = Column(Text, nullable=False)
    execution_plan = Column(JSONB, default=[])
    insights       = Column(JSONB, default=[])
    recommendations = Column(JSONB, default=[])
    kpi_summary    = Column(JSONB, default={})
    anomaly_count  = Column(Integer, default=0)
    report_path    = Column(String(512), nullable=True)
    processing_sec = Column(Float, nullable=True)
    created_at     = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    session = relationship("Session", back_populates="analyses")
    reports = relationship("Report",  back_populates="analysis", cascade="all, delete-orphan")


class Report(Base):
    """Generated report record (html / markdown / pdf)."""
    __tablename__ = "reports"

    id          = Column(PG_UUID(as_uuid=True), primary_key=True)
    session_id  = Column(PG_UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    analysis_id = Column(PG_UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=True)
    format      = Column(String(50), nullable=False)   # html | markdown | pdf
    file_path   = Column(String(512), nullable=False)
    created_at  = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    session  = relationship("Session",  back_populates="reports")
    analysis = relationship("Analysis", back_populates="reports")