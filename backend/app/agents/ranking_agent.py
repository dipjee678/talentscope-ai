"""Agent 6: Ranking & Preference Filtering Agent.

Filters out jobs that do not satisfy location/preference constraints or fall below the user's
minimum CV matching threshold, and orders qualifying opportunities without altering raw match scores.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.models.entities import JobListing, SearchPreference
from app.services.skill_taxonomy import location_matches_countries


class RankingAgent:
    agent_name = "RankingAgent"

    def filter_and_rank(
        self,
        evaluated_items: List[Tuple[JobListing, Dict[str, Any]]],
        pref: SearchPreference,
    ) -> Tuple[List[Tuple[JobListing, Dict[str, Any]]], Dict[str, int]]:
        below_threshold = 0
        filtered_by_prefs = 0
        qualifying: List[Tuple[JobListing, Dict[str, Any]]] = []

        target_countries = pref.target_countries_json or []
        allowed_modes = {m.lower() for m in (pref.work_modes_json or []) if m}
        allowed_levels = {lv.lower() for lv in (pref.experience_levels_json or []) if lv}

        for job, match_data in evaluated_items:
            # 1. Country / geographic eligibility check
            if not location_matches_countries(job.country, job.location_raw, job.work_mode, target_countries):
                filtered_by_prefs += 1
                continue

            # 2. Optional strict work mode filter
            if allowed_modes and job.work_mode.lower() not in allowed_modes and job.work_mode != "unknown":
                filtered_by_prefs += 1
                continue

            # 3. Optional strict visa sponsorship filter
            if pref.visa_sponsorship_only and job.visa_sponsorship is False:
                filtered_by_prefs += 1
                continue

            # 4. Enforce minimum matching threshold strictly
            score = float(match_data["overall_score"])
            if score < float(pref.min_match_score):
                below_threshold += 1
                continue

            # Compute tie-breaking rank_score (does NOT mutate overall_score!)
            rank_bonus = 0.0
            if job.verification_status == "verified_active":
                rank_bonus += 1.5
            if job.is_direct_company_link:
                rank_bonus += 1.2
            if job.visa_sponsorship is True and pref.visa_sponsorship_only:
                rank_bonus += 2.0
            if allowed_levels and (job.experience_level or "").lower() in allowed_levels:
                rank_bonus += 1.0
            if (pref.internship and job.experience_level == "Internship") or (
                (pref.fresh_graduate or pref.entry_level) and job.experience_level == "Entry-Level"
            ):
                rank_bonus += 1.5
            if match_data.get("explicit_disqualifiers"):
                rank_bonus -= 4.0

            match_data["rank_score"] = round(score + rank_bonus, 2)
            qualifying.append((job, match_data))

        qualifying.sort(
            key=lambda pair: (pair[1]["rank_score"], pair[1]["overall_score"]),
            reverse=True,
        )

        return qualifying, {
            "below_threshold_excluded": below_threshold,
            "preference_filtered": filtered_by_prefs,
            "qualifying_matches": len(qualifying),
        }


ranking_agent = RankingAgent()
