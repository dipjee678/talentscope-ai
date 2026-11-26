"""Registry of all permitted job-source connectors and dynamic country-based selection."""
from __future__ import annotations

from typing import Dict, List

from app.services.job_sources.ats_sources import (
    AshbyCareerPagesConnector,
    GreenhouseCareerPagesConnector,
    LeverCareerPagesConnector,
)
from app.services.job_sources.base import BaseJobSourceConnector
from app.services.job_sources.keyed_sources import (
    AdzunaConnector,
    JoobleConnector,
    JSearchConnector,
    ReedUKConnector,
    USAJobsConnector,
)
from app.services.job_sources.open_sources import (
    ArbeitnowConnector,
    HimalayasConnector,
    JobicyConnector,
    JobTechDevSwedenConnector,
    RemoteOKConnector,
    RemotiveConnector,
    TheMuseConnector,
    WeWorkRemotelyRSSConnector,
)


def get_all_connectors() -> List[BaseJobSourceConnector]:
    return [
        RemotiveConnector(),
        ArbeitnowConnector(),
        RemoteOKConnector(),
        TheMuseConnector(),
        JobicyConnector(),
        HimalayasConnector(),
        WeWorkRemotelyRSSConnector(),
        JobTechDevSwedenConnector(),
        GreenhouseCareerPagesConnector(),
        LeverCareerPagesConnector(),
        AshbyCareerPagesConnector(),
        AdzunaConnector(),
        JoobleConnector(),
        USAJobsConnector(),
        ReedUKConnector(),
        JSearchConnector(),
    ]


def get_connector_map() -> Dict[str, BaseJobSourceConnector]:
    return {c.slug: c for c in get_all_connectors()}


# Transparency disclosure for portals without public unauthenticated APIs
NON_API_PORTAL_DISCLOSURES: List[Dict[str, str]] = [
    {
        "portal": "LinkedIn Jobs / Indeed / Glassdoor / Monster / CareerBuilder",
        "policy": (
            "Direct unauthenticated scraping is prohibited by Terms of Service and gated by anti-bot "
            "challenges. Listings from these portals are included legally when JSEARCH_API_KEY, "
            "ADZUNA_APP_ID/KEY, or JOOBLE_API_KEY is configured, alongside direct ATS career pages."
        ),
    }
]


def select_connectors_for_countries(
    target_countries: List[str],
    enabled_slugs: List[str] | None = None,
) -> List[BaseJobSourceConnector]:
    all_conns = get_all_connectors()
    if enabled_slugs:
        allowed = set(enabled_slugs)
        all_conns = [c for c in all_conns if c.slug in allowed]

    countries_low = {c.lower().strip() for c in target_countries if c}
    selected: List[BaseJobSourceConnector] = []

    for conn in all_conns:
        supp_low = {s.lower() for s in conn.supported_countries}
        if "worldwide" in supp_low or not countries_low or "worldwide" in countries_low or "remote / worldwide" in countries_low:
            selected.append(conn)
            continue
        if countries_low.intersection(supp_low):
            selected.append(conn)
            continue
        # European country routing for European boards
        eu_countries = {"germany", "france", "netherlands", "sweden", "spain", "poland", "ireland", "switzerland", "austria", "belgium", "italy"}
        if "europe" in supp_low and countries_low.intersection(eu_countries):
            selected.append(conn)

    return selected
