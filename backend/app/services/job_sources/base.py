"""Base classes, rate limiting, caching, and data structures for permitted job source connectors."""
from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.config import get_settings


@dataclass
class RawDiscoveredJob:
    source_slug: str
    source_name: str
    external_id: str
    title: str
    company_name: str
    location_raw: str
    source_url: str
    apply_url: str
    description_raw: str = ""
    company_logo_url: Optional[str] = None
    work_mode: Optional[str] = None
    employment_type: Optional[str] = None
    experience_level: Optional[str] = None
    category: Optional[str] = None
    industry: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    salary_period: Optional[str] = None
    salary_raw: Optional[str] = None
    visa_sponsorship: Optional[bool] = None
    published_at: Optional[datetime] = None
    application_deadline: Optional[datetime] = None
    is_direct_company_link: bool = False
    raw_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceSearchResult:
    source_slug: str
    source_name: str
    status: str  # ok | skipped_missing_key | error | rate_limited
    jobs: List[RawDiscoveredJob] = field(default_factory=list)
    queries_executed: List[str] = field(default_factory=list)
    pages_fetched: int = 0
    error_message: Optional[str] = None
    duration_ms: int = 0


class AsyncRateLimiter:
    """Per-source minimum-interval rate limiter to respect upstream servers."""

    def __init__(self) -> None:
        self._locks: Dict[str, asyncio.Lock] = {}
        self._last_call: Dict[str, float] = {}

    async def acquire(self, key: str, rpm: int = 30) -> None:
        min_interval = 60.0 / max(1, rpm)
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            elapsed = now - self._last_call.get(key, 0.0)
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
            self._last_call[key] = time.monotonic()


class TTLCache:
    """Lightweight TTL cache for job-source query responses to prevent redundant API hits."""

    def __init__(self, ttl_seconds: int = 300, max_entries: int = 256) -> None:
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._store: Dict[str, Tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if not entry:
            return None
        expires_at, val = entry
        if time.monotonic() > expires_at:
            self._store.pop(key, None)
            return None
        return val

    def set(self, key: str, value: Any) -> None:
        if len(self._store) >= self.max_entries:
            oldest_key = next(iter(self._store))
            self._store.pop(oldest_key, None)
        self._store[key] = (time.monotonic() + self.ttl, value)


rate_limiter = AsyncRateLimiter()
source_cache = TTLCache(ttl_seconds=300)


class BaseJobSourceConnector(ABC):
    slug: str = ""
    name: str = ""
    source_type: str = "international"  # international | country_specific | company_ats | government | aggregator
    base_url: str = ""
    requires_api_key: bool = False
    api_key_env_vars: List[str] = []
    supported_countries: List[str] = ["Worldwide"]
    rate_limit_rpm: int = 30
    terms_notes: str = "Official public API."

    def __init__(self) -> None:
        self.settings = get_settings()

    def is_configured(self) -> bool:
        if not self.requires_api_key:
            return True
        for var in self.api_key_env_vars:
            if not getattr(self.settings, var, ""):
                return False
        return True

    async def _request_with_retries(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        auth: Optional[Tuple[str, str]] = None,
        retries: int = 2,
    ) -> httpx.Response:
        req_headers = {
            "User-Agent": self.settings.HTTP_USER_AGENT,
            "Accept": "application/json, application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
        }
        if headers:
            req_headers.update(headers)

        last_exc: Optional[Exception] = None
        for attempt in range(retries + 1):
            await rate_limiter.acquire(self.slug, self.rate_limit_rpm)
            try:
                async with httpx.AsyncClient(
                    timeout=self.settings.SEARCH_HTTP_TIMEOUT_SECONDS,
                    follow_redirects=True,
                ) as client:
                    resp = await client.request(
                        method,
                        url,
                        params=params,
                        json=json_body,
                        headers=req_headers,
                        auth=auth,
                    )
                    if resp.status_code == 429:
                        if attempt < retries:
                            await asyncio.sleep(1.5 * (attempt + 1))
                            continue
                    resp.raise_for_status()
                    return resp
            except Exception as exc:
                last_exc = exc
                if attempt < retries:
                    await asyncio.sleep(0.8 * (attempt + 1))
        assert last_exc is not None
        raise last_exc

    @abstractmethod
    async def search(
        self,
        queries: List[str],
        countries: List[str],
        max_results: int = 25,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> SourceSearchResult:
        raise NotImplementedError
