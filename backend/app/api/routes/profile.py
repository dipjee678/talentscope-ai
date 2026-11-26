"""Candidate profile viewing and inline editing routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.api.routes.cv import serialize_profile
from app.core.database import get_db
from app.models.entities import CandidateProfile, CandidateSkill, UploadedCV, User
from app.schemas.cv import CandidateProfileResponse, CandidateProfileUpdateRequest
from app.services.skill_taxonomy import compute_semantic_embedding, normalize_skill

router = APIRouter(prefix="/profiles", tags=["Candidate Profiles"])


@router.get("/active", response_model=CandidateProfileResponse)
async def get_active_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CandidateProfileResponse:
    stmt = (
        select(CandidateProfile)
        .join(UploadedCV, CandidateProfile.cv_id == UploadedCV.id)
        .options(selectinload(CandidateProfile.skills))
        .where(CandidateProfile.user_id == current_user.id)
        .order_by(UploadedCV.is_active.desc(), UploadedCV.version_number.desc())
        .limit(1)
    )
    profile = (await db.execute(stmt)).scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No candidate profile found. Upload a CV first.",
        )
    return serialize_profile(profile)


@router.get("/{profile_id}", response_model=CandidateProfileResponse)
async def get_profile_by_id(
    profile_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CandidateProfileResponse:
    stmt = (
        select(CandidateProfile)
        .options(selectinload(CandidateProfile.skills))
        .where(CandidateProfile.id == profile_id, CandidateProfile.user_id == current_user.id)
    )
    profile = (await db.execute(stmt)).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    return serialize_profile(profile)


@router.put("/{profile_id}", response_model=CandidateProfileResponse)
async def update_profile(
    profile_id: str,
    payload: CandidateProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CandidateProfileResponse:
    stmt = (
        select(CandidateProfile)
        .options(selectinload(CandidateProfile.skills))
        .where(CandidateProfile.id == profile_id, CandidateProfile.user_id == current_user.id)
    )
    profile = (await db.execute(stmt)).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")

    scalar_fields = [
        "full_name",
        "headline",
        "email",
        "phone",
        "location",
        "summary",
        "years_of_experience",
        "highest_degree",
    ]
    for f in scalar_fields:
        val = getattr(payload, f)
        if val is not None:
            setattr(profile, f, val)

    json_mapping = {
        "universities": "universities_json",
        "education": "education_json",
        "programming_languages": "programming_languages_json",
        "technical_skills": "technical_skills_json",
        "soft_skills": "soft_skills_json",
        "experience": "experience_json",
        "internships": "internships_json",
        "projects": "projects_json",
        "certifications": "certifications_json",
        "spoken_languages": "spoken_languages_json",
        "career_interests": "career_interests_json",
        "achievements": "achievements_json",
    }
    skills_changed = False
    for req_key, col_name in json_mapping.items():
        val = getattr(payload, req_key)
        if val is not None:
            setattr(profile, col_name, val)
            if req_key in ("programming_languages", "technical_skills", "soft_skills"):
                skills_changed = True

    profile.manually_edited = True

    # Re-sync normalized skill rows and semantic embedding if skills or text changed
    if skills_changed:
        await db.execute(delete(CandidateSkill).where(CandidateSkill.profile_id == profile.id))
        seen = set()
        for cat, items in (
            ("programming_language", profile.programming_languages_json or []),
            ("technical", profile.technical_skills_json or []),
            ("soft", profile.soft_skills_json or []),
        ):
            for raw_sk in items:
                if not raw_sk or not raw_sk.strip():
                    continue
                canon, _ = normalize_skill(raw_sk)
                norm = canon.lower()
                if norm not in seen:
                    seen.add(norm)
                    db.add(
                        CandidateSkill(
                            profile_id=profile.id,
                            skill_name=canon,
                            normalized_name=norm,
                            category=cat,
                            source_section="manual_edit",
                        )
                    )

    composite_text = " ".join(
        filter(
            None,
            [
                profile.headline or "",
                profile.summary or "",
                profile.highest_degree or "",
                " ".join(profile.programming_languages_json or []),
                " ".join(profile.technical_skills_json or []),
                " ".join(profile.career_interests_json or []),
                " ".join(e.get("title", "") for e in (profile.experience_json or [])),
                " ".join(p.get("title", "") for p in (profile.projects_json or [])),
            ],
        )
    )
    profile.embedding_vector = compute_semantic_embedding(composite_text)

    # Recompute missing/unclear notices accurately after user edits
    missing = []
    if not profile.full_name:
        missing.append("Candidate full name is empty.")
    if not (profile.programming_languages_json or profile.technical_skills_json):
        missing.append("No technical skills or programming languages listed.")
    if not profile.highest_degree and not profile.education_json:
        missing.append("Education details are empty.")
    if profile.years_of_experience is None:
        missing.append("Total years of experience is not specified.")
    profile.missing_or_unclear_json = missing

    await db.commit()

    refreshed = (
        await db.execute(
            select(CandidateProfile)
            .options(selectinload(CandidateProfile.skills))
            .where(CandidateProfile.id == profile.id)
        )
    ).scalar_one()
    return serialize_profile(refreshed)
