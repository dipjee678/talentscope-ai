"""Agent 1: CV Analysis Agent.

Extracts structured candidate qualifications, skills, education, experience, internships,
projects, certifications, languages, career interests, and achievements from untrusted CV text.
Never fabricates qualifications and explicitly reports missing or unclear sections.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.security import detect_and_sanitize_prompt_injection, wrap_untrusted_data
from app.services.llm_client import llm_client
from app.services.skill_taxonomy import (
    SPOKEN_LANGUAGES,
    compute_semantic_embedding,
    detect_highest_degree,
    extract_skills_from_text,
    normalize_skill,
)

SECTION_HEADERS: Dict[str, re.Pattern[str]] = {
    "summary": re.compile(r"^\s*(professional\s+summary|summary|profile|objective|about\s+me)\s*:?\s*$", re.I),
    "education": re.compile(r"^\s*(education|academic\s+background|academic\s+qualifications|qualifications)\s*:?\s*$", re.I),
    "experience": re.compile(r"^\s*(work\s+experience|professional\s+experience|employment\s+history|experience)\s*:?\s*$", re.I),
    "internships": re.compile(r"^\s*(internships?|industrial\s+training)\s*:?\s*$", re.I),
    "projects": re.compile(r"^\s*(projects?|academic\s+projects|personal\s+projects|key\s+projects)\s*:?\s*$", re.I),
    "skills": re.compile(r"^\s*(technical\s+skills|skills|core\s+competencies|technologies|tech\s+stack)\s*:?\s*$", re.I),
    "certifications": re.compile(r"^\s*(certifications?|licenses?\s*&?\s*certifications?|courses)\s*:?\s*$", re.I),
    "achievements": re.compile(r"^\s*(achievements?|awards?|honors?|accomplishments?|publications?)\s*:?\s*$", re.I),
    "languages": re.compile(r"^\s*(languages?|spoken\s+languages)\s*:?\s*$", re.I),
    "interests": re.compile(r"^\s*(career\s+interests?|interests?|target\s+roles?)\s*:?\s*$", re.I),
}

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{4}")
UNIVERSITY_RE = re.compile(
    r"([A-Z][A-Za-z&.,'\-\s]{3,80}\b(?:University|Institute of Technology|College|Polytechnic|School of [A-Za-z\s]+|Academy))",
)
YEAR_RANGE_RE = re.compile(
    r"\b((?:19|20)\d{2})\s*(?:[-–—]|to)\s*((?:19|20)\d{2}|present|current|now)\b",
    re.I,
)
EXPERIENCE_YEARS_MENTION_RE = re.compile(
    r"\b(\d{1,2}(?:\.\d)?)\+?\s*years?\s+of\s+(?:professional\s+|relevant\s+|industry\s+)?experience\b",
    re.I,
)


class CVAnalysisAgent:
    agent_name = "CVAnalysisAgent"

    def _split_sections(self, text: str) -> Dict[str, List[str]]:
        sections: Dict[str, List[str]] = {"header": []}
        current = "header"
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            matched_sec: Optional[str] = None
            if len(line) <= 55:
                for sec_name, pattern in SECTION_HEADERS.items():
                    if pattern.match(line.rstrip(":")):
                        matched_sec = sec_name
                        break
            if matched_sec:
                current = matched_sec
                sections.setdefault(current, [])
            else:
                sections.setdefault(current, []).append(line)
        return sections

    def _extract_name_and_headline(self, header_lines: List[str], full_text: str) -> Tuple[Optional[str], Optional[str]]:
        name: Optional[str] = None
        headline: Optional[str] = None
        for line in header_lines[:6]:
            cleaned = re.sub(r"[|•·]", " ", line).strip()
            if EMAIL_RE.search(cleaned) or "http" in cleaned.lower() or "linkedin" in cleaned.lower():
                continue
            if PHONE_RE.search(cleaned) and sum(c.isdigit() for c in cleaned) >= 7:
                continue
            words = cleaned.split()
            if not name and 2 <= len(words) <= 5 and all(w[0].isupper() for w in words if w[0].isalpha()):
                name = cleaned
                continue
            if name and not headline and 2 <= len(words) <= 12:
                headline = cleaned
                break
        return name, headline

    def _estimate_experience_years(self, exp_lines: List[str], full_text: str) -> Optional[float]:
        explicit = EXPERIENCE_YEARS_MENTION_RE.search(full_text)
        if explicit:
            try:
                return round(float(explicit.group(1)), 1)
            except ValueError:
                pass

        now_year = datetime.now().year
        intervals: List[Tuple[int, int]] = []
        for line in exp_lines:
            for m in YEAR_RANGE_RE.finditer(line):
                start = int(m.group(1))
                end_raw = m.group(2).lower()
                end = now_year if end_raw in ("present", "current", "now") else int(end_raw)
                if 1985 <= start <= end <= now_year + 1:
                    intervals.append((start, min(end, now_year)))

        if not intervals:
            return None

        intervals.sort()
        merged: List[Tuple[int, int]] = [intervals[0]]
        for s, e in intervals[1:]:
            prev_s, prev_e = merged[-1]
            if s <= prev_e:
                merged[-1] = (prev_s, max(prev_e, e))
            else:
                merged.append((s, e))

        total = sum(max(0.5, float(e - s)) for s, e in merged)
        return round(min(total, 45.0), 1)

    def _parse_structured_entries(self, lines: List[str], max_items: int = 10) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None

        for line in lines:
            is_bullet = line.startswith(("-", "•", "*", "▪", "–"))
            has_date = bool(YEAR_RANGE_RE.search(line) or re.search(r"\b(19|20)\d{2}\b", line))
            if not is_bullet and (has_date or current is None or len(line) < 95):
                if current:
                    entries.append(current)
                current = {"title": line.lstrip("-•* "), "highlights": []}
            else:
                if current is None:
                    current = {"title": line.lstrip("-•* "), "highlights": []}
                else:
                    current["highlights"].append(line.lstrip("-•* ").strip())
        if current:
            entries.append(current)
        return entries[:max_items]

    async def analyze(self, raw_text: str, ocr_warnings: Optional[List[str]] = None) -> Dict[str, Any]:
        sanitized_text, injection_flags = detect_and_sanitize_prompt_injection(raw_text)
        sections = self._split_sections(sanitized_text)

        header_lines = sections.get("header", [])
        full_name, headline = self._extract_name_and_headline(header_lines, sanitized_text)

        email_match = EMAIL_RE.search(sanitized_text)
        phone_match = PHONE_RE.search(sanitized_text)
        email = email_match.group(0) if email_match else None
        phone = phone_match.group(0).strip() if phone_match else None

        # Skills extraction from entire CV
        skill_groups = extract_skills_from_text(sanitized_text)
        highest_degree, _ = detect_highest_degree(
            "\n".join(sections.get("education", [])) or sanitized_text
        )

        universities = sorted(
            {m.group(1).strip(" ,.-") for m in UNIVERSITY_RE.finditer(sanitized_text)}
        )[:6]

        edu_entries = self._parse_structured_entries(sections.get("education", []), max_items=6)
        exp_lines = sections.get("experience", [])
        intern_lines = list(sections.get("internships", []))

        # Separate internship entries embedded inside general experience section
        filtered_exp_lines: List[str] = []
        for line in exp_lines:
            if re.search(r"\bintern(ship)?\b", line, re.I):
                intern_lines.append(line)
            else:
                filtered_exp_lines.append(line)

        experience_entries = self._parse_structured_entries(filtered_exp_lines, max_items=10)
        internship_entries = self._parse_structured_entries(intern_lines, max_items=6)
        project_entries = self._parse_structured_entries(sections.get("projects", []), max_items=10)

        certifications = [
            ln.lstrip("-•* ").strip() for ln in sections.get("certifications", []) if len(ln.strip()) > 3
        ][:12]
        achievements = [
            ln.lstrip("-•* ").strip() for ln in sections.get("achievements", []) if len(ln.strip()) > 3
        ][:12]

        lang_text = "\n".join(sections.get("languages", [])) or sanitized_text
        spoken_languages = [
            lang for lang in SPOKEN_LANGUAGES
            if re.search(rf"\b{re.escape(lang)}\b", lang_text, re.I)
        ]

        career_interests = [
            ln.lstrip("-•* ").strip() for ln in sections.get("interests", []) if len(ln.strip()) > 2
        ][:8]
        if not career_interests and headline:
            career_interests = [headline]

        summary_text = " ".join(sections.get("summary", []))[:1200] or None
        years_exp = self._estimate_experience_years(filtered_exp_lines, sanitized_text)
        extraction_mode = "hybrid_nlp"

        # Optional LLM enrichment strictly grounded in the CV text
        if llm_client.is_available and len(sanitized_text.strip()) >= 60:
            llm_data = await llm_client.complete_json(
                system_prompt=(
                    "You are a precise CV Extraction Agent. Extract ONLY factual information explicitly "
                    "present in the candidate's CV. NEVER invent skills, degrees, companies, or years of experience. "
                    "Return JSON keys: full_name (str|null), headline (str|null), location (str|null), "
                    "summary (str|null), years_of_experience (number|null), highest_degree (str|null), "
                    "universities (list[str]), programming_languages (list[str]), technical_skills (list[str]), "
                    "soft_skills (list[str]), certifications (list[str]), spoken_languages (list[str]), "
                    "career_interests (list[str]), achievements (list[str])."
                ),
                user_prompt=wrap_untrusted_data("CANDIDATE_CV", sanitized_text[:14000]),
            )
            if llm_data:
                extraction_mode = f"llm+{llm_client.active_provider}"
                full_name = llm_data.get("full_name") or full_name
                headline = llm_data.get("headline") or headline
                summary_text = llm_data.get("summary") or summary_text
                highest_degree = llm_data.get("highest_degree") or highest_degree
                if isinstance(llm_data.get("years_of_experience"), (int, float)):
                    years_exp = float(llm_data["years_of_experience"])
                # Grounding check: only accept LLM-extracted skills whose substring appears in CV or canonical skills
                cv_low = sanitized_text.lower()
                for key_name, target_list in (
                    ("programming_languages", skill_groups["programming_languages"]),
                    ("technical_skills", skill_groups["technical_skills"]),
                    ("soft_skills", skill_groups["soft_skills"]),
                ):
                    for item in llm_data.get(key_name) or []:
                        if isinstance(item, str) and item.strip():
                            canon, _ = normalize_skill(item)
                            if item.strip().lower() in cv_low or canon.lower() in cv_low:
                                if canon not in target_list:
                                    target_list.append(canon)

        # Identify missing or unclear information transparently
        missing_or_unclear: List[str] = list(ocr_warnings or [])
        if not full_name:
            missing_or_unclear.append("Candidate full name could not be confidently identified from header.")
        if not skill_groups["programming_languages"] and not skill_groups["technical_skills"]:
            missing_or_unclear.append("No recognized technical skills or programming languages were detected.")
        if not highest_degree and not edu_entries:
            missing_or_unclear.append("Education / academic degree details are missing or unclear.")
        if not experience_entries and not internship_entries:
            missing_or_unclear.append("No structured work or internship history was found (please verify if fresh graduate).")
        if years_exp is None:
            missing_or_unclear.append("Total years of professional experience is not explicitly stated.")
        if not spoken_languages:
            missing_or_unclear.append("Spoken languages are not explicitly listed on the CV.")

        # Build normalized skill records
        skill_records: List[Dict[str, str]] = []
        seen_norm = set()
        for sk in skill_groups["programming_languages"]:
            norm = sk.lower()
            if norm not in seen_norm:
                seen_norm.add(norm)
                skill_records.append(
                    {"skill_name": sk, "normalized_name": norm, "category": "programming_language", "source_section": "cv"}
                )
        for sk in skill_groups["technical_skills"]:
            norm = sk.lower()
            if norm not in seen_norm:
                seen_norm.add(norm)
                skill_records.append(
                    {"skill_name": sk, "normalized_name": norm, "category": "technical", "source_section": "cv"}
                )
        for sk in skill_groups["soft_skills"]:
            norm = sk.lower()
            if norm not in seen_norm:
                seen_norm.add(norm)
                skill_records.append(
                    {"skill_name": sk, "normalized_name": norm, "category": "soft", "source_section": "cv"}
                )

        embedding = compute_semantic_embedding(sanitized_text)

        return {
            "full_name": full_name,
            "headline": headline,
            "email": email,
            "phone": phone,
            "location": None,
            "summary": summary_text,
            "years_of_experience": years_exp,
            "highest_degree": highest_degree,
            "universities": universities,
            "education": edu_entries,
            "programming_languages": sorted(set(skill_groups["programming_languages"])),
            "technical_skills": sorted(set(skill_groups["technical_skills"])),
            "soft_skills": sorted(set(skill_groups["soft_skills"])),
            "experience": experience_entries,
            "internships": internship_entries,
            "projects": project_entries,
            "certifications": certifications,
            "spoken_languages": spoken_languages,
            "career_interests": career_interests,
            "achievements": achievements,
            "missing_or_unclear": missing_or_unclear,
            "extraction_mode": extraction_mode,
            "prompt_injection_flags": injection_flags,
            "skills": skill_records,
            "embedding_vector": embedding,
        }


cv_analysis_agent = CVAnalysisAgent()
