"""Agent 2: Job Discovery Agent.

Dynamically selects relevant international, country-specific, government, and direct ATS
company career page connectors; synthesizes multi-angle search queries from the candidate
profile and search preferences; and executes parallel rate-limited discovery.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Tuple

from app.models.entities import CandidateProfile, SearchPreference
from app.services.job_sources.base import RawDiscoveredJob, SourceSearchResult
from app.services.job_sources.registry import (
    NON_API_PORTAL_DISCLOSURES,
    select_connectors_for_countries,
)


class JobDiscoveryAgent:
    agent_name = "JobDiscoveryAgent"

    def build_search_queries(
        self,
        profile: CandidateProfile,
        pref: SearchPreference,
    ) -> List[str]:
        """Generate multiple distinct search queries from candidate CV + optional preferences."""
        queries: List[str] = []

        # 1. Explicit custom keywords & job categories
        for kw in (pref.custom_keywords_json or []):
            if kw and kw.strip():
                queries.append(kw.strip())
        for cat in (pref.job_categories_json or []):
            if cat and cat.strip():
                queries.append(cat.strip())

        # 2. Candidate career interests & headline
        for interest in (profile.career_interests_json or [])[:2]:
            if interest and len(interest.split()) <= 5:
                queries.append(interest.strip())
        if profile.headline and len(profile.headline.split()) <= 6:
            queries.append(profile.headline.strip())

        # 3. Top programming languages & technical skills combinations
        prog = profile.programming_languages_json or []
        tech = profile.technical_skills_json or []
        if prog and tech:
            queries.append(f"{prog[0]} {tech[0]}")
        for sk in (prog[:2] + tech[:3]):
            queries.append(sk)

        # 4. Entry-level / internship modifiers when requested
        if pref.internship and queries:
            queries.insert(0, f"{queries[0]} intern")
        elif (pref.fresh_graduate or pref.entry_level) and queries:
            queries.append(f"junior {queries[0]}")

        # Deduplicate preserving order
        deduped: List[str] = []
        seen = set()
        for q in queries:
            norm = q.lower().strip()
            if norm and norm not in seen:
                seen.add(norm)
                deduped.append(q.strip())

        return deduped[:6] or ["Software Engineer"]

    async def discover(
        self,
        profile: CandidateProfile,
        pref: SearchPreference,
        custom_ats_boards: List[Dict[str, str]] | None = None,
    ) -> Tuple[List[RawDiscoveredJob], List[str], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Run parallel discovery across all selected connectors.

        Returns:
            (raw_jobs, generated_queries, searched_sources_summary, unavailable_sources_summary)
        """
        queries = self.build_search_queries(profile, pref)
        countries = pref.target_countries_json or ["Worldwide"]
        connectors = select_connectors_for_countries(
            target_countries=countries,
            enabled_slugs=pref.enabled_source_slugs_json or None,
        )

        extra_prefs = {
            "custom_ats_boards": custom_ats_boards or [],
            "visa_sponsorship_only": pref.visa_sponsorship_only,
            "work_modes": pref.work_modes_json or [],
        }

        sem = asyncio.Semaphore(6)

        async def _run_one(conn) -> SourceSearchResult:
            async with sem:
                return await conn.search(
                    queries=queries,
                    countries=countries,
                    max_results=pref.max_results_per_source or 25,
                    preferences=extra_prefs,
                )

        results: List[SourceSearchResult] = await asyncio.gather(
            *[_run_one(c) for c in connectors]
        )

        all_jobs: List[RawDiscoveredJob] = []
        searched_sources: List[Dict[str, Any]] = []
        unavailable_sources: List[Dict[str, Any]] = []

        for res in results:
            if res.status == "ok":
                all_jobs.extend(res.jobs)
                searched_sources.append(
                    {
                        "slug": res.source_slug,
                        "name": res.source_name,
                        "jobs_found": len(res.jobs),
                        "pages_fetched": res.pages_fetched,
                        "queries_executed": res.queries_executed,
                        "duration_ms": res.duration_ms,
                    }
                )
            else:
                unavailable_sources.append(
                    {
                        "slug": res.source_slug,
                        "name": res.source_name,
                        "status": res.status,
                        "reason": res.error_message or "Source unavailable during search.",
                    }
                )

        # Always attach transparent portal API restriction disclosures
        for disc in NON_API_PORTAL_DISCLOSURES:
            unavailable_sources.append(
                {
                    "slug": "restricted_portals_notice",
                    "name": disc["portal"],
                    "status": "policy_disclosure",
                    "reason": disc["policy"],
                }
            )

        return all_jobs, queries, searched_sources, unavailable_sources


job_discovery_agent = JobDiscoveryAgent()
