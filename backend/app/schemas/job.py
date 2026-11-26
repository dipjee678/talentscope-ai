"""Job listing, match breakdown, and side-by-side comparison schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class JobRequirementItem(BaseModel):
    requirement_type: str
    requirement_text: str
    normalized_key: str
    is_mandatory: bool
    min_years: Optional[float] = None


class JobListingResponse(BaseModel):
    id: str
    source_slug: str
    source_name: str
    external_id: Optional[str] = None
    title: str
    company_name: str
    company_logo_url: Optional[str] = None
    country: str
    city: Optional[str] = None
    location_raw: str
    work_mode: str
    employment_type: str
    experience_level: Optional[str] = None
    min_experience_years: Optional[float] = None
    required_education: Optional[str] = None
    industry: Optional[str] = None
    category: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    salary_period: Optional[str] = None
    salary_raw: Optional[str] = None
    visa_sponsorship: Optional[bool] = None
    english_speaking: bool = True
    description_text: str
    source_url: str
    apply_url: str
    is_direct_company_link: bool
    published_at: Optional[datetime] = None
    application_deadline: Optional[datetime] = None
    verification_status: str
    verification_details: Dict[str, Any] = {}
    last_verified_at: Optional[datetime] = None
    alternate_sources: List[Dict[str, str]] = []
    requirements: List[JobRequirementItem] = []
    created_at: datetime


class JobMatchResponse(BaseModel):
    id: str
    search_session_id: str
    job_id: str
    profile_id: str
    overall_score: float
    rank_score: float
    technical_skills_score: float
    education_score: float
    experience_score: float
    qualifications_score: float
    projects_score: float
    role_relevance_score: float
    weights_used: Dict[str, float]
    matched_skills: List[str] = []
    missing_mandatory_skills: List[str] = []
    missing_preferred_skills: List[str] = []
    unstated_on_cv: List[str] = []
    matching_qualifications: List[str] = []
    experience_compatibility: str
    education_compatibility: str
    explicit_disqualifiers: List[str] = []
    score_explanation: str
    strengths: List[str] = []
    weaknesses: List[str] = []
    calculation_breakdown: Dict[str, Any] = {}
    is_hidden: bool = False
    is_saved: bool = False
    application_status: Optional[str] = None
    job: JobListingResponse
    created_at: datetime


class JobComparisonRequest(BaseModel):
    job_ids: List[str]
    search_session_id: Optional[str] = None


class JobComparisonResponse(BaseModel):
    items: List[JobMatchResponse]
    shared_matched_skills: List[str] = []
    shared_missing_skills: List[str] = []
    recommendation_summary: str
