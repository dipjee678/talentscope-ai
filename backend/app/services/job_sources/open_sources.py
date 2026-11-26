"""Open, keyless official public job APIs and syndication feeds.

All connectors strictly use documented public endpoints, send compliant User-Agent headers,
respect rate limits, and never scrape behind authentication or anti-bot gates.
"""
from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional

from app.services.job_sources.base import (
    BaseJobSourceConnector,
    RawDiscoveredJob,
    SourceSearchResult,
    source_cache,
)


def _parse_iso_dt(val: Any) -> Optional[datetime]:
    if not val:
        return None
    if isinstance(val, (int, float)):
        try:
            # Handle unix epoch seconds or ms
            ts = val / 1000.0 if val > 1e12 else float(val)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            return None
    if isinstance(val, str):
        s = val.strip()
        try:
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            dt = datetime.fromisoformat(s)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                return parsedate_to_datetime(val)
            except Exception:
                return None
    return None


def _matches_any_query(text: str, queries: List[str]) -> bool:
    if not queries:
        return True
    low = text.lower()
    for q in queries:
        tokens = [t for t in q.lower().split() if len(t) >= 2]
        if tokens and all(t in low for t in tokens[:2]):
            return True
        if any(t in low for t in tokens if len(t) >= 4):
            return True
    return False


class RemotiveConnector(BaseJobSourceConnector):
    slug = "remotive"
    name = "Remotive"
    source_type = "international"
    base_url = "https://remotive.com/api/remote-jobs"
    requires_api_key = False
    supported_countries = ["Worldwide", "United States", "United Kingdom", "Canada", "Germany", "Europe"]
    rate_limit_rpm = 20
    terms_notes = "Official Remotive public JSON API (attribution link preserved)."

    async def search(
        self,
        queries: List[str],
        countries: List[str],
        max_results: int = 25,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> SourceSearchResult:
        t0 = time.monotonic()
        jobs: List[RawDiscoveredJob] = []
        seen_ids: set[str] = set()
        executed: List[str] = []
        pages = 0

        try:
            search_terms = (queries or ["software"])[:3]
            for term in search_terms:
                if len(jobs) >= max_results:
                    break
                cache_key = f"remotive::{term.lower()}"
                data = source_cache.get(cache_key)
                if data is None:
                    resp = await self._request_with_retries("GET", self.base_url, params={"search": term, "limit": max_results})
                    data = resp.json()
                    source_cache.set(cache_key, data)
                executed.append(term)
                pages += 1

                for item in (data.get("jobs") or []):
                    ext_id = str(item.get("id", ""))
                    if not ext_id or ext_id in seen_ids:
                        continue
                    seen_ids.add(ext_id)
                    url = item.get("url") or ""
                    if not url:
                        continue
                    jobs.append(
                        RawDiscoveredJob(
                            source_slug=self.slug,
                            source_name=self.name,
                            external_id=ext_id,
                            title=(item.get("title") or "").strip(),
                            company_name=(item.get("company_name") or "Unknown Company").strip(),
                            company_logo_url=item.get("company_logo"),
                            location_raw=(item.get("candidate_required_location") or "Worldwide").strip(),
                            source_url=url,
                            apply_url=url,
                            description_raw=item.get("description") or "",
                            work_mode="remote",
                            employment_type=(item.get("job_type") or "Full-time").replace("_", " ").title(),
                            category=item.get("category"),
                            salary_raw=item.get("salary") or None,
                            published_at=_parse_iso_dt(item.get("publication_date")),
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


class ArbeitnowConnector(BaseJobSourceConnector):
    slug = "arbeitnow"
    name = "Arbeitnow"
    source_type = "international"
    base_url = "https://www.arbeitnow.com/api/job-board-api"
    requires_api_key = False
    supported_countries = ["Germany", "Europe", "Netherlands", "United Kingdom", "Switzerland", "Worldwide"]
    rate_limit_rpm = 25
    terms_notes = "Official Arbeitnow public JSON API with pagination, remote, and visa sponsorship fields."

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
        try:
            for page_num in (1, 2):
                if len(jobs) >= max_results:
                    break
                cache_key = f"arbeitnow::p{page_num}"
                data = source_cache.get(cache_key)
                if data is None:
                    resp = await self._request_with_retries("GET", self.base_url, params={"page": page_num})
                    data = resp.json()
                    source_cache.set(cache_key, data)
                pages += 1
                items = data.get("data") or []
                if not items:
                    break
                for item in items:
                    blob = f"{item.get('title', '')} {' '.join(item.get('tags') or [])} {item.get('description', '')}"
                    if queries and not _matches_any_query(blob, queries):
                        continue
                    url = item.get("url") or ""
                    if not url:
                        continue
                    is_remote = bool(item.get("remote"))
                    visa = item.get("visa_sponsorship")
                    jobs.append(
                        RawDiscoveredJob(
                            source_slug=self.slug,
                            source_name=self.name,
                            external_id=str(item.get("slug") or url),
                            title=(item.get("title") or "").strip(),
                            company_name=(item.get("company_name") or "Unknown Company").strip(),
                            location_raw=(item.get("location") or ("Remote" if is_remote else "Europe")).strip(),
                            source_url=url,
                            apply_url=url,
                            description_raw=item.get("description") or "",
                            work_mode="remote" if is_remote else "onsite",
                            employment_type=", ".join(item.get("job_types") or ["Full-time"]),
                            category=", ".join((item.get("tags") or [])[:3]) or None,
                            visa_sponsorship=bool(visa) if visa is not None else None,
                            published_at=_parse_iso_dt(item.get("created_at")),
                        )
                    )
                    if len(jobs) >= max_results:
                        break
            return SourceSearchResult(
                source_slug=self.slug,
                source_name=self.name,
                status="ok",
                jobs=jobs,
                queries_executed=queries[:3],
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


class RemoteOKConnector(BaseJobSourceConnector):
    slug = "remoteok"
    name = "Remote OK"
    source_type = "international"
    base_url = "https://remoteok.com/api"
    requires_api_key = False
    supported_countries = ["Worldwide", "United States", "Europe", "United Kingdom", "Canada"]
    rate_limit_rpm = 12
    terms_notes = "Official Remote OK JSON feed (index 0 legal notice respected; direct link preserved)."

    async def search(
        self,
        queries: List[str],
        countries: List[str],
        max_results: int = 25,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> SourceSearchResult:
        t0 = time.monotonic()
        jobs: List[RawDiscoveredJob] = []
        try:
            cache_key = "remoteok::feed"
            items = source_cache.get(cache_key)
            if items is None:
                resp = await self._request_with_retries("GET", self.base_url)
                items = resp.json()
                source_cache.set(cache_key, items)

            # Element 0 is legal metadata object in Remote OK API
            listings = items[1:] if isinstance(items, list) and len(items) > 1 else []
            for item in listings:
                if not isinstance(item, dict):
                    continue
                title = (item.get("position") or item.get("title") or "").strip()
                if not title:
                    continue
                blob = f"{title} {' '.join(item.get('tags') or [])} {item.get('description', '')}"
                if queries and not _matches_any_query(blob, queries):
                    continue
                source_url = item.get("url") or f"https://remoteok.com/remote-jobs/{item.get('id', '')}"
                apply_url = item.get("apply_url") or source_url
                sal_min = float(item["salary_min"]) if item.get("salary_min") else None
                sal_max = float(item["salary_max"]) if item.get("salary_max") else None
                jobs.append(
                    RawDiscoveredJob(
                        source_slug=self.slug,
                        source_name=self.name,
                        external_id=str(item.get("id") or source_url),
                        title=title,
                        company_name=(item.get("company") or "Unknown Company").strip(),
                        company_logo_url=item.get("company_logo") or item.get("logo"),
                        location_raw=(item.get("location") or "Worldwide").strip(),
                        source_url=source_url,
                        apply_url=apply_url,
                        description_raw=item.get("description") or "",
                        work_mode="remote",
                        employment_type="Full-time",
                        category=", ".join((item.get("tags") or [])[:3]) or None,
                        salary_min=sal_min if sal_min and sal_min > 0 else None,
                        salary_max=sal_max if sal_max and sal_max > 0 else None,
                        salary_currency="USD" if (sal_min or sal_max) else None,
                        salary_period="year" if (sal_min or sal_max) else None,
                        published_at=_parse_iso_dt(item.get("date") or item.get("epoch")),
                    )
                )
                if len(jobs) >= max_results:
                    break
            return SourceSearchResult(
                source_slug=self.slug,
                source_name=self.name,
                status="ok",
                jobs=jobs,
                queries_executed=queries[:3],
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


class TheMuseConnector(BaseJobSourceConnector):
    slug = "themuse"
    name = "The Muse"
    source_type = "international"
    base_url = "https://www.themuse.com/api/public/jobs"
    requires_api_key = False
    supported_countries = ["United States", "United Kingdom", "Canada", "Germany", "India", "Worldwide"]
    rate_limit_rpm = 25
    terms_notes = "Official The Muse public REST API with multi-page search."

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
        try:
            for page_idx in (1, 2):
                if len(jobs) >= max_results:
                    break
                params: Dict[str, Any] = {"page": page_idx}
                cache_key = f"themuse::p{page_idx}"
                data = source_cache.get(cache_key)
                if data is None:
                    resp = await self._request_with_retries("GET", self.base_url, params=params)
                    data = resp.json()
                    source_cache.set(cache_key, data)
                pages += 1

                for item in (data.get("results") or []):
                    title = (item.get("name") or "").strip()
                    contents = item.get("contents") or ""
                    cats = [c.get("name", "") for c in (item.get("categories") or [])]
                    blob = f"{title} {' '.join(cats)} {contents}"
                    if queries and not _matches_any_query(blob, queries):
                        continue
                    locs = [loc.get("name", "") for loc in (item.get("locations") or []) if loc.get("name")]
                    loc_str = ", ".join(locs) if locs else "Flexible / Remote"
                    refs = item.get("refs") or {}
                    landing_url = refs.get("landing_page") or ""
                    if not landing_url:
                        continue
                    levels = [lv.get("name", "") for lv in (item.get("levels") or []) if lv.get("name")]
                    company = (item.get("company") or {}).get("name") or "Unknown Company"
                    jobs.append(
                        RawDiscoveredJob(
                            source_slug=self.slug,
                            source_name=self.name,
                            external_id=str(item.get("id") or landing_url),
                            title=title,
                            company_name=company,
                            location_raw=loc_str,
                            source_url=landing_url,
                            apply_url=landing_url,
                            description_raw=contents,
                            work_mode="remote" if "remote" in loc_str.lower() or "flexible" in loc_str.lower() else None,
                            employment_type="Internship" if any("intern" in l.lower() for l in levels) else "Full-time",
                            experience_level=", ".join(levels) or None,
                            category=", ".join(cats[:2]) or None,
                            published_at=_parse_iso_dt(item.get("publication_date")),
                        )
                    )
                    if len(jobs) >= max_results:
                        break
            return SourceSearchResult(
                source_slug=self.slug,
                source_name=self.name,
                status="ok",
                jobs=jobs,
                queries_executed=queries[:3],
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


class JobicyConnector(BaseJobSourceConnector):
    slug = "jobicy"
    name = "Jobicy"
    source_type = "international"
    base_url = "https://jobicy.com/api/v2/remote-jobs"
    requires_api_key = False
    supported_countries = ["Worldwide", "United States", "United Kingdom", "Canada", "Germany", "Australia"]
    rate_limit_rpm = 20
    terms_notes = "Official Jobicy v2 public JSON API."

    async def search(
        self,
        queries: List[str],
        countries: List[str],
        max_results: int = 25,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> SourceSearchResult:
        t0 = time.monotonic()
        jobs: List[RawDiscoveredJob] = []
        seen: set[str] = set()
        executed: List[str] = []
        pages = 0
        try:
            tags = [q.split()[0].lower() for q in (queries or ["python"])[:2] if q.strip()]
            for tag in tags or ["dev"]:
                if len(jobs) >= max_results:
                    break
                params = {"count": min(50, max_results * 2), "tag": tag}
                cache_key = f"jobicy::{tag}"
                data = source_cache.get(cache_key)
                if data is None:
                    resp = await self._request_with_retries("GET", self.base_url, params=params)
                    data = resp.json()
                    source_cache.set(cache_key, data)
                executed.append(tag)
                pages += 1
                for item in (data.get("jobs") or []):
                    ext_id = str(item.get("id") or "")
                    if not ext_id or ext_id in seen:
                        continue
                    seen.add(ext_id)
                    url = item.get("url") or ""
                    if not url:
                        continue
                    sal_min = float(item["annualSalaryMin"]) if item.get("annualSalaryMin") else None
                    sal_max = float(item["annualSalaryMax"]) if item.get("annualSalaryMax") else None
                    jobs.append(
                        RawDiscoveredJob(
                            source_slug=self.slug,
                            source_name=self.name,
                            external_id=ext_id,
                            title=(item.get("jobTitle") or "").strip(),
                            company_name=(item.get("companyName") or "Unknown Company").strip(),
                            company_logo_url=item.get("companyLogo"),
                            location_raw=(item.get("jobGeo") or "Worldwide").strip(),
                            source_url=url,
                            apply_url=url,
                            description_raw=item.get("jobDescription") or item.get("jobExcerpt") or "",
                            work_mode="remote",
                            employment_type=", ".join(item.get("jobType") or ["Full-time"])
                            if isinstance(item.get("jobType"), list)
                            else str(item.get("jobType") or "Full-time"),
                            experience_level=item.get("jobLevel"),
                            industry=", ".join(item.get("jobIndustry") or [])
                            if isinstance(item.get("jobIndustry"), list)
                            else item.get("jobIndustry"),
                            salary_min=sal_min,
                            salary_max=sal_max,
                            salary_currency=item.get("salaryCurrency"),
                            salary_period="year" if (sal_min or sal_max) else None,
                            published_at=_parse_iso_dt(item.get("pubDate")),
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


class HimalayasConnector(BaseJobSourceConnector):
    slug = "himalayas"
    name = "Himalayas"
    source_type = "international"
    base_url = "https://himalayas.app/jobs/api"
    requires_api_key = False
    supported_countries = ["Worldwide", "United States", "United Kingdom", "Canada", "Australia", "Europe"]
    rate_limit_rpm = 20
    terms_notes = "Official Himalayas public JSON API with offset pagination."

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
        try:
            for offset in (0, 20):
                if len(jobs) >= max_results:
                    break
                cache_key = f"himalayas::o{offset}"
                data = source_cache.get(cache_key)
                if data is None:
                    resp = await self._request_with_retries(
                        "GET", self.base_url, params={"limit": 20, "offset": offset}
                    )
                    data = resp.json()
                    source_cache.set(cache_key, data)
                pages += 1
                for item in (data.get("jobs") or []):
                    title = (item.get("title") or "").strip()
                    desc = item.get("description") or item.get("excerpt") or ""
                    cats = item.get("categories") or []
                    if queries and not _matches_any_query(f"{title} {' '.join(cats)} {desc}", queries):
                        continue
                    app_link = item.get("applicationLink") or item.get("guid") or ""
                    guid_url = item.get("guid") or app_link
                    if not app_link:
                        continue
                    locs = item.get("locationRestrictions") or []
                    loc_str = ", ".join(locs) if locs else "Worldwide"
                    seniority = item.get("seniority")
                    if isinstance(seniority, list):
                        seniority = ", ".join(seniority)
                    jobs.append(
                        RawDiscoveredJob(
                            source_slug=self.slug,
                            source_name=self.name,
                            external_id=str(item.get("guid") or app_link),
                            title=title,
                            company_name=(item.get("companyName") or "Unknown Company").strip(),
                            company_logo_url=item.get("companyLogo"),
                            location_raw=loc_str,
                            source_url=guid_url,
                            apply_url=app_link,
                            description_raw=desc,
                            work_mode="remote",
                            employment_type=item.get("employmentType") or "Full-time",
                            experience_level=seniority,
                            category=", ".join(cats[:2]) if cats else None,
                            salary_min=float(item["minSalary"]) if item.get("minSalary") else None,
                            salary_max=float(item["maxSalary"]) if item.get("maxSalary") else None,
                            salary_currency=item.get("currency"),
                            salary_period="year" if (item.get("minSalary") or item.get("maxSalary")) else None,
                            published_at=_parse_iso_dt(item.get("pubDate")),
                            application_deadline=_parse_iso_dt(item.get("expiryDate")),
                        )
                    )
                    if len(jobs) >= max_results:
                        break
            return SourceSearchResult(
                source_slug=self.slug,
                source_name=self.name,
                status="ok",
                jobs=jobs,
                queries_executed=queries[:3],
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


class WeWorkRemotelyRSSConnector(BaseJobSourceConnector):
    slug = "weworkremotely"
    name = "We Work Remotely"
    source_type = "international"
    base_url = "https://weworkremotely.com/remote-jobs.rss"
    requires_api_key = False
    supported_countries = ["Worldwide", "United States", "United Kingdom", "Canada", "Europe"]
    rate_limit_rpm = 15
    terms_notes = "Official We Work Remotely public RSS syndication feed."

    async def search(
        self,
        queries: List[str],
        countries: List[str],
        max_results: int = 25,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> SourceSearchResult:
        t0 = time.monotonic()
        jobs: List[RawDiscoveredJob] = []
        try:
            cache_key = "wwr::rss"
            xml_text = source_cache.get(cache_key)
            if xml_text is None:
                resp = await self._request_with_retries("GET", self.base_url)
                xml_text = resp.text
                source_cache.set(cache_key, xml_text)

            root = ET.fromstring(xml_text)
            for item in root.findall(".//item"):
                raw_title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                desc = item.findtext("description") or ""
                region = (item.findtext("region") or "Worldwide").strip()
                category = (item.findtext("category") or "").strip()
                pub_date = item.findtext("pubDate")
                if not raw_title or not link:
                    continue
                if queries and not _matches_any_query(f"{raw_title} {category} {desc}", queries):
                    continue
                if ":" in raw_title:
                    company, job_title = [p.strip() for p in raw_title.split(":", 1)]
                else:
                    company, job_title = "Remote Employer", raw_title

                jobs.append(
                    RawDiscoveredJob(
                        source_slug=self.slug,
                        source_name=self.name,
                        external_id=item.findtext("guid") or link,
                        title=job_title,
                        company_name=company,
                        location_raw=region or "Worldwide",
                        source_url=link,
                        apply_url=link,
                        description_raw=desc,
                        work_mode="remote",
                        employment_type=(item.findtext("type") or "Full-time").strip(),
                        category=category or None,
                        published_at=_parse_iso_dt(pub_date),
                    )
                )
                if len(jobs) >= max_results:
                    break
            return SourceSearchResult(
                source_slug=self.slug,
                source_name=self.name,
                status="ok",
                jobs=jobs,
                queries_executed=queries[:3],
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


class JobTechDevSwedenConnector(BaseJobSourceConnector):
    slug = "jobtechdev_se"
    name = "JobTechDev (Sweden Employment Service)"
    source_type = "government"
    base_url = "https://jobsearch.api.jobtechdev.se/search"
    requires_api_key = False
    supported_countries = ["Sweden", "Europe"]
    rate_limit_rpm = 30
    terms_notes = "Official Swedish Public Employment Service (Arbetsförmedlingen) CC0 Open Data API."

    async def search(
        self,
        queries: List[str],
        countries: List[str],
        max_results: int = 25,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> SourceSearchResult:
        t0 = time.monotonic()
        jobs: List[RawDiscoveredJob] = []
        seen: set[str] = set()
        executed: List[str] = []
        pages = 0
        try:
            for q in (queries or ["software developer"])[:2]:
                if len(jobs) >= max_results:
                    break
                params = {"q": q, "limit": min(25, max_results)}
                cache_key = f"jobtech_se::{q.lower()}"
                data = source_cache.get(cache_key)
                if data is None:
                    resp = await self._request_with_retries("GET", self.base_url, params=params)
                    data = resp.json()
                    source_cache.set(cache_key, data)
                executed.append(q)
                pages += 1
                for hit in (data.get("hits") or []):
                    ext_id = str(hit.get("id") or "")
                    if not ext_id or ext_id in seen:
                        continue
                    seen.add(ext_id)
                    webpage = hit.get("webpage_url") or ""
                    app_details = hit.get("application_details") or {}
                    apply_url = app_details.get("url") or webpage
                    if not apply_url:
                        continue
                    workplace = hit.get("workplace_address") or {}
                    city = workplace.get("municipality") or ""
                    loc_str = f"{city}, Sweden" if city else "Sweden"
                    desc_obj = hit.get("description") or {}
                    employer = (hit.get("employer") or {}).get("name") or "Swedish Employer"
                    jobs.append(
                        RawDiscoveredJob(
                            source_slug=self.slug,
                            source_name=self.name,
                            external_id=ext_id,
                            title=(hit.get("headline") or "").strip(),
                            company_name=employer,
                            company_logo_url=hit.get("logo_url"),
                            location_raw=loc_str,
                            source_url=webpage or apply_url,
                            apply_url=apply_url,
                            description_raw=desc_obj.get("text") or "",
                            work_mode=None,
                            employment_type=(hit.get("working_hours_type") or {}).get("label") or "Full-time",
                            published_at=_parse_iso_dt(hit.get("publication_date")),
                            application_deadline=_parse_iso_dt(hit.get("application_deadline")),
                            is_direct_company_link=bool(app_details.get("url")),
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
