"""CV upload and structured candidate profile schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CandidateSkillItem(BaseModel):
    id: Optional[str] = None
    skill_name: str
    normalized_name: Optional[str] = None
    category: str = "technical"
    proficiency: Optional[str] = None
    source_section: Optional[str] = None


class CandidateProfileResponse(BaseModel):
    id: str
    user_id: str
    cv_id: str
    full_name: Optional[str] = None
    headline: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    summary: Optional[str] = None
    years_of_experience: Optional[float] = None
    highest_degree: Optional[str] = None
    universities: List[str] = []
    education: List[Dict[str, Any]] = []
    programming_languages: List[str] = []
    technical_skills: List[str] = []
    soft_skills: List[str] = []
    experience: List[Dict[str, Any]] = []
    internships: List[Dict[str, Any]] = []
    projects: List[Dict[str, Any]] = []
    certifications: List[str] = []
    spoken_languages: List[str] = []
    career_interests: List[str] = []
    achievements: List[str] = []
    missing_or_unclear: List[str] = []
    extraction_mode: str = "hybrid_nlp"
    manually_edited: bool = False
    skills: List[CandidateSkillItem] = []
    created_at: datetime
    updated_at: datetime


class CandidateProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    headline: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    summary: Optional[str] = None
    years_of_experience: Optional[float] = Field(default=None, ge=0, le=60)
    highest_degree: Optional[str] = None
    universities: Optional[List[str]] = None
    education: Optional[List[Dict[str, Any]]] = None
    programming_languages: Optional[List[str]] = None
    technical_skills: Optional[List[str]] = None
    soft_skills: Optional[List[str]] = None
    experience: Optional[List[Dict[str, Any]]] = None
    internships: Optional[List[Dict[str, Any]]] = None
    projects: Optional[List[Dict[str, Any]]] = None
    certifications: Optional[List[str]] = None
    spoken_languages: Optional[List[str]] = None
    career_interests: Optional[List[str]] = None
    achievements: Optional[List[str]] = None


class UploadedCVResponse(BaseModel):
    id: str
    user_id: str
    original_filename: str
    file_extension: str
    content_type: str
    file_size_bytes: int
    version_number: int
    is_active: bool
    parse_status: str
    ocr_status: str
    security_scan_status: str
    security_scan_notes: List[str] = []
    prompt_injection_flags: List[str] = []
    created_at: datetime
    profile: Optional[CandidateProfileResponse] = None
