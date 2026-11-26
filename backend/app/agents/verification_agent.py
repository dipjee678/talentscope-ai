"""Agent 5: Job Verification and Duplicate Detection Agent.

Responsibilities:
  1. Verify listing & application URL reachability without bypassing anti-bot protections.
  2. Detect expired listings via deadline timestamp or explicit page closure notices.
  3. Deduplicate across job boards using canonical URLs, normalized (company, title, location)
     fingerprints, and semantic description similarity.
  4. Prioritize direct first-party company application links over third-party aggregators.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from app.core.config import get_settings
from app.models.entities import JobListing
from app.services.skill_taxonomy import cosine_similarity

CLOSED_JOB_MARKERS = (
    "no longer accepting applications",
    "this job has expired",
    "position has been filled",
    "job is no longer available",
    "this position is closed",
    "sorry, the job you are looking for is no longer open",
)

TRACKING_QUERY_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "gh_src", "lever-source", "source", "fbclid", "gclid",
}


def canonicalize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url.strip())
    clean_query = urlencode(
        [(k, v) for k, v in parse_qsl(parsed.query) if k.lower() not in TRACKING_QUERY_PARAMS]
    )
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", clean_query, ""))


class VerificationAgent:
    agent_name = "VerificationAgent"

    def __init__(self) -> None:
        self.settings = get_settings()

    async def _probe_single_job(self, job: JobListing) -> None:
        now = datetime.now(timezone.utc)

        # 1. Check deadline expiration first
        if job.application_deadline:
            dl = job.application_deadline
            if dl.tzinfo is None:
                dl = dl.replace(tzinfo=timezone.utc)
            if dl < now:
                job.verification_status = "expired"
                job.last_verified_at = now
                job.verification_details_json = {
                    "reason": f"Application deadline passed ({dl.date().isoformat()}).",
                    "checked_url": job.apply_url,
                }
                return

        if not job.apply_url.startswith(("http://", "https://")):
            job.verification_status = "broken_link"
            job.last_verified_at = now
            job.verification_details_json = {"reason": "Invalid application URL scheme."}
            return

        if not self.settings.VERIFY_LIVE_URLS:
            job.verification_status = "unverified"
            job.last_verified_at = now
            job.verification_details_json = {
                "reason": "Live HTTP probing disabled in configuration; metadata validated only."
            }
            return

        headers = {
            "User-Agent": self.settings.HTTP_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Range": "bytes=0-12288",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.VERIFY_HTTP_TIMEOUT_SECONDS,
                follow_redirects=True,
            ) as client:
                resp = await client.get(job.apply_url, headers=headers)
                code = resp.status_code

                if code in (404, 410):
                    job.verification_status = "expired"
                    job.verification_details_json = {
                        "http_status": code,
                        "reason": "Application page returned HTTP 404/410 (listing removed or closed).",
                        "final_url": str(resp.url),
                    }
                elif 500 <= code < 600:
                    job.verification_status = "broken_link"
                    job.verification_details_json = {
                        "http_status": code,
                        "reason": f"Upstream server error (HTTP {code}).",
                    }
                elif code in (401, 403, 429):
                    # Respect anti-bot / auth boundaries — honestly mark unverified rather than faking
                    job.verification_status = "unverified"
                    job.verification_details_json = {
                        "http_status": code,
                        "reason": (
                            f"Host restricted automated verification (HTTP {code}); "
                            "sourced from permitted feed—click Apply to view in browser."
                        ),
                    }
                elif 200 <= code < 400:
                    snippet = (resp.text or "")[:12000].lower()
                    if any(marker in snippet for marker in CLOSED_JOB_MARKERS):
                        job.verification_status = "expired"
                        job.verification_details_json = {
                            "http_status": code,
                            "reason": "Listing page indicates applications are closed.",
                            "final_url": str(resp.url),
                        }
                    else:
                        job.verification_status = "verified_active"
                        job.verification_details_json = {
                            "http_status": code,
                            "reason": "Application link responded HTTP 200 OK with active job content.",
                            "final_url": str(resp.url),
                        }
                else:
                    job.verification_status = "unverified"
                    job.verification_details_json = {"http_status": code}
        except Exception as exc:
            job.verification_status = "unverified"
            job.verification_details_json = {
                "reason": f"Verification probe timed out or could not connect ({type(exc).__name__})."
            }

        job.last_verified_at = now

    def deduplicate(self, jobs: List[JobListing]) -> Tuple[List[JobListing], int]:
        """Deduplicate listings while prioritizing direct company career page links."""
        # Sort so direct company links and richer descriptions come first as canonical winners
        ordered = sorted(
            jobs,
            key=lambda j: (
                1 if j.is_direct_company_link else 0,
                1 if (j.salary_min or j.salary_max or j.salary_raw) else 0,
                len(j.description_text or ""),
            ),
            reverse=True,
        )

        canonicals: List[JobListing] = []
        by_url: Dict[str, JobListing] = {}
        by_fingerprint: Dict[str, JobListing] = {}
        by_company: Dict[str, List[JobListing]] = {}
        duplicates_removed = 0

        for job in ordered:
            canon_url = canonicalize_url(job.apply_url)
            comp_key = re.sub(r"[^a-z0-9]", "", (job.company_name or "").lower())

            match_winner: JobListing | None = None
            if canon_url and canon_url in by_url:
                match_winner = by_url[canon_url]
            elif job.dedup_fingerprint in by_fingerprint:
                match_winner = by_fingerprint[job.dedup_fingerprint]
            elif comp_key and comp_key in by_company:
                for candidate in by_company[comp_key]:
                    sim = cosine_similarity(job.embedding_vector, candidate.embedding_vector)
                    if sim >= 0.92:
                        match_winner = candidate
                        break

            if match_winner is not None:
                job.is_duplicate = True
                job.canonical_job_id = match_winner.id
                alt = list(match_winner.alternate_sources_json or [])
                alt.append({"source_name": job.source_name, "source_url": job.source_url})
                match_winner.alternate_sources_json = alt
                duplicates_removed += 1
            else:
                job.is_duplicate = False
                canonicals.append(job)
                if canon_url:
                    by_url[canon_url] = job
                by_fingerprint[job.dedup_fingerprint] = job
                if comp_key:
                    by_company.setdefault(comp_key, []).append(job)

        return canonicals, duplicates_removed

    async def verify_and_deduplicate(self, jobs: List[JobListing]) -> Tuple[List[JobListing], Dict[str, int]]:
        canonicals, dup_count = self.deduplicate(jobs)

        sem = asyncio.Semaphore(self.settings.VERIFY_MAX_CONCURRENCY)

        async def _guarded_probe(j: JobListing) -> None:
            async with sem:
                await self._probe_single_job(j)

        await asyncio.gather(*[_guarded_probe(j) for j in canonicals])

        verified_active = sum(1 for j in canonicals if j.verification_status == "verified_active")
        unverified = sum(1 for j in canonicals if j.verification_status == "unverified")
        expired_or_broken = sum(
            1 for j in canonicals if j.verification_status in ("expired", "broken_link")
        )

        active_pool = [
            j for j in canonicals if j.verification_status not in ("expired", "broken_link")
        ]
        metrics = {
            "duplicates_removed": dup_count,
            "verified_active": verified_active,
            "unverified": unverified,
            "expired_or_broken_removed": expired_or_broken,
            "surviving_jobs": len(active_pool),
        }
        return active_pool, metrics


verification_agent = VerificationAgent()
