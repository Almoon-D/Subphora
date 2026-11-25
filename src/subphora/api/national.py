# Copyright (c) 2026 Almoon-D. All rights reserved.
"""``GET /api/national``: the national water-potential map the front end draws: its layers
with their legends, the regions built and the sources to credit. Before the first build it
says so (``built`` is false) and still lists the layers, so the panel can tell the owner
how to build them."""

from datetime import datetime
from typing import Literal

from subphora.config import Settings
from subphora.config.national import TileLayer
from subphora.domain import DomainModel
from subphora.domain.potential import Variable
from subphora.store.national import MapManifest

# The API's tile route, with MapLibre's placeholders.
NATIONAL_TILES = "/api/national/tiles/{layer_id}/{{z}}/{{x}}/{{y}}"


class LegendClass(DomainModel):
    # The class holds values from ``min`` (inclusive) to ``max``; None is unbounded.
    min: float | None
    max: float | None
    colour: str


class NationalLayer(DomainModel):
    id: str
    variable: Variable
    tiles: tuple[str, ...]
    min_zoom: int
    max_zoom: int
    tile_size: int
    opacity: float
    visible: bool
    unit: str
    legend: tuple[LegendClass, ...]


class NationalRegion(DomainModel):
    id: str
    name: str
    bbox: tuple[float, float, float, float]
    built_at: datetime


class NationalMap(DomainModel):
    # The score is a relative potential index until session 07 calibrates it.
    kind: Literal["index"] = "index"
    built: bool
    rendered_at: datetime | None
    bounds: tuple[float, float, float, float] | None
    regions: tuple[NationalRegion, ...]
    layers: tuple[NationalLayer, ...]
    attributions: tuple[str, ...]


def _legend(layer: TileLayer) -> tuple[LegendClass, ...]:
    edges: list[float | None] = [None, *layer.breaks, None]
    return tuple(
        LegendClass(min=edges[i], max=edges[i + 1], colour=colour)
        for i, colour in enumerate(layer.colours)
    )


def national_map(settings: Settings, published: MapManifest | None) -> NationalMap:
    tiles = settings.national.tiles
    services = [d.service for d in settings.national.datasets.all().values()]
    attributions = dict.fromkeys(settings.sources.service(s).attribution for s in services)
    return NationalMap(
        built=published is not None,
        rendered_at=None if published is None else published.rendered_at,
        bounds=None if published is None else published.bounds,
        regions=()
        if published is None
        else tuple(
            NationalRegion(id=r.region_id, name=r.name, bbox=r.bbox, built_at=r.built_at)
            for r in published.regions
        ),
        layers=tuple(
            NationalLayer(
                id=layer.id,
                variable=layer.variable,
                tiles=(NATIONAL_TILES.format(layer_id=layer.id),),
                min_zoom=tiles.min_zoom,
                max_zoom=tiles.max_zoom,
                tile_size=tiles.tile_size,
                opacity=layer.opacity,
                visible=layer.visible,
                unit=layer.unit,
                legend=_legend(layer),
            )
            for layer in tiles.layers
        ),
        attributions=tuple(attributions),
    )
