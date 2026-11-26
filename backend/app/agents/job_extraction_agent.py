"""Agent 3: Job Extraction Agent.

Normalizes raw HTML/text job descriptions, neutralizes prompt-injection attempts,
extracts structured job metadata (never fabricating salary or deadlines), and separates
mandatory requirements, preferred qualifications, and explicit disqualifiers.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from app.core.security import detect_and_sanitize_prompt_injection
from app.services.job_sources.base import RawDiscoveredJob
from app.services.skill_taxonomy import (
    compute_semantic_embedding,
    detect_highest_degree,
    extract_skills_from_text,
    infer_country_from_location,
)

PREFERRED_CUE_RE = re.compile(
    r"\b(preferred|nice\s+to\s+have|bonus|plus|desirable|ideally|advantageous|optional)\b",
    re.I,
)
MIN_YEARS_RE = re.compile(
    r"\b(\d{1,2})\+?\s*(?:-\s*\d{1,2}\s*)?years?\s+(?:of\s+)?(?:relevant\s+|professional\s+|industry\s+|hands-on\s+)?experience\b",
    re.I,
)
SALARY_EXTRACT_RE = re.compile(
    r"(?:(USD|EUR|GBP|CAD|AUD|CHF|SEK|SGD|\$|€|£)\s*)?"
    r"(\d{2,3}(?:,\d{3})+|\d{2,3}k)"
    r"(?:\s*[-–to]+\s*(?:USD|EUR|GBP|CAD|AUD|CHF|SEK|SGD|\$|€|£)?\s*(\d{2,3}(?:,\d{3})+|\d{2,3}k))?",
    re.I,
)
VISA_POSITIVE_RE = re.compile(
    r"\b(visa\s+sponsorship\s+(?:is\s+)?available|we\s+sponsor\s+visas|relocation\s+and\s+visa\s+support|sponsorship\s+provided)\b",
    re.I,
)
VISA_NEGATIVE_RE = re.compile(
    r"\b(no\s+visa\s+sponsorship|unable\s+to\s+sponsor|cannot\s+sponsor|without\s+(?:current\s+or\s+future\s+)?sponsorship|must\s+have\s+permanent\s+work\s+authorization)\b",
    re.I,
)
DISQUALIFIER_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    ("Active Security Clearance Required", re.compile(r"\b(active\s+(?:ts/sci|secret|top\s+secret)\s+clearance|security\s+clearance\s+required)\b", re.I)),
    ("Citizenship Requirement", re.compile(r"\b(u\.?s\.?\s+citizenship\s+required|must\s+be\s+a\s+u\.?s\.?\s+citizen|british\s+citizenship\s+required)\b", re.I)),
    ("No Visa Sponsorship Offered", VISA_NEGATIVE_RE),
]

DIRECT_ATS_DOMAINS = (
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "myworkdayjobs.com",
    "smartrecruiters.com",
    "bamboohr.com",
    "workable.com",
    "personio.de",
    "personio.com",
    "teamtailor.com",
    "icims.com",
)
THIRD_PARTY_AGGREGATOR_DOMAINS = (
    "remotive.com",
    "arbeitnow.com",
    "remoteok.com",
    "themuse.com",
    "jobicy.com",
    "himalayas.app",
    "weworkremotely.com",
    "adzuna.",
    "jooble.org",
    "reed.co.uk",
    "indeed.com",
    "linkedin.com",
    "glassdoor.com",
)


@dataclass
class ExtractedJobBundle:
    listing_fields: Dict[str, Any]
    requirements: List[Dict[str, Any]] = field(default_factory=list)


def _html_to_clean_text(raw: str) -> str:
    if not raw:
        return ""
    if "<" in raw and ">" in raw:
        soup = BeautifulSoup(raw, "html.parser")
        for bad in soup(["script", "style", "noscript", "iframe"]):
            bad.decompose()
        text = soup.get_text(separator="\n")
    else:
        text = raw
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def _infer_work_mode(explicit_mode: Optional[str], title: str, loc: str, desc: str) -> str:
    if explicit_mode and explicit_mode.lower() in ("remote", "hybrid", "onsite"):
        return explicit_mode.lower()
    head = f"{title} {loc}".lower()
    if "hybrid" in head:
        return "hybrid"
    if "remote" in head or "anywhere" in head or "work from home" in head:
        return "remote"
    low_desc = desc[:1500].lower()
    if "hybrid" in low_desc:
        return "hybrid"
    if "100% remote" in low_desc or "fully remote" in low_desc:
        return "remote"
    return "onsite"


def _infer_experience_level(explicit_level: Optional[str], title: str, min_years: Optional[float]) -> str:
    combined = f"{explicit_level or ''} {title}".lower()
    if any(k in combined for k in ("intern", "internship", "working student")):
        return "Internship"
    if any(k in combined for k in ("junior", "entry", "graduate", "new grad", "associate")):
        return "Entry-Level"
    if any(k in combined for k in ("principal", "staff", "lead", "architect", "director", "vp", "head of")):
        return "Lead / Principal"
    if any(k in combined for k in ("senior", "sr.", "sr ")):
        return "Senior"
    if min_years is not None:
        if min_years <= 1:
            return "Entry-Level"
        if min_years >= 5:
            return "Senior"
    return "Mid-Level"


def _parse_money_token(tok: str) -> Optional[float]:
    t = tok.strip().lower().replace(",", "")
    if t.endswith("k"):
        try:
            return float(t[:-1]) * 1000.0
        except ValueError:
            return None
    try:
        val = float(t)
        return val if val >= 500 else None
    except ValueError:
        return None


def _parse_salary_if_present(raw_job: RawDiscoveredJob, clean_desc: str) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str], Optional[str]]:
    if raw_job.salary_min or raw_job.salary_max:
        cur = raw_job.salary_currency or "USD"
        per = raw_job.salary_period or "year"
        lo = raw_job.salary_min
        hi = raw_job.salary_max
        raw_str = raw_job.salary_raw
        if not raw_str:
            if lo and hi:
                raw_str = f"{cur} {int(lo):,} - {int(hi):,} / {per}"
            elif lo:
                raw_str = f"{cur} {int(lo):,}+ / {per}"
            elif hi:
                raw_str = f"Up to {cur} {int(hi):,} / {per}"
        return lo, hi, cur, per, raw_str

    if raw_job.salary_raw:
        m = SALARY_EXTRACT_RE.search(raw_job.salary_raw)
        if m:
            sym = (m.group(1) or "USD").upper()
            cur = {"$": "USD", "€": "EUR", "£": "GBP"}.get(sym, sym)
            lo = _parse_money_token(m.group(2))
            hi = _parse_money_token(m.group(3)) if m.group(3) else lo
            return lo, hi, cur, "year", raw_job.salary_raw.strip()
        return None, None, None, None, raw_job.salary_raw.strip()

    # Never invent salary if not explicitly present
    return None, None, None, None, None


def _is_direct_company_url(url: str, flagged_direct: bool) -> bool:
    if flagged_direct:
        return True
    host = (urlparse(url).netloc or "").lower()
    if any(d in host for d in DIRECT_ATS_DOMAINS):
        return True
    if any(d in host for d in THIRD_PARTY_AGGREGATOR_DOMAINS):
        return False
    return bool(host)


def compute_dedup_fingerprint(company: str, title: str, country: str) -> str:
    norm_c = re.sub(r"[^a-z0-9]", "", (company or "").lower())
    norm_t = re.sub(r"[^a-z0-9]", "", (title or "").lower())
    norm_loc = re.sub(r"[^a-z0-9]", "", (country or "").lower())
    raw = f"{norm_c}::{norm_t}::{norm_loc}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


class JobExtractionAgent:
    agent_name = "JobExtractionAgent"

    def extract(self, raw_job: RawDiscoveredJob) -> ExtractedJobBundle:
        clean_desc = _html_to_clean_text(raw_job.description_raw)
        sanitized_desc, injection_flags = detect_and_sanitize_prompt_injection(clean_desc)

        country = infer_country_from_location(raw_job.location_raw)
        city = None
        if "," in raw_job.location_raw:
            first_part = raw_job.location_raw.split(",", 1)[0].strip()
            if first_part and first_part.lower() != country.lower() and len(first_part) <= 60:
                city = first_part

        work_mode = _infer_work_mode(raw_job.work_mode, raw_job.title, raw_job.location_raw, sanitized_desc)

        # Extract minimum required years of experience if stated
        years_matches = [float(m.group(1)) for m in MIN_YEARS_RE.finditer(sanitized_desc)]
        min_years = min(years_matches) if years_matches else None

        exp_level = _infer_experience_level(raw_job.experience_level, raw_job.title, min_years)
        req_degree, _ = detect_highest_degree(sanitized_desc)

        sal_min, sal_max, sal_cur, sal_per, sal_raw = _parse_salary_if_present(raw_job, sanitized_desc)

        visa = raw_job.visa_sponsorship
        if visa is None:
            if VISA_NEGATIVE_RE.search(sanitized_desc):
                visa = False
            elif VISA_POSITIVE_RE.search(sanitized_desc):
                visa = True

        # Separate mandatory vs preferred lines in description
        mandatory_lines: List[str] = []
        preferred_lines: List[str] = []
        in_preferred_block = False

        for line in sanitized_desc.splitlines():
            low = line.lower().strip()
            if len(low) < 60 and PREFERRED_CUE_RE.search(low):
                in_preferred_block = True
                continue
            if len(low) < 60 and any(h in low for h in ("responsibilities", "benefits", "about us", "what we offer")):
                in_preferred_block = False

            if in_preferred_block or PREFERRED_CUE_RE.search(low):
                preferred_lines.append(line)
            else:
                mandatory_lines.append(line)

        mandatory_blob = f"{raw_job.title}\n" + "\n".join(mandatory_lines)
        preferred_blob = "\n".join(preferred_lines)

        mand_skills_dict = extract_skills_from_text(mandatory_blob)
        pref_skills_dict = extract_skills_from_text(preferred_blob)

        mand_skills = set(mand_skills_dict["programming_languages"] + mand_skills_dict["technical_skills"])
        pref_skills = set(pref_skills_dict["programming_languages"] + pref_skills_dict["technical_skills"]) - mand_skills

        requirements: List[Dict[str, Any]] = []
        for sk in sorted(mand_skills):
            requirements.append(
                {
                    "requirement_type": "technical_skill",
                    "requirement_text": f"Required proficiency in {sk}",
                    "normalized_key": sk.lower(),
                    "is_mandatory": True,
                    "min_years": None,
                }
            )
        for sk in sorted(pref_skills):
            requirements.append(
                {
                    "requirement_type": "technical_skill",
                    "requirement_text": f"Preferred experience with {sk}",
                    "normalized_key": sk.lower(),
                    "is_mandatory": False,
                    "min_years": None,
                }
            )

        if req_degree:
            is_deg_pref = bool(re.search(r"degree.*preferred|or\s+equivalent\s+practical\s+experience", sanitized_desc, re.I))
            requirements.append(
                {
                    "requirement_type": "education",
                    "requirement_text": req_degree,
                    "normalized_key": req_degree.lower(),
                    "is_mandatory": not is_deg_pref,
                    "min_years": None,
                }
            )

        if min_years is not None:
            requirements.append(
                {
                    "requirement_type": "experience",
                    "requirement_text": f"{int(min_years) if min_years.is_integer() else min_years}+ years of relevant experience",
                    "normalized_key": "years_of_experience",
                    "is_mandatory": True,
                    "min_years": min_years,
                }
            )

        for label, pattern in DISQUALIFIER_PATTERNS:
            if pattern.search(sanitized_desc):
                requirements.append(
                    {
                        "requirement_type": "disqualifier",
                        "requirement_text": label,
                        "normalized_key": label.lower().replace(" ", "_"),
                        "is_mandatory": True,
                        "min_years": None,
                    }
                )

        is_direct = _is_direct_company_url(raw_job.apply_url, raw_job.is_direct_company_link)
        fingerprint = compute_dedup_fingerprint(raw_job.company_name, raw_job.title, country)
        embedding = compute_semantic_embedding(f"{raw_job.title} {raw_job.category or ''} {sanitized_desc[:4000]}")

        listing_fields = {
            "source_slug": raw_job.source_slug,
            "source_name": raw_job.source_name,
            "external_id": raw_job.external_id,
            "dedup_fingerprint": fingerprint,
            "title": raw_job.title[:300],
            "company_name": raw_job.company_name[:255],
            "company_logo_url": raw_job.company_logo_url,
            "country": country[:128],
            "city": city[:128] if city else None,
            "location_raw": raw_job.location_raw[:255],
            "work_mode": work_mode,
            "employment_type": (raw_job.employment_type or "Full-time")[:64],
            "experience_level": exp_level,
            "min_experience_years": min_years,
            "required_education": req_degree,
            "industry": raw_job.industry[:128] if raw_job.industry else None,
            "category": raw_job.category[:128] if raw_job.category else None,
            "salary_min": sal_min,
            "salary_max": sal_max,
            "salary_currency": sal_cur,
            "salary_period": sal_per,
            "salary_raw": sal_raw[:200] if sal_raw else None,
            "visa_sponsorship": visa,
            "english_speaking": True,
            "description_text": sanitized_desc,
            "source_url": raw_job.source_url[:1024],
            "apply_url": raw_job.apply_url[:1024],
            "is_direct_company_link": is_direct,
            "published_at": raw_job.published_at,
            "application_deadline": raw_job.application_deadline,
            "prompt_injection_detected": bool(injection_flags),
            "embedding_vector": embedding,
            "raw_metadata_json": raw_job.raw_metadata or {},
        }
        return ExtractedJobBundle(listing_fields=listing_fields, requirements=requirements)


job_extraction_agent = JobExtractionAgent()
