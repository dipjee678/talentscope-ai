"""Central Agent Orchestrator.

Coordinates all 7 specialized agents across an asynchronous, observable pipeline:
  1. CVAnalysisAgent (verifies candidate profile readiness)
  2. JobDiscoveryAgent (parallel multi-source search)
  3. JobExtractionAgent (HTML cleaning, prompt-injection stripping, requirement structuring)
  4. VerificationAgent (deduplication + live link & expiration verification)
  5. MatchingAgent (6-dimension weighted CV-to-job scoring)
  6. RankingAgent (threshold filtering + preference-aware ranking)
  7. ReportingAgent (coverage report + dashboard notification)
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.agents.job_discovery_agent import job_discovery_agent
from app.agents.job_extraction_agent import job_extraction_agent
from app.agents.matching_agent import matching_agent
from app.agents.ranking_agent import ranking_agent
from app.agents.reporting_agent import reporting_agent
from app.agents.verification_agent import verification_agent
from app.core.database import AsyncSessionLocal
from app.models.entities import (
    AgentExecutionLog,
    CandidateProfile,
    JobListing,
    JobMatch,
    JobRequirement,
    Notification,
    SearchPreference,
    SearchSession,
    UploadedCV,
    User,
)

logger = logging.getLogger(__name__)


class SearchEventBus:
    """In-process pub/sub event bus for real-time Server-Sent Events (SSE) progress updates."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[asyncio.Queue[Dict[str, Any]]]] = defaultdict(list)

    def publish(self, session_id: str, event: Dict[str, Any]) -> None:
        for q in list(self._subscribers.get(session_id, [])):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def open(self, session_id: str) -> "asyncio.Queue[Dict[str, Any]]":
        queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=100)
        self._subscribers[session_id].append(queue)
        return queue

    def close(self, session_id: str, queue: "asyncio.Queue[Dict[str, Any]]") -> None:
        subs = self._subscribers.get(session_id)
        if subs and queue in subs:
            subs.remove(queue)
        if subs is not None and not subs:
            self._subscribers.pop(session_id, None)

    async def subscribe(self, session_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=100)
        self._subscribers[session_id].append(queue)
        try:
            while True:
                item = await queue.get()
                yield item
                if item.get("terminal"):
                    break
        finally:
            if queue in self._subscribers.get(session_id, []):
                self._subscribers[session_id].remove(queue)


search_event_bus = SearchEventBus()


class SearchCancelled(Exception):
    """Raised between stages when the user cancelled the session."""


TERMINAL_STATUSES = ("completed", "failed", "cancelled")


class AgentOrchestrator:
    async def _raise_if_cancelled(self, db, session_id: str) -> None:
        current = (
            await db.execute(select(SearchSession.status).where(SearchSession.id == session_id))
        ).scalar_one_or_none()
        if current == "cancelled":
            raise SearchCancelled()

    async def _log_stage(
        self,
        db,
        session_obj: SearchSession,
        agent_name: str,
        stage: str,
        progress: int,
        message: str,
        level: str = "info",
        metrics: Dict[str, Any] | None = None,
        duration_ms: int | None = None,
        check_cancel: bool = True,
    ) -> None:
        if check_cancel:
            await self._raise_if_cancelled(db, session_obj.id)
        session_obj.current_stage = stage
        session_obj.progress_percent = progress
        log_entry = AgentExecutionLog(
            search_session_id=session_obj.id,
            agent_name=agent_name,
            stage=stage,
            level=level,
            message=message,
            metrics_json=metrics or {},
            duration_ms=duration_ms,
        )
        db.add(log_entry)
        await db.commit()

        search_event_bus.publish(
            session_obj.id,
            {
                "session_id": session_obj.id,
                "status": session_obj.status,
                "stage": stage,
                "progress_percent": progress,
                "agent_name": agent_name,
                "level": level,
                "message": message,
                "metrics": metrics or {},
                "terminal": session_obj.status in TERMINAL_STATUSES,
            },
        )

    async def execute_search_session(self, session_id: str) -> None:
        async with AsyncSessionLocal() as db:
            session_obj = (
                await db.execute(select(SearchSession).where(SearchSession.id == session_id))
            ).scalar_one_or_none()
            if not session_obj or session_obj.status == "cancelled":
                return

            session_obj.status = "running"
            session_obj.started_at = datetime.now(timezone.utc)
            await db.commit()

            try:
                # Stage 1: Load & verify CV Candidate Profile
                t_stage = time.monotonic()
                user = (await db.execute(select(User).where(User.id == session_obj.user_id))).scalar_one()
                pref = (
                    await db.execute(select(SearchPreference).where(SearchPreference.id == session_obj.preference_id))
                ).scalar_one()
                cv = (
                    await db.execute(
                        select(UploadedCV)
                        .options(selectinload(UploadedCV.profile).selectinload(CandidateProfile.skills))
                        .where(UploadedCV.id == session_obj.cv_id)
                    )
                ).scalar_one_or_none()

                if not cv or not cv.profile:
                    raise ValueError("Uploaded CV or structured candidate profile not found.")

                profile = cv.profile
                skill_total = len(profile.programming_languages_json or []) + len(profile.technical_skills_json or [])
                await self._log_stage(
                    db,
                    session_obj,
                    "CVAnalysisAgent",
                    "cv_verification",
                    12,
                    f"Loaded structured candidate profile ({skill_total} technical skills, degree: {profile.highest_degree or 'unstated'}).",
                    metrics={"skills_count": skill_total},
                    duration_ms=int((time.monotonic() - t_stage) * 1000),
                )

                # Stage 2: Autonomous Multi-Source Job Discovery
                t_stage = time.monotonic()
                await self._log_stage(
                    db,
                    session_obj,
                    "JobDiscoveryAgent",
                    "discovering_jobs",
                    25,
                    f"Initiating parallel search across permitted sources for {', '.join(pref.target_countries_json)}...",
                )
                raw_jobs, queries, searched_sources, unavailable_sources = await job_discovery_agent.discover(
                    profile=profile,
                    pref=pref,
                    custom_ats_boards=user.custom_ats_boards_json or [],
                )
                session_obj.generated_queries_json = queries
                session_obj.sources_searched_count = len(searched_sources)
                session_obj.sources_searched_json = searched_sources
                session_obj.sources_unavailable_json = unavailable_sources
                session_obj.jobs_discovered_count = len(raw_jobs)
                await self._log_stage(
                    db,
                    session_obj,
                    "JobDiscoveryAgent",
                    "discovery_complete",
                    45,
                    f"Discovered {len(raw_jobs)} raw job postings across {len(searched_sources)} active job sources using {len(queries)} search queries.",
                    metrics={
                        "sources_searched": len(searched_sources),
                        "raw_jobs": len(raw_jobs),
                        "queries": queries,
                    },
                    duration_ms=int((time.monotonic() - t_stage) * 1000),
                )

                # Stage 3: Job Extraction & Structuring
                t_stage = time.monotonic()
                transient_jobs: List[JobListing] = []
                reqs_by_job_idx: Dict[str, List[JobRequirement]] = {}

                for raw in raw_jobs:
                    if not raw.title or not raw.apply_url:
                        continue
                    bundle = job_extraction_agent.extract(raw)
                    job_entity = JobListing(**bundle.listing_fields)
                    db.add(job_entity)
                    await db.flush()

                    req_entities: List[JobRequirement] = []
                    for r_dict in bundle.requirements:
                        req_ent = JobRequirement(job_id=job_entity.id, **r_dict)
                        db.add(req_ent)
                        req_entities.append(req_ent)

                    transient_jobs.append(job_entity)
                    reqs_by_job_idx[job_entity.id] = req_entities

                await db.commit()
                await self._log_stage(
                    db,
                    session_obj,
                    "JobExtractionAgent",
                    "extraction_complete",
                    60,
                    f"Extracted structured requirements, mandatory vs preferred skills, and metadata for {len(transient_jobs)} listings.",
                    metrics={"extracted_count": len(transient_jobs)},
                    duration_ms=int((time.monotonic() - t_stage) * 1000),
                )

                # Stage 4: Verification & Duplicate Detection
                t_stage = time.monotonic()
                active_jobs, ver_metrics = await verification_agent.verify_and_deduplicate(transient_jobs)
                session_obj.duplicates_removed_count = ver_metrics["duplicates_removed"]
                session_obj.expired_removed_count = ver_metrics["expired_or_broken_removed"]
                session_obj.jobs_verified_count = ver_metrics["verified_active"] + ver_metrics["unverified"]
                await db.commit()

                await self._log_stage(
                    db,
                    session_obj,
                    "VerificationAgent",
                    "verification_complete",
                    78,
                    (
                        f"Deduplicated {ver_metrics['duplicates_removed']} duplicate(s), filtered "
                        f"{ver_metrics['expired_or_broken_removed']} expired/broken link(s), leaving "
                        f"{len(active_jobs)} active listings ({ver_metrics['verified_active']} HTTP-verified)."
                    ),
                    metrics=ver_metrics,
                    duration_ms=int((time.monotonic() - t_stage) * 1000),
                )

                # Stage 5: Intelligent CV-to-Job Matching
                t_stage = time.monotonic()
                evaluated_pairs: List[Tuple[JobListing, Dict[str, Any]]] = []
                for job_entity in active_jobs:
                    eval_res = matching_agent.evaluate(
                        profile=profile,
                        job=job_entity,
                        requirements=reqs_by_job_idx.get(job_entity.id, []),
                        weights=pref.matching_weights_json,
                        visa_required_by_user=pref.visa_sponsorship_only,
                    )
                    evaluated_pairs.append((job_entity, eval_res))

                await self._log_stage(
                    db,
                    session_obj,
                    "MatchingAgent",
                    "matching_complete",
                    90,
                    f"Computed 6-dimension CV matching scores and explanations for {len(evaluated_pairs)} verified listings.",
                    metrics={"evaluated_jobs": len(evaluated_pairs)},
                    duration_ms=int((time.monotonic() - t_stage) * 1000),
                )

                # Stage 6: Ranking & Threshold Filtering
                t_stage = time.monotonic()
                qualifying_pairs, rank_metrics = ranking_agent.filter_and_rank(evaluated_pairs, pref)
                session_obj.below_threshold_count = rank_metrics["below_threshold_excluded"]
                session_obj.jobs_matched_count = len(qualifying_pairs)

                for job_entity, m_data in qualifying_pairs:
                    db.add(
                        JobMatch(
                            search_session_id=session_obj.id,
                            user_id=session_obj.user_id,
                            job_id=job_entity.id,
                            profile_id=profile.id,
                            overall_score=m_data["overall_score"],
                            rank_score=m_data["rank_score"],
                            technical_skills_score=m_data["technical_skills_score"],
                            education_score=m_data["education_score"],
                            experience_score=m_data["experience_score"],
                            qualifications_score=m_data["qualifications_score"],
                            projects_score=m_data["projects_score"],
                            role_relevance_score=m_data["role_relevance_score"],
                            weights_used_json=m_data["weights_used"],
                            matched_skills_json=m_data["matched_skills"],
                            missing_mandatory_skills_json=m_data["missing_mandatory_skills"],
                            missing_preferred_skills_json=m_data["missing_preferred_skills"],
                            unstated_on_cv_json=m_data["unstated_on_cv"],
                            matching_qualifications_json=m_data["matching_qualifications"],
                            experience_compatibility=m_data["experience_compatibility"],
                            education_compatibility=m_data["education_compatibility"],
                            explicit_disqualifiers_json=m_data["explicit_disqualifiers"],
                            score_explanation=m_data["score_explanation"],
                            strengths_json=m_data["strengths"],
                            weaknesses_json=m_data["weaknesses"],
                            calculation_breakdown_json=m_data["calculation_breakdown"],
                        )
                    )
                await db.commit()

                await self._log_stage(
                    db,
                    session_obj,
                    "RankingAgent",
                    "ranking_complete",
                    96,
                    (
                        f"Ranked {len(qualifying_pairs)} qualifying opportunities above "
                        f"{pref.min_match_score:g}% threshold ({rank_metrics['below_threshold_excluded']} below threshold excluded)."
                    ),
                    metrics=rank_metrics,
                    duration_ms=int((time.monotonic() - t_stage) * 1000),
                )

                # Stage 7: Reporting & Notifications
                t_stage = time.monotonic()
                report = reporting_agent.build_coverage_report(
                    target_countries=pref.target_countries_json,
                    min_match_score=pref.min_match_score,
                    generated_queries=queries,
                    searched_sources=searched_sources,
                    unavailable_sources=unavailable_sources,
                    discovered_count=len(raw_jobs),
                    verification_metrics=ver_metrics,
                    ranking_metrics=rank_metrics,
                )
                session_obj.coverage_report_json = report
                session_obj.status = "completed"
                session_obj.completed_at = datetime.now(timezone.utc)

                db.add(
                    Notification(
                        user_id=session_obj.user_id,
                        type="search_completed",
                        title=f"AI Job Search Complete: {len(qualifying_pairs)} Matches Found",
                        body=(
                            f"Searched {len(searched_sources)} sources for {', '.join(pref.target_countries_json)} "
                            f"and identified {len(qualifying_pairs)} qualifying role(s) ≥ {pref.min_match_score:g}%."
                        ),
                        link_url=f"/jobs?session_id={session_obj.id}",
                    )
                )
                await self._log_stage(
                    db,
                    session_obj,
                    "ReportingAgent",
                    "completed",
                    100,
                    f"Search complete! {len(qualifying_pairs)} verified, ranked job opportunities ready on your dashboard.",
                    metrics={"qualifying_matches": len(qualifying_pairs)},
                    duration_ms=int((time.monotonic() - t_stage) * 1000),
                )
            except SearchCancelled:
                await db.rollback()
                await db.refresh(session_obj)
                session_obj.status = "cancelled"
                session_obj.current_stage = "cancelled"
                session_obj.completed_at = datetime.now(timezone.utc)
                await self._log_stage(
                    db,
                    session_obj,
                    "AgentOrchestrator",
                    "cancelled",
                    session_obj.progress_percent,
                    "Search cancelled by user.",
                    level="warning",
                    check_cancel=False,
                )
            except Exception as exc:
                logger.exception("Orchestrator failed for session %s", session_id)
                # The failed statement leaves the transaction unusable; reset before recording failure.
                await db.rollback()
                await db.refresh(session_obj)
                session_obj.status = "failed"
                session_obj.error_message = str(exc)[:2000]
                session_obj.completed_at = datetime.now(timezone.utc)
                await self._log_stage(
                    db,
                    session_obj,
                    "AgentOrchestrator",
                    "failed",
                    session_obj.progress_percent,
                    f"Search encountered an unexpected error: {exc}",
                    level="error",
                    check_cancel=False,
                )


agent_orchestrator = AgentOrchestrator()
