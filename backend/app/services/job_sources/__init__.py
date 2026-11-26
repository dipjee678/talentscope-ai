"""Job sources package."""
from app.services.job_sources.base import BaseJobSourceConnector, RawDiscoveredJob, SourceSearchResult
from app.services.job_sources.registry import (
    NON_API_PORTAL_DISCLOSURES,
    get_all_connectors,
    get_connector_map,
    select_connectors_for_countries,
)

__all__ = [
    "BaseJobSourceConnector",
    "RawDiscoveredJob",
    "SourceSearchResult",
    "NON_API_PORTAL_DISCLOSURES",
    "get_all_connectors",
    "get_connector_map",
    "select_connectors_for_countries",
]
