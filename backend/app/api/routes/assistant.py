"""AI Career Assistant API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.entities import CandidateProfile, JobListing, JobMatch, UploadedCV, User
from app.schemas.assistant import AssistantRequest, AssistantResponse
from app.services.career_assistant import career_assistant_service

router = APIRouter(prefix="/assistant", tags=["AI Career Assistant"])


@router.post("/generate", response_model=AssistantResponse)
async def generate_career_guidance(
    payload: AssistantRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AssistantResponse:
    if payload.cv_id:
        prof_stmt = (
            select(CandidateProfile)
            .where(CandidateProfile.cv_id == payload.cv_id, CandidateProfile.user_id == current_user.id)
        )
    else:
        prof_stmt = (
            select(CandidateProfile)
            .join(UploadedCV, CandidateProfile.cv_id == UploadedCV.id)
            .where(CandidateProfile.user_id == current_user.id)
            .order_by(UploadedCV.is_active.desc(), UploadedCV.version_number.desc())
            .limit(1)
        )
    profile = (await db.execute(prof_stmt)).scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Please upload a CV first so the AI Career Assistant can ground its advice in your profile.",
        )

    job = None
    reqs = None
    existing_match = None
    if payload.job_id:
        job = (
            await db.execute(
                select(JobListing)
                .options(selectinload(JobListing.requirements))
                .where(JobListing.id == payload.job_id)
            )
        ).scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target job not found.")
        reqs = job.requirements or []
        existing_match = (
            await db.execute(
                select(JobMatch)
                .where(JobMatch.user_id == current_user.id, JobMatch.job_id == job.id)
                .order_by(JobMatch.overall_score.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    compare_tuples = []
    if payload.action == "compare_jobs" and payload.compare_job_ids:
        for jid in payload.compare_job_ids[:4]:
            cj = (
                await db.execute(
                    select(JobListing)
                    .options(selectinload(JobListing.requirements))
                    .where(JobListing.id == jid)
                )
            ).scalar_one_or_none()
            if cj:
                cm = (
                    await db.execute(
                        select(JobMatch)
                        .where(JobMatch.user_id == current_user.id, JobMatch.job_id == cj.id)
                        .order_by(JobMatch.overall_score.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                compare_tuples.append((cj, cj.requirements or [], cm))

    return await career_assistant_service.generate(
        req=payload,
        profile=profile,
        job=job,
        requirements=reqs,
        existing_match=existing_match,
        compare_jobs_list=compare_tuples,
    )
