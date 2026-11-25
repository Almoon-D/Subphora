# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Search and drawing: from what the person typed or drew to one AreaOfInterest.

1. ``search`` reads the text (``countries.es.search``) and answers every valid reading as
   an Interpretation with the API path that resolves it. Coordinates are converted here and
   kept only where they fall in one of Spain's territories (``config/defaults/search.yaml``);
   a name asks CartoCiudad for candidates of the configured types.
2. Each ``resolve`` path returns the area: a cadastral parcel (Catastro), a SIGPAC enclosure
   or parcel, a CartoCiudad place, a point, or a drawn polygon.
3. A typed or drawn place is on land when SIGPAC has an enclosure under it, which also
   names the province; in a territory SIGPAC does not cover, its box alone decides, and the
   area says so (``land_checked``).

Every answer is cached for its service's lifetime once it parses; a "not found" is asked
again next time. Queries are never logged: they may be the owner's address or parcel.
"""

from collections.abc import Collection, Sequence
from urllib.parse import urlencode

from subphora.config import Settings
from subphora.config.search import Territory
from subphora.config.sources import Service
from subphora.countries.es import Province, local_crs, province_by_code
from subphora.countries.es.coordinates import LON_LAT, CoordinateReading
from subphora.countries.es.crs import latitude_band, utm_crs
from subphora.countries.es.search import Cadastral, Coordinates, Name, Sigpac, recognise
from subphora.countries.es.sigpac import SigpacReference, parse_sigpac
from subphora.domain.aoi import (
    POINT_ORIGINS,
    AoiOrigin,
    AreaOfInterest,
    Interpretation,
    PointGeometry,
    SearchAnswer,
    SearchError,
    SearchFailure,
    SearchKind,
)
from subphora.domain.parcels import (
    LocalPoint,
    LookupFailure,
    MultiPolygon,
    ParcelLookupError,
    Polygon,
    Position,
)
from subphora.domain.provenance import Provenance
from subphora.geo import (
    ReprojectionError,
    ShapeError,
    bbox_of,
    check_simple_ring,
    geodesic_area_m2,
    point_inside,
    to_lon_lat,
    transform_point,
)
from subphora.services.fetching import CachedFetcher, Fetched, UpstreamFailure
from subphora.services.parcels import ParcelService
from subphora.sources import CatalogueClient
from subphora.sources.cartociudad import (
    CANDIDATES_PATH,
    FIND_PATH,
    NO_CONTENT,
    candidates_params,
    find_params,
    parse_candidates,
    parse_find,
)
from subphora.sources.sigpac import (
    SIGPAC_CRS,
    parse_enclosures,
    parse_point,
    point_path,
    reference_path,
)
from subphora.store import FileCache
from subphora.store.file_cache import Clock, utc_now

CATASTRO_SOURCE = "catastro-wfs-parcels"
_PARCEL_FAILURES = {
    LookupFailure.MALFORMED: SearchFailure.MALFORMED_REFERENCE,
    LookupFailure.NOT_SUPPORTED: SearchFailure.TERRITORY_NOT_SUPPORTED,
    LookupFailure.NOT_FOUND: SearchFailure.NOT_FOUND,
    LookupFailure.UPSTREAM_TIMEOUT: SearchFailure.UPSTREAM_TIMEOUT,
    LookupFailure.UPSTREAM_ERROR: SearchFailure.UPSTREAM_ERROR,
}
_POINT_SEARCHES = frozenset({AoiOrigin.COORDINATES, AoiOrigin.DRAWN_POINT})
# Degrees in a label: six decimals, about 0.1 m.
_DEGREE_DECIMALS = 6


def _number(value: float) -> str:
    """A coordinate as typed, without trailing zeros: 440000, 4474000.5."""
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _degrees_label(lon: float, lat: float) -> str:
    return f"{lat:.{_DEGREE_DECIMALS}f}, {lon:.{_DEGREE_DECIMALS}f}"


class AoiService:
    def __init__(
        self,
        client: CatalogueClient,
        settings: Settings,
        cache: FileCache,
        parcels: ParcelService,
        clock: Clock = utc_now,
    ) -> None:
        self._fetcher = CachedFetcher(client, cache, clock)
        self._search = settings.search
        self._parcels = parcels
        self._sigpac = settings.sources.service(settings.search.sigpac.service)
        self._carto = settings.sources.service(settings.search.cartociudad.service)
        self._territories = settings.search.territories
        self._zones = tuple(sorted({z for t in self._territories for z in t.utm_zones}))
        # A territory's zone must have a CRS, and its fixed province must exist.
        self._crs_by_zone = {zone: utm_crs(zone) for zone in self._zones}
        for territory in self._territories:
            if territory.province is not None and province_by_code(territory.province) is None:
                raise ValueError(f"territory {territory.id}: no province {territory.province}")

    # ── search ───────────────────────────────────────────────────────────────────────────

    async def search(self, text: str) -> SearchAnswer:
        """Every reading of the text; raises SearchError when none gives a place."""
        found: list[Interpretation] = []
        errors: list[SearchError] = []
        for reading in recognise(text, self._zones):
            try:
                match reading:
                    case Cadastral(reference):
                        found.append(
                            Interpretation(
                                kind=SearchKind.CADASTRAL,
                                origin=AoiOrigin.CADASTRAL,
                                label=reference.parcel,
                                detail=None,
                                position=None,
                                resolve=f"/api/aoi/cadastral/{reference.parcel}",
                            )
                        )
                    case Sigpac(reference):
                        found.append(_sigpac_interpretation(reference))
                    case Coordinates(readings):
                        found.extend(await self._coordinate_interpretations(readings))
                    case Name(name):
                        found.extend(await self._candidates(name))
            except SearchError as exc:
                errors.append(exc)
        if not found:
            raise errors[0]
        return SearchAnswer(interpretations=tuple(found))

    async def _coordinate_interpretations(
        self, readings: Sequence[CoordinateReading]
    ) -> list[Interpretation]:
        placed: list[tuple[CoordinateReading, str, float, float, Territory]] = []
        errors: list[SearchError] = []
        for reading in readings:
            try:
                placed.append((reading, *self._place_reading(reading)))
            except SearchError as exc:
                errors.append(exc)
        if len(placed) > 1:
            # Several readings fit Spain's boxes: offer only those on land.
            on_land = [entry for entry in placed if await self._maybe_on_land(*entry[2:])]
            if not on_land:
                raise _outside("no reading of the coordinates falls on land in Spain")
            placed = on_land
        if not placed:
            # A stated zone that is wrong says so; otherwise the place is not in Spain.
            wrong_zone = [e for e in errors if e.failure == SearchFailure.WRONG_UTM_ZONE]
            raise wrong_zone[0] if wrong_zone else errors[0]
        return [
            Interpretation(
                kind=SearchKind.COORDINATES,
                origin=AoiOrigin.COORDINATES,
                label=_reading_label(reading),
                detail=crs,
                position=(lon, lat),
                resolve="/api/aoi/point?"
                + urlencode(
                    {
                        "crs": crs,
                        "x": repr(reading.x),
                        "y": repr(reading.y),
                        "origin": AoiOrigin.COORDINATES.value,
                    }
                ),
            )
            for reading, crs, lon, lat, _territory in placed
        ]

    async def _maybe_on_land(self, lon: float, lat: float, territory: Territory) -> bool:
        """False only when SIGPAC says there is no land at the point; a territory without
        the land check, or a SIGPAC that cannot answer, keeps the reading."""
        try:
            await self._land(territory, lon, lat)
        except SearchError as exc:
            return exc.failure != SearchFailure.OUTSIDE_COUNTRY
        return True

    def _place_reading(self, reading: CoordinateReading) -> tuple[str, float, float, Territory]:
        """The reading's CRS, its point in Spain and the territory; raises SearchError."""
        if reading.zone is None:
            crs, (lon, lat) = LON_LAT, (reading.x, reading.y)
        else:
            crs = self._crs_by_zone[reading.zone]
            lon, lat = self._to_lon_lat(reading.x, reading.y, crs)
        territory = self._territory(lon, lat)
        if reading.zone is None:
            if territory is None:
                raise _outside(f"{_degrees_label(lon, lat)} is outside Spain")
            return crs, lon, lat, territory
        if territory is None or reading.zone not in territory.utm_zones:
            raise self._zone_error(reading)
        if reading.band not in (None, "N") and latitude_band(lat) != reading.band:
            raise SearchError(
                SearchFailure.WRONG_UTM_ZONE,
                f"band {reading.band} does not hold the point, which is in band "
                f"{latitude_band(lat)}",
            )
        return crs, lon, lat, territory

    def _zone_error(self, reading: CoordinateReading) -> SearchError:
        others = []
        for zone in self._zones:
            if zone == reading.zone:
                continue
            lon, lat = self._to_lon_lat(reading.x, reading.y, self._crs_by_zone[zone])
            territory = self._territory(lon, lat)
            if territory is not None and zone in territory.utm_zones:
                others.append(zone)
        if reading.stated and others:
            return SearchError(
                SearchFailure.WRONG_UTM_ZONE,
                f"in zone {reading.zone} the point is outside Spain; it is in Spain in zone "
                + ", ".join(str(zone) for zone in others),
            )
        return _outside(f"UTM zone {reading.zone}: the point is outside Spain")

    def _to_lon_lat(self, x: float, y: float, crs: str) -> Position:
        try:
            return to_lon_lat([(x, y)], crs)[0]
        except ReprojectionError as exc:
            raise SearchError(SearchFailure.MALFORMED_COORDINATES, str(exc)) from exc

    def _territory(self, lon: float, lat: float) -> Territory | None:
        for territory in self._territories:
            west, south, east, north = territory.bbox
            if west <= lon <= east and south <= lat <= north:
                return territory
        return None

    async def _candidates(self, name: str) -> list[Interpretation]:
        settings = self._search.cartociudad
        fetched = await self._fetch(
            self._carto,
            self._carto.base_url + CANDIDATES_PATH,
            candidates_params(name, settings.max_candidates),
        )
        candidates = parse_candidates(fetched.content)
        await self._fetcher.store(self._carto, fetched)
        found = [
            Interpretation(
                kind=SearchKind.PLACE,
                origin=AoiOrigin(settings.types[candidate.type]),
                label=candidate.address,
                detail=candidate.province,
                position=None,
                resolve="/api/aoi/place?" + urlencode({"type": candidate.type, "id": candidate.id}),
            )
            for candidate in candidates
            if candidate.type in settings.types
        ]
        if not found:
            raise SearchError(
                SearchFailure.NO_MATCH, "CartoCiudad has no place by that name", self._carto.id
            )
        return found

    # ── resolve ──────────────────────────────────────────────────────────────────────────

    async def cadastral(self, reference: str) -> AreaOfInterest:
        try:
            parcel = await self._parcels.lookup(reference)
        except ParcelLookupError as exc:
            raise SearchError(_PARCEL_FAILURES[exc.failure], exc.detail, CATASTRO_SOURCE) from exc
        return AreaOfInterest(
            origin=AoiOrigin.CADASTRAL,
            label=parcel.reference,
            geometry=parcel.geometry,
            bbox=parcel.bbox,
            centre=parcel.reference_point,
            centre_local=parcel.reference_point_local,
            area_m2=parcel.area_m2,
            municipality=parcel.municipality,
            province=parcel.province,
            province_code=parcel.province_code,
            region_code=parcel.region_code,
            land_checked=True,
            sources=parcel.sources,
            parcel=parcel,
        )

    async def sigpac(self, code: str) -> AreaOfInterest:
        reference = parse_sigpac(code)
        fetched = await self._fetch(
            self._sigpac, self._sigpac.base_url + reference_path(reference.parts), {}
        )
        enclosures = parse_enclosures(fetched.content, reference.code)
        if any(enclosure.province != reference.province for enclosure in enclosures):
            raise _upstream("SIGPAC: an enclosure of another province", self._sigpac.id)
        province = self._province(f"{reference.province:02d}", self._sigpac.id)
        try:
            polygons = tuple(
                tuple(to_lon_lat([(lat, lon) for lon, lat in ring], SIGPAC_CRS) for ring in polygon)
                for enclosure in enclosures
                for polygon in enclosure.polygons
            )
            area = self._outline(
                origin=(
                    AoiOrigin.SIGPAC_PARCEL
                    if reference.enclosure is None
                    else AoiOrigin.SIGPAC_ENCLOSURE
                ),
                label=reference.code,
                polygons=polygons,
                centre=point_inside(polygons),
                area_m2=sum(enclosure.area_m2 for enclosure in enclosures),
                municipality=None,
                province=province,
                sources=(fetched.provenance,),
            )
        except (ReprojectionError, ValueError) as exc:
            raise _upstream(f"SIGPAC: unusable geometry ({exc})", self._sigpac.id) from exc
        await self._fetcher.store(self._sigpac, fetched)
        return area

    async def place(self, place_type: str, place_id: str) -> AreaOfInterest:
        origin = self._search.cartociudad.types.get(place_type)
        if origin is None:
            raise SearchError(
                SearchFailure.NOT_FOUND, f"places of type {place_type!r} are not offered"
            )
        fetched = await self._fetch(
            self._carto,
            self._carto.base_url + FIND_PATH,
            find_params(place_id, place_type),
            empty_statuses=(NO_CONTENT,),
        )
        found = parse_find(fetched.content, place_id)
        province = self._province(found.province_code, self._carto.id)
        aoi_origin = AoiOrigin(origin)
        try:
            if aoi_origin in POINT_ORIGINS:
                area = self._point(
                    aoi_origin,
                    found.label,
                    found.centre,
                    province,
                    (fetched.provenance,),
                    land_checked=True,
                    municipality=found.municipality,
                )
            elif found.polygons is None:
                raise _upstream(
                    f"CartoCiudad: the {place_type} {place_id} has no outline", self._carto.id
                )
            else:
                area = self._outline(
                    origin=aoi_origin,
                    label=found.label,
                    polygons=found.polygons,
                    centre=found.centre,
                    area_m2=geodesic_area_m2(found.polygons),
                    municipality=found.municipality,
                    province=province,
                    sources=(fetched.provenance,),
                )
        except (ReprojectionError, ValueError) as exc:
            raise _upstream(f"CartoCiudad: unusable geometry ({exc})", self._carto.id) from exc
        await self._fetcher.store(self._carto, fetched)
        return area

    async def point(self, crs: str, x: float, y: float, origin: AoiOrigin) -> AreaOfInterest:
        """A typed or drawn point; ``crs`` is LON_LAT or the CRS of a UTM zone of Spain."""
        if origin not in _POINT_SEARCHES:
            raise SearchError(SearchFailure.MALFORMED_COORDINATES, f"{origin} is not a point")
        zones = [zone for zone, zone_crs in self._crs_by_zone.items() if zone_crs == crs]
        if crs != LON_LAT and not zones:
            raise SearchError(SearchFailure.MALFORMED_COORDINATES, f"{crs} is not offered")
        reading = CoordinateReading(x=x, y=y, zone=zones[0] if zones else None)
        _crs, lon, lat, territory = self._place_reading(reading)
        province, sources, checked = await self._land(territory, lon, lat)
        label = (
            _reading_label(reading) if origin == AoiOrigin.COORDINATES else _degrees_label(lon, lat)
        )
        return self._point(origin, label, (lon, lat), province, sources, land_checked=checked)

    async def polygon(self, ring: Sequence[Position]) -> AreaOfInterest:
        """A drawn polygon: one closed ring, simple, within one territory of Spain."""
        positions = tuple((float(lon), float(lat)) for lon, lat in ring)
        limit = self._search.drawn_polygon.max_vertices
        if len(positions) - 1 > limit:
            raise SearchError(
                SearchFailure.INVALID_POLYGON, f"a drawn polygon has at most {limit} vertices"
            )
        try:
            check_simple_ring(positions)
        except ShapeError as exc:
            raise SearchError(SearchFailure.INVALID_POLYGON, str(exc)) from exc
        territory = self._territory(*positions[0])
        if territory is None or any(self._territory(*p) != territory for p in positions):
            raise _outside("a drawn area lies inside one territory of Spain")
        polygons: tuple[Polygon, ...] = ((positions,),)
        centre = point_inside(polygons)
        province, sources, checked = await self._land(territory, *centre)
        return self._outline(
            origin=AoiOrigin.DRAWN_POLYGON,
            label=None,
            polygons=polygons,
            centre=centre,
            area_m2=geodesic_area_m2(polygons),
            municipality=None,
            province=province,
            sources=sources,
            land_checked=checked,
        )

    # ── helpers ──────────────────────────────────────────────────────────────────────────

    async def _land(
        self, territory: Territory, lon: float, lat: float
    ) -> tuple[Province, tuple[Provenance, ...], bool]:
        """The province at the point, the source that said so, and whether it was checked."""
        if territory.province is not None:
            return self._province(territory.province, None), (), False
        fetched = await self._fetch(self._sigpac, self._sigpac.base_url + point_path(lon, lat), {})
        code = parse_point(fetched.content)
        if code is None:
            raise _outside(
                f"SIGPAC has no enclosure at {_degrees_label(lon, lat)}: at sea or outside Spain",
                self._sigpac.id,
            )
        province = self._province(f"{code:02d}", self._sigpac.id)
        await self._fetcher.store(self._sigpac, fetched)
        return province, (fetched.provenance,), True

    def _province(self, code: str, source: str | None) -> Province:
        province = province_by_code(code)
        if province is None:
            raise _upstream(f"unknown province code {code}", source)
        return province

    async def _fetch(
        self,
        service: Service,
        url: str,
        params: dict[str, str],
        empty_statuses: Collection[int] = (),
    ) -> Fetched:
        try:
            return await self._fetcher.fetch(service, url, params, empty_statuses)
        except UpstreamFailure as exc:
            failure = (
                SearchFailure.UPSTREAM_TIMEOUT if exc.timeout else SearchFailure.UPSTREAM_ERROR
            )
            raise SearchError(failure, exc.detail, service.id) from exc

    def _local(self, province: Province, point: Position) -> LocalPoint:
        crs = local_crs(province.region, point[0])
        x, y = transform_point(point, crs)
        return LocalPoint(crs=crs, x=x, y=y)

    def _point(
        self,
        origin: AoiOrigin,
        label: str,
        point: Position,
        province: Province,
        sources: tuple[Provenance, ...],
        *,
        land_checked: bool,
        municipality: str | None = None,
    ) -> AreaOfInterest:
        lon, lat = point
        return AreaOfInterest(
            origin=origin,
            label=label,
            geometry=PointGeometry(coordinates=point),
            bbox=(lon, lat, lon, lat),
            centre=point,
            centre_local=self._local(province, point),
            area_m2=None,
            municipality=municipality,
            province=province.name,
            province_code=province.iso,
            region_code=province.region,
            land_checked=land_checked,
            sources=sources,
        )

    def _outline(
        self,
        *,
        origin: AoiOrigin,
        label: str | None,
        polygons: tuple[Polygon, ...],
        centre: Position,
        area_m2: float,
        municipality: str | None,
        province: Province,
        sources: tuple[Provenance, ...],
        land_checked: bool = True,
    ) -> AreaOfInterest:
        return AreaOfInterest(
            origin=origin,
            label=label,
            geometry=MultiPolygon(coordinates=polygons),
            bbox=bbox_of(polygons),
            centre=centre,
            centre_local=self._local(province, centre),
            area_m2=area_m2,
            municipality=municipality,
            province=province.name,
            province_code=province.iso,
            region_code=province.region,
            land_checked=land_checked,
            sources=sources,
        )


def _sigpac_interpretation(reference: SigpacReference) -> Interpretation:
    return Interpretation(
        kind=SearchKind.SIGPAC,
        origin=(
            AoiOrigin.SIGPAC_PARCEL if reference.enclosure is None else AoiOrigin.SIGPAC_ENCLOSURE
        ),
        label=reference.code,
        detail=None,
        position=None,
        resolve=f"/api/aoi/sigpac/{reference.code}",
    )


def _reading_label(reading: CoordinateReading) -> str:
    if reading.zone is None:
        return _degrees_label(reading.x, reading.y)
    return f"{reading.zone}{reading.band or ''} {_number(reading.x)} {_number(reading.y)}"


def _outside(detail: str, source: str | None = None) -> SearchError:
    return SearchError(SearchFailure.OUTSIDE_COUNTRY, detail, source)


def _upstream(detail: str, source: str | None) -> SearchError:
    return SearchError(SearchFailure.UPSTREAM_ERROR, detail, source)
