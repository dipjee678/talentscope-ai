"""FastAPI application entrypoint for TalentScope AI."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text, update

from app.api.routes import assistant, auth, cv, dashboard, jobs, profile, searches, sources, tracker
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, init_db
from app.core.logging import configure_logging
from app.core.storage import storage_service
from app.models.entities import JobSource, SearchSession, UploadedCV, User
from app.services.job_sources.registry import get_all_connectors

settings = get_settings()
configure_logging(debug=settings.DEBUG)


async def _seed_job_sources_and_enforce_retention() -> None:
    async with AsyncSessionLocal() as db:
        # 1. Sync registered job sources into job_sources table
        existing_rows = (await db.execute(select(JobSource))).scalars().all()
        by_slug = {r.slug: r for r in existing_rows}
        for conn in get_all_connectors():
            if conn.slug not in by_slug:
                db.add(
                    JobSource(
                        slug=conn.slug,
                        name=conn.name,
                        source_type=conn.source_type,
                        base_url=conn.base_url,
                        requires_api_key=conn.requires_api_key,
                        api_key_env_vars_json=conn.api_key_env_vars,
                        supported_countries_json=conn.supported_countries,
                        rate_limit_rpm=conn.rate_limit_rpm,
                        terms_notes=conn.terms_notes,
                    )
                )

        # 2. Enforce user-configured CV data retention policy
        now = datetime.now(timezone.utc)
        users = (await db.execute(select(User))).scalars().all()
        for u in users:
            cutoff = now - timedelta(days=max(7, u.data_retention_days or 365))
            expired_cvs = (
                await db.execute(
                    select(UploadedCV).where(
                        UploadedCV.user_id == u.id, UploadedCV.created_at < cutoff
                    )
                )
            ).scalars().all()
            for old_cv in expired_cvs:
                storage_service.delete(old_cv.encrypted_storage_path, old_cv.storage_backend)
                await db.delete(old_cv)

        await db.commit()


async def _fail_orphaned_local_searches() -> None:
    """In local (in-process) mode a restart kills running searches; don't leave them spinning forever."""
    if settings.TASK_RUNNER_MODE.lower() == "celery":
        return
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(SearchSession)
            .where(SearchSession.status.in_(("queued", "running")))
            .values(
                status="failed",
                current_stage="failed",
                error_message="Search was interrupted by a server restart. Please start it again.",
                completed_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await _seed_job_sources_and_enforce_retention()
    await _fail_orphaned_local_searches()
    yield


app = FastAPI(
    title="TalentScope AI — Agentic Job Discovery & Matching API",
    version="1.0.0",
    description=(
        "Autonomous 7-agent job discovery, verification, deduplication, explainable CV matching, "
        "application tracking, and grounded career assistant API."
    ),
    lifespan=lifespan,
    docs_url="/docs" if (settings.DEBUG or not settings.is_production) else None,
    redoc_url="/redoc" if (settings.DEBUG or not settings.is_production) else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/health", tags=["System"])
async def health_check():
    db_ok = True
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "ok" if db_ok else "unreachable",
        "service": settings.APP_NAME,
        "version": "1.0.0",
    }


prefix = settings.API_PREFIX
app.include_router(auth.router, prefix=prefix)
app.include_router(cv.router, prefix=prefix)
app.include_router(profile.router, prefix=prefix)
app.include_router(sources.router, prefix=prefix)
app.include_router(searches.router, prefix=prefix)
app.include_router(jobs.router, prefix=prefix)
app.include_router(tracker.router, prefix=prefix)
app.include_router(assistant.router, prefix=prefix)
app.include_router(dashboard.dashboard_router, prefix=prefix)
app.include_router(dashboard.settings_router, prefix=prefix)
