# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Schema of the legal filter's settings (``config/defaults/legal.yaml``) and of its rules
as data (``config/legal/<country>/``, MASTER_PLAN §4.5, decision 0014).

``areas.yaml`` names every river-basin district (its authority, and whether its plan's rules
are loaded) and every region (whether its water law is); every other file holds the rules of
one area, keyed by its code: ES for national rules, a region (ES-AN) for a regional water
law, a district (ES050) for a basin plan. Each rule has its source, article, publication
date and the date it was read; its ``kind`` names the mechanics in ``subphora.legal``.
Whether each map layer a rule reads exists, and each field it reads is one the layer's
answer keeps, is checked against the map sections by ``Settings``.
"""

import re
from datetime import date
from typing import Annotated, Literal, Self

from pydantic import Field, PositiveFloat, model_validator

from subphora.config.base import Section

_DISTRICT = r"^ES\d{3}$"
_REGION = r"^ES-[A-Z]{2}$"
_AREA = r"^ES(-[A-Z]{2}|\d{3})?$"
_ID = r"^[a-z0-9][a-z0-9-]*$"


class Translated(Section):
    """A text the interface shows, in every language it speaks."""

    en: str = Field(min_length=1)
    es: str = Field(min_length=1)


class Source(Section):
    name: str = Field(min_length=1)
    url: str = Field(pattern=r"^https://")
    article: str = Field(min_length=1)
    # The text's publication, or its last consolidated update.
    published: date
    # When Subphora last read it at the source.
    checked: date


class LoadState(Section):
    """Whether an area's rules are loaded: all that bear on a new well, only part, or
    none; ``reason`` says what is missing and why (required unless loaded)."""

    state: Literal["loaded", "partial", "not_read"]
    reason: Translated | None = None

    @model_validator(mode="after")
    def _reason(self) -> Self:
        if (self.reason is None) != (self.state == "loaded"):
            raise ValueError("an area not fully loaded says why, and only then")
        return self


class District(Section):
    name: str = Field(min_length=1)
    authority: str = Field(min_length=1)
    level: Literal["state", "regional"]
    note: Translated | None = None
    plan: LoadState


class Region(Section):
    name: str = Field(min_length=1)
    water_law: LoadState


class Areas(Section):
    districts: dict[Annotated[str, Field(pattern=_DISTRICT)], District] = Field(min_length=1)
    regions: dict[Annotated[str, Field(pattern=_REGION)], Region] = Field(min_length=1)


class Where(Section):
    """Narrows a rule to some districts of its area (a regional law, for instance)."""

    districts: list[Annotated[str, Field(pattern=_DISTRICT)]] = Field(min_length=1)


class _Rule(Section):
    id: str = Field(pattern=_ID)
    area: str = Field(pattern=_AREA)
    title: Translated
    source: Source
    where: Where | None = None
    # An open question the text does not settle, shown with the outcome.
    uncertain: Translated | None = None


class NoticeRule(_Rule):
    """A well of the small-use regime is notified to the authority (it never blocks)."""

    kind: Literal["notice"]
    max_volume_m3: PositiveFloat


class ConcessionRule(_Rule):
    """Above the small-use volume a concession is needed."""

    kind: Literal["concession"]
    max_volume_m3: PositiveFloat


class AuthorisationRule(_Rule):
    """Every new well needs this authority's authorisation."""

    kind: Literal["authorisation"]


class LayerMatch(Section):
    """A feature of a map layer at the point whose ``field`` holds one of ``values``
    (any value when none is listed)."""

    layer: str = Field(min_length=1)
    field: str = Field(min_length=1)
    values: list[str] = Field(default_factory=list)

    def matches(self, value: str) -> bool:
        return not self.values or value in self.values


class BodyAuthorisationRule(_Rule):
    """A small-use well needs an authorisation where its body is declared at risk, is in
    poor quantitative status, or carries a layer's mark (preventive control)."""

    kind: Literal["body_authorisation"]
    declared_at_risk: bool = False
    poor_quantitative: bool = False
    marked: list[LayerMatch] = Field(default_factory=list)
    # Only wells of the small-use regime; None for any well.
    max_volume_m3: PositiveFloat | None = None

    @model_validator(mode="after")
    def _some_trigger(self) -> Self:
        if not (self.declared_at_risk or self.poor_quantitative or self.marked):
            raise ValueError(f"rule {self.id}: names no body status that triggers it")
        return self


class NoNewConcessionsRule(_Rule):
    """No new concession in a body in poor quantitative status."""

    kind: Literal["no_new_concessions"]
    # Wells up to this volume are not concessions and the rule does not touch them.
    above_volume_m3: PositiveFloat


BodyClass = Literal["good", "poor", "outside", "any"]


class DistanceCase(Section):
    """A minimum distance to existing wells and springs, for a body class: fixed, or a
    curve of (volume m³/year, distance m) points read linearly and clamped at its ends;
    none when the text leaves it to the authorisation. ``flow_below_l_s``: the case
    applies only when the planned flow is known to be below it."""

    bodies: list[BodyClass] = Field(min_length=1)
    # The case applies only to wells of at most this volume (m³/year).
    max_volume_m3: PositiveFloat | None = None
    distance_m: PositiveFloat | None = None
    curve: list[tuple[float, float]] | None = Field(default=None, min_length=2)
    flow_below_l_s: PositiveFloat | None = None
    none_set: bool = False

    @model_validator(mode="after")
    def _one_distance(self) -> Self:
        given = sum(x is not None for x in (self.distance_m, self.curve)) + self.none_set
        if given != 1:
            raise ValueError("a distance case has a distance, a curve or none_set, once")
        if self.curve is not None:
            volumes = [v for v, _ in self.curve]
            if volumes != sorted(volumes) or len(set(volumes)) != len(volumes):
                raise ValueError("a distance curve rises in volume")
            if any(d <= 0 for _, d in self.curve):
                raise ValueError("a distance curve's distances are positive")
        return self


class WellDistanceRule(_Rule):
    """The minimum distance from a new well to existing wells and springs. The first case
    that fits the place decides; with the body's status unknown, the strictest case."""

    kind: Literal["well_distance"]
    cases: list[DistanceCase] = Field(min_length=1)
    # National rules this one replaces where it applies ("failing the plan's, these").
    supersedes: list[str] = Field(default_factory=list)


class ZoneRule(_Rule):
    """A zone of an official layer: a feature matching ``match`` gives ``outcome``; any
    other feature of the layer at the point is shown as a condition to check."""

    kind: Literal["zone"]
    match: LayerMatch
    outcome: Literal["blocks", "authorisation"]
    # The field that names the feature for the interface.
    label_field: str = Field(min_length=1)


class WaterDomainRule(_Rule):
    """Inside the public water domain, its easement or the zona de policía, a well needs
    the basin authority's authorisation. The official zone where it is mapped, else a
    band of ``distance_m`` around the channels derived from the terrain model."""

    kind: Literal["water_domain"]
    zones: LayerMatch
    distance_m: PositiveFloat


Rule = Annotated[
    NoticeRule
    | ConcessionRule
    | AuthorisationRule
    | BodyAuthorisationRule
    | NoNewConcessionsRule
    | WellDistanceRule
    | ZoneRule
    | WaterDomainRule,
    Field(discriminator="kind"),
]


class Planned(Section):
    """The well the filter assumes, unless the owner sets theirs in ``owner.yaml``."""

    volume_m3_year: PositiveFloat
    # The pump's maximum instantaneous flow; None: not known (stricter distances apply).
    max_flow_l_s: PositiveFloat | None = None


class BodyLayers(Section):
    """The national layers a place's body and its legal status are read from, and the
    fields of their answers that say it."""

    status_layer: str = Field(min_length=1)
    code_field: str = Field(min_length=1)
    name_field: str = Field(min_length=1)
    quantitative_field: str = Field(min_length=1)
    poor_values: list[str] = Field(min_length=1)
    good_values: list[str] = Field(min_length=1)
    at_risk_layer: str = Field(min_length=1)
    at_risk_code_field: str = Field(min_length=1)
    declaration_field: str = Field(min_length=1)
    # The district is the body code's first characters (ES040MSBT… is in ES040).
    district_pattern: str = Field(min_length=1)

    @model_validator(mode="after")
    def _pattern(self) -> Self:
        if re.compile(self.district_pattern).groups != 1:
            raise ValueError("district_pattern captures the district code in one group")
        return self


class Texts(Section):
    """The texts a status carries (shown in the interface through its own translations)."""

    disclaimer: str = Field(min_length=1)
    source: str = Field(min_length=1)
    # A candidate's status between computing the map and assessing it.
    not_evaluated: str = Field(min_length=1)
    no_body: Translated
    bodies_unread: Translated
    unknown_district: Translated
    unknown_region: Translated
    permits: list[Translated] = Field(min_length=1)


class LegalSettings(Section):
    country: str = Field(pattern=r"^[a-z]{2}$")
    # The map zoom a point is asked at: the tolerance around it is a few metres.
    tap_zoom: float = Field(ge=0, le=22)
    planned: Planned
    bodies: BodyLayers
    texts: Texts
    # Filled from config/legal/<country>/ by the loader.
    areas: Areas
    rules: list[Rule] = Field(min_length=1)

    @model_validator(mode="after")
    def _rules_consistent(self) -> Self:
        ids = [r.id for r in self.rules]
        if len(set(ids)) != len(ids):
            raise ValueError("legal rule ids must be unique")
        known = {"ES", *self.areas.districts, *self.areas.regions}
        for rule in self.rules:
            if rule.area not in known:
                raise ValueError(f"rule {rule.id}: no area {rule.area!r}")
            if rule.where is not None:
                outside = set(rule.where.districts) - set(self.areas.districts)
                if outside:
                    raise ValueError(f"rule {rule.id}: unknown districts {sorted(outside)}")
            if isinstance(rule, WellDistanceRule):
                missing = set(rule.supersedes) - set(ids)
                if missing:
                    raise ValueError(f"rule {rule.id}: supersedes unknown {sorted(missing)}")
        return self

    def layer_matches(self) -> list[tuple[str, LayerMatch]]:
        """Every (rule id, layer match) the rules read, for the map-layer check."""
        found: list[tuple[str, LayerMatch]] = []
        for rule in self.rules:
            if isinstance(rule, BodyAuthorisationRule):
                found.extend((rule.id, m) for m in rule.marked)
            elif isinstance(rule, ZoneRule):
                found.append((rule.id, rule.match))
            elif isinstance(rule, WaterDomainRule):
                found.append((rule.id, rule.zones))
        return found
