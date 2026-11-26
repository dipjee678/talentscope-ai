"""Tests for PDF CV upload, DOCX CV upload, scanned PDF OCR detection, skill extraction, and profile editing."""
from __future__ import annotations

import pytest

from tests.conftest import (
    build_sample_docx_bytes,
    build_sample_pdf_bytes,
    build_scanned_blank_pdf_bytes,
)


async def _register_and_headers(client, email: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "ValidPassword123", "full_name": "Candidate Test"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_upload_valid_pdf_cv_and_extract_skills(test_env):
    client, _ = test_env
    headers = await _register_and_headers(client, "pdf_user@example.com")

    pdf_bytes = build_sample_pdf_bytes([
        "Nadia Rahman",
        "Machine Learning & Software Engineer",
        "nadia@example.com | +880-1711-000111",
        "Education",
        "Bachelor of Science in Computer Science and Engineering, Bangladesh University of Engineering and Technology (2020 - 2024)",
        "Technical Skills",
        "C++, Python, Java, SQL, Machine Learning, PyTorch, Docker, Git",
        "Projects",
        "Real-time Fraud Detection Pipeline using Python, SQL, and Machine Learning",
        "Certifications",
        "AWS Certified Cloud Practitioner",
        "Languages",
        "English, Bengali",
    ])

    resp = await client.post(
        "/api/v1/cvs/upload",
        headers=headers,
        files={"file": ("nadia_cv.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["parse_status"] == "completed"
    assert body["ocr_status"] == "not_needed"
    assert body["security_scan_status"] == "clean"

    prof = body["profile"]
    assert prof["full_name"] == "Nadia Rahman"
    assert "Bachelor" in (prof["highest_degree"] or "")
    for expected_lang in ("C++", "Python", "Java", "SQL"):
        assert expected_lang in prof["programming_languages"]
    assert "Machine Learning" in prof["technical_skills"]
    assert "PyTorch" in prof["technical_skills"]
    assert "English" in prof["spoken_languages"]
    assert len(prof["projects"]) >= 1

    # Original file is preserved and downloadable identically
    dl = await client.get(f"/api/v1/cvs/{body['id']}/download", headers=headers)
    assert dl.status_code == 200
    assert dl.content == pdf_bytes


@pytest.mark.asyncio
async def test_upload_docx_cv_and_profile_manual_edit(test_env):
    client, _ = test_env
    headers = await _register_and_headers(client, "docx_user@example.com")

    docx_bytes = build_sample_docx_bytes([
        "Marcus Weber",
        "Full-Stack TypeScript Engineer",
        "Experience",
        "Software Engineer at CloudWorks (2021 - 2025)",
        "- Built Next.js, React, TypeScript, and Node.js microservices on AWS",
        "Education",
        "Master of Science in Informatics, Technical University of Munich",
        "Technical Skills",
        "TypeScript, JavaScript, React, Next.js, Node.js, PostgreSQL, AWS, Kubernetes",
    ])

    resp = await client.post(
        "/api/v1/cvs/upload",
        headers=headers,
        files={
            "file": (
                "marcus_cv.docx",
                docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert resp.status_code == 201
    prof = resp.json()["profile"]
    assert prof["full_name"] == "Marcus Weber"
    assert "TypeScript" in prof["programming_languages"]
    assert "React" in prof["technical_skills"]
    assert "Master" in (prof["highest_degree"] or "")
    assert prof["years_of_experience"] == 4.0

    # User edits extracted profile inline
    upd = await client.put(
        f"/api/v1/profiles/{prof['id']}",
        headers=headers,
        json={
            "location": "Berlin, Germany",
            "technical_skills": ["React", "Next.js", "Node.js", "PostgreSQL", "AWS", "Kubernetes", "GraphQL"],
            "spoken_languages": ["English", "German"],
        },
    )
    assert upd.status_code == 200
    updated_prof = upd.json()
    assert updated_prof["manually_edited"] is True
    assert updated_prof["location"] == "Berlin, Germany"
    assert "GraphQL" in updated_prof["technical_skills"]


@pytest.mark.asyncio
async def test_scanned_pdf_triggers_ocr_detection_and_flags_missing_fields(test_env):
    client, _ = test_env
    headers = await _register_and_headers(client, "scanned_user@example.com")

    scanned_pdf = build_scanned_blank_pdf_bytes()
    resp = await client.post(
        "/api/v1/cvs/upload",
        headers=headers,
        files={"file": ("scanned_resume.pdf", scanned_pdf, "application/pdf")},
    )
    assert resp.status_code == 201
    body = resp.json()
    # Since local Tesseract / Vision key may not be installed in CI/test env, OCR status is cleanly disclosed
    assert body["ocr_status"] in ("scanned_ocr_unavailable", "completed_tesseract", "completed_vision_llm")
    assert len(body["profile"]["missing_or_unclear"]) > 0
