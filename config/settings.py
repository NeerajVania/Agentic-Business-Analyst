"""
config/settings.py
==================
Centralised application settings using Pydantic BaseSettings.
All values are read from environment variables / .env file.
"""

import json
import os
from functools import lru_cache
from pathlib import Path
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _strip_ssl_params(url: str) -> str:
    """Remove SSL query params that asyncpg doesn't accept as URL params."""
    from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    # asyncpg handles SSL via connect_args, not URL params
    for key in ("sslmode", "ssl", "sslcert", "sslkey", "sslrootcert"):
        query.pop(key, None)
    new_query = urlencode({k: v[0] for k, v in query.items()})
    return urlunparse(parsed._replace(query=new_query))


def _build_async_db_url(url: str) -> str:
    """Convert a standard postgresql:// URL to postgresql+asyncpg:// for async use."""
    url = _strip_ssl_params(url)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def _build_sync_db_url(url: str) -> str:
    """Ensure sync URL uses plain postgresql:// driver."""
    url = _strip_ssl_params(url)
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────
    app_name: str = Field("Agentic Data Analyst", alias="APP_NAME")
    app_env: str = Field("development", alias="APP_ENV")
    debug: bool = Field(True, alias="DEBUG")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    use_in_memory_fallback: bool = Field(False, alias="USE_IN_MEMORY_FALLBACK")

    @field_validator("debug", mode="before")
    def parse_debug(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "y", "on", "dev", "development", "debug"}:
                return True
            if normalized in {"false", "0", "no", "n", "off", "prod", "production", "release"}:
                return False
        return value

    # ── Mistral AI ────────────────────────────────────────────
    mistral_api_key: str = Field("", alias="MISTRAL_API_KEY")
    mistral_model: str = Field("mistral-large-latest", alias="MISTRAL_MODEL")
    mistral_small_model: str = Field("mistral-small-latest", alias="MISTRAL_SMALL_MODEL")

    @field_validator("mistral_api_key", mode="before")
    def validate_mistral_api_key(cls, value):
        if not isinstance(value, str) or not value.strip():
            import warnings
            warnings.warn("MISTRAL_API_KEY is not set — AI features will be unavailable")
            return ""
        return value

    # ── HuggingFace ───────────────────────────────────────────
    huggingface_api_token: str = Field("", alias="HUGGINGFACE_API_TOKEN")
    embedding_model: str = Field("sentence-transformers/all-MiniLM-L6-v2", alias="EMBEDDING_MODEL")

    # ── LangSmith ─────────────────────────────────────────────
    langsmith_api_key: str = Field("", alias="LANGSMITH_API_KEY")
    langchain_tracing_v2: bool = Field(False, alias="LANGCHAIN_TRACING_V2")
    langchain_project: str = Field("agentic-data-analyst", alias="LANGCHAIN_PROJECT")

    # ── Database ──────────────────────────────────────────────
    # Raw URL from environment can be provided in standard or asyncpg format.
    database_url: str = Field(
        "postgresql+asyncpg://postgres:password@localhost:5432/agentdb",
        alias="DATABASE_URL",
    )
    database_sync_url: str = Field(
        "",
        alias="DATABASE_SYNC_URL",
    )

    @model_validator(mode="after")
    def fix_database_urls(self) -> "Settings":
        """Ensure async and sync DB URLs use the correct driver prefix."""
        raw = self.database_url
        self.database_url = _build_async_db_url(raw)
        if not self.database_sync_url:
            self.database_sync_url = _build_sync_db_url(raw)
        else:
            self.database_sync_url = _build_sync_db_url(self.database_sync_url)
        return self

    # ── Redis ─────────────────────────────────────────────────
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")

    # ── ChromaDB ─────────────────────────────────────────────
    chroma_host: str = Field("localhost", alias="CHROMA_HOST")
    chroma_port: int = Field(8001, alias="CHROMA_PORT")
    chroma_collection: str = Field("knowledge_base", alias="CHROMA_COLLECTION")

    # ── FastAPI / Auth ────────────────────────────────────────
    api_host: str = Field("localhost", alias="API_HOST")
    api_port: int = Field(8000, alias="API_PORT")
    secret_key: str = Field("change-me-in-production", alias="SECRET_KEY")
    algorithm: str = Field("HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(1440, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    require_auth: bool = Field(False, alias="REQUIRE_AUTH")
    max_upload_size_mb: int = Field(50, alias="MAX_UPLOAD_SIZE_MB")

    # ── Storage Paths ─────────────────────────────────────────
    upload_dir: Path = Field(Path("./data/uploads"), alias="UPLOAD_DIR")
    reports_dir: Path = Field(Path("./data/reports"), alias="REPORTS_DIR")
    vectorstore_dir: Path = Field(Path("./data/vectorstore"), alias="VECTORSTORE_DIR")

    # ── CORS ──────────────────────────────────────────────────
    allowed_origins: str | list[str] = Field(
        ["http://localhost:8501", "http://localhost:3000"],
        alias="ALLOWED_ORIGINS",
    )

    @field_validator("allowed_origins", mode="before")
    def parse_allowed_origins(cls, value):
        if value is None:
            return ["http://localhost:8501", "http://localhost:3000"]
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return ["http://localhost:8501", "http://localhost:3000"]
            if text.startswith("[") and text.endswith("]"):
                try:
                    return json.loads(text)
                except ValueError:
                    pass
            return [item.strip() for item in text.split(",") if item.strip()]
        return value

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        for d in [self.upload_dir, self.reports_dir, self.vectorstore_dir]:
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    settings = Settings()
    settings.ensure_directories()
    return settings
