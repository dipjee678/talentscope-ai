"""Job source inspection routes."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.entities import User
from app.schemas.search import JobSourceInfoResponse
from app.services.job_sources.registry import get_all_connectors

router = APIRouter(prefix="/sources", tags=["Job Sources"])


@router.get("", response_model=List[JobSourceInfoResponse])
async def list_job_sources(
    current_user: User = Depends(get_current_user),
) -> List[JobSourceInfoResponse]:
    connectors = get_all_connectors()
    return [
        JobSourceInfoResponse(
            slug=c.slug,
            name=c.name,
            source_type=c.source_type,
            base_url=c.base_url,
            requires_api_key=c.requires_api_key,
            api_key_configured=c.is_configured(),
            api_key_env_vars=c.api_key_env_vars,
            supported_countries=c.supported_countries,
            is_enabled=True,
            rate_limit_rpm=c.rate_limit_rpm,
            terms_notes=c.terms_notes,
        )
        for c in connectors
    ]
