"""Saved jobs and Job Application Tracking System routes.

Never auto-submits applications; all status transitions and notes are explicitly user-controlled.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.api.routes.jobs import serialize_job_listing
from app.core.database import get_db
from app.models.entities import JobApplication, JobListing, JobMatch, SavedJob, User
from app.schemas.tracker import (
    ApplicationResponse,
    ApplicationUpdateRequest,
    ApplicationUpsertRequest,
    SavedJobResponse,
    SaveJobRequest,
)

router = APIRouter(prefix="/tracker", tags=["Application Tracker"])


@router.post("/saved", response_model=SavedJobResponse, status_code=status.HTTP_201_CREATED)
async def save_job(
    payload: SaveJobRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedJobResponse:
    job = (
        await db.execute(
            select(JobListing)
            .options(selectinload(JobListing.requirements))
            .where(JobListing.id == payload.job_id)
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job listing not found.")

    existing = (
        await db.execute(
            select(SavedJob)
            .options(selectinload(SavedJob.job).selectinload(JobListing.requirements))
            .where(SavedJob.user_id == current_user.id, SavedJob.job_id == payload.job_id)
        )
    ).scalar_one_or_none()

    if existing:
        if payload.notes is not None:
            existing.notes = payload.notes
            await db.commit()
        return SavedJobResponse(
            id=existing.id,
            job_id=existing.job_id,
            notes=existing.notes,
            created_at=existing.created_at,
            job=serialize_job_listing(existing.job),
        )

    rec = SavedJob(user_id=current_user.id, job_id=payload.job_id, notes=payload.notes)
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return SavedJobResponse(
        id=rec.id,
        job_id=rec.job_id,
        notes=rec.notes,
        created_at=rec.created_at,
        job=serialize_job_listing(job),
    )


@router.get("/saved", response_model=List[SavedJobResponse])
async def list_saved_jobs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[SavedJobResponse]:
    stmt = (
        select(SavedJob)
        .options(selectinload(SavedJob.job).selectinload(JobListing.requirements))
        .where(SavedJob.user_id == current_user.id)
        .order_by(SavedJob.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        SavedJobResponse(
            id=r.id,
            job_id=r.job_id,
            notes=r.notes,
            created_at=r.created_at,
            job=serialize_job_listing(r.job),
        )
        for r in rows
    ]


@router.delete("/saved/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unsave_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    rec = (
        await db.execute(
            select(SavedJob).where(SavedJob.user_id == current_user.id, SavedJob.job_id == job_id)
        )
    ).scalar_one_or_none()
    if rec:
        await db.delete(rec)
        await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _serialize_application(db: AsyncSession, app_rec: JobApplication, user_id: str) -> ApplicationResponse:
    score = (
        await db.execute(
            select(JobMatch.overall_score)
            .where(JobMatch.user_id == user_id, JobMatch.job_id == app_rec.job_id)
            .order_by(JobMatch.overall_score.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    return ApplicationResponse(
        id=app_rec.id,
        user_id=app_rec.user_id,
        job_id=app_rec.job_id,
        status=app_rec.status,
        applied_at=app_rec.applied_at,
        application_url=app_rec.application_url or app_rec.job.apply_url,
        notes=app_rec.notes,
        follow_up_at=app_rec.follow_up_at,
        history=app_rec.history_json or [],
        match_score=score,
        job=serialize_job_listing(app_rec.job),
        created_at=app_rec.created_at,
        updated_at=app_rec.updated_at,
    )


@router.post("/applications", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def upsert_application(
    payload: ApplicationUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    job = (
        await db.execute(
            select(JobListing)
            .options(selectinload(JobListing.requirements))
            .where(JobListing.id == payload.job_id)
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job listing not found.")

    existing = (
        await db.execute(
            select(JobApplication)
            .options(selectinload(JobApplication.job).selectinload(JobListing.requirements))
            .where(JobApplication.user_id == current_user.id, JobApplication.job_id == payload.job_id)
        )
    ).scalar_one_or_none()

    now_iso = datetime.now(timezone.utc).isoformat()
    applied_ts = payload.applied_at
    if payload.status == "applied" and applied_ts is None:
        applied_ts = datetime.now(timezone.utc)

    if existing:
        history = list(existing.history_json or [])
        if existing.status != payload.status:
            history.append({"status": payload.status, "timestamp": now_iso, "note": payload.notes or ""})
        existing.status = payload.status
        if applied_ts is not None:
            existing.applied_at = applied_ts
        if payload.application_url is not None:
            existing.application_url = payload.application_url
        if payload.notes is not None:
            existing.notes = payload.notes
        if payload.follow_up_at is not None:
            existing.follow_up_at = payload.follow_up_at
        existing.history_json = history
        await db.commit()
        await db.refresh(existing)
        return await _serialize_application(db, existing, current_user.id)

    app_rec = JobApplication(
        user_id=current_user.id,
        job_id=payload.job_id,
        status=payload.status,
        applied_at=applied_ts,
        application_url=payload.application_url or job.apply_url,
        notes=payload.notes,
        follow_up_at=payload.follow_up_at,
        history_json=[{"status": payload.status, "timestamp": now_iso, "note": payload.notes or "Added to tracker"}],
    )
    db.add(app_rec)
    await db.commit()

    loaded = (
        await db.execute(
            select(JobApplication)
            .options(selectinload(JobApplication.job).selectinload(JobListing.requirements))
            .where(JobApplication.id == app_rec.id)
        )
    ).scalar_one()
    return await _serialize_application(db, loaded, current_user.id)


@router.get("/applications", response_model=List[ApplicationResponse])
async def list_applications(
    status_filter: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ApplicationResponse]:
    stmt = (
        select(JobApplication)
        .options(selectinload(JobApplication.job).selectinload(JobListing.requirements))
        .where(JobApplication.user_id == current_user.id)
        .order_by(JobApplication.updated_at.desc())
    )
    if status_filter:
        stmt = stmt.where(JobApplication.status == status_filter)
    rows = (await db.execute(stmt)).scalars().all()
    return [await _serialize_application(db, r, current_user.id) for r in rows]


@router.patch("/applications/{app_id}", response_model=ApplicationResponse)
async def update_application(
    app_id: str,
    payload: ApplicationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    stmt = (
        select(JobApplication)
        .options(selectinload(JobApplication.job).selectinload(JobListing.requirements))
        .where(JobApplication.id == app_id, JobApplication.user_id == current_user.id)
    )
    app_rec = (await db.execute(stmt)).scalar_one_or_none()
    if not app_rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked application not found.")

    history = list(app_rec.history_json or [])
    if payload.status and payload.status != app_rec.status:
        history.append(
            {
                "status": payload.status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "note": payload.notes or "",
            }
        )
        app_rec.status = payload.status
        if payload.status == "applied" and app_rec.applied_at is None:
            app_rec.applied_at = datetime.now(timezone.utc)

    if payload.applied_at is not None:
        app_rec.applied_at = payload.applied_at
    if payload.application_url is not None:
        app_rec.application_url = payload.application_url
    if payload.notes is not None:
        app_rec.notes = payload.notes
    if payload.follow_up_at is not None:
        app_rec.follow_up_at = payload.follow_up_at
    app_rec.history_json = history

    await db.commit()
    await db.refresh(app_rec)
    return await _serialize_application(db, app_rec, current_user.id)


@router.delete("/applications/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    app_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    stmt = select(JobApplication).where(
        JobApplication.id == app_id, JobApplication.user_id == current_user.id
    )
    app_rec = (await db.execute(stmt)).scalar_one_or_none()
    if not app_rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked application not found.")
    await db.delete(app_rec)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
