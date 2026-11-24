# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Schema of ``config/defaults/sources.yaml``: the catalogue of external services.

The catalogue is the only list of hosts the HTTP client may call (hard rule 4). Each entry
records what session 01 observed live; ``subphora sources check`` re-checks those facts.
"""

import re
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, PositiveFloat, PositiveInt, model_validator

from subphora.config.base import Section

ServiceKind = Literal["wms", "wmts", "wfs", "wcs", "ogc_api", "rest", "download"]

# Kinds whose capabilities document lists layers and the CRS they can be drawn in.
KINDS_WITH_CRS: frozenset[str] = frozenset({"wms", "wmts", "wfs"})
KINDS_WITH_CAPABILITIES: frozenset[str] = KINDS_WITH_CRS | {"wcs", "ogc_api"}

_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
# ISO 3166-1 alpha-2 (a country: ES) or ISO 3166-2 (a region or province: ES-AN, ES-Z).
_AREA = re.compile(r"^[A-Z]{2}(-[A-Z0-9]{1,3})?$")


def host_of(url: str) -> str:
    """The lower-cased host of an absolute https URL; anything else is an error."""
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError(f"{url!r} is not an absolute https URL")
    return parts.hostname.lower()


class ClientSettings(Section):
    """How the HTTP client behaves towards every host."""

    # `{version}` is replaced by the package version. Generic: no contact data (hard rule 4).
    user_agent: str
    connect_timeout_s: PositiveFloat
    read_timeout_s: PositiveFloat
    # Retries after a transport error (reset, refused, timeout); HTTP errors are not retried.
    retries: int = Field(ge=0, le=5)
    retry_backoff_s: float = Field(ge=0)
    # A response larger than this is cut off and the probe fails: probes fetch samples only.
    max_response_bytes: PositiveInt
    # The Origin sent with every probe, to see whether a browser could call the service.
    cors_probe_origin: str

    @model_validator(mode="after")
    def _generic_user_agent(self) -> Self:
        if "@" in self.user_agent or "http" in self.user_agent.lower():
            raise ValueError("user_agent must be generic: no e-mail address or URL")
        if "{version}" not in self.user_agent:
            raise ValueError("user_agent must contain {version}")
        return self


class Politeness(Section):
    """Per-service limits. Services on one host share the strictest of them."""

    max_concurrent: PositiveInt
    min_interval_s: float = Field(ge=0)
    # 0 means never cache (Google: hard rule 4).
    cache_lifetime_s: int = Field(ge=0)


class SampleRequest(Section):
    """One small request that shows the service answers with real data."""

    description: str
    # Appended to the service's base URL.
    path: str = ""
    # A list value repeats the parameter (WCS subsets).
    params: dict[str, str | list[str]] = Field(default_factory=dict)
    expect_content_type: str
    # A string the body must contain (a layer name, a reference, a field).
    expect_text: str | None = None


class Service(Section):
    id: str
    name: str
    publisher: str
    kind: ServiceKind
    # The areas the service covers and the areas inside them it does not, as ISO 3166 codes.
    coverage: list[str]
    coverage_excludes: list[str] = Field(default_factory=list)
    base_url: str
    # Layers, feature types, coverages or collections of interest; the capabilities probe
    # checks that each one is offered.
    layers: list[str] = Field(default_factory=list)
    crs: list[str] = Field(default_factory=list)
    # Whether the service offers EPSG:3857 (MapLibre draws only that). None: not applicable.
    web_mercator: bool | None = None
    # Whether a browser may call it directly (Access-Control-Allow-Origin). None: unknown.
    cors: bool | None = None
    licence: str
    attribution: str
    terms_url: str
    # The docs/knowledge/ file with the observed behaviour and terms of this service.
    knowledge: str
    needs_key: bool = False
    # Name of the environment variable holding the key; keys never live in config/.
    key_env: str | None = None
    politeness: Politeness
    sample: SampleRequest | None = None

    @property
    def host(self) -> str:
        return host_of(self.base_url)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if not _ID.match(self.id):
            raise ValueError(f"service id {self.id!r} must be lower-case words joined by '-'")
        host_of(self.base_url)
        host_of(self.terms_url)
        if not self.coverage:
            raise ValueError(f"{self.id}: coverage names at least one area")
        bad = [a for a in self.coverage + self.coverage_excludes if not _AREA.match(a)]
        if bad:
            raise ValueError(f"{self.id}: {bad} are not ISO 3166 area codes (ES, ES-AN)")
        if set(self.coverage) & set(self.coverage_excludes):
            raise ValueError(f"{self.id}: an area cannot be both covered and excluded")
        if not self.knowledge.startswith("docs/knowledge/") or not self.knowledge.endswith(".md"):
            raise ValueError(f"{self.id}: knowledge must be a docs/knowledge/*.md file")
        if self.needs_key != (self.key_env is not None):
            raise ValueError(f"{self.id}: key_env is required exactly when needs_key is true")
        if self.key_env is not None and not _ENV_NAME.match(self.key_env):
            raise ValueError(f"{self.id}: key_env must be an environment variable name")
        if (self.web_mercator is None) == (self.kind in KINDS_WITH_CRS):
            raise ValueError(f"{self.id}: web_mercator is required for wms, wmts and wfs only")
        if self.kind in KINDS_WITH_CAPABILITIES and not self.layers:
            raise ValueError(f"{self.id}: a {self.kind} service names its layers of interest")
        if self.sample is None and self.kind not in KINDS_WITH_CAPABILITIES:
            raise ValueError(f"{self.id}: a {self.kind} service needs a sample request")
        return self


class SourcesSettings(Section):
    """``config/defaults/sources.yaml``."""

    client: ClientSettings
    services: list[Service]

    @model_validator(mode="after")
    def _unique_ids(self) -> Self:
        ids = [service.id for service in self.services]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"duplicate service ids: {duplicates}")
        return self

    def allowed_hosts(self) -> frozenset[str]:
        return frozenset(service.host for service in self.services)

    def service(self, service_id: str) -> Service:
        for service in self.services:
            if service.id == service_id:
                return service
        raise KeyError(service_id)
