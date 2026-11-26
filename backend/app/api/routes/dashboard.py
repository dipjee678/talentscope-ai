"""Dashboard overview metrics, notifications, and user settings / privacy routes."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.api.routes.auth import serialize_user
from app.api.routes.jobs import serialize_job_match
from app.api.routes.searches import serialize_session
from app.core.config import get_settings
from app.core.database import get_db
from app.core.storage import storage_service
from app.models.entities import (
    JobApplication,
    JobListing,
    JobMatch,
    Notification,
    SavedJob,
    SearchSession,
    UploadedCV,
    User,
)
from app.schemas.auth import SettingsUpdateRequest, UserResponse
from app.schemas.search import MatchingWeights
from app.services.llm_client import llm_client

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
settings_router = APIRouter(prefix="/settings", tags=["Settings & Privacy"])


@dashboard_router.get("/summary")
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    cv_count = (
        await db.execute(select(func.count(UploadedCV.id)).where(UploadedCV.user_id == current_user.id))
    ).scalar_one()

    active_cv = (
        await db.execute(
            select(UploadedCV)
            .options(selectinload(UploadedCV.profile))
            .where(UploadedCV.user_id == current_user.id)
            .order_by(UploadedCV.is_active.desc(), UploadedCV.version_number.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    sessions = (
        await db.execute(
            select(SearchSession)
            .options(selectinload(SearchSession.logs))
            .where(SearchSession.user_id == current_user.id)
            .order_by(SearchSession.created_at.desc())
            .limit(5)
        )
    ).scalars().all()

    total_matches = (
        await db.execute(
            select(func.count(JobMatch.id)).where(
                JobMatch.user_id == current_user.id, JobMatch.is_hidden.is_(False)
            )
        )
    ).scalar_one()

    top_matches_rows = (
        await db.execute(
            select(JobMatch)
            .options(selectinload(JobMatch.job).selectinload(JobListing.requirements))
            .where(JobMatch.user_id == current_user.id, JobMatch.is_hidden.is_(False))
            .order_by(JobMatch.overall_score.desc())
            .limit(6)
        )
    ).scalars().all()

    app_counts_raw = (
        await db.execute(
            select(JobApplication.status, func.count(JobApplication.id))
            .where(JobApplication.user_id == current_user.id)
            .group_by(JobApplication.status)
        )
    ).all()
    pipeline_counts = {st: cnt for st, cnt in app_counts_raw}

    saved_count = (
        await db.execute(select(func.count(SavedJob.id)).where(SavedJob.user_id == current_user.id))
    ).scalar_one()

    notifs = (
        await db.execute(
            select(Notification)
            .where(Notification.user_id == current_user.id)
            .order_by(Notification.created_at.desc())
            .limit(8)
        )
    ).scalars().all()

    return {
        "cv_count": cv_count,
        "active_cv_filename": active_cv.original_filename if active_cv else None,
        "active_cv_id": active_cv.id if active_cv else None,
        "profile_headline": active_cv.profile.headline if (active_cv and active_cv.profile) else None,
        "total_searches": len(sessions),
        "total_qualifying_matches": total_matches,
        "saved_jobs_count": saved_count,
        "application_pipeline": pipeline_counts,
        "recent_searches": [serialize_session(s, include_logs=False) for s in sessions],
        "top_matches": [serialize_job_match(m, set(), {}) for m in top_matches_rows],
        "notifications": [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "body": n.body,
                "link_url": n.link_url,
                "is_read": n.is_read,
                "created_at": n.created_at,
            }
            for n in notifs
        ],
    }


@dashboard_router.post("/notifications/{notif_id}/read")
async def mark_notification_read(
    notif_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, bool]:
    notif = (
        await db.execute(
            select(Notification).where(
                Notification.id == notif_id, Notification.user_id == current_user.id
            )
        )
    ).scalar_one_or_none()
    if notif:
        notif.is_read = True
        await db.commit()
    return {"ok": True}


@settings_router.get("/system-status")
async def get_system_status(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    cfg = get_settings()
    return {
        "llm_provider": llm_client.active_provider,
        "llm_available": llm_client.is_available,
        "task_runner_mode": cfg.TASK_RUNNER_MODE,
        "storage_backend": cfg.STORAGE_BACKEND,
        "database_dialect": "postgresql+pgvector" if cfg.is_postgres else "sqlite",
        "verify_live_urls": cfg.VERIFY_LIVE_URLS,
        "encryption_at_rest": True,
    }


@settings_router.put("", response_model=UserResponse)
async def update_user_settings(
    payload: SettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    if payload.full_name is not None:
        current_user.full_name = payload.full_name.strip()
    if payload.theme_preference is not None:
        current_user.theme_preference = payload.theme_preference
    if payload.data_retention_days is not None:
        current_user.data_retention_days = payload.data_retention_days
    if payload.default_weights is not None:
        mw = MatchingWeights(**payload.default_weights)
        current_user.default_weights_json = mw.normalized_dict()
    if payload.custom_ats_boards is not None:
        current_user.custom_ats_boards_json = [b.model_dump() for b in payload.custom_ats_boards]

    await db.commit()
    await db.refresh(current_user)
    return serialize_user(current_user)


@settings_router.delete("/purge-cvs", status_code=status.HTTP_204_NO_CONTENT)
async def purge_all_user_cvs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    cvs = (
        await db.execute(select(UploadedCV).where(UploadedCV.user_id == current_user.id))
    ).scalars().all()
    for cv in cvs:
        storage_service.delete(cv.encrypted_storage_path, cv.storage_backend)
    await db.execute(delete(UploadedCV).where(UploadedCV.user_id == current_user.id))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@settings_router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    cvs = (
        await db.execute(select(UploadedCV).where(UploadedCV.user_id == current_user.id))
    ).scalars().all()
    for cv in cvs:
        storage_service.delete(cv.encrypted_storage_path, cv.storage_backend)
    await db.delete(current_user)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
