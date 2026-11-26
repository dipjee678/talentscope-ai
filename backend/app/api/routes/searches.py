"""Autonomous AI Job Search session routes + Server-Sent Events (SSE) live progress stream."""
from __future__ import annotations

import asyncio
import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents import orchestrator as orchestrator_module
from app.agents.orchestrator import TERMINAL_STATUSES, search_event_bus
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.entities import (
    DEFAULT_MATCHING_WEIGHTS,
    SearchPreference,
    SearchSession,
    UploadedCV,
    User,
)
from app.schemas.search import (
    AgentLogResponse,
    SearchSessionResponse,
    SearchStartRequest,
)
from app.workers.tasks import dispatch_search_session

router = APIRouter(prefix="/searches", tags=["Autonomous Job Search"])


def serialize_session(s: SearchSession, include_logs: bool = True) -> SearchSessionResponse:
    logs = []
    if include_logs and s.logs:
        ordered_logs = sorted(s.logs, key=lambda lg: lg.created_at)
        logs = [
            AgentLogResponse(
                id=lg.id,
                agent_name=lg.agent_name,
                stage=lg.stage,
                level=lg.level,
                message=lg.message,
                metrics=lg.metrics_json or {},
                duration_ms=lg.duration_ms,
                created_at=lg.created_at,
            )
            for lg in ordered_logs
        ]
    return SearchSessionResponse(
        id=s.id,
        user_id=s.user_id,
        cv_id=s.cv_id,
        preference_id=s.preference_id,
        status=s.status,
        current_stage=s.current_stage,
        progress_percent=s.progress_percent,
        config_snapshot=s.config_snapshot_json or {},
        generated_queries=s.generated_queries_json or [],
        sources_searched_count=s.sources_searched_count,
        sources_searched=s.sources_searched_json or [],
        sources_unavailable=s.sources_unavailable_json or [],
        jobs_discovered_count=s.jobs_discovered_count,
        jobs_verified_count=s.jobs_verified_count,
        duplicates_removed_count=s.duplicates_removed_count,
        expired_removed_count=s.expired_removed_count,
        below_threshold_count=s.below_threshold_count,
        jobs_matched_count=s.jobs_matched_count,
        coverage_report=s.coverage_report_json or {},
        error_message=s.error_message,
        started_at=s.started_at,
        completed_at=s.completed_at,
        created_at=s.created_at,
        logs=logs,
    )


@router.post("", response_model=SearchSessionResponse, status_code=status.HTTP_201_CREATED)
async def start_ai_job_search(
    payload: SearchStartRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchSessionResponse:
    cv_stmt = (
        select(UploadedCV)
        .options(selectinload(UploadedCV.profile))
        .where(UploadedCV.id == payload.cv_id, UploadedCV.user_id == current_user.id)
    )
    cv = (await db.execute(cv_stmt)).scalar_one_or_none()
    if not cv or not cv.profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Selected CV or structured candidate profile was not found.",
        )

    weights = (
        payload.matching_weights.normalized_dict()
        if payload.matching_weights
        else (current_user.default_weights_json or dict(DEFAULT_MATCHING_WEIGHTS))
    )

    pref = SearchPreference(
        user_id=current_user.id,
        cv_id=cv.id,
        name=payload.name or f"Search: {', '.join(payload.target_countries[:3])}",
        target_countries_json=payload.target_countries,
        min_match_score=payload.min_match_score,
        job_categories_json=payload.job_categories,
        industries_json=payload.industries,
        experience_levels_json=payload.experience_levels,
        employment_types_json=payload.employment_types,
        work_modes_json=payload.work_modes,
        visa_sponsorship_only=payload.visa_sponsorship_only,
        english_only=payload.english_only,
        fresh_graduate=payload.fresh_graduate,
        internship=payload.internship,
        entry_level=payload.entry_level,
        custom_keywords_json=payload.custom_keywords,
        matching_weights_json=weights,
        max_results_per_source=payload.max_results_per_source,
        enabled_source_slugs_json=payload.enabled_source_slugs,
    )
    db.add(pref)
    await db.flush()

    snapshot = {
        "cv_filename": cv.original_filename,
        "target_countries": payload.target_countries,
        "min_match_score": payload.min_match_score,
        "job_categories": payload.job_categories,
        "industries": payload.industries,
        "experience_levels": payload.experience_levels,
        "employment_types": payload.employment_types,
        "work_modes": payload.work_modes,
        "visa_sponsorship_only": payload.visa_sponsorship_only,
        "english_only": payload.english_only,
        "fresh_graduate": payload.fresh_graduate,
        "internship": payload.internship,
        "entry_level": payload.entry_level,
        "matching_weights": weights,
    }

    session_obj = SearchSession(
        user_id=current_user.id,
        cv_id=cv.id,
        preference_id=pref.id,
        status="queued",
        current_stage="queued",
        progress_percent=2,
        config_snapshot_json=snapshot,
    )
    db.add(session_obj)
    await db.commit()

    dispatch_search_session(session_obj.id)

    loaded = (
        await db.execute(
            select(SearchSession)
            .options(selectinload(SearchSession.logs))
            .where(SearchSession.id == session_obj.id)
        )
    ).scalar_one()
    return serialize_session(loaded)


@router.get("", response_model=List[SearchSessionResponse])
async def list_search_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[SearchSessionResponse]:
    stmt = (
        select(SearchSession)
        .options(selectinload(SearchSession.logs))
        .where(SearchSession.user_id == current_user.id)
        .order_by(SearchSession.created_at.desc())
        .limit(50)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [serialize_session(s, include_logs=False) for s in rows]


@router.get("/{session_id}", response_model=SearchSessionResponse)
async def get_search_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchSessionResponse:
    stmt = (
        select(SearchSession)
        .options(selectinload(SearchSession.logs))
        .where(SearchSession.id == session_id, SearchSession.user_id == current_user.id)
    )
    session_obj = (await db.execute(stmt)).scalar_one_or_none()
    if not session_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search session not found.")
    return serialize_session(session_obj, include_logs=True)


@router.post("/{session_id}/cancel", response_model=SearchSessionResponse)
async def cancel_search_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchSessionResponse:
    stmt = (
        select(SearchSession)
        .options(selectinload(SearchSession.logs))
        .where(SearchSession.id == session_id, SearchSession.user_id == current_user.id)
    )
    session_obj = (await db.execute(stmt)).scalar_one_or_none()
    if not session_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search session not found.")
    if session_obj.status in ("queued", "running"):
        session_obj.status = "cancelled"
        session_obj.current_stage = "cancelled"
        await db.commit()
    return serialize_session(session_obj)


SSE_KEEPALIVE_SECONDS = 15.0
SSE_EVENT_END = "\n\n"
SSE_KEEPALIVE_COMMENT = ": keepalive" + SSE_EVENT_END


def _sse(payload: dict) -> str:
    return "data: " + json.dumps(payload) + SSE_EVENT_END


async def _current_status(session_id: str) -> str | None:
    async with orchestrator_module.AsyncSessionLocal() as fresh_db:
        return (
            await fresh_db.execute(select(SearchSession.status).where(SearchSession.id == session_id))
        ).scalar_one_or_none()


@router.get("/{session_id}/stream")
async def stream_search_progress(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    # Subscribe before reading the status so no event published in between is lost.
    queue = search_event_bus.open(session_id)
    stmt = select(SearchSession).where(
        SearchSession.id == session_id, SearchSession.user_id == current_user.id
    )
    session_obj = (await db.execute(stmt)).scalar_one_or_none()
    if not session_obj:
        search_event_bus.close(session_id, queue)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search session not found.")

    initial = {
        "session_id": session_obj.id,
        "status": session_obj.status,
        "stage": session_obj.current_stage,
        "progress_percent": session_obj.progress_percent,
        "terminal": session_obj.status in TERMINAL_STATUSES,
    }

    async def event_generator():
        try:
            yield _sse(initial)
            if initial["terminal"]:
                return
            while True:
                try:
                    evt = await asyncio.wait_for(queue.get(), timeout=SSE_KEEPALIVE_SECONDS)
                except asyncio.TimeoutError:
                    # Idle: the search may be running in another process (Celery) or have died.
                    current = await _current_status(session_id)
                    if current is None or current in TERMINAL_STATUSES:
                        yield _sse({"session_id": session_id, "status": current, "terminal": True})
                        return
                    yield SSE_KEEPALIVE_COMMENT
                    continue
                yield _sse(evt)
                if evt.get("terminal"):
                    return
        finally:
            search_event_bus.close(session_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
