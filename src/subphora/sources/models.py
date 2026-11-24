# Copyright (c) 2026 Almoon-D. All rights reserved.
"""What a probe reports about one check of one service."""

from enum import StrEnum

from subphora.domain import DomainModel


class CheckStatus(StrEnum):
    OK = "ok"
    FAILED = "failed"
    NOT_CHECKED = "not checked"


class CheckName(StrEnum):
    # The capabilities document parses and offers every layer of interest.
    CAPABILITIES = "capabilities"
    # EPSG:3857 is offered (or not) exactly as the catalogue records.
    WEB_MERCATOR = "epsg:3857"
    # A browser may (or may not) call the service, as the catalogue records.
    CORS = "cors"
    # One small real request answers with the expected content.
    SAMPLE = "sample"


class CheckResult(DomainModel):
    service_id: str
    check: CheckName
    status: CheckStatus
    detail: str
