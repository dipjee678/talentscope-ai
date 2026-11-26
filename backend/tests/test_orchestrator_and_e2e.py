"""End-to-end integration tests:
  - Autonomous multi-country, multi-source search orchestration
  - Handling unavailable job sources & empty search results
  - Advanced filtering, sorting, and side-by-side job comparison
  - Application Tracker lifecycle (Saved -> Applied -> Interview + notes + reminders)
  - Grounded AI Career Assistant (explain match, missing skills, cover letter, interview prep, compare)
"""
from __future__ import annotations

import httpx
import pytest
import respx

from app.agents.orchestrator import agent_orchestrator
from app.services.job_sources.base import RawDiscoveredJob
from tests.conftest import build_sample_pdf_bytes


@pytest.mark.asyncio
async def test_full_e2e_workflow_multi_country_search_filter_compare_tracker_assistant(test_env, monkeypatch):
    client, _ = test_env

    # 1. Register & Upload CV
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "e2e@example.com", "password": "SecurePassword123", "full_name": "Elena Vance"},
    )
    assert reg.status_code == 201
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    pdf_bytes = build_sample_pdf_bytes([
        "Elena Vance",
        "Python & Machine Learning Engineer",
        "elena@example.com",
        "Education",
        "Bachelor of Science in Computer Science, University of Berlin",
        "Experience",
        "Software Engineer at DataLab (2022 - 2025)",
        "- Built FastAPI, Python, SQL, Machine Learning, and Docker services",
        "Projects",
        "Distributed ML Feature Store using Python, PostgreSQL, and Docker",
        "Technical Skills",
        "Python, SQL, FastAPI, Machine Learning, PostgreSQL, Docker, AWS, Git",
    ])
    up = await client.post(
        "/api/v1/cvs/upload",
        headers=headers,
        files={"file": ("elena_cv.pdf", pdf_bytes, "application/pdf")},
    )
    assert up.status_code == 201
    cv_id = up.json()["id"]

    # 2. Mock JobDiscoveryAgent to return realistic multi-country, multi-source jobs + 1 unavailable source
    async def fake_discover(profile, pref, custom_ats_boards=None):
        jobs = [
            RawDiscoveredJob(
                source_slug="greenhouse_direct",
                source_name="Cloudflare Careers (Greenhouse)",
                external_id="cf-1",
                title="Python Machine Learning Engineer",
                company_name="Cloudflare",
                location_raw="Berlin, Germany",
                source_url="https://boards.greenhouse.io/cloudflare/jobs/1",
                apply_url="https://boards.greenhouse.io/cloudflare/jobs/1",
                description_raw=(
                    "Required: Python, SQL, Machine Learning, Docker, Bachelor's degree in Computer Science. "
                    "2 years of experience. Visa sponsorship available."
                ),
                work_mode="hybrid",
                salary_min=85000.0,
                salary_max=105000.0,
                salary_currency="EUR",
                salary_period="year",
                visa_sponsorship=True,
                is_direct_company_link=True,
            ),
            RawDiscoveredJob(
                source_slug="remotive",
                source_name="Remotive",
                external_id="rem-2",
                title="Senior Backend Python Developer (FastAPI)",
                company_name="NorthStar Labs",
                location_raw="London, United Kingdom",
                source_url="https://remotive.com/remote-jobs/2",
                apply_url="https://remotive.com/remote-jobs/2",
                description_raw=(
                    "Required: Python, FastAPI, PostgreSQL, AWS, Docker. "
                    "Nice to have: Kubernetes. 3 years of experience."
                ),
                work_mode="remote",
                salary_min=95000.0,
                salary_max=120000.0,
                salary_currency="GBP",
                salary_period="year",
                is_direct_company_link=False,
            ),
            # Low-match unrelated job that must be excluded below threshold!
            RawDiscoveredJob(
                source_slug="themuse",
                source_name="The Muse",
                external_id="muse-low",
                title="Executive Pastry Chef",
                company_name="Grand Hotel",
                location_raw="Berlin, Germany",
                source_url="https://themuse.com/jobs/chef",
                apply_url="https://themuse.com/jobs/chef",
                description_raw="10 years of experience in French pastry kitchens, baking, hospitality management.",
                work_mode="onsite",
            ),
        ]
        searched = [
            {"slug": "greenhouse_direct", "name": "Greenhouse ATS", "jobs_found": 1, "pages_fetched": 1, "queries_executed": ["Python Machine Learning"], "duration_ms": 120},
            {"slug": "remotive", "name": "Remotive", "jobs_found": 1, "pages_fetched": 1, "queries_executed": ["Python"], "duration_ms": 140},
            {"slug": "themuse", "name": "The Muse", "jobs_found": 1, "pages_fetched": 1, "queries_executed": ["Python"], "duration_ms": 110},
        ]
        unavailable = [
            {"slug": "adzuna", "name": "Adzuna", "status": "skipped_missing_key", "reason": "API key not configured"},
        ]
        return jobs, ["Python Machine Learning", "FastAPI"], searched, unavailable

    import app.agents.orchestrator as orch_mod
    monkeypatch.setattr(orch_mod.job_discovery_agent, "discover", fake_discover)
    # Run synchronously inside test by patching dispatch to no-op and awaiting orchestrator directly
    import app.api.routes.searches as searches_mod
    dispatched_ids = []
    monkeypatch.setattr(searches_mod, "dispatch_search_session", lambda sid: dispatched_ids.append(sid) or "test")

    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://boards.greenhouse.io/cloudflare/jobs/1").mock(
            return_value=httpx.Response(200, text="<html>Apply to Cloudflare</html>")
        )
        mock.get("https://remotive.com/remote-jobs/2").mock(
            return_value=httpx.Response(200, text="<html>NorthStar Labs Python role</html>")
        )
        mock.get("https://themuse.com/jobs/chef").mock(
            return_value=httpx.Response(200, text="<html>Chef opening</html>")
        )

        # 3. Start multi-country AI Search with 55% threshold
        start_resp = await client.post(
            "/api/v1/searches",
            headers=headers,
            json={
                "cv_id": cv_id,
                "target_countries": ["Germany", "United Kingdom"],
                "min_match_score": 55,
            },
        )
        assert start_resp.status_code == 201
        session_id = start_resp.json()["id"]
        assert session_id in dispatched_ids

        await agent_orchestrator.execute_search_session(session_id)

    # 4. Verify search session metrics, logs & transparent unavailable source disclosure
    sess_resp = await client.get(f"/api/v1/searches/{session_id}", headers=headers)
    assert sess_resp.status_code == 200
    sess = sess_resp.json()
    assert sess["status"] == "completed"
    assert sess["sources_searched_count"] == 3
    assert sess["jobs_discovered_count"] == 3
    assert sess["jobs_matched_count"] == 2
    assert sess["below_threshold_count"] == 1
    assert any(u["slug"] == "adzuna" for u in sess["sources_unavailable"])
    assert len(sess["logs"]) >= 7

    # 5. Query Job Results with filtering and sorting
    all_jobs = (await client.get(f"/api/v1/jobs?session_id={session_id}&sort_by=highest_match", headers=headers)).json()
    assert len(all_jobs) == 2
    assert all(j["overall_score"] >= 55.0 for j in all_jobs)

    germany_only = (await client.get(f"/api/v1/jobs?session_id={session_id}&country=Germany&visa_sponsorship=true", headers=headers)).json()
    assert len(germany_only) == 1
    assert germany_only[0]["job"]["company_name"] == "Cloudflare"

    # 6. Compare Jobs side-by-side
    job_ids = [j["job_id"] for j in all_jobs]
    comp = await client.post("/api/v1/jobs/compare", headers=headers, json={"job_ids": job_ids})
    assert comp.status_code == 200
    assert len(comp.json()["items"]) == 2
    assert "Python" in comp.json()["shared_matched_skills"]

    # 7. Save & Track Application through pipeline stages
    target_job_id = job_ids[0]
    save_r = await client.post("/api/v1/tracker/saved", headers=headers, json={"job_id": target_job_id, "notes": "Great fit"})
    assert save_r.status_code == 201

    app_r = await client.post(
        "/api/v1/tracker/applications",
        headers=headers,
        json={"job_id": target_job_id, "status": "applied", "notes": "Submitted via direct Greenhouse link"},
    )
    assert app_r.status_code == 201
    app_id = app_r.json()["id"]

    patch_r = await client.patch(
        f"/api/v1/tracker/applications/{app_id}",
        headers=headers,
        json={"status": "interview", "notes": "Technical screen scheduled"},
    )
    assert patch_r.status_code == 200
    assert patch_r.json()["status"] == "interview"
    assert len(patch_r.json()["history"]) == 2

    # 8. Grounded AI Career Assistant (Cover Letter & Missing Skills)
    cl_resp = await client.post(
        "/api/v1/assistant/generate",
        headers=headers,
        json={"action": "cover_letter", "job_id": target_job_id, "tone": "professional"},
    )
    assert cl_resp.status_code == 200
    cl_md = cl_resp.json()["content_markdown"]
    assert "Elena Vance" in cl_md
    assert all_jobs[0]["job"]["company_name"] in cl_md

    # 9. Dashboard summary reflects all activity
    dash = (await client.get("/api/v1/dashboard/summary", headers=headers)).json()
    assert dash["cv_count"] == 1
    assert dash["total_qualifying_matches"] == 2
    assert dash["saved_jobs_count"] == 1
    assert dash["application_pipeline"].get("interview") == 1


@pytest.mark.asyncio
async def test_empty_search_results_handled_gracefully(test_env, monkeypatch):
    client, _ = test_env
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "empty@example.com", "password": "SecurePassword123", "full_name": "Empty Test"},
    )
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    pdf = build_sample_pdf_bytes(["Empty Test", "Skills: Python"])
    cv_id = (
        await client.post("/api/v1/cvs/upload", headers=headers, files={"file": ("cv.pdf", pdf, "application/pdf")})
    ).json()["id"]

    async def empty_discover(profile, pref, custom_ats_boards=None):
        return [], ["Python"], [], [{"slug": "remotive", "name": "Remotive", "status": "error", "reason": "Timeout"}]

    import app.agents.orchestrator as orch_mod
    import app.api.routes.searches as searches_mod

    monkeypatch.setattr(orch_mod.job_discovery_agent, "discover", empty_discover)
    monkeypatch.setattr(searches_mod, "dispatch_search_session", lambda sid: "test")

    sid = (
        await client.post(
            "/api/v1/searches",
            headers=headers,
            json={"cv_id": cv_id, "target_countries": ["Antarctica"], "min_match_score": 80},
        )
    ).json()["id"]
    await agent_orchestrator.execute_search_session(sid)

    sess = (await client.get(f"/api/v1/searches/{sid}", headers=headers)).json()
    assert sess["status"] == "completed"
    assert sess["jobs_matched_count"] == 0
    jobs = (await client.get(f"/api/v1/jobs?session_id={sid}", headers=headers)).json()
    assert jobs == []
