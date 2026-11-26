"""Agent 7: Reporting Agent.

Compiles transparent search coverage summaries, source limitations, match statistics,
and user notifications once the autonomous pipeline completes.
"""
from __future__ import annotations

from typing import Any, Dict, List


class ReportingAgent:
    agent_name = "ReportingAgent"

    def build_coverage_report(
        self,
        target_countries: List[str],
        min_match_score: float,
        generated_queries: List[str],
        searched_sources: List[Dict[str, Any]],
        unavailable_sources: List[Dict[str, Any]],
        discovered_count: int,
        verification_metrics: Dict[str, int],
        ranking_metrics: Dict[str, int],
    ) -> Dict[str, Any]:
        top_sources = sorted(
            searched_sources, key=lambda s: s.get("jobs_found", 0), reverse=True
        )
        return {
            "target_countries": target_countries,
            "min_match_threshold_percent": min_match_score,
            "queries_executed": generated_queries,
            "sources_searched_count": len(searched_sources),
            "sources_searched": top_sources,
            "sources_unavailable": unavailable_sources,
            "pipeline_funnel": {
                "raw_discovered": discovered_count,
                "duplicates_removed": verification_metrics.get("duplicates_removed", 0),
                "expired_or_broken_removed": verification_metrics.get("expired_or_broken_removed", 0),
                "verified_active": verification_metrics.get("verified_active", 0),
                "unverified_reachable": verification_metrics.get("unverified", 0),
                "filtered_by_location_or_prefs": ranking_metrics.get("preference_filtered", 0),
                "excluded_below_threshold": ranking_metrics.get("below_threshold_excluded", 0),
                "final_qualifying_jobs": ranking_metrics.get("qualifying_matches", 0),
            },
            "transparency_statement": (
                f"Searched {len(searched_sources)} permitted job source(s) across {len(generated_queries)} "
                f"multi-angle queries. No job search engine indexes every opening worldwide; portals "
                "without open APIs or unconfigured API keys are listed transparently under unavailable sources."
            ),
        }


reporting_agent = ReportingAgent()
