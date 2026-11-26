"""Grounded AI Career Assistant service.

Generates strictly truthful, candidate-grounded guidance:
  - explain_match: Why a job matches the CV
  - missing_skills: Mandatory & preferred skill gap breakdown
  - cv_improvements: Concrete, non-fabricated CV strengthening tips
  - cover_letter: Tailored truthful cover letter citing only real CV evidence
  - interview_prep: Role-specific technical & behavioral interview preparation
  - learning_roadmap: Prioritized upskilling roadmap
  - compare_jobs: Side-by-side career comparison of multiple jobs
  - plain_english: Plain-language breakdown of job requirements
  - free_chat: Grounded career Q&A
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.agents.matching_agent import matching_agent
from app.core.security import wrap_untrusted_data
from app.models.entities import CandidateProfile, JobListing, JobMatch, JobRequirement
from app.schemas.assistant import AssistantRequest, AssistantResponse
from app.services.llm_client import llm_client


class CareerAssistantService:
    def _build_profile_digest(self, profile: CandidateProfile) -> Dict[str, Any]:
        return {
            "full_name": profile.full_name or "Candidate",
            "headline": profile.headline or "Professional Candidate",
            "highest_degree": profile.highest_degree,
            "universities": profile.universities_json or [],
            "years_of_experience": profile.years_of_experience,
            "programming_languages": profile.programming_languages_json or [],
            "technical_skills": profile.technical_skills_json or [],
            "soft_skills": profile.soft_skills_json or [],
            "projects": [p.get("title", "") for p in (profile.projects_json or [])[:5]],
            "experience": [e.get("title", "") for e in (profile.experience_json or [])[:5]],
            "internships": [i.get("title", "") for i in (profile.internships_json or [])[:4]],
            "certifications": profile.certifications_json or [],
            "achievements": (profile.achievements_json or [])[:5],
        }

    def _compute_or_extract_match(
        self,
        profile: CandidateProfile,
        job: JobListing,
        requirements: List[JobRequirement],
        existing_match: Optional[JobMatch],
    ) -> Dict[str, Any]:
        if existing_match:
            return {
                "overall_score": existing_match.overall_score,
                "matched_skills": existing_match.matched_skills_json or [],
                "missing_mandatory_skills": existing_match.missing_mandatory_skills_json or [],
                "missing_preferred_skills": existing_match.missing_preferred_skills_json or [],
                "unstated_on_cv": existing_match.unstated_on_cv_json or [],
                "experience_compatibility": existing_match.experience_compatibility,
                "education_compatibility": existing_match.education_compatibility,
                "explicit_disqualifiers": existing_match.explicit_disqualifiers_json or [],
                "strengths": existing_match.strengths_json or [],
                "weaknesses": existing_match.weaknesses_json or [],
                "score_explanation": existing_match.score_explanation,
            }
        return matching_agent.evaluate(profile=profile, job=job, requirements=requirements)

    async def generate(
        self,
        req: AssistantRequest,
        profile: CandidateProfile,
        job: Optional[JobListing] = None,
        requirements: Optional[List[JobRequirement]] = None,
        existing_match: Optional[JobMatch] = None,
        compare_jobs_list: Optional[List[tuple[JobListing, List[JobRequirement], Optional[JobMatch]]]] = None,
    ) -> AssistantResponse:
        digest = self._build_profile_digest(profile)
        all_cand_skills = digest["programming_languages"] + digest["technical_skills"]

        # Deterministic baseline content (guaranteed truthful & always available)
        title = "AI Career Assistant Analysis"
        md = ""
        highlights: List[str] = []

        if req.action == "compare_jobs" and compare_jobs_list:
            title = f"Comparative Analysis of {len(compare_jobs_list)} Opportunities"
            rows = []
            best_tuple = None
            best_score = -1.0
            for j_item, j_reqs, j_match in compare_jobs_list:
                m = self._compute_or_extract_match(profile, j_item, j_reqs, j_match)
                sc = float(m["overall_score"])
                if sc > best_score:
                    best_score = sc
                    best_tuple = (j_item, m)
                rows.append(
                    f"| **{j_item.title}** ({j_item.company_name}) | **{sc}%** | {j_item.work_mode.title()} ({j_item.country}) | "
                    f"{j_item.salary_raw or 'Not disclosed'} | {', '.join(m['matched_skills'][:4]) or 'General'} | "
                    f"{', '.join(m['missing_mandatory_skills'][:3]) or 'None'} |"
                )
            winner_line = ""
            if best_tuple:
                wj, wm = best_tuple
                winner_line = (
                    f"\n\n### Top Fit Recommendation\n"
                    f"**{wj.title} at {wj.company_name}** currently shows the strongest alignment (**{wm['overall_score']}%**), "
                    f"matching `{', '.join(wm['matched_skills'][:5]) or 'your profile background'}` with "
                    f"{len(wm['missing_mandatory_skills'])} missing mandatory skill(s)."
                )
                highlights = [
                    f"Highest CV alignment: {wj.title} at {wj.company_name} ({wm['overall_score']}%)",
                    f"Compared {len(compare_jobs_list)} roles across skills, work mode, salary, and gaps.",
                ]
            md = (
                "### Side-by-Side Opportunity Matrix\n\n"
                "| Role & Company | Match | Mode & Country | Compensation | Key Matched Skills | Mandatory Gaps |\n"
                "|---|---:|---|---|---|---|\n"
                + "\n".join(rows)
                + winner_line
            )

        elif job is not None:
            m = self._compute_or_extract_match(profile, job, requirements or [], existing_match)
            matched_str = ", ".join(m["matched_skills"]) if m["matched_skills"] else "foundational profile alignment"
            miss_mand = m["missing_mandatory_skills"]
            miss_pref = m["missing_preferred_skills"]

            if req.action == "explain_match":
                title = f"Why Your CV Matches: {job.title} at {job.company_name}"
                highlights = list(m["strengths"][:4])
                md = (
                    f"### Overall Alignment: **{m['overall_score']}%**\n\n"
                    f"{m['score_explanation']}\n\n"
                    f"#### Key Alignment Drivers\n"
                    + ("\n".join(f"- {s}" for s in m["strengths"]) or "- Relevant foundational background.")
                    + "\n\n#### Potential Application Risks\n"
                    + ("\n".join(f"- {w}" for w in m["weaknesses"]) or "- No major structural gaps detected.")
                    + (
                        "\n\n#### Unstated on CV (Not Penalized as Absent)\n"
                        + "\n".join(f"- {u}" for u in m["unstated_on_cv"])
                        if m["unstated_on_cv"]
                        else ""
                    )
                )

            elif req.action == "missing_skills":
                title = f"Skill Gap Analysis: {job.title} ({job.company_name})"
                highlights = [
                    f"{len(m['matched_skills'])} matched skills",
                    f"{len(miss_mand)} missing mandatory skills",
                    f"{len(miss_pref)} missing preferred skills",
                ]
                md = (
                    f"### Verified Skills Already on Your CV\n"
                    f"{', '.join(f'`{s}`' for s in m['matched_skills']) or 'None explicitly matched from job text.'}\n\n"
                    f"### Mandatory Requirements Not Found on Your CV\n"
                    + ("\n".join(f"- **{s}** — Core requirement in the job posting; if you have used `{s}` in coursework or projects, add it explicitly to your CV." for s in miss_mand) or "- None! Your CV covers all detected mandatory technical skills.")
                    + "\n\n### Preferred / Bonus Skills to Strengthen Competitiveness\n"
                    + ("\n".join(f"- **{s}** — Listed as a bonus/preferred qualification." for s in miss_pref) or "- No additional preferred skill gaps identified.")
                )

            elif req.action == "cv_improvements":
                title = f"Truthful CV Tailoring Suggestions for {job.title}"
                highlights = [
                    "Strictly truthful edits—highlight existing evidence without exaggerating.",
                    f"Emphasize matched skills ({matched_str}) in your top summary & project bullets.",
                ]
                md = (
                    f"### Tailoring Your CV for **{job.company_name}** ({job.title})\n\n"
                    f"1. **Lead with Verified Overlapping Stack:** Move `{matched_str}` into the top third of your Skills and Summary sections so recruiters see immediate alignment.\n"
                    f"2. **Quantify Existing Projects & Experience:** For your listed items ({', '.join(digest['projects'][:3] + digest['experience'][:2]) or 'your core projects'}), add measurable outcomes (latency, dataset size, test coverage, users served) where accurate.\n"
                    + (
                        f"3. **Clarify Unstated Experience if Applicable:** Your CV does not currently mention `{', '.join(miss_mand[:4])}`. **Only if you genuinely have hands-on experience with these**, document where you used them; never claim skills you cannot defend in an interview.\n"
                        if miss_mand
                        else "3. **Strong Technical Coverage:** Your CV already lists the core technical skills requested.\n"
                    )
                    + (
                        f"4. **Resolve Missing Profile Metadata:** {', '.join(profile.missing_or_unclear_json[:3])}\n"
                        if profile.missing_or_unclear_json
                        else ""
                    )
                )

            elif req.action == "cover_letter":
                title = f"Tailored Cover Letter — {job.title} at {job.company_name}"
                cand_name = digest["full_name"]
                edu_phrase = (
                    f"With a {digest['highest_degree']}"
                    + (f" from {digest['universities'][0]}" if digest["universities"] else "")
                    if digest["highest_degree"]
                    else "Through my technical background"
                )
                proj_evidence = (
                    f"In my work on {', '.join(digest['projects'][:2])}, I applied {', '.join((m['matched_skills'] or all_cand_skills)[:4])} to build reliable solutions."
                    if digest["projects"]
                    else (
                        f"Across my experience ({', '.join(digest['experience'][:2])}), I have worked hands-on with {', '.join((m['matched_skills'] or all_cand_skills)[:4])}."
                        if digest["experience"]
                        else f"I bring practical proficiency in {', '.join((m['matched_skills'] or all_cand_skills)[:5] or ['modern software engineering'])}."
                    )
                )
                highlights = [
                    "100% grounded in your verified CV skills, education, and projects.",
                    "Zero fabricated employers, metrics, or unverified claims.",
                ]
                md = (
                    f"Dear Hiring Team at **{job.company_name}**,\n\n"
                    f"I am writing to express my strong interest in the **{job.title}** position ({job.location_raw}). "
                    f"{edu_phrase}, my background aligns closely with your team's focus on {matched_str}.\n\n"
                    f"{proj_evidence} "
                    + (
                        f"Additionally, my internship experience ({digest['internships'][0]}) strengthened my collaborative engineering workflow and delivery discipline.\n\n"
                        if digest["internships"]
                        else "\n\n"
                    )
                    + f"What draws me to **{job.company_name}** is the opportunity to contribute directly to impactful engineering challenges while continuing to deepen my expertise"
                    + (f" in areas such as {', '.join(miss_pref[:2])}." if miss_pref else ".")
                    + "\n\nThank you for considering my application. I would welcome the opportunity to discuss how my background can support your team's goals.\n\n"
                    f"Sincerely,\n**{cand_name}**"
                )

            elif req.action == "interview_prep":
                title = f"Interview Preparation Guide: {job.title} at {job.company_name}"
                focus_skills = (m["matched_skills"] + miss_mand)[:6] or all_cand_skills[:5]
                highlights = [f"Prepare deep-dive stories on: {', '.join(focus_skills[:4])}"]
                md = (
                    f"### 1. Core Technical Topics to Review\n"
                    + "\n".join(
                        f"- **{sk}**: Review core architecture, trade-offs, debugging scenarios, and production best practices."
                        for sk in focus_skills
                    )
                    + "\n\n### 2. Gap-Mitigation Talking Points\n"
                    + (
                        "\n".join(
                            f"- **{gap}**: Prepare an honest, structured answer showing adjacent concepts you know ({', '.join(m['matched_skills'][:2]) or 'core fundamentals'}) and how quickly you ramp up."
                            for gap in miss_mand[:4]
                        )
                        if miss_mand
                        else "- Your core technical stack matches well; focus on depth, edge cases, and scalability."
                    )
                    + "\n\n### 3. Project & Behavioral Deep-Dives (STAR Format)\n"
                    + "\n".join(
                        f"- Walk through architecture decisions, bottlenecks solved, and lessons learned in **{p}**."
                        for p in (digest["projects"][:3] or digest["experience"][:3] or ["your primary technical project"])
                    )
                )

            elif req.action == "learning_roadmap":
                title = f"Targeted Skill Roadmap for {job.title}"
                targets = miss_mand + miss_pref
                highlights = [f"{len(targets)} prioritized skill(s) to close gaps"]
                if targets:
                    md = (
                        "### Priority 1 — Mandatory Job Gaps\n"
                        + ("\n".join(f"1. **{s}**: Build a small end-to-end portfolio module integrating `{s}` with your existing `{all_cand_skills[0] if all_cand_skills else 'core'}` stack." for s in miss_mand) or "- None required.")
                        + "\n\n### Priority 2 — Preferred Differentiators\n"
                        + ("\n".join(f"- **{s}**: Add automated tests and documentation demonstrating practical usage." for s in miss_pref) or "- None listed.")
                    )
                else:
                    md = (
                        "Your CV already covers the detected technical stack for this role! To stand out further:\n"
                        "- Deepen system design, observability, and automated testing around your existing stack.\n"
                        "- Publish clean architecture READMEs on your top projects."
                    )

            elif req.action == "plain_english":
                title = f"Plain-Language Breakdown: {job.title} at {job.company_name}"
                highlights = [
                    f"Work Arrangement: {job.work_mode.title()} ({job.location_raw})",
                    f"Experience Tier: {job.experience_level or 'Unspecified'}",
                ]
                md = (
                    f"### What This Role Actually Involves\n"
                    f"**{job.company_name}** is hiring a **{job.title}** ({job.employment_type}, **{job.work_mode.title()}** in **{job.location_raw}**).\n\n"
                    f"### Must-Have Requirements in Simple Terms\n"
                    f"- **Core Tools:** {', '.join(r.normalized_key.title() for r in (requirements or []) if r.requirement_type == 'technical_skill' and r.is_mandatory) or 'General domain skills described in listing'}\n"
                    f"- **Experience Expected:** {f'{job.min_experience_years:g}+ years' if job.min_experience_years is not None else (job.experience_level or 'Flexible / Not strictly stated')}\n"
                    f"- **Academic Background:** {job.required_education or 'No strict degree requirement detected'}\n"
                    f"- **Compensation:** {job.salary_raw or 'Not publicly listed in posting'}\n"
                    + (
                        f"- **Important Restrictions:** {', '.join(m['explicit_disqualifiers'])}\n"
                        if m["explicit_disqualifiers"]
                        else ""
                    )
                )

            else:  # free_chat with job context
                title = f"Career Advisor — {job.title}"
                md = (
                    f"Based on your CV (**{m['overall_score']}% match** with **{job.title}** at **{job.company_name}**):\n\n"
                    f"- **Strengths:** {'; '.join(m['strengths']) or 'Solid baseline skills.'}\n"
                    f"- **Gaps to watch:** {'; '.join(m['weaknesses']) or 'None flagged.'}\n"
                )

        else:
            # Profile-only career guidance (no specific job selected)
            title = "Profile & Career Readiness Guidance"
            highlights = [
                f"Detected {len(all_cand_skills)} technical/programming skills on your CV.",
                f"Highest degree: {digest['highest_degree'] or 'Not specified'}",
            ]
            md = (
                f"### Candidate Snapshot: **{digest['full_name']}**\n"
                f"- **Programming & Tech Stack:** {', '.join(all_cand_skills) or 'Add technical skills on your Profile page'}\n"
                f"- **Projects & Experience:** {len(digest['projects'])} project(s), {len(digest['experience'])} role(s), {len(digest['internships'])} internship(s)\n\n"
                "### Actionable Next Steps\n"
                "1. Select any discovered job in the Assistant dropdown to generate a tailored cover letter, skill gap plan, or interview prep guide.\n"
                + (
                    "2. Review missing/unclear CV items on your Candidate Profile page:\n"
                    + "\n".join(f"   - {item}" for item in (profile.missing_or_unclear_json or []))
                    if profile.missing_or_unclear_json
                    else "2. Your structured profile is complete and ready for multi-country AI job discovery."
                )
            )

        # If an external LLM provider is configured, optionally refine prose while enforcing strict grounding
        generation_mode = "deterministic_grounded"
        if llm_client.is_available:
            job_context = (
                wrap_untrusted_data(
                    "TARGET_JOB",
                    f"Title: {job.title}\nCompany: {job.company_name}\nLocation: {job.location_raw}\nDescription:\n{job.description_text[:5000]}",
                )
                if job
                else "No single target job selected."
            )
            llm_text = await llm_client.complete_text(
                system_prompt=(
                    "You are the TalentScope Truthful AI Career Assistant. "
                    "STRICT GROUNDING RULE: You may ONLY cite qualifications, skills, degrees, projects, "
                    "and work history explicitly present in CANDIDATE_FACTS. Never invent employers, metrics, "
                    "years of experience, or skills. Format cleanly in GitHub-flavored Markdown."
                ),
                user_prompt=(
                    f"Action: {req.action} (Tone: {req.tone})\n"
                    f"User Question: {req.user_message or 'Provide thorough grounded guidance.'}\n\n"
                    f"CANDIDATE_FACTS:\n{digest}\n\n"
                    f"BASELINE_VERIFIED_ANALYSIS:\n{md}\n\n"
                    f"{job_context}"
                ),
            )
            if llm_text and len(llm_text.strip()) > 60:
                md = llm_text.strip()
                generation_mode = f"llm_grounded ({llm_client.active_provider})"

        return AssistantResponse(
            action=req.action,
            title=title,
            content_markdown=md,
            highlights=highlights,
            grounded_facts_used={
                "candidate_name": digest["full_name"],
                "skills_count": len(all_cand_skills),
                "target_job": f"{job.title} @ {job.company_name}" if job else None,
            },
            generation_mode=generation_mode,
        )


career_assistant_service = CareerAssistantService()
