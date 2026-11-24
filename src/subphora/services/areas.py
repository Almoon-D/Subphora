# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The official boundaries regional layers are drawn and asked inside (decision 0023).

An area's boundary is read once from its national WFS (the IGN's administrative units or
MITECO's river-basin districts), rounded to the configured grid and kept in the file cache
for the service's cache lifetime; the server keeps the rounded boundaries it has read in
memory. A point outside an area's configured bbox never reads the boundary.
"""

import asyncio
import json

from subphora.config import Settings
from subphora.config.regional import Area, RegionalSettings
from subphora.domain.areas import AreaBoundary, AreaKind
from subphora.domain.layers import LayerError, LayerFailure
from subphora.domain.parcels import MultiPolygon
from subphora.domain.provenance import Provenance
from subphora.geo.areas import BoundaryError, bounds, contains, in_box, round_to_grid, within
from subphora.geo.areas import MultiPolygon as Rings
from subphora.services.fetching import CachedFetcher, UpstreamFailure
from subphora.sources import CatalogueClient
from subphora.sources.boundaries import BoundaryParseError, boundary_params, parse_boundary
from subphora.store import FileCache
from subphora.store.file_cache import Clock, utc_now


class AreaService:
    def __init__(
        self,
        client: CatalogueClient,
        settings: Settings,
        cache: FileCache,
        clock: Clock = utc_now,
    ) -> None:
        self._fetcher = CachedFetcher(client, cache, clock)
        self._regional: RegionalSettings = settings.regional
        self._settings = settings
        self._read: dict[str, tuple[AreaBoundary, Rings]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _area(self, area_id: str) -> Area:
        try:
            return self._regional.area(area_id)
        except KeyError:
            raise LayerError(LayerFailure.UNKNOWN_AREA, f"no area {area_id!r}") from None

    async def boundary(self, area_id: str) -> AreaBoundary:
        """The area's rounded boundary; raises LayerError."""
        return (await self._load(area_id))[0]

    async def holds(self, area_id: str, lon: float, lat: float) -> bool:
        """Whether the point lies in the area; raises LayerError if its boundary cannot be
        read (only for points inside the area's bbox)."""
        if not in_box(self._area(area_id).bbox, lon, lat):
            return False
        return contains((await self._load(area_id))[1], lon, lat)

    async def _load(self, area_id: str) -> tuple[AreaBoundary, Rings]:
        area = self._area(area_id)
        lock = self._locks.setdefault(area_id, asyncio.Lock())
        async with lock:
            if area_id not in self._read:
                self._read[area_id] = await self._fetch(area)
            return self._read[area_id]

    async def _fetch(self, area: Area) -> tuple[AreaBoundary, Rings]:
        grid = self._regional.boundaries.grid_deg
        source = self._regional.boundaries.sources[area.kind]
        service = self._settings.sources.service(source.service)
        key = f"boundary {source.type_name} {area.code} grid={grid}"
        kept = await self._fetcher.recall(service, key)
        if kept is not None:
            try:
                rings = _rings(json.loads(kept.content))
            except ValueError, TypeError:
                pass  # unreadable: read the boundary again, and the new one replaces it
            else:
                return self._boundary(area, rings, kept.provenance, grid), rings
        params = boundary_params(
            source.type_name,
            source.code_property,
            area.code,
            source.namespaces,
            source.output_format,
        )
        try:
            fetched = await self._fetcher.fetch(service, service.base_url, params)
        except UpstreamFailure as exc:
            failure = LayerFailure.UPSTREAM_TIMEOUT if exc.timeout else LayerFailure.UPSTREAM_ERROR
            raise LayerError(failure, exc.detail) from exc
        try:
            rings = tuple(
                polygon
                for geometry in parse_boundary(fetched.content)
                for polygon in round_to_grid(geometry, grid)
            )
        except (BoundaryParseError, BoundaryError) as exc:
            raise LayerError(
                LayerFailure.UPSTREAM_ERROR, f"{service.publisher}, area {area.id}: {exc}"
            ) from exc
        boundary = self._boundary(area, rings, fetched.provenance, grid)
        await self._fetcher.remember(service, key, json.dumps(rings).encode(), fetched.provenance)
        return boundary, rings

    @staticmethod
    def _boundary(area: Area, rings: Rings, source: Provenance, grid: float) -> AreaBoundary:
        box = bounds(rings)
        if not within(box, area.bbox):
            raise LayerError(
                LayerFailure.UPSTREAM_ERROR,
                f"the boundary of {area.id} {box} reaches outside its configured bbox",
            )
        return AreaBoundary.model_validate(
            {
                "id": area.id,
                "kind": AreaKind(area.kind),
                "bbox": box,
                "geometry": MultiPolygon(
                    coordinates=tuple(
                        tuple((*ring, ring[0]) for ring in polygon) for polygon in rings
                    )
                ),
                "source": source,
                "grid_deg": grid,
            }
        )


def _rings(data: object) -> Rings:
    if not isinstance(data, list) or not data:
        raise ValueError("a kept boundary is a non-empty list of polygons")
    return tuple(
        tuple(tuple((float(x), float(y)) for x, y in ring) for ring in polygon) for polygon in data
    )
