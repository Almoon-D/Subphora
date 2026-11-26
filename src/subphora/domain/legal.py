# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The legal status a place or a candidate spot carries (hard rule 2, MASTER_PLAN §4.5).

Every candidate has one, and so does an area's legal panel: the competent water authority,
the groundwater body and its legal status, each rule that was evaluated (its source,
article and dates, and what it says here), the rules that could not be loaded and why, and
the disclaimer that it is guidance, not legal advice. The state follows from the findings
by one function (``verdict``), so a status can never claim more than its findings show.
"""

from collections.abc import Sequence
from datetime import date
from enum import StrEnum
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from subphora.domain import DomainModel


class LegalState(StrEnum):
    # Only before a place is assessed (a stored result older than the filter).
    NOT_EVALUATED = "not_evaluated"
    PROBABLY_NOT_ALLOWED = "probably_not_allowed"
    CONDITIONS_APPLY = "conditions_apply"
    NO_BLOCKING_RULE = "no_blocking_rule"
    RULES_NOT_LOADED = "rules_not_loaded"


class Outcome(StrEnum):
    """What one rule says at a place."""

    # The rule forbids the well here (a closed zone, an exclusion circle).
    BLOCKS = "blocks"
    # The well needs an authority's authorisation or a concession first.
    AUTHORISATION = "authorisation"
    # The rule may stop or condition the well, and the app could not check it.
    CHECK = "check"
    # A step the owner must take that does not stop the well (a notice).
    NOTICE = "notice"
    # The rule was checked and does not stop or condition the well here.
    CLEAR = "clear"
    # The rule does not apply to this use or place.
    NOT_APPLICABLE = "not_applicable"


_CONDITIONS = frozenset({Outcome.AUTHORISATION, Outcome.CHECK})


class RuleSource(DomainModel):
    """Where a rule is written: the official text, its article, when it was published or
    last consolidated, and when Subphora last read it."""

    name: str = Field(min_length=1)
    url: str = Field(pattern=r"^https://")
    article: str = Field(min_length=1)
    published: date
    checked: date


class Finding(DomainModel):
    """One rule evaluated at a place. ``message`` names the text the interface shows
    (``legal.message.<message>``), filled with ``values``."""

    rule_id: str = Field(min_length=1)
    # The area the rule is keyed by: ES, a region (ES-AN) or a district (ES050).
    area: str = Field(pattern=r"^ES(-[A-Z]{2}|\d{3})?$")
    title: dict[str, str] = Field(min_length=1)
    source: RuleSource
    outcome: Outcome
    message: str = Field(pattern=r"^[a-z_]+$")
    values: dict[str, str | float] = Field(default_factory=dict)
    # An open question the text read does not settle (shown beside the outcome).
    uncertain: dict[str, str] | None = None


class NotLoadedScope(StrEnum):
    BASIN_PLAN = "basin_plan"
    REGIONAL_LAW = "regional_law"
    DISTRICT = "district"


class NotLoaded(DomainModel):
    """Rules that apply here and could not be loaded, and why."""

    scope: NotLoadedScope
    # The area whose rules are missing; None when the district itself is unknown.
    area: str | None
    # Per language; "en" always.
    reason: dict[str, str] = Field(min_length=1)

    @model_validator(mode="after")
    def _english(self) -> Self:
        if not self.reason.get("en"):
            raise ValueError("a reason is always given in English")
        return self


class Authority(DomainModel):
    """The river-basin district of a place and who manages its groundwater."""

    district: str = Field(pattern=r"^ES\d{3}$")
    district_name: str = Field(min_length=1)
    name: str = Field(min_length=1)
    level: Literal["state", "regional"]
    # What the location alone cannot settle (two authorities in one district), per language.
    note: dict[str, str] | None = None


class BodyStatus(DomainModel):
    """The groundwater body at a place and its legal status, as the official layers say.
    None in a field: that layer could not be read (never guessed)."""

    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    # The plan's quantitative status ("Bueno", "Malo"), as MITECO writes it.
    quantitative_status: str | None
    # Declared at risk (or overexploited) by its basin authority.
    declared_at_risk: bool | None
    declaration: str | None = None


def verdict(
    findings: Sequence[Finding], not_loaded: Sequence[NotLoaded]
) -> tuple[LegalState, str | None]:
    """The state the findings support, and the reason when rules are missing.

    A rule that blocks decides, whatever is missing; otherwise missing rules leave the
    place "rules not loaded"; otherwise any authorisation or unchecked rule means
    "conditions apply"."""
    if any(f.outcome is Outcome.BLOCKS for f in findings):
        return LegalState.PROBABLY_NOT_ALLOWED, None
    if not_loaded:
        return LegalState.RULES_NOT_LOADED, " ".join(n.reason["en"] for n in not_loaded)
    if any(f.outcome in _CONDITIONS for f in findings):
        return LegalState.CONDITIONS_APPLY, None
    return LegalState.NO_BLOCKING_RULE, None


class LegalStatus(DomainModel):
    state: LegalState
    # What the state rests on: the rules read, or why none were.
    source: str = Field(min_length=1)
    assessed_at: AwareDatetime
    disclaimer: str = Field(min_length=1)
    # Why rules could not be loaded; only for that state.
    reason: str | None = Field(default=None, min_length=1)
    # The place's region (ISO 3166-2), district authority and body, where known.
    region: str | None = None
    authority: Authority | None = None
    body: BodyStatus | None = None
    findings: tuple[Finding, ...] = ()
    not_loaded: tuple[NotLoaded, ...] = ()
    # Other permits a well needs, which the filter names but does not evaluate (per language).
    permits: tuple[dict[str, str], ...] = ()

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if (self.reason is not None) != (self.state is LegalState.RULES_NOT_LOADED):
            raise ValueError("only 'rules not loaded' carries a reason, and it always does")
        if self.state is LegalState.NOT_EVALUATED:
            if self.findings or self.not_loaded:
                raise ValueError("a place not evaluated has no findings")
            return self
        if self.authority is None and not any(
            n.scope is NotLoadedScope.DISTRICT for n in self.not_loaded
        ):
            raise ValueError("an evaluated place names its authority or says it is unknown")
        state, reason = verdict(self.findings, self.not_loaded)
        if state is not self.state or (reason is not None and reason != self.reason):
            raise ValueError(f"the findings support {state}, not {self.state}")
        return self
