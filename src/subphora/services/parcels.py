# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Look up a cadastral parcel: validate, check coverage, fetch (cached), reproject.

1. The reference is validated by the country module before anything leaves the server.
2. A rustic reference names its province: a province outside Catastro's coverage (the
   foral territories, decision 0010) is refused without calling out.
3. The WFS gives the outline and the area; the non-protected data service gives the
   municipality and province. Both answers are cached for the catalogue's lifetime, and
   only once they parse as a parcel: a "not found" is asked again next time.
4. The outline is reprojected from the srsName the answer declares to EPSG:4326, and the
   reference point into the projected CRS of the parcel's location.
"""

from subphora.config.sources import Service, SourcesSettings
from subphora.countries.es import Province, local_crs, parse_reference, province_by_code
from subphora.domain.parcels import (
    CadastralParcel,
    LocalPoint,
    LookupFailure,
    MultiPolygon,
    ParcelLookupError,
)
from subphora.geo import bbox_of, to_lon_lat, transform_point
from subphora.services.fetching import CachedFetcher, Fetched, UpstreamFailure
from subphora.sources import CatalogueClient
from subphora.sources.catastro import (
    DNPRC_PATH,
    OVC_SERVICE_ID,
    WFS_SERVICE_ID,
    RawParcel,
    dnprc_params,
    parse_dnprc,
    parse_wfs_parcel,
    wfs_parcel_params,
)
from subphora.store import FileCache
from subphora.store.file_cache import Clock, utc_now


class ParcelService:
    def __init__(
        self,
        client: CatalogueClient,
        sources: SourcesSettings,
        cache: FileCache,
        clock: Clock = utc_now,
    ) -> None:
        self._fetcher = CachedFetcher(client, cache, clock)
        self._wfs = sources.service(WFS_SERVICE_ID)
        self._ovc = sources.service(OVC_SERVICE_ID)

    async def lookup(self, raw_reference: str) -> CadastralParcel:
        """The parcel; raises ParcelLookupError with the reason it cannot be returned."""
        reference = parse_reference(raw_reference)
        parcel = reference.parcel
        if reference.province_code is not None:
            self._ensure_covered(reference.province_code)

        wfs = await self._fetch(self._wfs, self._wfs.base_url, wfs_parcel_params(parcel))
        raw = parse_wfs_parcel(wfs.content, parcel)
        ovc = await self._fetch(self._ovc, self._ovc.base_url + DNPRC_PATH, dnprc_params(parcel))
        place = parse_dnprc(ovc.content, parcel)
        province = self._ensure_covered(place.province_code)
        try:
            result = _assemble(raw, place.municipality, place.province, province, wfs, ovc)
        except ValueError as exc:
            # A position pyproj cannot reproject, or a place outside Spain's UTM zones.
            raise ParcelLookupError(
                LookupFailure.UPSTREAM_ERROR, f"Catastro: unusable geometry ({exc})"
            ) from exc
        await self._store(self._wfs, wfs)
        await self._store(self._ovc, ovc)
        return result

    def _ensure_covered(self, province_code: str) -> Province:
        province = province_by_code(province_code)
        if province is None:
            raise ParcelLookupError(
                LookupFailure.UPSTREAM_ERROR, f"Catastro: unknown province code {province_code}"
            )
        excluded = set(self._wfs.coverage_excludes)
        if province.region in excluded or province.iso in excluded:
            raise ParcelLookupError(
                LookupFailure.NOT_SUPPORTED,
                f"the cadastre of {province.region} is not supported yet (decision 0010)",
            )
        return province

    async def _fetch(self, service: Service, url: str, params: dict[str, str]) -> Fetched:
        try:
            return await self._fetcher.fetch(service, url, params)
        except UpstreamFailure as exc:
            failure = (
                LookupFailure.UPSTREAM_TIMEOUT if exc.timeout else LookupFailure.UPSTREAM_ERROR
            )
            raise ParcelLookupError(failure, exc.detail) from exc

    async def _store(self, service: Service, fetched: Fetched) -> None:
        await self._fetcher.store(service, fetched)


def _assemble(
    raw: RawParcel,
    municipality: str,
    province_name: str,
    province: Province,
    *fetched: Fetched,
) -> CadastralParcel:
    polygons = tuple(
        tuple(to_lon_lat(ring, raw.srs) for ring in polygon) for polygon in raw.polygons
    )
    point = to_lon_lat([raw.reference_point], raw.reference_point_srs)[0]
    crs = local_crs(province.region, point[0])
    x, y = transform_point(point, crs)
    return CadastralParcel(
        reference=raw.reference,
        area_m2=raw.area_m2,
        municipality=municipality,
        province=province_name,
        province_code=province.iso,
        region_code=province.region,
        geometry=MultiPolygon(coordinates=polygons),
        bbox=bbox_of(polygons),
        reference_point=point,
        reference_point_local=LocalPoint(crs=crs, x=x, y=y),
        sources=tuple(f.provenance for f in fetched),
    )
