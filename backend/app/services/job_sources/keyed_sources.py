"""Official API-key job connectors: Adzuna, Jooble, USAJOBS, Reed UK, and JSearch.

Never fakes responses when API keys are unconfigured; instead returns status='skipped_missing_key'
so the UI and Reporting Agent transparently disclose what requires keys.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from app.services.job_sources.base import (
    BaseJobSourceConnector,
    RawDiscoveredJob,
    SourceSearchResult,
)
from app.services.job_sources.open_sources import _parse_iso_dt

ADZUNA_COUNTRY_MAP: Dict[str, str] = {
    "united states": "us",
    "united kingdom": "gb",
    "germany": "de",
    "france": "fr",
    "canada": "ca",
    "australia": "au",
    "india": "in",
    "netherlands": "nl",
    "singapore": "sg",
    "switzerland": "ch",
    "poland": "pl",
    "spain": "es",
    "italy": "it",
    "austria": "at",
    "belgium": "be",
    "brazil": "br",
    "mexico": "mx",
    "new zealand": "nz",
    "south africa": "za",
}


class AdzunaConnector(BaseJobSourceConnector):
    slug = "adzuna"
    name = "Adzuna"
    source_type = "aggregator"
    base_url = "https://api.adzuna.com/v1/api/jobs"
    requires_api_key = True
    api_key_env_vars = ["ADZUNA_APP_ID", "ADZUNA_APP_KEY"]
    supported_countries = [
        "United States", "United Kingdom", "Germany", "France", "Canada",
        "Australia", "India", "Netherlands", "Singapore", "Switzerland", "Poland", "Spain",
    ]
    rate_limit_rpm = 25
    terms_notes = "Official Adzuna REST API (requires free developer ADZUNA_APP_ID & ADZUNA_APP_KEY)."

    async def search(
        self,
        queries: List[str],
        countries: List[str],
        max_results: int = 25,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> SourceSearchResult:
        if not self.is_configured():
            return SourceSearchResult(
                source_slug=self.slug,
                source_name=self.name,
                status="skipped_missing_key",
                error_message="Configure ADZUNA_APP_ID and ADZUNA_APP_KEY in .env to enable Adzuna country search.",
            )
        t0 = time.monotonic()
        jobs: List[RawDiscoveredJob] = []
        pages = 0
        executed: List[str] = []
        country_codes = [
            ADZUNA_COUNTRY_MAP[c.lower()]
            for c in countries
            if c.lower() in ADZUNA_COUNTRY_MAP
        ] or ["gb", "us"]

        try:
            q_str = (queries or ["software engineer"])[0]
            for cc in country_codes[:3]:
                if len(jobs) >= max_results:
                    break
                url = f"{self.base_url}/{cc}/search/1"
                resp = await self._request_with_retries(
                    "GET",
                    url,
                    params={
                        "app_id": self.settings.ADZUNA_APP_ID,
                        "app_key": self.settings.ADZUNA_APP_KEY,
                        "what": q_str,
                        "results_per_page": min(25, max_results),
                        "content-type": "application/json",
                    },
                )
                pages += 1
                executed.append(f"{q_str} ({cc})")
                data = resp.json()
                for item in (data.get("results") or []):
                    redirect_url = item.get("redirect_url") or ""
                    if not redirect_url:
                        continue
                    jobs.append(
                        RawDiscoveredJob(
                            source_slug=self.slug,
                            source_name=self.name,
                            external_id=str(item.get("id") or redirect_url),
                            title=(item.get("title") or "").strip(),
                            company_name=((item.get("company") or {}).get("display_name") or "Unknown Company").strip(),
                            location_raw=((item.get("location") or {}).get("display_name") or cc.upper()).strip(),
                            source_url=redirect_url,
                            apply_url=redirect_url,
                            description_raw=item.get("description") or "",
                            employment_type=(item.get("contract_time") or "full_time").replace("_", " ").title(),
                            category=(item.get("category") or {}).get("label"),
                            salary_min=float(item["salary_min"]) if item.get("salary_min") else None,
                            salary_max=float(item["salary_max"]) if item.get("salary_max") else None,
                            salary_period="year" if (item.get("salary_min") or item.get("salary_max")) else None,
                            published_at=_parse_iso_dt(item.get("created")),
                        )
                    )
                    if len(jobs) >= max_results:
                        break
            return SourceSearchResult(
                source_slug=self.slug,
                source_name=self.name,
                status="ok",
                jobs=jobs,
                queries_executed=executed,
                pages_fetched=pages,
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
        except Exception as exc:
            return SourceSearchResult(
                source_slug=self.slug,
                source_name=self.name,
                status="error",
                error_message=str(exc),
                queries_executed=executed,
                pages_fetched=pages,
                duration_ms=int((time.monotonic() - t0) * 1000),
            )


class JoobleConnector(BaseJobSourceConnector):
    slug = "jooble"
    name = "Jooble"
    source_type = "aggregator"
    base_url = "https://jooble.org/api"
    requires_api_key = True
    api_key_env_vars = ["JOOBLE_API_KEY"]
    supported_countries = ["Worldwide"]
    rate_limit_rpm = 25
    terms_notes = "Official Jooble REST API covering 65+ countries (requires JOOBLE_API_KEY)."

    async def search(
        self,
        queries: List[str],
        countries: List[str],
        max_results: int = 25,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> SourceSearchResult:
        if not self.is_configured():
            return SourceSearchResult(
                source_slug=self.slug,
                source_name=self.name,
                status="skipped_missing_key",
                error_message="Configure JOOBLE_API_KEY in .env to enable Jooble global aggregator search.",
            )
        t0 = time.monotonic()
        jobs: List[RawDiscoveredJob] = []
        pages = 0
        q_str = (queries or ["software engineer"])[0]
        try:
            for country in (countries or [""])[:2]:
                if len(jobs) >= max_results:
                    break
                url = f"{self.base_url}/{self.settings.JOOBLE_API_KEY}"
                payload = {
                    "keywords": q_str,
                    "location": "" if country.lower() in ("worldwide", "remote / worldwide") else country,
                    "page": "1",
                }
                resp = await self._request_with_retries("POST", url, json_body=payload)
                pages += 1
                data = resp.json()
                for item in (data.get("jobs") or []):
                    link = item.get("link") or ""
                    if not link:
                        continue
                    jobs.append(
                        RawDiscoveredJob(
                            source_slug=self.slug,
                            source_name=self.name,
                            external_id=str(item.get("id") or link),
                            title=(item.get("title") or "").strip(),
                            company_name=(item.get("company") or "Unknown Company").strip(),
                            location_raw=(item.get("location") or country or "Worldwide").strip(),
                            source_url=link,
                            apply_url=link,
                            description_raw=item.get("snippet") or "",
                            employment_type=item.get("type") or "Full-time",
                            salary_raw=item.get("salary") or None,
                            published_at=_parse_iso_dt(item.get("updated")),
                        )
                    )
                    if len(jobs) >= max_results:
                        break
            return SourceSearchResult(
                source_slug=self.slug,
                source_name=self.name,
                status="ok",
                jobs=jobs,
                queries_executed=[q_str],
                pages_fetched=pages,
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
        except Exception as exc:
            return SourceSearchResult(
                source_slug=self.slug,
                source_name=self.name,
                status="error",
                error_message=str(exc),
                pages_fetched=pages,
                duration_ms=int((time.monotonic() - t0) * 1000),
            )


class USAJobsConnector(BaseJobSourceConnector):
    slug = "usajobs"
    name = "USAJOBS (U.S. Government)"
    source_type = "government"
    base_url = "https://data.usajobs.gov/api/Search"
    requires_api_key = True
    api_key_env_vars = ["USAJOBS_API_KEY"]
    supported_countries = ["United States"]
    rate_limit_rpm = 25
    terms_notes = "Official U.S. OPM federal civil-service API (requires free USAJOBS_API_KEY)."

    async def search(
        self,
        queries: List[str],
        countries: List[str],
        max_results: int = 25,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> SourceSearchResult:
        if not self.is_configured():
            return SourceSearchResult(
                source_slug=self.slug,
                source_name=self.name,
                status="skipped_missing_key",
                error_message="Configure USAJOBS_API_KEY in .env to search official U.S. government jobs.",
            )
        t0 = time.monotonic()
        jobs: List[RawDiscoveredJob] = []
        q_str = (queries or ["software"])[0]
        try:
            resp = await self._request_with_retries(
                "GET",
                self.base_url,
                params={"Keyword": q_str, "ResultsPerPage": min(25, max_results)},
                headers={
                    "Host": "data.usajobs.gov",
                    "User-Agent": self.settings.USAJOBS_USER_AGENT,
                    "Authorization-Key": self.settings.USAJOBS_API_KEY,
                },
            )
            items = ((resp.json().get("SearchResult") or {}).get("SearchResultItems")) or []
            for entry in items:
                desc = entry.get("MatchedObjectDescriptor") or {}
                apply_uris = desc.get("ApplyURI") or []
                pos_uri = desc.get("PositionURI") or (apply_uris[0] if apply_uris else "")
                if not pos_uri:
                    continue
                rem = (desc.get("PositionRemuneration") or [{}])[0]
                qual = desc.get("QualificationSummary") or ""
                summary = ((desc.get("UserArea") or {}).get("Details") or {}).get("JobSummary") or ""
                jobs.append(
                    RawDiscoveredJob(
                        source_slug=self.slug,
                        source_name=self.name,
                        external_id=str(entry.get("MatchedObjectId") or pos_uri),
                        title=(desc.get("PositionTitle") or "").strip(),
                        company_name=(desc.get("OrganizationName") or "U.S. Federal Government").strip(),
                        location_raw=(desc.get("PositionLocationDisplay") or "United States").strip(),
                        source_url=pos_uri,
                        apply_url=apply_uris[0] if apply_uris else pos_uri,
                        description_raw=f"{summary}\n\n{qual}".strip(),
                        salary_min=float(rem["MinimumRange"]) if rem.get("MinimumRange") else None,
                        salary_max=float(rem["MaximumRange"]) if rem.get("MaximumRange") else None,
                        salary_currency="USD",
                        salary_period=rem.get("Description"),
                        published_at=_parse_iso_dt(desc.get("PublicationStartDate")),
                        application_deadline=_parse_iso_dt(desc.get("ApplicationCloseDate")),
                        is_direct_company_link=True,
                    )
                )
            return SourceSearchResult(
                source_slug=self.slug,
                source_name=self.name,
                status="ok",
                jobs=jobs[:max_results],
                queries_executed=[q_str],
                pages_fetched=1,
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
        except Exception as exc:
            return SourceSearchResult(
                source_slug=self.slug,
                source_name=self.name,
                status="error",
                error_message=str(exc),
                duration_ms=int((time.monotonic() - t0) * 1000),
            )


class ReedUKConnector(BaseJobSourceConnector):
    slug = "reed_uk"
    name = "Reed.co.uk"
    source_type = "country_specific"
    base_url = "https://www.reed.co.uk/api/1.0/search"
    requires_api_key = True
    api_key_env_vars = ["REED_API_KEY"]
    supported_countries = ["United Kingdom"]
    rate_limit_rpm = 25
    terms_notes = "Official Reed UK Jobseeker API (requires free REED_API_KEY)."

    async def search(
        self,
        queries: List[str],
        countries: List[str],
        max_results: int = 25,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> SourceSearchResult:
        if not self.is_configured():
            return SourceSearchResult(
                source_slug=self.slug,
                source_name=self.name,
                status="skipped_missing_key",
                error_message="Configure REED_API_KEY in .env to enable Reed UK job search.",
            )
        t0 = time.monotonic()
        jobs: List[RawDiscoveredJob] = []
        q_str = (queries or ["software engineer"])[0]
        try:
            resp = await self._request_with_retries(
                "GET",
                self.base_url,
                params={"keywords": q_str, "resultsToTake": min(25, max_results)},
                auth=(self.settings.REED_API_KEY, ""),
            )
            for item in (resp.json().get("results") or []):
                job_url = item.get("jobUrl") or ""
                if not job_url:
                    continue
                jobs.append(
                    RawDiscoveredJob(
                        source_slug=self.slug,
                        source_name=self.name,
                        external_id=str(item.get("jobId") or job_url),
                        title=(item.get("jobTitle") or "").strip(),
                        company_name=(item.get("employerName") or "UK Employer").strip(),
                        location_raw=f"{item.get('locationName', 'UK')}, United Kingdom",
                        source_url=job_url,
                        apply_url=job_url,
                        description_raw=item.get("jobDescription") or "",
                        salary_min=float(item["minimumSalary"]) if item.get("minimumSalary") else None,
                        salary_max=float(item["maximumSalary"]) if item.get("maximumSalary") else None,
                        salary_currency=item.get("currency") or "GBP",
                        salary_period="year" if (item.get("minimumSalary") or item.get("maximumSalary")) else None,
                        published_at=_parse_iso_dt(item.get("date")),
                        application_deadline=_parse_iso_dt(item.get("expirationDate")),
                    )
                )
            return SourceSearchResult(
                source_slug=self.slug,
                source_name=self.name,
                status="ok",
                jobs=jobs[:max_results],
                queries_executed=[q_str],
                pages_fetched=1,
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
        except Exception as exc:
            return SourceSearchResult(
                source_slug=self.slug,
                source_name=self.name,
                status="error",
                error_message=str(exc),
                duration_ms=int((time.monotonic() - t0) * 1000),
            )


class JSearchConnector(BaseJobSourceConnector):
    slug = "jsearch"
    name = "JSearch (Google Jobs / LinkedIn / Indeed / Glassdoor Gateway)"
    source_type = "aggregator"
    base_url = "https://jsearch.p.rapidapi.com/search"
    requires_api_key = True
    api_key_env_vars = ["JSEARCH_API_KEY"]
    supported_countries = ["Worldwide"]
    rate_limit_rpm = 20
    terms_notes = (
        "Permitted commercial API gateway indexing Google for Jobs (LinkedIn, Indeed, Glassdoor, Monster). "
        "Requires JSEARCH_API_KEY."
    )

    async def search(
        self,
        queries: List[str],
        countries: List[str],
        max_results: int = 25,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> SourceSearchResult:
        if not self.is_configured():
            return SourceSearchResult(
                source_slug=self.slug,
                source_name=self.name,
                status="skipped_missing_key",
                error_message=(
                    "Configure JSEARCH_API_KEY in .env to include Google Jobs / LinkedIn / Indeed / Glassdoor "
                    "listings via the licensed JSearch API."
                ),
            )
        t0 = time.monotonic()
        jobs: List[RawDiscoveredJob] = []
        q_base = (queries or ["software engineer"])[0]
        country = (countries or ["United States"])[0]
        full_query = f"{q_base} in {country}" if country.lower() != "worldwide" else q_base
        try:
            resp = await self._request_with_retries(
                "GET",
                self.base_url,
                params={"query": full_query, "page": "1", "num_pages": "2"},
                headers={
                    "X-RapidAPI-Key": self.settings.JSEARCH_API_KEY,
                    "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
                },
            )
            for item in (resp.json().get("data") or []):
                apply_link = item.get("job_apply_link") or item.get("job_google_link") or ""
                if not apply_link:
                    continue
                city = item.get("job_city") or ""
                ctry = item.get("job_country") or country
                loc = f"{city}, {ctry}".strip(", ")
                publisher = item.get("job_publisher") or "JSearch"
                jobs.append(
                    RawDiscoveredJob(
                        source_slug=self.slug,
                        source_name=f"JSearch ({publisher})",
                        external_id=str(item.get("job_id") or apply_link),
                        title=(item.get("job_title") or "").strip(),
                        company_name=(item.get("employer_name") or "Unknown Company").strip(),
                        company_logo_url=item.get("employer_logo"),
                        location_raw=loc,
                        source_url=item.get("job_google_link") or apply_link,
                        apply_url=apply_link,
                        description_raw=item.get("job_description") or "",
                        work_mode="remote" if item.get("job_is_remote") else "onsite",
                        employment_type=(item.get("job_employment_type") or "FULLTIME").title(),
                        salary_min=float(item["job_min_salary"]) if item.get("job_min_salary") else None,
                        salary_max=float(item["job_max_salary"]) if item.get("job_max_salary") else None,
                        salary_currency=item.get("job_salary_currency"),
                        salary_period=(item.get("job_salary_period") or "").lower() or None,
                        published_at=_parse_iso_dt(item.get("job_posted_at_datetime_utc")),
                        application_deadline=_parse_iso_dt(item.get("job_offer_expiration_datetime_utc")),
                        is_direct_company_link=bool(item.get("job_apply_is_direct")),
                    )
                )
                if len(jobs) >= max_results:
                    break
            return SourceSearchResult(
                source_slug=self.slug,
                source_name=self.name,
                status="ok",
                jobs=jobs,
                queries_executed=[full_query],
                pages_fetched=1,
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
        except Exception as exc:
            return SourceSearchResult(
                source_slug=self.slug,
                source_name=self.name,
                status="error",
                error_message=str(exc),
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
