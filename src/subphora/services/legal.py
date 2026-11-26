# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The legal status of a place or of an area's candidates (MASTER_PLAN §4.5, hard rule 2).

What the rules read at a place comes from the official map layers' feature info, through
the same catalogue, cache and field filter as a tap: the groundwater body and its
quantitative status, whether it is declared at risk, the public water domain, and every
official zone a rule names. A layer that cannot be read is passed on as unknown, so the
rule that needed it becomes a condition to check; it never fails the request or the job.
At a candidate the distances to the nearest water point and channel come from its map.
"""

import asyncio
import logging
from collections.abc import Mapping, Sequence

from subphora.config import Settings
from subphora.config.legal import LegalSettings
from subphora.domain.layers import LayerError
from subphora.domain.legal import BodyStatus, LegalStatus
from subphora.domain.parcel_map import AreaAnalysis, Candidate, Site
from subphora.legal import Distance, LayerAnswer, PlaceFacts, assess, district_of, layers_read
from subphora.services.layers import LayerService
from subphora.store.file_cache import Clock, utc_now

_log = logging.getLogger(__name__)

# How each distance was measured, as the interface names it.
INVENTORY = "inventory"
TERRAIN = "terrain"


class LegalService:
    def __init__(self, layers: LayerService, settings: Settings, clock: Clock = utc_now) -> None:
        self._layers = layers
        self._legal: LegalSettings = settings.legal
        self._clock = clock

    async def _answer(self, layer_id: str, lon: float, lat: float) -> LayerAnswer:
        try:
            features, covers = await self._layers.features_at(
                layer_id, lon, lat, self._legal.tap_zoom
            )
        except LayerError as exc:
            _log.warning("legal: %s at %.5f, %.5f: %s", layer_id, lon, lat, exc.detail)
            return LayerAnswer(features=None)
        return LayerAnswer(features=features, covers=covers)

    async def facts(
        self,
        lon: float,
        lat: float,
        region: str | None,
        water_point: Distance | None = None,
        channel: Distance | None = None,
    ) -> PlaceFacts:
        """What the rules read at the point: the body and its status first, then every
        layer the rules of its district and region name."""
        bodies = self._legal.bodies
        status, at_risk = await asyncio.gather(
            self._answer(bodies.status_layer, lon, lat),
            self._answer(bodies.at_risk_layer, lon, lat),
        )
        body = None if status.features is None else _body(self._legal, status.features, at_risk)
        ids = layers_read(self._legal, district_of(self._legal, body), region)
        answers = dict(
            zip(ids, await asyncio.gather(*(self._answer(i, lon, lat) for i in ids)), strict=True)
        )
        answers |= {bodies.status_layer: status, bodies.at_risk_layer: at_risk}
        planned = self._legal.planned
        return PlaceFacts(
            region=region,
            bodies_read=status.features is not None,
            body=body,
            layers=answers,
            water_point=water_point,
            channel=channel,
            volume_m3_year=planned.volume_m3_year,
            max_flow_l_s=planned.max_flow_l_s,
        )

    async def place(self, lon: float, lat: float, region: str | None) -> LegalStatus:
        """An area's legal panel: the rules at a point, without distances (those are
        measured per candidate on the detailed map)."""
        return assess(self._legal, await self.facts(lon, lat, region), self._clock())

    async def candidates(self, analysis: AreaAnalysis, region: str | None) -> AreaAnalysis:
        """The analysis with every candidate's legal status assessed."""
        assessed = await asyncio.gather(*(self._candidate(c, region) for c in analysis.candidates))
        return analysis.model_copy(update={"candidates": tuple(assessed)})

    async def _candidate(self, candidate: Candidate, region: str | None) -> Candidate:
        water_point, channel = site_distances(candidate.site)
        facts = await self.facts(
            candidate.longitude, candidate.latitude, region, water_point, channel
        )
        legal = assess(self._legal, facts, self._clock())
        return candidate.model_copy(update={"legal": legal})


def site_distances(site: Site) -> tuple[Distance, Distance | None]:
    """A candidate's measured distances, for the engine."""
    point = Distance(
        metres=site.water_point.metres, reach_m=site.water_point.reach_m, method=INVENTORY
    )
    channel = (
        None
        if site.channel is None
        else Distance(metres=site.channel.metres, reach_m=site.channel.reach_m, method=TERRAIN)
    )
    return point, channel


def _body(
    legal: LegalSettings, features: Sequence[Mapping[str, str]], at_risk: LayerAnswer
) -> BodyStatus | None:
    """The body at the point: where horizons overlap, the one in the worst quantitative
    status. Declared at risk when the at-risk layer has that body there (unknown when the
    layer could not be read)."""
    settings = legal.bodies
    bodies = [f for f in features if f.get(settings.code_field) and f.get(settings.name_field)]
    if not bodies:
        return None
    worst = next(
        (f for f in bodies if f.get(settings.quantitative_field) in settings.poor_values), bodies[0]
    )
    code = worst[settings.code_field]
    declared: bool | None = None
    declaration = None
    if at_risk.features is not None:
        same = [f for f in at_risk.features if f.get(settings.at_risk_code_field) == code]
        declared = bool(same)
        if same:
            declaration = same[0].get(settings.declaration_field) or None
    return BodyStatus(
        code=code,
        name=worst[settings.name_field],
        quantitative_status=worst.get(settings.quantitative_field) or None,
        declared_at_risk=declared,
        declaration=declaration,
    )


__all__ = ["INVENTORY", "TERRAIN", "LegalService", "site_distances"]
