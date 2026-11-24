# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Where a piece of data came from and when it was fetched from its publisher."""

from pydantic import AwareDatetime

from subphora.domain import DomainModel


class Provenance(DomainModel):
    service_id: str
    publisher: str
    attribution: str
    retrieved_at: AwareDatetime
