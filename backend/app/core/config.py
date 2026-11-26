"""Core application configuration loaded from environment variables."""
from __future__ import annotations

import base64
import hashlib
import re
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core application
    APP_NAME: str = "TalentScope AI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Security & encryption
    JWT_SECRET_KEY: str = "dev-only-change-me-in-production-64-char-minimum-secret-key-0123456789"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    FILE_ENCRYPTION_KEY: str = ""

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/talentscope.db"

    # Task runner & caching
    TASK_RUNNER_MODE: str = "local"  # "local" | "celery"
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # File storage
    STORAGE_BACKEND: str = "local"  # "local" | "s3" | "db" (encrypted blob in the database; for hosts without disks)
    LOCAL_STORAGE_DIR: str = "./data/uploads"
    MAX_UPLOAD_SIZE_MB: int = 10
    S3_BUCKET: str = "talentscope-cvs"
    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_REGION: str = "us-east-1"

    # Malware scanning
    CLAMD_HOST: str = ""
    CLAMD_PORT: int = 3310

    # LLM / AI provider
    LLM_PROVIDER: str = "none"  # openai | anthropic | gemini | openai_compatible | none
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_BASE_URL: str = ""
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-latest"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # External job source API keys
    ADZUNA_APP_ID: str = ""
    ADZUNA_APP_KEY: str = ""
    JOOBLE_API_KEY: str = ""
    USAJOBS_API_KEY: str = ""
    USAJOBS_USER_AGENT: str = "talentscope-user@example.com"
    REED_API_KEY: str = ""
    JSEARCH_API_KEY: str = ""

    # HTTP & Agent parameters
    HTTP_USER_AGENT: str = "TalentScopeAI/1.0 (+https://talentscope.local/bot)"
    SEARCH_HTTP_TIMEOUT_SECONDS: float = 15.0
    VERIFY_HTTP_TIMEOUT_SECONDS: float = 8.0
    DEFAULT_MAX_RESULTS_PER_SOURCE: int = 25
    VERIFY_MAX_CONCURRENCY: int = 10
    VERIFY_LIVE_URLS: bool = True

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        """Accept plain `postgres://` / `postgresql://` URLs (as given by Render, Heroku, Railway, Neon)
        and convert them to the async driver form. asyncpg does not understand libpq's `sslmode`
        query parameter, so it is translated to asyncpg's `ssl` parameter."""
        if not isinstance(v, str):
            return v
        v = v.strip()
        if v.startswith("postgres://"):
            v = "postgresql+asyncpg://" + v[len("postgres://"):]
        elif v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v[len("postgresql://"):]
        if v.startswith("postgresql+asyncpg://") and "sslmode=" in v:
            v = re.sub(r"sslmode=", "ssl=", v)
        return v

    @model_validator(mode="after")
    def _guard_production_secrets(self) -> "Settings":
        if self.APP_ENV.lower() == "production":
            weak = (
                not self.JWT_SECRET_KEY
                or len(self.JWT_SECRET_KEY) < 32
                or self.JWT_SECRET_KEY.startswith(("dev-only", "replace-with"))
            )
            if weak:
                raise ValueError(
                    "APP_ENV=production requires a strong JWT_SECRET_KEY (32+ random characters). "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
                )
        return self

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def effective_fernet_key(self) -> bytes:
        if self.FILE_ENCRYPTION_KEY:
            key = self.FILE_ENCRYPTION_KEY.strip().encode("utf-8")
            try:
                if len(base64.urlsafe_b64decode(key)) == 32:
                    return key  # already a proper Fernet key
            except Exception:
                pass
            # Any other random secret (e.g. a host-generated value) is stretched into a Fernet key.
            return base64.urlsafe_b64encode(hashlib.sha256(key).digest())
        digest = hashlib.sha256(self.JWT_SECRET_KEY.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    @property
    def is_postgres(self) -> bool:
        return self.DATABASE_URL.startswith("postgresql")

    @property
    def storage_dir_path(self) -> Path:
        p = Path(self.LOCAL_STORAGE_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
