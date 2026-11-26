"""AI Career Assistant request and response schemas."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AssistantRequest(BaseModel):
    action: str = Field(
        ...,
        pattern="^(explain_match|missing_skills|cv_improvements|cover_letter|interview_prep|learning_roadmap|compare_jobs|plain_english|free_chat)$",
    )
    cv_id: Optional[str] = None
    job_id: Optional[str] = None
    compare_job_ids: List[str] = []
    user_message: Optional[str] = Field(default=None, max_length=3000)
    tone: str = Field(default="professional", pattern="^(professional|concise|enthusiastic)$")


class AssistantResponse(BaseModel):
    action: str
    title: str
    content_markdown: str
    highlights: List[str] = []
    grounded_facts_used: Dict[str, Any] = {}
    generation_mode: str  # "llm_grounded" | "deterministic_grounded"
    disclaimer: str = (
        "Generated strictly from your verified CV profile and the target job listing. "
        "Please review before submitting any application materials."
    )
