"""Saved jobs and application tracking schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.job import JobListingResponse

VALID_APPLICATION_STATUSES = (
    "saved",
    "interested",
    "applied",
    "assessment",
    "interview",
    "offer",
    "rejected",
)


class SaveJobRequest(BaseModel):
    job_id: str
    notes: Optional[str] = None


class SavedJobResponse(BaseModel):
    id: str
    job_id: str
    notes: Optional[str] = None
    created_at: datetime
    job: JobListingResponse


class ApplicationUpsertRequest(BaseModel):
    job_id: str
    status: str = Field(
        default="saved",
        pattern="^(saved|interested|applied|assessment|interview|offer|rejected)$",
    )
    applied_at: Optional[datetime] = None
    application_url: Optional[str] = None
    notes: Optional[str] = None
    follow_up_at: Optional[datetime] = None


class ApplicationUpdateRequest(BaseModel):
    status: Optional[str] = Field(
        default=None,
        pattern="^(saved|interested|applied|assessment|interview|offer|rejected)$",
    )
    applied_at: Optional[datetime] = None
    application_url: Optional[str] = None
    notes: Optional[str] = None
    follow_up_at: Optional[datetime] = None


class ApplicationResponse(BaseModel):
    id: str
    user_id: str
    job_id: str
    status: str
    applied_at: Optional[datetime] = None
    application_url: Optional[str] = None
    notes: Optional[str] = None
    follow_up_at: Optional[datetime] = None
    history: List[Dict[str, Any]] = []
    match_score: Optional[float] = None
    job: JobListingResponse
    created_at: datetime
    updated_at: datetime
