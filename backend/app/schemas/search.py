"""Search configuration, job source metadata, and live search session schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class MatchingWeights(BaseModel):
    technical_skills: float = Field(default=30.0, ge=0.0, le=100.0)
    education: float = Field(default=15.0, ge=0.0, le=100.0)
    work_experience: float = Field(default=20.0, ge=0.0, le=100.0)
    required_qualifications: float = Field(default=15.0, ge=0.0, le=100.0)
    projects_achievements: float = Field(default=10.0, ge=0.0, le=100.0)
    role_relevance: float = Field(default=10.0, ge=0.0, le=100.0)

    def normalized_dict(self) -> Dict[str, float]:
        raw = {
            "technical_skills": self.technical_skills,
            "education": self.education,
            "work_experience": self.work_experience,
            "required_qualifications": self.required_qualifications,
            "projects_achievements": self.projects_achievements,
            "role_relevance": self.role_relevance,
        }
        total = sum(raw.values())
        if total <= 0:
            return {
                "technical_skills": 30.0,
                "education": 15.0,
                "work_experience": 20.0,
                "required_qualifications": 15.0,
                "projects_achievements": 10.0,
                "role_relevance": 10.0,
            }
        return {k: round((v / total) * 100.0, 2) for k, v in raw.items()}


class SearchStartRequest(BaseModel):
    cv_id: str = Field(..., min_length=1)
    target_countries: List[str] = Field(..., min_length=1)
    min_match_score: float = Field(default=50.0, ge=0.0, le=100.0)
    name: Optional[str] = None
    job_categories: List[str] = []
    industries: List[str] = []
    experience_levels: List[str] = []
    employment_types: List[str] = []
    work_modes: List[str] = []  # remote | hybrid | onsite
    visa_sponsorship_only: bool = False
    english_only: bool = False
    fresh_graduate: bool = False
    internship: bool = False
    entry_level: bool = False
    custom_keywords: List[str] = []
    matching_weights: Optional[MatchingWeights] = None
    max_results_per_source: int = Field(default=25, ge=5, le=100)
    enabled_source_slugs: List[str] = []

    @model_validator(mode="after")
    def validate_countries(self) -> "SearchStartRequest":
        cleaned = [c.strip() for c in self.target_countries if c and c.strip()]
        if not cleaned:
            raise ValueError("At least one target country is required.")
        self.target_countries = cleaned
        return self


class AgentLogResponse(BaseModel):
    id: str
    agent_name: str
    stage: str
    level: str
    message: str
    metrics: Dict[str, Any] = {}
    duration_ms: Optional[int] = None
    created_at: datetime


class SearchSessionResponse(BaseModel):
    id: str
    user_id: str
    cv_id: str
    preference_id: str
    status: str
    current_stage: str
    progress_percent: int
    config_snapshot: Dict[str, Any] = {}
    generated_queries: List[str] = []
    sources_searched_count: int
    sources_searched: List[Dict[str, Any]] = []
    sources_unavailable: List[Dict[str, Any]] = []
    jobs_discovered_count: int
    jobs_verified_count: int
    duplicates_removed_count: int
    expired_removed_count: int
    below_threshold_count: int
    jobs_matched_count: int
    coverage_report: Dict[str, Any] = {}
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    logs: List[AgentLogResponse] = []


class JobSourceInfoResponse(BaseModel):
    slug: str
    name: str
    source_type: str
    base_url: str
    requires_api_key: bool
    api_key_configured: bool
    api_key_env_vars: List[str] = []
    supported_countries: List[str] = []
    is_enabled: bool = True
    rate_limit_rpm: int = 30
    terms_notes: str = ""
