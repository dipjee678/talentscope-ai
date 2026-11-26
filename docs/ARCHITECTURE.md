# System Architecture & Implementation Roadmap

## 1. Architectural Overview

**TalentScope AI** is an autonomous, multi-agent job discovery, verification, and CV-to-job matching platform. Instead of relying on static job scrapes or monolithic prompts, the platform orchestrates **7 specialized agents** across an asynchronous pipeline with explicit data provenance, verification gates, prompt-injection isolation, and transparent explainable scoring.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                     Next.js 15 Frontend (TypeScript / Tailwind)             │
│  13 SaaS Pages · Light/Dark Mode · Live SSE Agent Progress · Job Comparison │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │ REST + SSE (JWT Auth)
┌──────────────────────────────────────▼───────────────────────────────────────┐
│                      FastAPI Backend (Python 3.12+ / Async)                  │
│  Auth & RBAC · Security/Malware Scanner · Encrypted File Vault · Rate Limits │
├──────────────────────────────────────┬───────────────────────────────────────┤
│                        Central Agent Orchestrator                            │
│    (Celery + Redis in Production / Async Task Runner in Local Dev Mode)      │
│                                                                              │
│  [1] CV Analysis Agent ──► [2] Job Discovery Agent ──► [3] Extraction Agent  │
│                                                                 │            │
│  [7] Reporting Agent ◄── [6] Ranking Agent ◄── [5] Verification ◄── [4] Match│
└──────────────┬──────────────────────────────────────────┬────────────────────┘
               │                                          │
┌──────────────▼──────────────────┐     ┌─────────────────▼────────────────────┐
│  PostgreSQL 16 + pgvector       │     │  Permitted External Job Sources      │
│  (SQLite fallback for local dev)│     │  • Open APIs: Remotive, Arbeitnow,   │
│  S3 / MinIO / Encrypted Local   │     │    RemoteOK, The Muse, Jobicy,       │
│  Redis (Cache + Celery Broker)  │     │    Himalayas, WWR RSS, JobTechDev SE │
│                                 │     │  • Direct ATS: Greenhouse, Lever,    │
│                                 │     │    Ashby (Company Career Pages)      │
│                                 │     │  • Keyed APIs: Adzuna, Jooble,       │
│                                 │     │    USAJOBS, Reed UK, JSearch         │
└─────────────────────────────────┘     └──────────────────────────────────────┘
```

---

## 2. External Job Sources & Legal Access Policy

We strictly use **official APIs, open public feeds, and documented ATS endpoints**. We never bypass CAPTCHAs, authentication walls, or anti-bot protections, and we never fabricate listings.

| Source | Category | Auth Required | Geographic Coverage | Notes & Limitations |
|---|---|---|---|---|
| **Remotive** | International Remote | No | Worldwide / Country-tagged | Official public JSON API; software, data, product, design, marketing |
| **Arbeitnow** | Europe / Global | No | Germany, EU, Remote, Global | Official public JSON API; includes `visa_sponsorship` & `remote` metadata |
| **Remote OK** | International Remote | No | Worldwide | Public JSON feed; requires compliant `User-Agent`, rate-limited |
| **The Muse** | International | No | US, Europe, Canada, APAC | Official public API with pagination, levels, categories, company info |
| **Jobicy** | International Remote | No | Worldwide / Geo-tagged | Official v2 public REST API with geo, tag, and industry filters |
| **Himalayas** | International Remote | No | Worldwide / Country-restricted | Official public JSON API with salary, seniority, and timezone restrictions |
| **We Work Remotely** | International Remote | No | Worldwide | Official public RSS feeds; attribution preserved |
| **JobTechDev (Arbetsförmedlingen)** | Country-Specific (SE) | No | Sweden | Official Swedish Public Employment Service open-data API (CC0) |
| **Greenhouse Boards** | Direct Company Career Pages | No | Global (per company) | Official public ATS JSON API (`boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true`) |
| **Lever Postings** | Direct Company Career Pages | No | Global (per company) | Official public ATS JSON API (`api.lever.co/v0/postings/{slug}?mode=json`) |
| **Ashby Boards** | Direct Company Career Pages | No | Global (per company) | Official public ATS JSON API (`api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true`) |
| **Adzuna** | Multi-Country Aggregator | API Key (`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`) | 19+ countries (US, UK, DE, FR, CA, AU, IN, SG, NL, CH, etc.) | Free developer tier available; country-routed endpoints |
| **Jooble** | Multi-Country Aggregator | API Key (`JOOBLE_API_KEY`) | 65+ countries | Free API key on request; aggregates career pages & boards |
| **USAJOBS** | Government Portal (US) | API Key (`USAJOBS_API_KEY`) | United States | Official US federal employment API |
| **Reed UK** | Country-Specific (UK) | API Key (`REED_API_KEY`) | United Kingdom | Official UK Jobseeker API |
| **JSearch (RapidAPI)** | Major Boards Gateway | Paid/Freemium Key (`JSEARCH_API_KEY`) | Global | Permitted API gateway indexing LinkedIn, Indeed, Glassdoor via Google for Jobs |

### Platforms Without Public Search APIs
LinkedIn Jobs, Indeed, Glassdoor, Monster, CareerBuilder, and Wellfound do not provide open, unauthenticated public search APIs and prohibit unauthorized scraping in their Terms of Service. Our platform:
1. Clearly discloses this in the **Search Coverage & Limitations** panel.
2. Enables legal access to LinkedIn/Indeed/Glassdoor listings via **JSearch**, **Adzuna**, or **Jooble** when the user configures those API keys.
3. Queries direct **company career pages** (Greenhouse, Lever, Ashby) so users get direct company apply URLs often ahead of aggregator syndication.

---

## 3. Seven-Agent Pipeline Specification

1. **Agent 1 — CV Analysis Agent (`cv_analysis_agent.py`)**
   - Extracts text from PDF (`pypdf` + `pdfplumber`), DOCX (`python-docx`), and legacy DOC (safe text fallback + warning).
   - Detects scanned PDFs (low text density) and runs OCR via Tesseract (`pytesseract` + `pymupdf`) or configured Vision LLM; flags manual review if OCR engines are unavailable.
   - Runs prompt-injection sanitization on untrusted document content.
   - Outputs structured candidate profile JSON (never fabricates missing fields; explicitly lists `missing_or_unclear_fields`).

2. **Agent 2 — Job Discovery Agent (`job_discovery_agent.py`)**
   - Dynamically selects applicable connectors based on target countries, work mode, employment preferences, and configured API keys.
   - Generates diverse search queries from the candidate's target roles, core technical skills, and experience level.
   - Executes parallel async paginated requests with per-source token-bucket rate limiting, timeouts, exponential backoff retries, and response caching.
   - Records exact source telemetry (queried, skipped due to missing key, failed with error, jobs returned).

3. **Agent 3 — Job Extraction Agent (`job_extraction_agent.py`)**
   - Cleans HTML/markdown descriptions and strips potential prompt-injection payloads.
   - Extracts structured requirements separated into **mandatory** vs **preferred** skills, qualifications, experience years, education level, remote/hybrid/onsite mode, salary (strictly only when present), publication date, application deadline, visa sponsorship signals, and language requirements.

4. **Agent 4 — Matching Agent (`matching_agent.py`)**
   - Computes a transparent, deterministic + semantic hybrid score across 6 configurable weighted dimensions:
     - Technical Skills (default 30%)
     - Work Experience (default 20%)
     - Education (default 15%)
     - Required Qualifications (default 15%)
     - Projects & Achievements (default 10%)
     - Job Role Relevance (default 10%)
   - Combines canonical skill taxonomy normalization + TF-IDF / vector cosine similarity (and optional LLM semantic rubric review).
   - Never inflates scores; separates mandatory vs preferred matches; flags explicit disqualifiers independently; labels unmentioned CV items as "not stated on CV" rather than "lacks skill".

5. **Agent 5 — Verification Agent (`verification_agent.py`)**
   - Verifies listing URL & direct application URL via live HTTP HEAD/GET probes (respecting rate limits and timeouts) and checks page signals for expired/closed postings ("no longer accepting applications", 404/410, past deadline).
   - Deduplicates listings across sources using canonical URL, normalized `(company, title, country/city)`, and text-similarity clustering.
   - Prioritizes direct company career page / ATS application links over third-party aggregator URLs.
   - Assigns transparent verification statuses: `verified_active`, `expired`, `broken_link`, `unverified`.

6. **Agent 6 — Ranking Agent (`ranking_agent.py`)**
   - Excludes expired/broken listings and jobs strictly below the user's `min_match_score` threshold.
   - Computes ranking order incorporating user preference alignment (work mode, visa sponsorship, entry-level/fresh grad/internship flags, verification confidence) while preserving the pure, uninflated CV matching percentage.

7. **Agent 7 — Reporting Agent (`reporting_agent.py`)**
   - Persists final ranked matches, deduplication stats, verification stats, and per-source coverage/limitation report.
   - Creates in-app notifications and finalizes search session telemetry.

---

## 4. Relational Database Schema (14 Normalized Tables)

1. `users` — UUID PK, email (unique), password_hash, full_name, role (`user`/`admin`), data_retention_days, default_weights_json, theme_preference, timestamps.
2. `uploaded_cvs` — UUID PK, user_id FK, original_filename, content_type, file_size_bytes, sha256_hash, encrypted_storage_path, storage_backend, version_number, is_active, parse_status, ocr_status, security_scan_status, security_scan_notes, extracted_text_encrypted, prompt_injection_flags_json, created_at.
3. `candidate_profiles` — UUID PK, user_id FK, cv_id FK (unique per CV version), full_name, headline, email, phone, location, summary, years_of_experience, education_json, experience_json, internships_json, projects_json, certifications_json, languages_json, career_interests_json, achievements_json, soft_skills_json, missing_or_unclear_json, embedding_vector, manually_edited, timestamps.
4. `candidate_skills` — UUID PK, profile_id FK, skill_name, normalized_name, category (`technical`, `programming_language`, `framework`, `tool`, `cloud`, `soft`), proficiency, source_section, unique `(profile_id, normalized_name)`.
5. `job_sources` — UUID PK, slug (unique), name, source_type (`international`, `country_specific`, `company_ats`, `government`, `aggregator`), base_url, requires_api_key, supported_countries_json, is_enabled, rate_limit_rpm, config_json, notes, timestamps.
6. `search_preferences` — UUID PK, user_id FK, name, cv_id FK, target_countries_json, min_match_score, job_categories_json, industries_json, experience_levels_json, employment_types_json, work_modes_json, visa_sponsorship_only, english_only, fresh_graduate, internship, entry_level, matching_weights_json, max_results_per_source, enabled_source_slugs_json, timestamps.
7. `search_sessions` — UUID PK, user_id FK, cv_id FK, preference_id FK, status (`queued`, `running`, `completed`, `failed`, `cancelled`), current_stage, progress_percent, config_snapshot_json, sources_searched_count, sources_unavailable_json, jobs_discovered_count, jobs_verified_count, duplicates_removed_count, expired_removed_count, below_threshold_count, jobs_matched_count, coverage_report_json, error_message, started_at, completed_at, created_at.
8. `job_listings` — UUID PK, source_id FK, external_id, dedup_fingerprint, title, company_name, company_logo_url, country, city, location_raw, work_mode (`remote`, `hybrid`, `onsite`, `unknown`), employment_type, experience_level, industry, category, salary_min, salary_max, salary_currency, salary_period, salary_raw, visa_sponsorship, language, description_text, description_html_sanitized, source_url, apply_url, is_direct_company_link, published_at, application_deadline, verification_status (`verified_active`, `expired`, `broken_link`, `unverified`), verification_details_json, last_verified_at, is_duplicate, canonical_job_id FK, prompt_injection_detected, embedding_vector, raw_metadata_json, created_at, updated_at.
9. `job_requirements` — UUID PK, job_id FK, requirement_type (`technical_skill`, `education`, `experience`, `qualification`, `language`, `disqualifier`), requirement_text, normalized_key, is_mandatory, min_years, created_at.
10. `job_matches` — UUID PK, search_session_id FK, user_id FK, job_id FK, profile_id FK, overall_score, rank_score, technical_skills_score, education_score, experience_score, qualifications_score, projects_score, role_relevance_score, weights_used_json, matched_skills_json, missing_skills_json, unstated_on_cv_json, matching_qualifications_json, experience_compatibility, education_compatibility, explicit_disqualifiers_json, score_explanation, strengths_json, weaknesses_json, calculation_breakdown_json, is_hidden, created_at, unique `(search_session_id, job_id)`.
11. `saved_jobs` — UUID PK, user_id FK, job_id FK, notes, created_at, unique `(user_id, job_id)`.
12. `job_applications` — UUID PK, user_id FK, job_id FK, status (`saved`, `interested`, `applied`, `assessment`, `interview`, `offer`, `rejected`), applied_at, application_url, notes, follow_up_at, history_json, created_at, updated_at, unique `(user_id, job_id)`.
13. `agent_execution_logs` — UUID PK, search_session_id FK, agent_name, stage, level (`info`, `warning`, `error`), message, metrics_json, duration_ms, created_at.
14. `notifications` — UUID PK, user_id FK, type, title, body, link_url, is_read, created_at.

---

## 5. Phased Implementation Roadmap

- **Phase 1: Foundation** — Monorepo structure, FastAPI app, SQLAlchemy 2.0 + Alembic migrations, Argon2/JWT auth, security scanner, encrypted file vault.
- **Phase 2: AI CV Analysis** — PDF/DOCX/DOC + OCR extraction, prompt-injection firewall, structured candidate profile generator, editable profile & skill APIs.
- **Phase 3: Job Discovery & Extraction** — 15+ real permitted source connectors (8 open APIs, 3 direct ATS career page APIs, 5 keyed country/global APIs), query builder, parallel rate-limited fetching, structured requirement extraction.
- **Phase 4: AI Matching Engine** — Configurable 6-dimension weighted scoring, hybrid taxonomy + semantic similarity, mandatory vs preferred separation, disqualifier isolation, full explainability.
- **Phase 5: Verification & Orchestrator** — Live URL/status verification, expiration detection, multi-signal deduplication prioritizing direct company links, 7-agent orchestrator with SSE progress and Celery/local runner.
- **Phase 6: Dashboard & Application Tracker** — Full Next.js SaaS frontend with all 13 pages, advanced filters & sorting, side-by-side job comparison, Kanban/table tracker with reminders.
- **Phase 7: AI Career Assistant** — Grounded career assistant (match explanation, skill gap plan, CV improvements, truthful cover letters, interview prep, job comparison, plain-English requirement breakdown).
- **Phase 8: Testing & Deployment** — Comprehensive unit/integration/security tests covering all 15 required test cases, Docker Compose stack (Postgres+pgvector, Redis, Celery, FastAPI, Next.js), full setup & deployment docs.
