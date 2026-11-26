# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The legal filter's engine: the rules of ``config/legal/<country>/`` evaluated at one
place (MASTER_PLAN §4.5).

It receives what is known at the place (its region, its groundwater body and that body's
legal status, the official zones under it, the distances to the nearest water point and
channel) and never fetches anything. What could not be read is ``None`` and makes the rule
that needed it a condition to check, never a pass. A rule applies where its area key does:
ES everywhere, a region (ES-AN) inside it, a district (ES050) inside it.
"""

import itertools
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from subphora.config.legal import (
    AuthorisationRule,
    BodyAuthorisationRule,
    ConcessionRule,
    DistanceCase,
    LayerMatch,
    LegalSettings,
    NoNewConcessionsRule,
    NoticeRule,
    Rule,
    Translated,
    WaterDomainRule,
    WellDistanceRule,
    ZoneRule,
)
from subphora.domain.legal import (
    Authority,
    BodyStatus,
    Finding,
    LegalStatus,
    NotLoaded,
    NotLoadedScope,
    Outcome,
    RuleSource,
    verdict,
)

type Fields = Mapping[str, str]

_CLASSES = ("good", "poor", "outside")


@dataclass(frozen=True, slots=True)
class LayerAnswer:
    """A map layer asked at the place: the fields of each feature there, or ``None`` when
    the layer could not be read. ``covers`` is False where the layer's area does not
    reach the place (a regional layer elsewhere): it has nothing to say there."""

    features: tuple[Fields, ...] | None
    covers: bool = True


@dataclass(frozen=True, slots=True)
class Distance:
    """A distance measured around the place: ``metres`` to the nearest feature, or None
    when none lies within ``reach_m`` (as far as the search looked)."""

    metres: float | None
    reach_m: float
    # How it was measured, for the interface ("inventory", "terrain").
    method: str


@dataclass(frozen=True, slots=True)
class PlaceFacts:
    """Everything the rules read at one place. ``None``: not known there."""

    region: str | None
    # False when the bodies layer could not be read; then ``body`` is None too.
    bodies_read: bool
    body: BodyStatus | None
    layers: Mapping[str, LayerAnswer] = field(default_factory=dict)
    water_point: Distance | None = None
    channel: Distance | None = None
    volume_m3_year: float = 0.0
    max_flow_l_s: float | None = None


def _tr(text: Translated) -> dict[str, str]:
    return {"en": text.en, "es": text.es}


def district_of(settings: LegalSettings, body: BodyStatus | None) -> str | None:
    """The district a body's code names, or None."""
    if body is None:
        return None
    found = re.match(settings.bodies.district_pattern, body.code)
    return found.group(1) if found else None


def body_class(settings: LegalSettings, facts: PlaceFacts) -> str | None:
    """good, poor or outside (no body); None when the status is not known."""
    if not facts.bodies_read:
        return None
    if facts.body is None:
        return "outside"
    status = facts.body.quantitative_status
    if status in settings.bodies.poor_values:
        return "poor"
    if status in settings.bodies.good_values:
        return "good"
    return None


def _applies(rule: Rule, district: str | None, region: str | None, body: str | None) -> bool:
    if rule.area == "ES":
        area_ok = True
    elif rule.area.startswith("ES-"):
        area_ok = rule.area == region
    else:
        area_ok = rule.area == district
    if not area_ok:
        return False
    where = rule.where
    if where is None:
        return True
    if where.districts is not None and (district is None or district not in where.districts):
        return False
    return where.bodies is None or (body is not None and where.has_body(body))


def _body_code(facts: PlaceFacts) -> str | None:
    return None if facts.body is None else facts.body.code


class _Evaluator:
    def __init__(self, settings: LegalSettings, facts: PlaceFacts) -> None:
        self.settings = settings
        self.facts = facts
        self.cls = body_class(settings, facts)

    def finding(self, rule: Rule, outcome: Outcome, message: str, **values: str | float) -> Finding:
        source = rule.source
        return Finding(
            rule_id=rule.id,
            area=rule.area,
            title=_tr(rule.title),
            source=RuleSource(
                name=source.name,
                url=source.url,
                article=source.article,
                published=source.published,
                checked=source.checked,
            ),
            outcome=outcome,
            message=message,
            values=values,
            uncertain=None if rule.uncertain is None else _tr(rule.uncertain),
        )

    def evaluate(self, rule: Rule) -> Finding:
        volume = self.facts.volume_m3_year
        if rule.applies_above_m3 is not None and volume <= rule.applies_above_m3:
            return self.finding(
                rule, Outcome.NOT_APPLICABLE, "only_concessions", limit=rule.applies_above_m3
            )
        if rule.applies_up_to_m3 is not None and volume > rule.applies_up_to_m3:
            return self.finding(
                rule, Outcome.NOT_APPLICABLE, "above_small_use", limit=rule.applies_up_to_m3
            )
        match rule:
            case NoticeRule():
                return self.notice(rule)
            case ConcessionRule():
                return self.concession(rule)
            case AuthorisationRule():
                return self.finding(rule, Outcome.AUTHORISATION, "authorisation_needed")
            case BodyAuthorisationRule():
                return self.body_authorisation(rule)
            case NoNewConcessionsRule():
                return self.no_new_concessions(rule)
            case WellDistanceRule():
                return self.well_distance(rule)
            case ZoneRule():
                return self.zone(rule)
            case WaterDomainRule():
                return self.water_domain(rule)

    def notice(self, rule: NoticeRule) -> Finding:
        if self.facts.volume_m3_year > rule.max_volume_m3:
            return self.finding(
                rule, Outcome.NOT_APPLICABLE, "above_small_use", limit=rule.max_volume_m3
            )
        return self.finding(rule, Outcome.NOTICE, "notify_authority", limit=rule.max_volume_m3)

    def concession(self, rule: ConcessionRule) -> Finding:
        volume = self.facts.volume_m3_year
        if volume > rule.max_volume_m3:
            return self.finding(
                rule, Outcome.AUTHORISATION, "concession_needed", volume=volume,
                limit=rule.max_volume_m3,
            )  # fmt: skip
        return self.finding(
            rule, Outcome.NOT_APPLICABLE, "within_small_use", volume=volume,
            limit=rule.max_volume_m3,
        )  # fmt: skip

    def _marked(self, match: LayerMatch) -> bool | None:
        """Whether a feature of the layer at the place matches; None: not known."""
        answer = self.facts.layers.get(match.layer)
        if answer is None or answer.features is None:
            return None
        if not answer.covers:
            return False
        return any(match.matches(f.get(match.field, "")) for f in answer.features)

    def body_authorisation(self, rule: BodyAuthorisationRule) -> Finding:
        if rule.max_volume_m3 is not None and self.facts.volume_m3_year > rule.max_volume_m3:
            return self.finding(
                rule, Outcome.NOT_APPLICABLE, "above_small_use", limit=rule.max_volume_m3
            )
        if not self.facts.bodies_read:
            return self.finding(rule, Outcome.CHECK, "body_unknown")
        body = self.facts.body
        if body is None:
            return self.finding(rule, Outcome.CLEAR, "outside_bodies")
        triggers: list[tuple[str, bool | None]] = []
        if rule.declared_at_risk:
            triggers.append(("declared_at_risk", body.declared_at_risk))
        if rule.poor_quantitative:
            triggers.append(("poor_quantitative", None if self.cls is None else self.cls == "poor"))
        triggers.extend((f"marked:{m.layer}", self._marked(m)) for m in rule.marked)
        hit = [name for name, value in triggers if value]
        if hit:
            return self.finding(
                rule, Outcome.AUTHORISATION, "authorisation_body", body=body.name,
                because=hit[0],
            )  # fmt: skip
        if any(value is None for _, value in triggers):
            return self.finding(rule, Outcome.CHECK, "status_unknown", body=body.name)
        return self.finding(rule, Outcome.CLEAR, "body_not_marked", body=body.name)

    def no_new_concessions(self, rule: NoNewConcessionsRule) -> Finding:
        if rule.when == "always":
            return self.finding(rule, Outcome.BLOCKS, "no_new_concessions_here")
        if self.cls is None:
            return self.finding(rule, Outcome.CHECK, "status_unknown", body=self._body_name())
        if self.cls == "poor":
            return self.finding(rule, Outcome.BLOCKS, "no_new_concessions", body=self._body_name())
        return self.finding(rule, Outcome.CLEAR, "body_not_poor", body=self._body_name())

    def _body_name(self) -> str:
        return "" if self.facts.body is None else self.facts.body.name

    def _case_fits(self, case: DistanceCase, cls: str) -> bool:
        if "any" not in case.bodies and cls not in case.bodies:
            return False
        volume = self.facts.volume_m3_year
        if case.max_volume_m3 is not None and volume > case.max_volume_m3:
            return False
        if case.volume_below_m3 is not None and volume >= case.volume_below_m3:
            return False
        flow = self.facts.max_flow_l_s
        if case.flow_below_l_s is not None and (flow is None or flow >= case.flow_below_l_s):
            return False
        return case.flow_up_to_l_s is None or (flow is not None and flow <= case.flow_up_to_l_s)

    def _case_distance(self, case: DistanceCase) -> float | None:
        if case.distance_m is not None:
            return case.distance_m
        if case.curve is None:
            return None
        volume = self.facts.volume_m3_year
        points = case.curve
        if volume <= points[0][0]:
            return points[0][1]
        for (v0, d0), (v1, d1) in itertools.pairwise(points):
            if volume <= v1:
                return d0 + (d1 - d0) * (volume - v0) / (v1 - v0)
        return points[-1][1]

    def _first_fit(self, rule: WellDistanceRule, cls: str) -> DistanceCase | None:
        return next((case for case in rule.cases if self._case_fits(case, cls)), None)

    def min_distance(self, rule: WellDistanceRule) -> tuple[float | None, bool]:
        """The rule's distance here and whether the body's class was known. With it
        unknown, the strictest of the distances each class would get; None when the text
        leaves it to the authorisation (or no case fits)."""
        if self.cls is not None:
            case = self._first_fit(rule, self.cls)
            return (None if case is None else self._case_distance(case)), True
        fits = [self._first_fit(rule, cls) for cls in _CLASSES]
        known = [d for c in fits if c is not None and (d := self._case_distance(c)) is not None]
        return (max(known) if known else None), False

    def well_distance(self, rule: WellDistanceRule) -> Finding:
        minimum, known = self.min_distance(rule)
        if minimum is None:
            return self.finding(rule, Outcome.CHECK, "distance_by_authorisation")
        point = self.facts.water_point
        values: dict[str, str | float] = {"minimum": round(minimum, 1)}
        if not known:
            values["assumed"] = "strictest"
        if point is None:
            return self.finding(rule, Outcome.CHECK, "distance_not_measured", **values)
        values["method"] = point.method
        if point.metres is None:
            if point.reach_m < minimum:
                return self.finding(
                    rule, Outcome.CHECK, "distance_not_measured", reach=point.reach_m, **values
                )
            return self.finding(
                rule, Outcome.CLEAR, "no_point_within", reach=point.reach_m, **values
            )
        values["distance"] = round(point.metres, 1)
        if point.metres < minimum:
            return self.finding(rule, Outcome.BLOCKS, "too_close_to_point", **values)
        return self.finding(rule, Outcome.CLEAR, "point_far_enough", **values)

    def zone(self, rule: ZoneRule) -> Finding:
        answer = self.facts.layers.get(rule.match.layer)
        if answer is None or answer.features is None:
            return self.finding(rule, Outcome.CHECK, "zone_unknown")
        if not answer.covers:
            return self.finding(rule, Outcome.NOT_APPLICABLE, "zone_not_here")
        matched = [f for f in answer.features if rule.match.matches(f.get(rule.match.field, ""))]
        if matched:
            name = matched[0].get(rule.label_field, "")
            return self.finding(rule, Outcome(rule.outcome), "inside_zone", zone=name)
        if answer.features:
            feature = answer.features[0]
            return self.finding(
                rule, Outcome.CHECK, "zone_other", zone=feature.get(rule.label_field, ""),
                value=feature.get(rule.match.field, ""),
            )  # fmt: skip
        return self.finding(rule, Outcome.CLEAR, "outside_zone")

    def water_domain(self, rule: WaterDomainRule) -> Finding:
        answer = self.facts.layers.get(rule.zones.layer)
        official = None if answer is None else answer.features
        if official:
            for feature in official:
                zone = feature.get(rule.zones.field, "")
                if rule.zones.matches(zone):
                    return self.finding(
                        rule, Outcome.AUTHORISATION, "inside_water_domain", zone=zone
                    )
        channel = self.facts.channel
        if channel is None:
            return self.finding(rule, Outcome.CHECK, "channel_not_measured")
        values: dict[str, str | float] = {"limit": rule.distance_m, "method": channel.method}
        if official is None:
            values["official"] = "unread"
        if channel.metres is None:
            if channel.reach_m < rule.distance_m:
                return self.finding(rule, Outcome.CHECK, "channel_not_measured", **values)
            return self.finding(
                rule, Outcome.CLEAR, "no_channel_within", reach=channel.reach_m, **values
            )
        values["distance"] = round(channel.metres, 1)
        if channel.metres < rule.distance_m:
            return self.finding(rule, Outcome.AUTHORISATION, "near_channel", **values)
        return self.finding(rule, Outcome.CLEAR, "far_from_channel", **values)


def layers_read(
    settings: LegalSettings, district: str | None, region: str | None, body: str | None = None
) -> list[str]:
    """The map layers the rules that apply in this district, region and body read."""
    applying = {r.id for r in settings.rules if _applies(r, district, region, body)}
    return list(dict.fromkeys(m.layer for rule, m in settings.layer_matches() if rule in applying))


def _authority(settings: LegalSettings, district: str) -> Authority | None:
    entry = settings.areas.districts.get(district)
    if entry is None:
        return None
    return Authority(
        district=district,
        district_name=entry.name,
        name=entry.authority,
        level=entry.level,
        note=None if entry.note is None else _tr(entry.note),
    )


def _not_loaded(
    settings: LegalSettings, facts: PlaceFacts, district: str | None
) -> list[NotLoaded]:
    texts = settings.texts
    missing: list[NotLoaded] = []
    if district is None:
        reason = texts.no_body if facts.bodies_read else texts.bodies_unread
        missing.append(NotLoaded(scope=NotLoadedScope.DISTRICT, area=None, reason=_tr(reason)))
    else:
        entry = settings.areas.districts.get(district)
        if entry is None:
            missing.append(
                NotLoaded(
                    scope=NotLoadedScope.DISTRICT,
                    area=district,
                    reason=_tr(texts.unknown_district),
                )
            )
        elif entry.plan.reason is not None:
            missing.append(
                NotLoaded(
                    scope=NotLoadedScope.BASIN_PLAN, area=district, reason=_tr(entry.plan.reason)
                )
            )
    region = None if facts.region is None else settings.areas.regions.get(facts.region)
    if region is None:
        missing.append(
            NotLoaded(
                scope=NotLoadedScope.REGIONAL_LAW,
                area=facts.region,
                reason=_tr(texts.unknown_region),
            )
        )
    elif region.water_law.reason is not None:
        missing.append(
            NotLoaded(
                scope=NotLoadedScope.REGIONAL_LAW,
                area=facts.region,
                reason=_tr(region.water_law.reason),
            )
        )
    return missing


def assess(settings: LegalSettings, facts: PlaceFacts, at: datetime) -> LegalStatus:
    """The legal status of one place: every rule that applies there, evaluated, and the
    state its findings support."""
    district = district_of(settings, facts.body)
    region = facts.region
    applicable = [r for r in settings.rules if _applies(r, district, region, _body_code(facts))]
    superseded: dict[str, str] = {}
    for rule in applicable:
        if isinstance(rule, WellDistanceRule):
            for other in rule.supersedes:
                superseded.setdefault(other, rule.id)
    evaluator = _Evaluator(settings, facts)
    findings = []
    for rule in applicable:
        if rule.id in superseded:
            findings.append(
                evaluator.finding(
                    rule, Outcome.NOT_APPLICABLE, "superseded", by=superseded[rule.id]
                )
            )
        else:
            findings.append(evaluator.evaluate(rule))
    not_loaded = _not_loaded(settings, facts, district)
    state, reason = verdict(findings, not_loaded)
    texts = settings.texts
    return LegalStatus(
        state=state,
        source=texts.source,
        assessed_at=at,
        disclaimer=texts.disclaimer,
        reason=reason,
        region=region,
        authority=None if district is None else _authority(settings, district),
        body=facts.body,
        findings=tuple(findings),
        not_loaded=tuple(not_loaded),
        permits=tuple(_tr(p) for p in texts.permits),
    )
