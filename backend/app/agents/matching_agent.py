"""Agent 4: Intelligent CV-to-Job Matching Engine.

Evaluates every job against the candidate's CV across 6 configurable weighted criteria:
  - Technical Skills (default 30%)
  - Education (default 15%)
  - Work Experience (default 20%)
  - Required Qualifications (default 15%)
  - Projects & Achievements (default 10%)
  - Job Role Relevance (default 10%)

Key guarantees:
  - Never inflates matching scores.
  - Distinguishes mandatory vs preferred requirements.
  - Never treats unstated CV fields as proof a candidate lacks a skill.
  - Isolates explicit disqualifiers separately.
  - Produces a transparent mathematical calculation breakdown.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Set

from app.models.entities import CandidateProfile, DEFAULT_MATCHING_WEIGHTS, JobListing, JobRequirement
from app.services.skill_taxonomy import (
    DEGREE_LEVELS,
    cosine_similarity,
    detect_highest_degree,
    normalize_skill,
)


MIN_SKILL_EVIDENCE = 3
# Ceiling when the job title belongs to none of the candidate's professional families.
OFF_FIELD_CEILING = 60.0

# Broad professional families used to recognise related job titles.
ROLE_FAMILIES: Dict[str, tuple] = {
    "software": ("software", "developer", "engineer", "programmer", "backend", "back-end", "frontend",
                 "front-end", "full-stack", "fullstack", "full stack", "devops", "sre", "platform", "web",
                 "entwickler", "développeur", "desarrollador", "ingenieur", "ingénieur"),
    "data": ("data", "machine learning", " ml ", "analytics", "analyst", "scientist", "ai "),
    "security": ("security", "secops", "devsecops", "cyber"),
    "design": ("designer", "ux", "ui "),
    "product": ("product manager", "product owner"),
}


def _degree_rank_from_label(label: str | None) -> int:
    if not label:
        return 0
    _, rank = detect_highest_degree(label)
    if rank > 0:
        return rank
    low = label.lower()
    for k, v in DEGREE_LEVELS.items():
        if k in low:
            return v
    return 0


class MatchingAgent:
    agent_name = "MatchingAgent"

    def evaluate(
        self,
        profile: CandidateProfile,
        job: JobListing,
        requirements: List[JobRequirement],
        weights: Dict[str, float] | None = None,
        visa_required_by_user: bool = False,
    ) -> Dict[str, Any]:
        active_weights = dict(DEFAULT_MATCHING_WEIGHTS)
        if weights:
            total_w = sum(max(0.0, float(v)) for v in weights.values())
            if total_w > 0:
                for k in active_weights:
                    active_weights[k] = round((max(0.0, float(weights.get(k, 0.0))) / total_w) * 100.0, 2)

        # Candidate skill inventory (canonical lowercase -> display)
        cand_skills_map: Dict[str, str] = {}
        for sk in (profile.programming_languages_json or []) + (profile.technical_skills_json or []):
            canon, _ = normalize_skill(sk)
            cand_skills_map[canon.lower()] = canon

        mandatory_skill_reqs = [
            r for r in requirements if r.requirement_type == "technical_skill" and r.is_mandatory
        ]
        preferred_skill_reqs = [
            r for r in requirements if r.requirement_type == "technical_skill" and not r.is_mandatory
        ]
        disqualifier_reqs = [
            r for r in requirements if r.requirement_type == "disqualifier"
        ]

        matched_skills: List[str] = []
        missing_mandatory: List[str] = []
        missing_preferred: List[str] = []
        unstated_on_cv: List[str] = []

        for req in mandatory_skill_reqs:
            if req.normalized_key in cand_skills_map:
                matched_skills.append(cand_skills_map[req.normalized_key])
            else:
                canon, _ = normalize_skill(req.normalized_key)
                missing_mandatory.append(canon)

        for req in preferred_skill_reqs:
            if req.normalized_key in cand_skills_map:
                matched_skills.append(cand_skills_map[req.normalized_key])
            else:
                canon, _ = normalize_skill(req.normalized_key)
                missing_preferred.append(canon)

        # Semantic similarity between CV and Job vectors (0.0 .. 1.0)
        sem_sim = cosine_similarity(profile.embedding_vector, job.embedding_vector)

        # 1. Technical Skills Score (0..100)
        if mandatory_skill_reqs or preferred_skill_reqs:
            if mandatory_skill_reqs and preferred_skill_reqs:
                mand_ratio = (len(mandatory_skill_reqs) - len(missing_mandatory)) / len(mandatory_skill_reqs)
                pref_ratio = (len(preferred_skill_reqs) - len(missing_preferred)) / len(preferred_skill_reqs)
                tech_score = (mand_ratio * 80.0) + (pref_ratio * 20.0)
            elif mandatory_skill_reqs:
                mand_ratio = (len(mandatory_skill_reqs) - len(missing_mandatory)) / len(mandatory_skill_reqs)
                tech_score = mand_ratio * 100.0
            else:
                pref_ratio = (len(preferred_skill_reqs) - len(missing_preferred)) / len(preferred_skill_reqs)
                tech_score = 45.0 + (pref_ratio * 55.0)
        else:
            # Job description did not name canonical skills explicitly; rely conservatively on semantic overlap
            tech_score = min(82.0, round(25.0 + sem_sim * 65.0, 1))

        # Thin-evidence shrinkage: a posting that names only 1-2 recognizable skills says little about
        # fit ("SQL" alone should not make a 100% technical match). Blend the ratio toward the
        # semantic prior until at least MIN_SKILL_EVIDENCE skills are named.
        named_skill_count = len(mandatory_skill_reqs) + len(preferred_skill_reqs)
        if 0 < named_skill_count < MIN_SKILL_EVIDENCE:
            prior = min(82.0, 25.0 + sem_sim * 65.0)
            pseudo = MIN_SKILL_EVIDENCE - named_skill_count
            tech_score = round((tech_score * named_skill_count + prior * pseudo) / MIN_SKILL_EVIDENCE, 1)

        # 2. Education Score (0..100)
        cand_deg_rank = _degree_rank_from_label(profile.highest_degree)
        req_deg_rank = _degree_rank_from_label(job.required_education)
        if req_deg_rank == 0:
            if cand_deg_rank >= 3:
                edu_score = 92.0
                edu_compat = f"Candidate holds {profile.highest_degree}; job lists no strict degree barrier."
            elif cand_deg_rank > 0:
                edu_score = 80.0
                edu_compat = f"Candidate holds {profile.highest_degree}; compatible with flexible degree criteria."
            else:
                edu_score = 65.0
                edu_compat = "Degree not stated on CV; job does not mandate a specific academic degree."
                unstated_on_cv.append("Academic degree level (not stated on CV)")
        else:
            if cand_deg_rank == 0:
                edu_score = 50.0
                edu_compat = (
                    f"Job requests {job.required_education}, while academic degree is not explicitly stated on the CV."
                )
                unstated_on_cv.append(f"Academic degree ({job.required_education} requested)")
            elif cand_deg_rank >= req_deg_rank:
                edu_score = 100.0
                edu_compat = f"Meets or exceeds requirement ({profile.highest_degree} vs {job.required_education})."
            elif cand_deg_rank == req_deg_rank - 1:
                edu_score = 62.0
                edu_compat = f"One degree tier below {job.required_education} ({profile.highest_degree})."
            else:
                edu_score = 30.0
                edu_compat = f"Below requested {job.required_education}."

        # 3. Work Experience Score (0..100)
        # Count internships as 0.45 yr practical experience credit each when full-time years are 0/low
        internship_count = len(profile.internships_json or [])
        project_count = len(profile.projects_json or [])
        base_years = profile.years_of_experience
        effective_years = (base_years or 0.0) + min(1.5, internship_count * 0.45)

        req_years = job.min_experience_years
        if req_years is None:
            lvl = (job.experience_level or "").lower()
            if "intern" in lvl:
                req_years = 0.0
            elif "entry" in lvl:
                req_years = 0.5
            elif "senior" in lvl:
                req_years = 5.0
            elif "lead" in lvl or "principal" in lvl:
                req_years = 7.0
            else:
                req_years = 2.0

        if base_years is None and not (profile.experience_json or profile.internships_json):
            unstated_on_cv.append("Total years of work experience (not explicitly stated on CV)")
            if req_years <= 1.0:
                exp_score = 42.0 if project_count > 0 else 35.0
                exp_compat = (
                    f"Job asks for ~{req_years:g} yr experience; CV emphasizes academic/project background "
                    "without formal full-time tenure listed."
                )
            else:
                exp_score = max(20.0, round(45.0 - (req_years * 4.5), 1))
                exp_compat = (
                    f"Job targets ~{req_years:g}+ years experience; formal work duration is not listed on the CV."
                )
        elif req_years <= 0.0:
            exp_score = 96.0
            exp_compat = "Compatible with internship / zero-experience requirement."
        elif effective_years >= req_years:
            exp_score = 100.0
            exp_compat = f"Candidate experience ({effective_years:.1f} effective yrs) meets {req_years:g}+ yr requirement."
        else:
            ratio = effective_years / max(0.5, req_years)
            # Partial credit when strong academic projects exist for 1-year roles
            project_bridge = 12.0 if (req_years <= 1.5 and project_count >= 1) else 0.0
            exp_score = min(88.0, round((ratio * 78.0) + project_bridge + 28.0 * (1.0 if req_years <= 1.0 else 0.0), 1))
            if effective_years == 0 and req_years == 1.0 and project_count >= 1:
                exp_score = 40.0
            exp_compat = (
                f"Candidate shows {effective_years:.1f} effective yrs vs {req_years:g}+ yrs requested "
                f"({int(round(ratio * 100))}% tenure coverage)."
            )

        # 4. Required Qualifications Score (0..100) — composite of mandatory skills, degree, & certifications
        qual_parts: List[float] = [tech_score, edu_score]
        matching_quals: List[str] = []
        if matched_skills:
            matching_quals.append(f"Core technical stack alignment ({', '.join(matched_skills[:5])})")
        if cand_deg_rank >= max(1, req_deg_rank) and profile.highest_degree:
            matching_quals.append(profile.highest_degree)
        if profile.certifications_json:
            qual_parts.append(88.0)
            matching_quals.append(f"{len(profile.certifications_json)} certification(s) on profile")
        qual_score = round(sum(qual_parts) / len(qual_parts), 1)

        # 5. Projects & Achievements Score (0..100)
        ach_count = len(profile.achievements_json or [])
        if project_count == 0 and ach_count == 0:
            unstated_on_cv.append("Dedicated projects or achievements section")
            projects_score = round(45.0 + sem_sim * 25.0, 1)
        else:
            proj_text = " ".join(
                f"{p.get('title', '')} {' '.join(p.get('highlights', []))}"
                for p in (profile.projects_json or [])
            ).lower()
            skill_hits_in_projects = sum(1 for sk in matched_skills if sk.lower() in proj_text)
            projects_score = min(
                98.0,
                round(65.0 + min(20.0, project_count * 7.0) + min(13.0, skill_hits_in_projects * 4.5 + ach_count * 3.0), 1),
            )

        # 6. Job Role Relevance Score (0..100)
        role_titles_blob = " ".join(
            filter(
                None,
                [
                    profile.headline or "",
                    " ".join(profile.career_interests_json or []),
                    " ".join(e.get("title", "") for e in (profile.experience_json or [])),
                ],
            )
        ).lower()
        # Same professional family (e.g. "Backend Engineer" vs "Full-Stack Developer") counts as
        # partial title overlap even when no exact title word is shared.
        job_title_lower = job.title.lower()
        cand_families = {f for f, kws in ROLE_FAMILIES.items() if any(k in role_titles_blob for k in kws)}
        job_families = {f for f, kws in ROLE_FAMILIES.items() if any(k in job_title_lower for k in kws)}
        same_family = bool(cand_families & job_families)
        job_title_tokens = {
            tok for tok in re.findall(r"[a-z0-9+#]{3,}", job.title.lower())
            if tok not in {"senior", "junior", "lead", "staff", "the", "and", "for", "remote"}
        }
        title_overlap = (
            sum(1 for t in job_title_tokens if t in role_titles_blob) / len(job_title_tokens)
            if job_title_tokens
            else 0.0
        )
        if same_family:
            title_overlap = max(title_overlap, 0.6)
        role_score = min(
            98.0,
            round((sem_sim * 55.0) + (title_overlap * 30.0) + (min(1.0, len(matched_skills) / 3.0) * 25.0), 1),
        )

        # Explicit disqualifiers isolated cleanly
        explicit_disqualifiers: List[str] = [d.requirement_text for d in disqualifier_reqs]
        if visa_required_by_user and job.visa_sponsorship is False:
            if "No Visa Sponsorship Offered" not in explicit_disqualifiers:
                explicit_disqualifiers.append("Job explicitly states visa sponsorship is unavailable.")
        if req_years is not None and req_years >= (effective_years + 4.0):
            explicit_disqualifiers.append(
                f"Mandatory tenure gap of {req_years - effective_years:.1f} years ({req_years:g}+ yrs required)."
            )

        # Final weighted calculation (never inflated)
        dimension_scores = {
            "technical_skills": round(tech_score, 1),
            "education": round(edu_score, 1),
            "work_experience": round(exp_score, 1),
            "required_qualifications": round(qual_score, 1),
            "projects_achievements": round(projects_score, 1),
            "role_relevance": round(role_score, 1),
        }

        weighted_contributions = {
            dim: round((dimension_scores[dim] * active_weights[dim]) / 100.0, 2)
            for dim in dimension_scores
        }
        raw_total = sum(weighted_contributions.values())
        # Relevance ceiling: education and experience describe eligibility, not fit, and score high
        # for almost any posting without explicit requirements. Without technical or role evidence a
        # job must not rank as a strong match, so the total is capped by that evidence.
        relevance_ceiling = 30.0 + 0.45 * tech_score + 0.40 * role_score
        off_field = bool(cand_families) and not same_family
        if off_field:
            relevance_ceiling = min(relevance_ceiling, OFF_FIELD_CEILING)
        relevance_capped = raw_total > relevance_ceiling
        overall_score = round(min(100.0, max(0.0, min(raw_total, relevance_ceiling))), 1)

        strengths: List[str] = []
        weaknesses: List[str] = []

        if matched_skills:
            strengths.append(f"Matched {len(matched_skills)} job-relevant skill(s): {', '.join(matched_skills[:6])}.")
        if edu_score >= 90:
            strengths.append(edu_compat)
        if exp_score >= 85:
            strengths.append(exp_compat)
        if projects_score >= 78 and project_count > 0:
            strengths.append(f"Demonstrated {project_count} relevant project(s) reinforcing practical readiness.")

        if missing_mandatory:
            weaknesses.append(f"Mandatory skills not found on CV: {', '.join(missing_mandatory[:6])}.")
        if missing_preferred:
            weaknesses.append(f"Preferred / bonus skills not listed: {', '.join(missing_preferred[:5])}.")
        if exp_score < 70:
            weaknesses.append(exp_compat)
        if explicit_disqualifiers:
            weaknesses.extend(explicit_disqualifiers)
        if relevance_capped and off_field:
            weaknesses.append(
                f"Job title appears to be outside your field; score capped at {round(relevance_ceiling, 1)}%."
            )
        elif relevance_capped:
            weaknesses.append(
                "Limited evidence this role matches your field (few shared skills / dissimilar title); "
                f"score capped at {round(relevance_ceiling, 1)}%."
            )

        formula_parts = [
            f"{dim.replace('_', ' ').title()} ({dimension_scores[dim]}% × {active_weights[dim]}% = {weighted_contributions[dim]} pts)"
            for dim in dimension_scores
        ]
        explanation = (
            f"Overall CV-to-job alignment is {overall_score}% calculated across 6 weighted dimensions: "
            + "; ".join(formula_parts)
            + (
                f". Weighted sum {round(raw_total, 1)}% was capped at {round(relevance_ceiling, 1)}% "
                "(relevance ceiling = 30 + 0.45 × technical + 0.40 × role relevance)"
                if relevance_capped
                else ""
            )
            + ". Note: Matching scores measure profile-to-requirement alignment and do not guarantee interview selection."
        )

        return {
            "overall_score": overall_score,
            "technical_skills_score": dimension_scores["technical_skills"],
            "education_score": dimension_scores["education"],
            "experience_score": dimension_scores["work_experience"],
            "qualifications_score": dimension_scores["required_qualifications"],
            "projects_score": dimension_scores["projects_achievements"],
            "role_relevance_score": dimension_scores["role_relevance"],
            "weights_used": active_weights,
            "matched_skills": sorted(set(matched_skills)),
            "missing_mandatory_skills": missing_mandatory,
            "missing_preferred_skills": missing_preferred,
            "unstated_on_cv": unstated_on_cv,
            "matching_qualifications": matching_quals,
            "experience_compatibility": exp_compat,
            "education_compatibility": edu_compat,
            "explicit_disqualifiers": explicit_disqualifiers,
            "score_explanation": explanation,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "calculation_breakdown": {
                "dimension_scores": dimension_scores,
                "weights": active_weights,
                "weighted_points": weighted_contributions,
                "semantic_similarity": round(sem_sim, 3),
                "weighted_sum": round(raw_total, 2),
                "relevance_ceiling": round(relevance_ceiling, 2),
                "relevance_capped": relevance_capped,
                "off_field_title": off_field,
                "total_score": overall_score,
            },
        }


matching_agent = MatchingAgent()
