# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The legal status a recommendation carries (hard rule 2, MASTER_PLAN §4.5).

Every candidate spot has one: what was decided, by what source, when, and the disclaimer
that it is guidance, not legal advice. Until the legal filter exists (session 09) the only
honest state is "not evaluated"; "rules not loaded" says which rules could not be read.
Neither is ever a blank.
"""

from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, Field, model_validator

from subphora.domain import DomainModel


class LegalState(StrEnum):
    NOT_EVALUATED = "not_evaluated"
    RULES_NOT_LOADED = "rules_not_loaded"


class LegalStatus(DomainModel):
    state: LegalState
    # What the state rests on: the rules read, or why none were.
    source: str = Field(min_length=1)
    assessed_at: AwareDatetime
    disclaimer: str = Field(min_length=1)
    # Why the rules could not be loaded; only for that state.
    reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _reason(self) -> Self:
        if (self.reason is not None) != (self.state is LegalState.RULES_NOT_LOADED):
            raise ValueError("only 'rules not loaded' carries a reason, and it always does")
        return self
