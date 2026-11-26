"""Tests for production/deployment hardening:
  - Hosted-Postgres URL normalization and the production secret guard
  - Database-backed encrypted CV storage (hosts without persistent disks)
  - Safe Content-Disposition for non-ASCII filenames
  - Mid-run search cancellation and failure recovery in the orchestrator
  - SSE stream termination for finished sessions
  - Failed-login throttling
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.models.entities import SearchSession, UploadedCV
from tests.conftest import build_sample_pdf_bytes

CV_LINES = [
    "Ada Example",
    "Software Engineer",
    "Education",
    "Bachelor of Science in Computer Science, Example University",
    "Technical Skills",
    "Python, SQL, Docker, Git",
]


async def _register(client, email: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "ValidPassword123", "full_name": "Ada Example"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _upload(client, headers, filename: str = "ada_cv.pdf") -> dict:
    resp = await client.post(
        "/api/v1/cvs/upload",
        headers=headers,
        files={"file": (filename, build_sample_pdf_bytes(CV_LINES), "application/pdf")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("postgres://u:p@host:5432/db", "postgresql+asyncpg://u:p@host:5432/db"),
        ("postgresql://u:p@host/db", "postgresql+asyncpg://u:p@host/db"),
        ("postgresql://u:p@host/db?sslmode=require", "postgresql+asyncpg://u:p@host/db?ssl=require"),
        ("postgresql+asyncpg://u:p@host/db", "postgresql+asyncpg://u:p@host/db"),
        ("sqlite+aiosqlite:///./data/x.db", "sqlite+aiosqlite:///./data/x.db"),
    ],
)
def test_database_url_normalization(raw, expected):
    assert Settings(_env_file=None, DATABASE_URL=raw).DATABASE_URL == expected


def test_file_encryption_key_accepts_any_secret():
    from cryptography.fernet import Fernet

    proper = Fernet.generate_key().decode()
    assert Settings(_env_file=None, FILE_ENCRYPTION_KEY=proper).effective_fernet_key == proper.encode()
    derived = Settings(_env_file=None, FILE_ENCRYPTION_KEY="host-generated-random-value").effective_fernet_key
    Fernet(derived)  # valid key


def test_production_rejects_default_jwt_secret():
    with pytest.raises(ValueError):
        Settings(_env_file=None, APP_ENV="production")
    ok = Settings(_env_file=None, APP_ENV="production", JWT_SECRET_KEY="x" * 48)
    assert ok.is_production


@pytest.mark.asyncio
async def test_db_storage_backend_roundtrip_and_unicode_filename(test_env, monkeypatch):
    client, session_factory = test_env
    import app.core.storage as storage_mod

    monkeypatch.setattr(storage_mod.storage_service.settings, "STORAGE_BACKEND", "db")
    headers = await _register(client, "dbstore@example.com")
    original = build_sample_pdf_bytes(CV_LINES)
    resp = await client.post(
        "/api/v1/cvs/upload",
        headers=headers,
        files={"file": ("Résumé \"final\".pdf", original, "application/pdf")},
    )
    assert resp.status_code == 201, resp.text
    cv_id = resp.json()["id"]

    async with session_factory() as db:
        row = (await db.execute(select(UploadedCV).where(UploadedCV.id == cv_id))).scalar_one()
        assert row.storage_backend == "db"
        assert row.encrypted_storage_path.startswith("db://")

    dl = await client.get(f"/api/v1/cvs/{cv_id}/download", headers=headers)
    assert dl.status_code == 200
    assert dl.content == original
    disposition = dl.headers["content-disposition"]
    assert "filename*=UTF-8''R%C3%A9sum%C3%A9" in disposition

    deleted = await client.delete(f"/api/v1/cvs/{cv_id}", headers=headers)
    assert deleted.status_code == 204


async def _start_search(client, headers, cv_id: str, monkeypatch) -> str:
    import app.api.routes.searches as searches_mod

    monkeypatch.setattr(searches_mod, "dispatch_search_session", lambda sid: "test")
    resp = await client.post(
        "/api/v1/searches",
        headers=headers,
        json={"cv_id": cv_id, "target_countries": ["Germany"], "min_match_score": 50},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_cancel_during_run_is_honoured(test_env, monkeypatch):
    client, session_factory = test_env
    headers = await _register(client, "cancel@example.com")
    cv = await _upload(client, headers)
    session_id = await _start_search(client, headers, cv["id"], monkeypatch)

    import app.agents.orchestrator as orch_mod

    async def discover_then_user_cancels(profile, pref, custom_ats_boards=None):
        cancel = await client.post(f"/api/v1/searches/{session_id}/cancel", headers=headers)
        assert cancel.status_code == 200
        return [], [], [], []

    monkeypatch.setattr(orch_mod.job_discovery_agent, "discover", discover_then_user_cancels)
    await orch_mod.agent_orchestrator.execute_search_session(session_id)

    async with session_factory() as db:
        s = (await db.execute(select(SearchSession).where(SearchSession.id == session_id))).scalar_one()
        assert s.status == "cancelled"
        assert s.completed_at is not None


@pytest.mark.asyncio
async def test_agent_crash_marks_session_failed(test_env, monkeypatch):
    client, session_factory = test_env
    headers = await _register(client, "crash@example.com")
    cv = await _upload(client, headers)
    session_id = await _start_search(client, headers, cv["id"], monkeypatch)

    import app.agents.orchestrator as orch_mod

    async def boom(profile, pref, custom_ats_boards=None):
        raise RuntimeError("source exploded")

    monkeypatch.setattr(orch_mod.job_discovery_agent, "discover", boom)
    await orch_mod.agent_orchestrator.execute_search_session(session_id)

    detail = await client.get(f"/api/v1/searches/{session_id}", headers=headers)
    body = detail.json()
    assert body["status"] == "failed"
    assert "source exploded" in body["error_message"]

    # A finished session's SSE stream sends one terminal event and closes.
    stream = await client.get(f"/api/v1/searches/{session_id}/stream", headers=headers)
    assert stream.status_code == 200
    assert '"terminal": true' in stream.text


@pytest.mark.asyncio
async def test_account_deletion_removes_everything(test_env, monkeypatch):
    client, session_factory = test_env
    headers = await _register(client, "leaver@example.com")
    cv = await _upload(client, headers)
    session_id = await _start_search(client, headers, cv["id"], monkeypatch)

    import app.agents.orchestrator as orch_mod
    from app.services.job_sources.base import RawDiscoveredJob

    async def one_job(profile, pref, custom_ats_boards=None):
        job = RawDiscoveredJob(
            source_slug="remotive",
            source_name="Remotive",
            external_id="del-1",
            title="Python Developer",
            company_name="Acme",
            location_raw="Berlin, Germany",
            source_url="https://example.com/jobs/1",
            apply_url="https://example.com/jobs/1",
            description_raw="Required: Python, SQL, Docker. Bachelor's degree in Computer Science.",
        )
        return [job], ["Python"], [{"slug": "remotive", "name": "Remotive", "jobs_found": 1}], []

    monkeypatch.setattr(orch_mod.job_discovery_agent, "discover", one_job)
    monkeypatch.setattr(orch_mod.verification_agent.settings, "VERIFY_LIVE_URLS", False, raising=False)
    await orch_mod.agent_orchestrator.execute_search_session(session_id)

    jobs = await client.get(f"/api/v1/jobs?session_id={session_id}", headers=headers)
    assert jobs.status_code == 200
    matches = jobs.json()
    assert matches, "expected the Python job to match the Python CV"
    saved = await client.post(
        "/api/v1/tracker/saved", headers=headers, json={"job_id": matches[0]["job_id"]}
    )
    assert saved.status_code == 201, saved.text

    resp = await client.delete("/api/v1/settings/account", headers=headers)
    assert resp.status_code == 204, resp.text

    async with session_factory() as db:
        assert (await db.execute(select(UploadedCV))).scalars().all() == []
        assert (await db.execute(select(SearchSession))).scalars().all() == []
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_failed_logins_are_throttled(test_env):
    client, _ = test_env
    await _register(client, "throttle@example.com")
    import app.api.routes.auth as auth_mod

    auth_mod._failed_logins.clear()
    try:
        for _ in range(auth_mod.LOGIN_MAX_FAILURES):
            bad = await client.post(
                "/api/v1/auth/login", json={"email": "throttle@example.com", "password": "WrongPassword1"}
            )
            assert bad.status_code == 401
        blocked = await client.post(
            "/api/v1/auth/login", json={"email": "throttle@example.com", "password": "ValidPassword123"}
        )
        assert blocked.status_code == 429
    finally:
        auth_mod._failed_logins.clear()
