"""Shared pytest fixtures: isolated async SQLite database, FastAPI HTTP client, and sample CV builders."""
from __future__ import annotations

import io
import os
import tempfile
import zipfile
from pathlib import Path
from typing import AsyncGenerator

import docx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, enable_sqlite_foreign_keys, get_db
from app.main import app


@pytest_asyncio.fixture(scope="function")
async def test_env(tmp_path: Path, monkeypatch):
    db_file = tmp_path / "test_talentscope.db"
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Set TEST_DATABASE_URL (e.g. postgresql+asyncpg://user@localhost:5432/talentscope_test) to run
    # the suite against PostgreSQL + pgvector; the schema is dropped and recreated per test.
    pg_url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if pg_url:
        from app.core.config import Settings

        db_url = Settings(_env_file=None, DATABASE_URL=pg_url).DATABASE_URL
        engine = create_async_engine(db_url)
    else:
        db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
        engine = create_async_engine(db_url, connect_args={"check_same_thread": False})
        enable_sqlite_foreign_keys(engine)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        if pg_url:
            await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Patch database session & local storage dir cleanly for isolated tests
    import app.agents.orchestrator as orch_mod
    import app.core.storage as storage_mod

    monkeypatch.setattr(orch_mod, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(storage_mod.storage_service.settings, "LOCAL_STORAGE_DIR", str(upload_dir))
    monkeypatch.setattr(storage_mod.storage_service.settings, "VERIFY_LIVE_URLS", True)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, session_factory

    app.dependency_overrides.clear()
    await engine.dispose()


def build_sample_pdf_bytes(lines: list[str]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 750
    for line in lines:
        c.drawString(50, y, line)
        y -= 16
        if y < 60:
            c.showPage()
            y = 750
    c.save()
    return buf.getvalue()


def build_scanned_blank_pdf_bytes() -> bytes:
    """Create a valid PDF with a drawn rectangle and zero selectable text (simulating a scanned PDF)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.rect(50, 50, 500, 700, stroke=1, fill=0)
    c.save()
    return buf.getvalue()


def build_sample_docx_bytes(paragraphs: list[str]) -> bytes:
    doc = docx.Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def build_malicious_macro_docx_bytes() -> bytes:
    raw = build_sample_docx_bytes(["Normal text"])
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw), "r") as zin, zipfile.ZipFile(out, "w") as zout:
        for item in zin.infolist():
            zout.writestr(item, zin.read(item.filename))
        zout.writestr("word/vbaProject.bin", b"FAKE_VBA_MACRO_PAYLOAD")
    return out.getvalue()
