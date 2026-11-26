"""CV upload, download, re-analysis, and user-controlled deletion routes."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, undefer

from app.agents.cv_analysis_agent import cv_analysis_agent
from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import decrypt_text, encrypt_text, validate_and_scan_upload
from app.core.storage import storage_service
from app.models.entities import CandidateProfile, CandidateSkill, UploadedCV, User
from app.schemas.cv import (
    CandidateProfileResponse,
    CandidateSkillItem,
    UploadedCVResponse,
)
from app.services.cv_extractor import extract_text_from_cv_bytes

router = APIRouter(prefix="/cvs", tags=["CV Management"])


def serialize_profile(profile: CandidateProfile) -> CandidateProfileResponse:
    skills = [
        CandidateSkillItem(
            id=s.id,
            skill_name=s.skill_name,
            normalized_name=s.normalized_name,
            category=s.category,
            proficiency=s.proficiency,
            source_section=s.source_section,
        )
        for s in (profile.skills or [])
    ]
    return CandidateProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        cv_id=profile.cv_id,
        full_name=profile.full_name,
        headline=profile.headline,
        email=profile.email,
        phone=profile.phone,
        location=profile.location,
        summary=profile.summary,
        years_of_experience=profile.years_of_experience,
        highest_degree=profile.highest_degree,
        universities=profile.universities_json or [],
        education=profile.education_json or [],
        programming_languages=profile.programming_languages_json or [],
        technical_skills=profile.technical_skills_json or [],
        soft_skills=profile.soft_skills_json or [],
        experience=profile.experience_json or [],
        internships=profile.internships_json or [],
        projects=profile.projects_json or [],
        certifications=profile.certifications_json or [],
        spoken_languages=profile.spoken_languages_json or [],
        career_interests=profile.career_interests_json or [],
        achievements=profile.achievements_json or [],
        missing_or_unclear=profile.missing_or_unclear_json or [],
        extraction_mode=profile.extraction_mode,
        manually_edited=profile.manually_edited,
        skills=skills,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def serialize_cv(cv: UploadedCV) -> UploadedCVResponse:
    return UploadedCVResponse(
        id=cv.id,
        user_id=cv.user_id,
        original_filename=cv.original_filename,
        file_extension=cv.file_extension,
        content_type=cv.content_type,
        file_size_bytes=cv.file_size_bytes,
        version_number=cv.version_number,
        is_active=cv.is_active,
        parse_status=cv.parse_status,
        ocr_status=cv.ocr_status,
        security_scan_status=cv.security_scan_status,
        security_scan_notes=cv.security_scan_notes_json or [],
        prompt_injection_flags=cv.prompt_injection_flags_json or [],
        created_at=cv.created_at,
        profile=serialize_profile(cv.profile) if cv.profile else None,
    )


@router.post("/upload", response_model=UploadedCVResponse, status_code=status.HTTP_201_CREATED)
async def upload_cv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadedCVResponse:
    settings = get_settings()
    filename = Path(file.filename or "resume.pdf").name
    raw_bytes = await file.read()

    scan = validate_and_scan_upload(
        filename=filename,
        content_type=file.content_type,
        content=raw_bytes,
        max_size_bytes=settings.max_upload_bytes,
    )
    if not scan.is_safe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=" ".join(scan.notes),
        )

    ext = Path(filename).suffix.lower()
    storage_path, backend_type, inline_blob = storage_service.save_encrypted(current_user.id, ext, raw_bytes)

    # Determine next CV version number for this user and mark previous versions inactive by default
    max_ver_res = await db.execute(
        select(func.coalesce(func.max(UploadedCV.version_number), 0)).where(
            UploadedCV.user_id == current_user.id
        )
    )
    next_version = int(max_ver_res.scalar_one() or 0) + 1

    await db.execute(
        update(UploadedCV)
        .where(UploadedCV.user_id == current_user.id)
        .values(is_active=False)
    )

    extraction = await extract_text_from_cv_bytes(filename, raw_bytes)
    parsed = await cv_analysis_agent.analyze(extraction.text, ocr_warnings=extraction.warnings)

    cv_record = UploadedCV(
        user_id=current_user.id,
        original_filename=filename,
        file_extension=ext,
        content_type=file.content_type or "application/octet-stream",
        file_size_bytes=len(raw_bytes),
        sha256_hash=scan.sha256_hash,
        encrypted_storage_path=storage_path,
        storage_backend=backend_type,
        encrypted_file_blob=inline_blob,
        version_number=next_version,
        is_active=True,
        parse_status="completed" if extraction.text.strip() else "manual_review_needed",
        ocr_status=extraction.ocr_status,
        security_scan_status=scan.status,
        security_scan_notes_json=scan.notes,
        extracted_text_encrypted=encrypt_text(extraction.text),
        prompt_injection_flags_json=parsed["prompt_injection_flags"],
    )
    db.add(cv_record)
    await db.flush()

    profile = CandidateProfile(
        user_id=current_user.id,
        cv_id=cv_record.id,
        full_name=parsed["full_name"] or current_user.full_name,
        headline=parsed["headline"],
        email=parsed["email"] or current_user.email,
        phone=parsed["phone"],
        location=parsed["location"],
        summary=parsed["summary"],
        years_of_experience=parsed["years_of_experience"],
        highest_degree=parsed["highest_degree"],
        universities_json=parsed["universities"],
        education_json=parsed["education"],
        programming_languages_json=parsed["programming_languages"],
        technical_skills_json=parsed["technical_skills"],
        soft_skills_json=parsed["soft_skills"],
        experience_json=parsed["experience"],
        internships_json=parsed["internships"],
        projects_json=parsed["projects"],
        certifications_json=parsed["certifications"],
        spoken_languages_json=parsed["spoken_languages"],
        career_interests_json=parsed["career_interests"],
        achievements_json=parsed["achievements"],
        missing_or_unclear_json=parsed["missing_or_unclear"],
        extraction_mode=parsed["extraction_mode"],
        manually_edited=False,
        embedding_vector=parsed["embedding_vector"],
    )
    db.add(profile)
    await db.flush()

    for sk in parsed["skills"]:
        db.add(
            CandidateSkill(
                profile_id=profile.id,
                skill_name=sk["skill_name"],
                normalized_name=sk["normalized_name"],
                category=sk["category"],
                source_section=sk.get("source_section"),
            )
        )

    await db.commit()

    stmt = (
        select(UploadedCV)
        .options(selectinload(UploadedCV.profile).selectinload(CandidateProfile.skills))
        .where(UploadedCV.id == cv_record.id)
    )
    loaded = (await db.execute(stmt)).scalar_one()
    return serialize_cv(loaded)


@router.get("", response_model=List[UploadedCVResponse])
async def list_cvs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[UploadedCVResponse]:
    stmt = (
        select(UploadedCV)
        .options(selectinload(UploadedCV.profile).selectinload(CandidateProfile.skills))
        .where(UploadedCV.user_id == current_user.id)
        .order_by(UploadedCV.version_number.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [serialize_cv(cv) for cv in rows]


@router.get("/{cv_id}", response_model=UploadedCVResponse)
async def get_cv(
    cv_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadedCVResponse:
    stmt = (
        select(UploadedCV)
        .options(selectinload(UploadedCV.profile).selectinload(CandidateProfile.skills))
        .where(UploadedCV.id == cv_id, UploadedCV.user_id == current_user.id)
    )
    cv = (await db.execute(stmt)).scalar_one_or_none()
    if not cv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found.")
    return serialize_cv(cv)


@router.post("/{cv_id}/activate", response_model=UploadedCVResponse)
async def activate_cv(
    cv_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadedCVResponse:
    stmt = (
        select(UploadedCV)
        .options(selectinload(UploadedCV.profile).selectinload(CandidateProfile.skills))
        .where(UploadedCV.id == cv_id, UploadedCV.user_id == current_user.id)
    )
    cv = (await db.execute(stmt)).scalar_one_or_none()
    if not cv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found.")

    await db.execute(
        update(UploadedCV).where(UploadedCV.user_id == current_user.id).values(is_active=False)
    )
    cv.is_active = True
    await db.commit()
    await db.refresh(cv)
    return serialize_cv(cv)


@router.get("/{cv_id}/download")
async def download_original_cv(
    cv_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    stmt = (
        select(UploadedCV)
        .options(undefer(UploadedCV.encrypted_file_blob))
        .where(UploadedCV.id == cv_id, UploadedCV.user_id == current_user.id)
    )
    cv = (await db.execute(stmt)).scalar_one_or_none()
    if not cv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found.")

    try:
        raw_bytes = storage_service.load_decrypted(
            cv.encrypted_storage_path,
            cv.storage_backend,
            cv.encrypted_file_blob if cv.storage_backend == "db" else None,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored CV file missing.")

    return Response(
        content=raw_bytes,
        media_type=cv.content_type or "application/octet-stream",
        headers={"Content-Disposition": _content_disposition(cv.original_filename)},
    )


@router.delete("/{cv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cv(
    cv_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    stmt = select(UploadedCV).where(UploadedCV.id == cv_id, UploadedCV.user_id == current_user.id)
    cv = (await db.execute(stmt)).scalar_one_or_none()
    if not cv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found.")

    storage_service.delete(cv.encrypted_storage_path, cv.storage_backend)
    was_active = cv.is_active
    await db.delete(cv)
    await db.commit()

    if was_active:
        latest = (
            await db.execute(
                select(UploadedCV)
                .where(UploadedCV.user_id == current_user.id)
                .order_by(UploadedCV.version_number.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if latest:
            latest.is_active = True
            await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _content_disposition(filename: str) -> str:
    """RFC 6266 header that survives quotes and non-ASCII names (raw latin-1 headers would 500)."""
    ascii_name = "".join(c if 32 <= ord(c) < 127 and c not in '"\\' else "_" for c in filename) or "cv"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def get_decrypted_cv_text(cv: UploadedCV) -> str:
    return decrypt_text(cv.extracted_text_encrypted)
