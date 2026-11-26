# TalentScope AI — Autonomous Agentic Job Discovery & Matching Platform

TalentScope AI is a full-stack, production-oriented **AI-powered agentic job discovery and CV matching platform**. Users upload their CV (PDF, DOCX, or DOC), select one or more target countries, configure a minimum CV-to-job matching percentage (0–100%), and launch a **7-agent autonomous search pipeline** across permitted international job boards, government portals, and direct employer ATS career pages.

---

## Core Architecture

- **Frontend (`frontend/`)**: Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS, Light & Dark modes, 13 complete SaaS views.
- **Backend (`backend/`)**: Python FastAPI, async SQLAlchemy 2.0, Alembic migrations, 14 normalized relational tables (`PostgreSQL 16 + pgvector` in Docker/Production; zero-config `SQLite` fallback for instant local dev).
- **Orchestration**: 7 specialized agents coordinated by a Central Orchestrator with live Server-Sent Events (SSE) progress telemetry, running via **Celery + Redis** in production or in-process `asyncio` in local development.
- **Security & Privacy**: Bcrypt password hashing, JWT access/refresh auth, RBAC, user data isolation, Fernet AES encryption at rest for uploaded CVs and extracted text, structural/macro/PDF-JavaScript/EICAR malware scanning, PII-redacting logging, prompt-injection sanitization & untrusted-data isolation, and user-controlled CV deletion / data retention.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the complete architectural diagram, 14-table schema, and agent specifications, and [FEATURE_STATUS.md](FEATURE_STATUS.md) for the feature completion & integration matrix.

---

## Permitted Job Sources & Transparency

### Active Out-of-the-Box (No API Key Required)
1. **Remotive** (Official public JSON API)
2. **Arbeitnow** (Official public JSON API — Europe/Germany/Global + visa sponsorship metadata)
3. **Remote OK** (Official public JSON feed with compliant `User-Agent`)
4. **The Muse** (Official public REST API)
5. **Jobicy** (Official v2 public REST API)
6. **Himalayas** (Official public JSON API with salary & seniority)
7. **We Work Remotely** (Official public RSS syndication feed)
8. **JobTechDev / Arbetsförmedlingen** (Official Swedish Public Employment Service CC0 Open Data API)
9. **Direct Company Career Pages via Public ATS APIs**:
   - **Greenhouse Boards API** (Stripe, Cloudflare, Datadog, GitLab, Figma, Coinbase, Vercel, Duolingo + user-configurable boards)
   - **Lever Postings API** (Mistral AI, Palantir, Spotify, Zoox + user-configurable boards)
   - **Ashby Job Boards API** (Linear, Notion, Ramp, Supabase + user-configurable boards)

### Optional Keyed Official Integrations (Configure in `.env`)
- **Adzuna** (`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`) — 19+ country-specific endpoints
- **Jooble** (`JOOBLE_API_KEY`) — 65+ countries
- **USAJOBS** (`USAJOBS_API_KEY`, `USAJOBS_USER_AGENT`) — Official U.S. Federal Government API
- **Reed.co.uk** (`REED_API_KEY`) — Official UK Jobseeker API
- **JSearch / RapidAPI** (`JSEARCH_API_KEY`) — Licensed Google for Jobs gateway (LinkedIn, Indeed, Glassdoor, Monster)

> **Policy Note:** TalentScope AI strictly respects `robots.txt`, rate limits, and website Terms of Service. It never bypasses CAPTCHAs, logins, or anti-bot walls, and it never fabricates job listings, salaries, deadlines, or candidate qualifications.

---

## Quick Start (Local Development — Windows / macOS / Linux)

### 1. Configure Environment
```bash
cp .env.example .env
```
(Default `.env` works immediately with zero external API keys using local encrypted SQLite + deterministic hybrid NLP + 11 keyless job APIs/ATS connectors. Add `OPENAI_API_KEY` / `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` and keyed job APIs whenever desired.)

### 2. Start Backend (FastAPI)
```bash
cd backend
python -m venv .venv
# Windows:
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\uvicorn app.main:app --reload --port 8000
```
Open interactive OpenAPI / Swagger API docs at: `http://localhost:8000/docs`

### 3. Start Frontend (Next.js)
```bash
cd frontend
npm install
npm run dev
```
Open the SaaS web application at: `http://localhost:3000`

---

## Deploy to Render (free tier)

The repo includes a [`render.yaml`](render.yaml) Blueprint that creates a free PostgreSQL 16 database,
the FastAPI backend (Docker, with Tesseract OCR) and the Next.js frontend.

1. Push this folder to a GitHub repository.
2. In the Render dashboard choose **New → Blueprint**, pick the repository and click **Apply**.
   Secrets (`JWT_SECRET_KEY`, `FILE_ENCRYPTION_KEY`) are generated automatically.
3. When the services are live, open the `talentscope-api` service and copy its URL. Render names are
   global, so it usually has a suffix (e.g. `https://talentscope-api-x1y2.onrender.com`). Set
   `BACKEND_URL` on `talentscope-web` → **Environment** to that URL (no trailing slash) and choose
   **Save, rebuild, and deploy**. Until you do, sign-up and login will fail.
4. Open the `talentscope-web` URL and create an account.

How it fits the free tier: the browser only talks to the frontend, which proxies `/api/v1/*` to the
backend (no CORS setup); CVs are stored encrypted inside Postgres (`STORAGE_BACKEND=db`) because free
services have no disk; searches run in-process (`TASK_RUNNER_MODE=local`). Free services sleep after
15 minutes idle — the UI shows a "waking up the server" notice during the ~1 minute cold start, and a
search interrupted by a restart is marked as failed so it can be re-run. Free Render databases expire
after 30 days unless upgraded.

---

## Production Deployment (Docker Compose)

Starts **PostgreSQL 16 + pgvector**, **Redis 7**, **FastAPI**, **Celery Worker**, and **Next.js**:

```bash
cp .env.example .env
# Edit .env to set a strong JWT_SECRET_KEY and any optional LLM / job API keys
docker compose up --build -d
```

---

## Running Automated Tests

```bash
cd backend
.\.venv\Scripts\pytest -v
# Optionally run the same suite against PostgreSQL + pgvector:
TEST_DATABASE_URL=postgresql://user@localhost:5432/talentscope_test .\.venv\Scripts\pytest -v
```
Tests verify authentication & user isolation, malware/active-content upload blocking, prompt-injection defense, PDF/DOCX/scanned-OCR extraction, 6-dimension matching calibration, live HTTP verification & direct-link deduplication, multi-country autonomous search orchestration, advanced filtering, comparison, application tracking, and the grounded AI Career Assistant.
