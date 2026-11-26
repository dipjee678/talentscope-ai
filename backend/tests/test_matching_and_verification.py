"""Tests for Intelligent CV-to-Job Matching Engine, Verification Agent, Expired Jobs, and Deduplication."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from app.agents.job_extraction_agent import job_extraction_agent
from app.agents.matching_agent import matching_agent
from app.agents.ranking_agent import ranking_agent
from app.agents.verification_agent import verification_agent
from app.models.entities import CandidateProfile, JobListing, JobRequirement, SearchPreference
from app.services.job_sources.base import RawDiscoveredJob
from app.services.skill_taxonomy import compute_semantic_embedding


def test_matching_engine_section_3d_cse_candidate_calibration():
    """Verify the exact Section 3.D example:
    Candidate: C++, Python, Java, SQL, Machine Learning, Bachelor's degree in CSE, Academic projects (0 yrs exp)
    Job: Python, SQL, Machine Learning, Bachelor's degree in Computer Science, 1 year of experience
    Expected: ~82% (non-inflated, realistic score with clear explanation).
    """
    cv_text = (
        "C++ Python Java SQL Machine Learning Bachelor's degree in Computer Science and Engineering. "
        "Academic projects: Machine Learning recommender system in Python and SQL."
    )
    profile = CandidateProfile(
        id="p1",
        user_id="u1",
        cv_id="c1",
        full_name="CSE Graduate",
        headline="Machine Learning & Python Engineer",
        years_of_experience=0.0,
        highest_degree="Bachelor's Degree",
        programming_languages_json=["C++", "Python", "Java", "SQL"],
        technical_skills_json=["Machine Learning"],
        projects_json=[
            {
                "title": "ML Fraud Classifier in Python and SQL",
                "highlights": ["Trained Machine Learning model on SQL dataset"],
            }
        ],
        career_interests_json=["Machine Learning Engineer", "Python Developer"],
        embedding_vector=compute_semantic_embedding(cv_text),
    )

    raw_job = RawDiscoveredJob(
        source_slug="greenhouse_direct",
        source_name="Acme AI Careers",
        external_id="gh-1",
        title="Junior Machine Learning Engineer",
        company_name="Acme AI",
        location_raw="Berlin, Germany",
        source_url="https://boards.greenhouse.io/acme/jobs/1",
        apply_url="https://boards.greenhouse.io/acme/jobs/1",
        description_raw=(
            "We are hiring a Junior Machine Learning Engineer.\n"
            "Requirements:\n"
            "- Strong proficiency in Python, SQL, and Machine Learning\n"
            "- Bachelor's degree in Computer Science\n"
            "- 1 year of experience in software or ML development"
        ),
        is_direct_company_link=True,
    )
    bundle = job_extraction_agent.extract(raw_job)
    job = JobListing(id="j1", **bundle.listing_fields)
    reqs = [JobRequirement(job_id="j1", **r) for r in bundle.requirements]

    result = matching_agent.evaluate(profile, job, reqs)
    assert 75.0 <= result["overall_score"] <= 88.0, f"Got {result['overall_score']}"
    assert "Python" in result["matched_skills"]
    assert "SQL" in result["matched_skills"]
    assert "Machine Learning" in result["matched_skills"]
    assert result["technical_skills_score"] == 100.0
    assert result["education_score"] == 100.0
    assert result["experience_score"] < 70.0  # Honest non-inflated tenure score!
    assert "do not guarantee" in result["score_explanation"].lower()


def test_matching_engine_isolates_explicit_disqualifiers_and_excludes_below_threshold():
    profile = CandidateProfile(
        id="p2",
        user_id="u1",
        cv_id="c2",
        headline="Frontend Developer",
        years_of_experience=1.0,
        highest_degree="Bachelor's Degree",
        programming_languages_json=["JavaScript"],
        technical_skills_json=["React"],
        embedding_vector=compute_semantic_embedding("JavaScript React frontend web"),
    )

    raw_job = RawDiscoveredJob(
        source_slug="themuse",
        source_name="The Muse",
        external_id="m-99",
        title="Staff Rust Kernel & Cybersecurity Architect",
        company_name="DefenseCorp",
        location_raw="United States",
        source_url="https://example.com/job/99",
        apply_url="https://example.com/job/99",
        description_raw=(
            "Required: Rust, C++, Kubernetes, Linux, Cybersecurity. "
            "Must have 8 years of experience. Active TS/SCI clearance required. No visa sponsorship."
        ),
    )
    bundle = job_extraction_agent.extract(raw_job)
    job = JobListing(id="j99", **bundle.listing_fields)
    reqs = [JobRequirement(job_id="j99", **r) for r in bundle.requirements]

    res = matching_agent.evaluate(profile, job, reqs, visa_required_by_user=True)
    assert res["overall_score"] < 45.0
    assert len(res["explicit_disqualifiers"]) >= 2

    pref = SearchPreference(
        user_id="u1",
        cv_id="c2",
        target_countries_json=["United States"],
        min_match_score=50.0,
    )
    qualifying, metrics = ranking_agent.filter_and_rank([(job, res)], pref)
    assert len(qualifying) == 0
    assert metrics["below_threshold_excluded"] == 1


@pytest.mark.asyncio
async def test_verification_deduplicates_prioritizing_direct_company_link_and_filters_expired():
    # Job 1: Aggregator listing (Remotive)
    raw_agg = RawDiscoveredJob(
        source_slug="remotive",
        source_name="Remotive",
        external_id="rem-1",
        title="Backend Python Engineer",
        company_name="Stripe",
        location_raw="Remote, Germany",
        source_url="https://remotive.com/jobs/1234",
        apply_url="https://remotive.com/jobs/1234?utm_source=api",
        description_raw="Build scalable Python, FastAPI, and PostgreSQL payments APIs.",
        is_direct_company_link=False,
    )
    # Job 2: Duplicate direct company ATS listing (Greenhouse) -> MUST WIN as canonical!
    raw_direct = RawDiscoveredJob(
        source_slug="greenhouse_direct",
        source_name="Stripe Careers (Greenhouse)",
        external_id="gh-1234",
        title="Backend Python Engineer",
        company_name="Stripe",
        location_raw="Remote, Germany",
        source_url="https://boards.greenhouse.io/stripe/jobs/1234",
        apply_url="https://boards.greenhouse.io/stripe/jobs/1234",
        description_raw="Build scalable Python, FastAPI, and PostgreSQL payments APIs with Stripe.",
        is_direct_company_link=True,
    )
    # Job 3: Expired deadline job
    raw_expired_dl = RawDiscoveredJob(
        source_slug="arbeitnow",
        source_name="Arbeitnow",
        external_id="arb-old",
        title="Data Analyst",
        company_name="OldCo",
        location_raw="Berlin, Germany",
        source_url="https://arbeitnow.com/jobs/old",
        apply_url="https://arbeitnow.com/jobs/old",
        description_raw="SQL and Python analytics.",
        application_deadline=datetime.now(timezone.utc) - timedelta(days=3),
    )
    # Job 4: Dead 404 link job
    raw_404 = RawDiscoveredJob(
        source_slug="remoteok",
        source_name="Remote OK",
        external_id="rok-404",
        title="Closed Role",
        company_name="GoneCo",
        location_raw="Worldwide",
        source_url="https://example.org/closed-job",
        apply_url="https://example.org/closed-job",
        description_raw="Python backend engineer.",
    )

    jobs = []
    for idx, r in enumerate([raw_agg, raw_direct, raw_expired_dl, raw_404], start=1):
        b = job_extraction_agent.extract(r)
        jobs.append(JobListing(id=f"job-{idx}", **b.listing_fields))

    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://boards.greenhouse.io/stripe/jobs/1234").mock(
            return_value=httpx.Response(200, text="<html><body>Backend Python Engineer - Apply Now</body></html>")
        )
        mock.get("https://example.org/closed-job").mock(
            return_value=httpx.Response(404, text="Not Found")
        )

        active_pool, metrics = await verification_agent.verify_and_deduplicate(jobs)

    assert metrics["duplicates_removed"] == 1
    assert metrics["expired_or_broken_removed"] == 2
    assert len(active_pool) == 1
    winner = active_pool[0]
    assert winner.is_direct_company_link is True
    assert winner.apply_url == "https://boards.greenhouse.io/stripe/jobs/1234"
    assert winner.verification_status == "verified_active"
    assert len(winner.alternate_sources_json) == 1


def _engineer_profile() -> CandidateProfile:
    cv_text = "Backend Software Engineer Python FastAPI PostgreSQL Docker AWS SQL JavaScript Git"
    return CandidateProfile(
        id="p-eng",
        user_id="u1",
        cv_id="c1",
        full_name="Backend Engineer",
        headline="Backend Software Engineer",
        years_of_experience=3.0,
        highest_degree="Bachelor's Degree",
        programming_languages_json=["Python", "JavaScript", "SQL"],
        technical_skills_json=["FastAPI", "PostgreSQL", "Docker", "AWS", "Git"],
        experience_json=[{"title": "Software Engineer", "company": "CloudCo"}],
        embedding_vector=compute_semantic_embedding(cv_text),
    )


def _score(profile: CandidateProfile, title: str, description: str) -> dict:
    raw = RawDiscoveredJob(
        source_slug="remotive",
        source_name="Remotive",
        external_id=title,
        title=title,
        company_name="Acme",
        location_raw="Remote",
        source_url="https://example.com/j",
        apply_url="https://example.com/j",
        description_raw=description,
    )
    bundle = job_extraction_agent.extract(raw)
    job = JobListing(id="j-" + title, **bundle.listing_fields)
    reqs = [JobRequirement(job_id=job.id, **r) for r in bundle.requirements]
    return matching_agent.evaluate(profile, job, reqs)


def test_off_field_job_is_capped_below_real_engineering_role():
    profile = _engineer_profile()
    support = _score(
        profile,
        "Product Support Specialist",
        "Help customers by email. Requirements: SQL, JavaScript and Git basics are a plus.",
    )
    backend = _score(
        profile,
        "Backend Developer",
        "Requirements: Python, FastAPI, PostgreSQL, Docker and AWS. 2 years of experience.",
    )
    assert support["overall_score"] <= 60.0
    assert support["calculation_breakdown"]["off_field_title"] is True
    assert any("outside your field" in w for w in support["weaknesses"])
    assert backend["overall_score"] > support["overall_score"] + 10


def test_single_named_skill_is_not_a_perfect_technical_match():
    profile = _engineer_profile()
    result = _score(profile, "Data Engineer", "Requirements: SQL.")
    assert result["technical_skills_score"] < 100.0
