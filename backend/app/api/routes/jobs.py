"""Job results dashboard, advanced filtering/sorting, job details, hide, and comparison routes."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.entities import (
    JobApplication,
    JobListing,
    JobMatch,
    SavedJob,
    User,
)
from app.schemas.job import (
    JobComparisonRequest,
    JobComparisonResponse,
    JobListingResponse,
    JobMatchResponse,
    JobRequirementItem,
)

router = APIRouter(prefix="/jobs", tags=["Job Results & Filtering"])


def serialize_job_listing(job: JobListing) -> JobListingResponse:
    reqs = [
        JobRequirementItem(
            requirement_type=r.requirement_type,
            requirement_text=r.requirement_text,
            normalized_key=r.normalized_key,
            is_mandatory=r.is_mandatory,
            min_years=r.min_years,
        )
        for r in (job.requirements or [])
    ]
    return JobListingResponse(
        id=job.id,
        source_slug=job.source_slug,
        source_name=job.source_name,
        external_id=job.external_id,
        title=job.title,
        company_name=job.company_name,
        company_logo_url=job.company_logo_url,
        country=job.country,
        city=job.city,
        location_raw=job.location_raw,
        work_mode=job.work_mode,
        employment_type=job.employment_type,
        experience_level=job.experience_level,
        min_experience_years=job.min_experience_years,
        required_education=job.required_education,
        industry=job.industry,
        category=job.category,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        salary_currency=job.salary_currency,
        salary_period=job.salary_period,
        salary_raw=job.salary_raw,
        visa_sponsorship=job.visa_sponsorship,
        english_speaking=job.english_speaking,
        description_text=job.description_text,
        source_url=job.source_url,
        apply_url=job.apply_url,
        is_direct_company_link=job.is_direct_company_link,
        published_at=job.published_at,
        application_deadline=job.application_deadline,
        verification_status=job.verification_status,
        verification_details=job.verification_details_json or {},
        last_verified_at=job.last_verified_at,
        alternate_sources=job.alternate_sources_json or [],
        requirements=reqs,
        created_at=job.created_at,
    )


def serialize_job_match(
    m: JobMatch,
    saved_ids: Set[str],
    app_status_map: Dict[str, str],
) -> JobMatchResponse:
    return JobMatchResponse(
        id=m.id,
        search_session_id=m.search_session_id,
        job_id=m.job_id,
        profile_id=m.profile_id,
        overall_score=m.overall_score,
        rank_score=m.rank_score,
        technical_skills_score=m.technical_skills_score,
        education_score=m.education_score,
        experience_score=m.experience_score,
        qualifications_score=m.qualifications_score,
        projects_score=m.projects_score,
        role_relevance_score=m.role_relevance_score,
        weights_used=m.weights_used_json or {},
        matched_skills=m.matched_skills_json or [],
        missing_mandatory_skills=m.missing_mandatory_skills_json or [],
        missing_preferred_skills=m.missing_preferred_skills_json or [],
        unstated_on_cv=m.unstated_on_cv_json or [],
        matching_qualifications=m.matching_qualifications_json or [],
        experience_compatibility=m.experience_compatibility,
        education_compatibility=m.education_compatibility,
        explicit_disqualifiers=m.explicit_disqualifiers_json or [],
        score_explanation=m.score_explanation,
        strengths=m.strengths_json or [],
        weaknesses=m.weaknesses_json or [],
        calculation_breakdown=m.calculation_breakdown_json or {},
        is_hidden=m.is_hidden,
        is_saved=m.job_id in saved_ids,
        application_status=app_status_map.get(m.job_id),
        job=serialize_job_listing(m.job),
        created_at=m.created_at,
    )


@router.get("", response_model=List[JobMatchResponse])
async def list_matching_jobs(
    session_id: Optional[str] = Query(default=None),
    country: Optional[str] = Query(default=None),
    city: Optional[str] = Query(default=None),
    min_score: Optional[float] = Query(default=None, ge=0, le=100),
    max_score: Optional[float] = Query(default=None, ge=0, le=100),
    company: Optional[str] = Query(default=None),
    industry: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    experience_level: Optional[str] = Query(default=None),
    salary_min: Optional[float] = Query(default=None),
    work_mode: Optional[str] = Query(default=None),
    employment_type: Optional[str] = Query(default=None),
    visa_sponsorship: Optional[bool] = Query(default=None),
    published_within_days: Optional[int] = Query(default=None, ge=1, le=365),
    has_deadline: Optional[bool] = Query(default=None),
    verification_status: Optional[str] = Query(default=None),
    search_query: Optional[str] = Query(default=None),
    include_hidden: bool = Query(default=False),
    sort_by: str = Query(
        default="highest_match",
        pattern="^(highest_match|latest_published|highest_salary|most_relevant|company_name)$",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[JobMatchResponse]:
    stmt = (
        select(JobMatch)
        .join(JobListing, JobMatch.job_id == JobListing.id)
        .options(selectinload(JobMatch.job).selectinload(JobListing.requirements))
        .where(JobMatch.user_id == current_user.id)
    )

    if session_id:
        stmt = stmt.where(JobMatch.search_session_id == session_id)
    if not include_hidden:
        stmt = stmt.where(JobMatch.is_hidden.is_(False))
    if min_score is not None:
        stmt = stmt.where(JobMatch.overall_score >= min_score)
    if max_score is not None:
        stmt = stmt.where(JobMatch.overall_score <= max_score)

    rows = (await db.execute(stmt)).scalars().all()

    # Deduplicate across sessions if viewing all sessions (keep highest match per job)
    if not session_id:
        best_by_fp: Dict[str, JobMatch] = {}
        for m in rows:
            fp = m.job.dedup_fingerprint
            if fp not in best_by_fp or m.overall_score > best_by_fp[fp].overall_score:
                best_by_fp[fp] = m
        rows = list(best_by_fp.values())

    # Apply rich attribute filters cleanly
    filtered: List[JobMatch] = []
    now = datetime.now(timezone.utc)
    for m in rows:
        j = m.job
        if country and country.lower() not in f"{j.country} {j.location_raw}".lower():
            continue
        if city and city.lower() not in f"{j.city or ''} {j.location_raw}".lower():
            continue
        if company and company.lower() not in j.company_name.lower():
            continue
        if industry and industry.lower() not in (j.industry or "").lower():
            continue
        if category and category.lower() not in (j.category or "").lower():
            continue
        if experience_level and experience_level.lower() != (j.experience_level or "").lower():
            continue
        if work_mode and work_mode.lower() != j.work_mode.lower():
            continue
        if employment_type and employment_type.lower() not in j.employment_type.lower():
            continue
        if visa_sponsorship is not None and j.visa_sponsorship is not visa_sponsorship:
            continue
        if verification_status and j.verification_status != verification_status:
            continue
        if salary_min is not None:
            top_sal = j.salary_max or j.salary_min
            if top_sal is None or top_sal < salary_min:
                continue
        if published_within_days is not None and j.published_at:
            pub = j.published_at if j.published_at.tzinfo else j.published_at.replace(tzinfo=timezone.utc)
            if pub < (now - timedelta(days=published_within_days)):
                continue
        if has_deadline is True and j.application_deadline is None:
            continue
        if search_query:
            q_low = search_query.lower()
            if q_low not in f"{j.title} {j.company_name} {j.description_text[:1000]}".lower():
                continue
        filtered.append(m)

    # Apply requested sorting
    if sort_by == "highest_match":
        filtered.sort(key=lambda m: (m.overall_score, m.rank_score), reverse=True)
    elif sort_by == "most_relevant":
        filtered.sort(key=lambda m: (m.rank_score, m.overall_score), reverse=True)
    elif sort_by == "latest_published":
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        filtered.sort(
            key=lambda m: (
                (m.job.published_at.replace(tzinfo=timezone.utc) if m.job.published_at and not m.job.published_at.tzinfo else m.job.published_at)
                or epoch
            ),
            reverse=True,
        )
    elif sort_by == "highest_salary":
        filtered.sort(key=lambda m: (m.job.salary_max or m.job.salary_min or 0.0), reverse=True)
    elif sort_by == "company_name":
        filtered.sort(key=lambda m: m.job.company_name.lower())

    saved_rows = (
        await db.execute(select(SavedJob.job_id).where(SavedJob.user_id == current_user.id))
    ).scalars().all()
    saved_ids = set(saved_rows)

    app_rows = (
        await db.execute(
            select(JobApplication.job_id, JobApplication.status).where(
                JobApplication.user_id == current_user.id
            )
        )
    ).all()
    app_map = {jid: st for jid, st in app_rows}

    return [serialize_job_match(m, saved_ids, app_map) for m in filtered]


@router.get("/{job_id}", response_model=JobMatchResponse)
async def get_job_detail(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobMatchResponse:
    stmt = (
        select(JobMatch)
        .options(selectinload(JobMatch.job).selectinload(JobListing.requirements))
        .where(JobMatch.job_id == job_id, JobMatch.user_id == current_user.id)
        .order_by(JobMatch.overall_score.desc())
        .limit(1)
    )
    match_row = (await db.execute(stmt)).scalar_one_or_none()
    if not match_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job match not found.")

    saved = (
        await db.execute(
            select(SavedJob.id).where(SavedJob.user_id == current_user.id, SavedJob.job_id == job_id)
        )
    ).scalar_one_or_none()
    app_st = (
        await db.execute(
            select(JobApplication.status).where(
                JobApplication.user_id == current_user.id, JobApplication.job_id == job_id
            )
        )
    ).scalar_one_or_none()

    return serialize_job_match(
        match_row,
        {job_id} if saved else set(),
        {job_id: app_st} if app_st else {},
    )


@router.post("/{job_id}/hide")
async def toggle_hide_job(
    job_id: str,
    hide: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, object]:
    stmt = select(JobMatch).where(JobMatch.job_id == job_id, JobMatch.user_id == current_user.id)
    matches = (await db.execute(stmt)).scalars().all()
    if not matches:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job match not found.")
    for m in matches:
        m.is_hidden = hide
    await db.commit()
    return {"job_id": job_id, "is_hidden": hide}


@router.post("/compare", response_model=JobComparisonResponse)
async def compare_jobs(
    payload: JobComparisonRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobComparisonResponse:
    if len(payload.job_ids) < 2 or len(payload.job_ids) > 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select between 2 and 4 jobs to compare.",
        )

    stmt = (
        select(JobMatch)
        .options(selectinload(JobMatch.job).selectinload(JobListing.requirements))
        .where(JobMatch.user_id == current_user.id, JobMatch.job_id.in_(payload.job_ids))
        .order_by(JobMatch.overall_score.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    by_job: Dict[str, JobMatch] = {}
    for r in rows:
        if r.job_id not in by_job:
            by_job[r.job_id] = r

    items = [serialize_job_match(by_job[jid], set(), {}) for jid in payload.job_ids if jid in by_job]
    if len(items) < 2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find at least 2 matched jobs for comparison.",
        )

    shared_matched = set(items[0].matched_skills)
    shared_missing = set(items[0].missing_mandatory_skills)
    for it in items[1:]:
        shared_matched &= set(it.matched_skills)
        shared_missing &= set(it.missing_mandatory_skills)

    top = max(items, key=lambda x: x.overall_score)
    summary = (
        f"{top.job.title} at {top.job.company_name} leads with a {top.overall_score}% CV match "
        f"({top.job.work_mode.title()}, {top.job.country}) and {len(top.missing_mandatory_skills)} "
        f"missing mandatory skill(s)."
    )

    return JobComparisonResponse(
        items=items,
        shared_matched_skills=sorted(shared_matched),
        shared_missing_skills=sorted(shared_missing),
        recommendation_summary=summary,
    )
