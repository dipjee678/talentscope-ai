"""Direct Company Career Page connectors via official public ATS Job Board APIs:
Greenhouse, Lever, and Ashby.

Provides direct first-party employer application URLs without intermediaries.
"""
from __future__ import annotations

import html
import time
from typing import Any, Dict, List, Optional, Tuple

from app.services.job_sources.base import (
    BaseJobSourceConnector,
    RawDiscoveredJob,
    SourceSearchResult,
    source_cache,
)
from app.services.job_sources.open_sources import _matches_any_query, _parse_iso_dt

# Curated verified public ATS company career boards across North America, Europe, UK, APAC, and Remote
DEFAULT_GREENHOUSE_BOARDS: List[Tuple[str, str]] = [
    ("stripe", "Stripe"),
    ("cloudflare", "Cloudflare"),
    ("datadog", "Datadog"),
    ("gitlab", "GitLab"),
    ("figma", "Figma"),
    ("coinbase", "Coinbase"),
    ("vercel", "Vercel"),
    ("duolingo", "Duolingo"),
]

DEFAULT_LEVER_BOARDS: List[Tuple[str, str]] = [
    ("mistral", "Mistral AI"),
    ("palantir", "Palantir Technologies"),
    ("spotify", "Spotify"),
    ("zoox", "Zoox"),
]

DEFAULT_ASHBY_BOARDS: List[Tuple[str, str]] = [
    ("linear", "Linear"),
    ("notion", "Notion"),
    ("ramp", "Ramp"),
    ("supabase", "Supabase"),
]


class GreenhouseCareerPagesConnector(BaseJobSourceConnector):
    slug = "greenhouse_direct"
    name = "Company Career Pages (Greenhouse ATS)"
    source_type = "company_ats"
    base_url = "https://boards-api.greenhouse.io/v1/boards"
    requires_api_key = False
    supported_countries = [
        "Worldwide", "United States", "United Kingdom", "Germany", "Canada",
        "France", "Netherlands", "Ireland", "Singapore", "India", "Australia",
    ]
    rate_limit_rpm = 45
    terms_notes = "Official Greenhouse public Job Board API; links directly to employer application forms."

    async def search(
        self,
        queries: List[str],
        countries: List[str],
        max_results: int = 25,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> SourceSearchResult:
        t0 = time.monotonic()
        jobs: List[RawDiscoveredJob] = []
        pages = 0
        boards = list(DEFAULT_GREENHOUSE_BOARDS)
        for custom in (preferences or {}).get("custom_ats_boards") or []:
            if custom.get("provider") == "greenhouse":
                boards.insert(0, (custom["slug"], custom["company_name"]))

        errors: List[str] = []
        for slug, company_name in boards:
            if len(jobs) >= max_results:
                break
            url = f"{self.base_url}/{slug}/jobs"
            cache_key = f"gh::{slug}"
            try:
                data = source_cache.get(cache_key)
                if data is None:
                    resp = await self._request_with_retries("GET", url, params={"content": "true"}, retries=1)
                    data = resp.json()
                    source_cache.set(cache_key, data)
                pages += 1
            except Exception as exc:
                errors.append(f"{slug}: {type(exc).__name__}")
                continue

            for item in (data.get("jobs") or []):
                title = (item.get("title") or "").strip()
                raw_content = html.unescape(item.get("content") or "")
                depts = [d.get("name", "") for d in (item.get("departments") or [])]
                if queries and not _matches_any_query(f"{title} {' '.join(depts)} {raw_content}", queries):
                    continue
                abs_url = item.get("absolute_url") or ""
                if not abs_url:
                    continue
                loc_name = ((item.get("location") or {}).get("name") or "Worldwide").strip()
                jobs.append(
                    RawDiscoveredJob(
                        source_slug=self.slug,
                        source_name=f"{company_name} Careers (Greenhouse)",
                        external_id=f"{slug}:{item.get('id')}",
                        title=title,
                        company_name=company_name,
                        location_raw=loc_name,
                        source_url=abs_url,
                        apply_url=abs_url,
                        description_raw=raw_content,
                        work_mode="remote" if "remote" in loc_name.lower() else None,
                        employment_type="Full-time",
                        category=", ".join(depts[:2]) if depts else None,
                        published_at=_parse_iso_dt(item.get("updated_at")),
                        is_direct_company_link=True,
                    )
                )
                if len(jobs) >= max_results:
                    break

        status = "ok" if pages > 0 else "error"
        return SourceSearchResult(
            source_slug=self.slug,
            source_name=self.name,
            status=status,
            jobs=jobs,
            queries_executed=queries[:3],
            pages_fetched=pages,
            error_message="; ".join(errors[:3]) if status == "error" else None,
            duration_ms=int((time.monotonic() - t0) * 1000),
        )


class LeverCareerPagesConnector(BaseJobSourceConnector):
    slug = "lever_direct"
    name = "Company Career Pages (Lever ATS)"
    source_type = "company_ats"
    base_url = "https://api.lever.co/v0/postings"
    requires_api_key = False
    supported_countries = [
        "Worldwide", "United States", "United Kingdom", "France", "Germany", "Sweden", "Canada",
    ]
    rate_limit_rpm = 40
    terms_notes = "Official Lever public Postings API; links directly to first-party company career pages."

    async def search(
        self,
        queries: List[str],
        countries: List[str],
        max_results: int = 25,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> SourceSearchResult:
        t0 = time.monotonic()
        jobs: List[RawDiscoveredJob] = []
        pages = 0
        boards = list(DEFAULT_LEVER_BOARDS)
        for custom in (preferences or {}).get("custom_ats_boards") or []:
            if custom.get("provider") == "lever":
                boards.insert(0, (custom["slug"], custom["company_name"]))

        errors: List[str] = []
        for slug, company_name in boards:
            if len(jobs) >= max_results:
                break
            url = f"{self.base_url}/{slug}"
            cache_key = f"lever::{slug}"
            try:
                items = source_cache.get(cache_key)
                if items is None:
                    resp = await self._request_with_retries("GET", url, params={"mode": "json"}, retries=1)
                    items = resp.json()
                    source_cache.set(cache_key, items)
                pages += 1
            except Exception as exc:
                errors.append(f"{slug}: {type(exc).__name__}")
                continue

            if not isinstance(items, list):
                continue

            for item in items:
                title = (item.get("text") or "").strip()
                desc_plain = item.get("descriptionPlain") or item.get("description") or ""
                lists_text = " ".join(
                    f"{lst.get('text', '')}: {lst.get('content', '')}"
                    for lst in (item.get("lists") or [])
                )
                full_desc = f"{desc_plain}\n{lists_text}"
                cats = item.get("categories") or {}
                if queries and not _matches_any_query(f"{title} {cats.get('team', '')} {full_desc}", queries):
                    continue
                hosted_url = item.get("hostedUrl") or ""
                apply_url = item.get("applyUrl") or hosted_url
                if not hosted_url:
                    continue
                loc_name = (cats.get("location") or "Worldwide").strip()
                workplace = (item.get("workplaceType") or "").lower()
                mode = workplace if workplace in ("remote", "hybrid", "onsite") else (
                    "remote" if "remote" in loc_name.lower() else None
                )
                sal_range = item.get("salaryRange") or {}
                jobs.append(
                    RawDiscoveredJob(
                        source_slug=self.slug,
                        source_name=f"{company_name} Careers (Lever)",
                        external_id=f"{slug}:{item.get('id')}",
                        title=title,
                        company_name=company_name,
                        location_raw=loc_name,
                        source_url=hosted_url,
                        apply_url=hosted_url,
                        description_raw=full_desc,
                        work_mode=mode,
                        employment_type=cats.get("commitment") or "Full-time",
                        category=cats.get("team") or cats.get("department"),
                        salary_min=float(sal_range["min"]) if sal_range.get("min") else None,
                        salary_max=float(sal_range["max"]) if sal_range.get("max") else None,
                        salary_currency=sal_range.get("currency"),
                        salary_period=sal_range.get("interval"),
                        published_at=_parse_iso_dt(item.get("createdAt")),
                        is_direct_company_link=True,
                    )
                )
                if len(jobs) >= max_results:
                    break

        status = "ok" if pages > 0 else "error"
        return SourceSearchResult(
            source_slug=self.slug,
            source_name=self.name,
            status=status,
            jobs=jobs,
            queries_executed=queries[:3],
            pages_fetched=pages,
            error_message="; ".join(errors[:3]) if status == "error" else None,
            duration_ms=int((time.monotonic() - t0) * 1000),
        )


class AshbyCareerPagesConnector(BaseJobSourceConnector):
    slug = "ashby_direct"
    name = "Company Career Pages (Ashby ATS)"
    source_type = "company_ats"
    base_url = "https://api.ashbyhq.com/posting-api/job-board"
    requires_api_key = False
    supported_countries = ["Worldwide", "United States", "United Kingdom", "Europe", "Canada"]
    rate_limit_rpm = 40
    terms_notes = "Official Ashby public Job Board API with structured compensation & remote flags."

    async def search(
        self,
        queries: List[str],
        countries: List[str],
        max_results: int = 25,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> SourceSearchResult:
        t0 = time.monotonic()
        jobs: List[RawDiscoveredJob] = []
        pages = 0
        boards = list(DEFAULT_ASHBY_BOARDS)
        for custom in (preferences or {}).get("custom_ats_boards") or []:
            if custom.get("provider") == "ashby":
                boards.insert(0, (custom["slug"], custom["company_name"]))

        errors: List[str] = []
        for slug, company_name in boards:
            if len(jobs) >= max_results:
                break
            url = f"{self.base_url}/{slug}"
            cache_key = f"ashby::{slug}"
            try:
                data = source_cache.get(cache_key)
                if data is None:
                    resp = await self._request_with_retries(
                        "GET", url, params={"includeCompensation": "true"}, retries=1
                    )
                    data = resp.json()
                    source_cache.set(cache_key, data)
                pages += 1
            except Exception as exc:
                errors.append(f"{slug}: {type(exc).__name__}")
                continue

            for item in (data.get("jobs") or []):
                title = (item.get("title") or "").strip()
                desc = item.get("descriptionPlain") or item.get("descriptionHtml") or ""
                dept = item.get("department") or item.get("team") or ""
                if queries and not _matches_any_query(f"{title} {dept} {desc}", queries):
                    continue
                job_url = item.get("jobUrl") or item.get("applyUrl") or ""
                apply_url = item.get("applyUrl") or job_url
                if not job_url:
                    continue
                is_remote = bool(item.get("isRemote"))
                workplace = (item.get("workplaceType") or "").lower()
                mode = workplace if workplace in ("remote", "hybrid", "onsite") else (
                    "remote" if is_remote else None
                )
                comp = item.get("compensation") or {}
                comp_summary = comp.get("compensationTierSummary") or comp.get("scrapeableCompensationSalarySummary")
                jobs.append(
                    RawDiscoveredJob(
                        source_slug=self.slug,
                        source_name=f"{company_name} Careers (Ashby)",
                        external_id=f"{slug}:{item.get('id')}",
                        title=title,
                        company_name=company_name,
                        location_raw=(item.get("location") or ("Remote" if is_remote else "United States")).strip(),
                        source_url=job_url,
                        apply_url=apply_url,
                        description_raw=desc,
                        work_mode=mode,
                        employment_type=item.get("employmentType") or "Full-time",
                        category=dept or None,
                        salary_raw=comp_summary,
                        published_at=_parse_iso_dt(item.get("publishedAt")),
                        is_direct_company_link=True,
                    )
                )
                if len(jobs) >= max_results:
                    break

        status = "ok" if pages > 0 else "error"
        return SourceSearchResult(
            source_slug=self.slug,
            source_name=self.name,
            status=status,
            jobs=jobs,
            queries_executed=queries[:3],
            pages_fetched=pages,
            error_message="; ".join(errors[:3]) if status == "error" else None,
            duration_ms=int((time.monotonic() - t0) * 1000),
        )
