"""Normalized 14-table SQLAlchemy 2.0 ORM schema with pgvector + JSON portable vector support."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    LargeBinary,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, deferred, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.core.database import Base

try:
    from pgvector.sqlalchemy import Vector as PGVector  # type: ignore
except Exception:  # pragma: no cover
    PGVector = None


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class EmbeddingVector(TypeDecorator):
    """Portable vector column: native pgvector Vector(dim) on PostgreSQL, JSON list on SQLite."""

    impl = JSON
    cache_ok = True

    def __init__(self, dim: int = 256, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.dim = dim

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql" and PGVector is not None:
            return dialect.type_descriptor(PGVector(self.dim))
        return dialect.type_descriptor(JSON())


DEFAULT_MATCHING_WEIGHTS: Dict[str, float] = {
    "technical_skills": 30.0,
    "education": 15.0,
    "work_experience": 20.0,
    "required_qualifications": 15.0,
    "projects_achievements": 10.0,
    "role_relevance": 10.0,
}


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    theme_preference: Mapped[str] = mapped_column(String(16), nullable=False, default="system")
    data_retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365)
    default_weights_json: Mapped[Dict[str, float]] = mapped_column(
        JSON, nullable=False, default=lambda: dict(DEFAULT_MATCHING_WEIGHTS)
    )
    custom_ats_boards_json: Mapped[List[Dict[str, str]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    cvs: Mapped[List["UploadedCV"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    profiles: Mapped[List["CandidateProfile"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    preferences: Mapped[List["SearchPreference"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    search_sessions: Mapped[List["SearchSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    saved_jobs: Mapped[List["SavedJob"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    applications: Mapped[List["JobApplication"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    notifications: Mapped[List["Notification"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class UploadedCV(Base):
    __tablename__ = "uploaded_cvs"
    __table_args__ = (
        Index("ix_uploaded_cvs_user_active", "user_id", "is_active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_extension: Mapped[str] = mapped_column(String(16), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    encrypted_storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(32), nullable=False, default="local")
    # Used only when STORAGE_BACKEND=db (hosts without persistent disks). Deferred so list
    # queries never pull file bytes.
    encrypted_file_blob: Mapped[Optional[bytes]] = deferred(
        mapped_column(LargeBinary, nullable=True)
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    parse_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    ocr_status: Mapped[str] = mapped_column(String(48), nullable=False, default="not_needed")
    security_scan_status: Mapped[str] = mapped_column(String(32), nullable=False, default="clean")
    security_scan_notes_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    extracted_text_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    prompt_injection_flags_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="cvs")
    profile: Mapped[Optional["CandidateProfile"]] = relationship(
        back_populates="cv", uselist=False, cascade="all, delete-orphan", passive_deletes=True
    )


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"
    __table_args__ = (
        UniqueConstraint("cv_id", name="uq_candidate_profile_cv"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cv_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("uploaded_cvs.id", ondelete="CASCADE"), nullable=False
    )
    full_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    headline: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    years_of_experience: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    highest_degree: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    universities_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    education_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    programming_languages_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    technical_skills_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    soft_skills_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    experience_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    internships_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    projects_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    certifications_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    spoken_languages_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    career_interests_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    achievements_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_or_unclear_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    extraction_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="hybrid_nlp")
    manually_edited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    embedding_vector: Mapped[Optional[List[float]]] = mapped_column(EmbeddingVector(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="profiles")
    cv: Mapped["UploadedCV"] = relationship(back_populates="profile")
    skills: Mapped[List["CandidateSkill"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", passive_deletes=True
    )


class CandidateSkill(Base):
    __tablename__ = "candidate_skills"
    __table_args__ = (
        UniqueConstraint("profile_id", "normalized_name", name="uq_profile_skill_norm"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_name: Mapped[str] = mapped_column(String(128), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(48), nullable=False, default="technical")
    proficiency: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    source_section: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    profile: Mapped["CandidateProfile"] = relationship(back_populates="skills")


class JobSource(Base):
    __tablename__ = "job_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(48), nullable=False)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    requires_api_key: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    api_key_env_vars_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    supported_countries_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rate_limit_rpm: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    terms_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    listings: Mapped[List["JobListing"]] = relationship(back_populates="source")


class SearchPreference(Base):
    __tablename__ = "search_preferences"
    __table_args__ = (
        CheckConstraint("min_match_score >= 0 AND min_match_score <= 100", name="ck_min_match_range"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cv_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("uploaded_cvs.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    target_countries_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    min_match_score: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    job_categories_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    industries_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    experience_levels_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    employment_types_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    work_modes_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    visa_sponsorship_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    english_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fresh_graduate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    internship: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    entry_level: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    custom_keywords_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    matching_weights_json: Mapped[Dict[str, float]] = mapped_column(
        JSON, nullable=False, default=lambda: dict(DEFAULT_MATCHING_WEIGHTS)
    )
    max_results_per_source: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    enabled_source_slugs_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="preferences")


class SearchSession(Base):
    __tablename__ = "search_sessions"
    __table_args__ = (
        Index("ix_search_sessions_user_status", "user_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cv_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("uploaded_cvs.id", ondelete="CASCADE"), nullable=False
    )
    preference_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("search_preferences.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    current_stage: Mapped[str] = mapped_column(String(64), nullable=False, default="queued")
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    config_snapshot_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    generated_queries_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    sources_searched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sources_searched_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    sources_unavailable_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    jobs_discovered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jobs_verified_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicates_removed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expired_removed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    below_threshold_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jobs_matched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    coverage_report_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="search_sessions")
    logs: Mapped[List["AgentExecutionLog"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True
    )
    matches: Mapped[List["JobMatch"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True
    )


class JobListing(Base):
    __tablename__ = "job_listings"
    __table_args__ = (
        Index("ix_job_listings_fingerprint", "dedup_fingerprint"),
        Index("ix_job_listings_country_mode", "country", "work_mode"),
        Index("ix_job_listings_verification", "verification_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    source_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("job_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_slug: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    dedup_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company_logo_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    country: Mapped[str] = mapped_column(String(128), nullable=False, default="Worldwide")
    city: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    location_raw: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    work_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    employment_type: Mapped[str] = mapped_column(String(64), nullable=False, default="Full-time")
    experience_level: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    min_experience_years: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    required_education: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    salary_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    salary_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    salary_period: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    salary_raw: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    visa_sponsorship: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    english_speaking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    apply_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    is_direct_company_link: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    application_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unverified")
    verification_details_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    canonical_job_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("job_listings.id", ondelete="SET NULL"), nullable=True
    )
    alternate_sources_json: Mapped[List[Dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    prompt_injection_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    embedding_vector: Mapped[Optional[List[float]]] = mapped_column(EmbeddingVector(256), nullable=True)
    raw_metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    source: Mapped[Optional["JobSource"]] = relationship(back_populates="listings")
    requirements: Mapped[List["JobRequirement"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )
    matches: Mapped[List["JobMatch"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )


class JobRequirement(Base):
    __tablename__ = "job_requirements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("job_listings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_type: Mapped[str] = mapped_column(String(48), nullable=False)
    requirement_text: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    min_years: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    job: Mapped["JobListing"] = relationship(back_populates="requirements")


class JobMatch(Base):
    __tablename__ = "job_matches"
    __table_args__ = (
        UniqueConstraint("search_session_id", "job_id", name="uq_session_job_match"),
        Index("ix_job_matches_user_score", "user_id", "overall_score"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    search_session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("search_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("job_listings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False
    )
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    rank_score: Mapped[float] = mapped_column(Float, nullable=False)
    technical_skills_score: Mapped[float] = mapped_column(Float, nullable=False)
    education_score: Mapped[float] = mapped_column(Float, nullable=False)
    experience_score: Mapped[float] = mapped_column(Float, nullable=False)
    qualifications_score: Mapped[float] = mapped_column(Float, nullable=False)
    projects_score: Mapped[float] = mapped_column(Float, nullable=False)
    role_relevance_score: Mapped[float] = mapped_column(Float, nullable=False)
    weights_used_json: Mapped[Dict[str, float]] = mapped_column(JSON, nullable=False, default=dict)
    matched_skills_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_mandatory_skills_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_preferred_skills_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    unstated_on_cv_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    matching_qualifications_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    experience_compatibility: Mapped[str] = mapped_column(Text, nullable=False, default="")
    education_compatibility: Mapped[str] = mapped_column(Text, nullable=False, default="")
    explicit_disqualifiers_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    score_explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    strengths_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    weaknesses_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    calculation_breakdown_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    session: Mapped["SearchSession"] = relationship(back_populates="matches")
    job: Mapped["JobListing"] = relationship(back_populates="matches")


class SavedJob(Base):
    __tablename__ = "saved_jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_user_saved_job"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("job_listings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="saved_jobs")
    job: Mapped["JobListing"] = relationship()


class JobApplication(Base):
    __tablename__ = "job_applications"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_user_job_application"),
        Index("ix_job_applications_user_status", "user_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("job_listings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="saved")
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    application_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    follow_up_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    history_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="applications")
    job: Mapped["JobListing"] = relationship()


class AgentExecutionLog(Base):
    __tablename__ = "agent_execution_logs"
    __table_args__ = (
        Index("ix_agent_logs_session_created", "search_session_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    search_session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("search_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metrics_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    session: Mapped["SearchSession"] = relationship(back_populates="logs")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_read", "user_id", "is_read"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(48), nullable=False, default="search_completed")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    link_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="notifications")
