# Copyright (c) 2026 Almoon-D. All rights reserved.
"""External services: the polite catalogue client and the probes that check each service.

This is the only layer that talks to the network (an import-linter contract keeps httpx out
of the layers below it). It calls only the hosts of the source catalogue (hard rule 4).
"""

from subphora.sources.client import CatalogueClient, HostNotAllowedError, SourceError
from subphora.sources.models import CheckName, CheckResult, CheckStatus
from subphora.sources.probes import check_catalogue, check_service, format_table

__all__ = [
    "CatalogueClient",
    "CheckName",
    "CheckResult",
    "CheckStatus",
    "HostNotAllowedError",
    "SourceError",
    "check_catalogue",
    "check_service",
    "format_table",
]
