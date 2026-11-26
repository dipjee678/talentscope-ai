"""Celery + Redis configuration and hybrid local-asyncio task dispatcher."""
from __future__ import annotations

import asyncio
import logging
from typing import Set

from celery import Celery

from app.agents.orchestrator import agent_orchestrator
from app.core.config import get_settings
from app.core.database import engine

logger = logging.getLogger(__name__)
settings = get_settings()

celery_app = Celery(
    "talentscope_workers",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,
    task_soft_time_limit=540,
    worker_prefetch_multiplier=1,
)

# Keep references to background asyncio tasks in local mode so they aren't garbage collected
_active_local_tasks: Set[asyncio.Task] = set()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=10, name="run_search_session_task")
def run_search_session_celery(self, session_id: str) -> str:
    async def _run() -> None:
        try:
            await agent_orchestrator.execute_search_session(session_id)
        finally:
            # asyncio.run() creates a fresh loop per task; pooled asyncpg connections are bound to
            # the loop that opened them, so release them before this loop closes.
            await engine.dispose()

    asyncio.run(_run())
    return session_id


def dispatch_search_session(session_id: str) -> str:
    """Dispatch autonomous search to Celery (production) or asyncio background task (local dev)."""
    cfg = get_settings()
    if cfg.TASK_RUNNER_MODE.lower() == "celery":
        run_search_session_celery.delay(session_id)
        return "celery"

    task = asyncio.create_task(agent_orchestrator.execute_search_session(session_id))
    _active_local_tasks.add(task)
    task.add_done_callback(_active_local_tasks.discard)
    return "local_async"
