# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The late-summer vegetation input (decision 0041) on synthetic rasters and a real SIGPAC
tile: NDVI and its composite, the anomaly with irrigated land masked, the STAC answers,
the vector tile reader, and the fetcher's cache, 404 fallback and failures."""

import json
import struct
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pytest
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.transform import from_origin

from subphora import __version__
from subphora.config import Settings
from subphora.config.national import VegetationDataset
from subphora.geo.grid import GridWindow
from subphora.geo.tiles import tile_bounds
from subphora.geo.vector_tiles import VectorTileError, polygons_at_least, wkb_polygon
from subphora.geo.vegetation import anomaly, composite, ndvi
from subphora.services import vegetation as vegetation_service
from subphora.services.inputs import InputFailure, InputFetcher
from subphora.services.vegetation import VegetationFetcher, select_scenes, tile_composite
from subphora.sources import CatalogueClient, HostNotAllowedError
from subphora.sources.sentinel import (
    Band,
    BandRead,
    BandReadError,
    Scene,
    SceneParseError,
    parse_scene_page,
    read_band,
    search_params,
)
from subphora.store import FileCache
from tests.support import fast_settings

FIXTURES = Path(__file__).parent.parent / "fixtures" / "sources"
TILE = (15, 16054, 12510)
TILE_BYTES = (FIXTURES / "sigpac_mvt_recinto_15_16054_12510.pbf").read_bytes()
COGS = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs"
NAN = np.nan


@pytest.fixture
def settings() -> Settings:
    return fast_settings()


@pytest.fixture
def dataset(settings: Settings) -> VegetationDataset:
    return settings.national.datasets.vegetation


# ── NDVI, its composite and its anomaly ────────────────────────────────────────────────


def test_ndvi_reads_reflectance_and_keeps_only_valid_clear_pixels() -> None:
    red = np.array([[2000, 2000, 2000, 0, 500]])
    nir = np.array([[4000, 4000, 4000, 4000, 4000]])
    scene_class = np.array([[4, 9, 5, 4, 4]])
    values = ndvi(red, nir, scene_class, (0.0001, 0.0001), (-0.1, -0.1), 0, [4, 5])
    # 0.3 and 0.1 reflectance: (0.3 - 0.1) / 0.4.
    assert values[0, 0] == pytest.approx(0.5)
    # Cloud (class 9), no data (0) and a negative reflectance (0.05 - 0.1) are missing.
    assert np.isnan(values[0, 1])
    assert values[0, 2] == pytest.approx(0.5)
    assert np.isnan(values[0, 3])
    assert np.isnan(values[0, 4])
    assert values.dtype == np.float32


def test_the_composite_takes_each_summers_median_then_the_median_over_summers() -> None:
    def grid(*row: float) -> np.ndarray:
        return np.array([row], dtype=np.float32)

    summers = [
        # A cloudy pixel in one scene takes the summer's other scene.
        [grid(0.2, NAN, 0.4), grid(0.4, 0.6, NAN)],
        [grid(0.3, 0.6, NAN)],
        [grid(0.5, 0.6, 0.4)],
        [],
    ]
    result = composite(summers, 3)
    assert result[0, 0] == pytest.approx(0.3)
    assert result[0, 1] == pytest.approx(0.6)
    # Only two summers saw the third pixel: fewer than three, so no value.
    assert np.isnan(result[0, 2])
    assert np.isnan(composite([[grid(0.2, 0.3, 0.4)]], 2)).all()
    with pytest.raises(ValueError, match="at least one scene"):
        composite([[], []], 1)


def test_the_anomaly_compares_with_the_dry_land_around_and_masks_irrigation() -> None:
    values = np.full((21, 21), 0.2, dtype=np.float32)
    values[:, 10] = 0.5  # a green strip, as along a spring line
    values[0:3, 0:3] = 0.9  # an irrigated plot, greener still
    irrigated = np.zeros((21, 21), dtype=bool)
    irrigated[0:3, 0:3] = True
    values[20, 20] = NAN
    result = anomaly(values, irrigated, 100.0, 300.0)
    # The strip stands out from the land within 300 m: 7 cells of it among the 29 there.
    assert result[10, 10] == pytest.approx(0.5 - (7 * 0.5 + 22 * 0.2) / 29, abs=1e-5)
    assert result[10, 0] == pytest.approx(0.0, abs=1e-5)
    # The irrigated plot is never part of the answer, nor of its neighbours' reference.
    assert np.isnan(result[0:3, 0:3]).all()
    assert result[4, 1] == pytest.approx(0.0, abs=1e-5)
    assert np.isnan(result[20, 20])
    # A cell with no dry land with a value around has no anomaly: never filled in.
    alone = np.full((3, 3), NAN, dtype=np.float32)
    alone[1, 1] = 0.4
    assert np.isnan(anomaly(alone, np.zeros((3, 3), dtype=bool), 100.0, 50.0)[0, 0])
    assert anomaly(alone, np.zeros((3, 3), dtype=bool), 100.0, 50.0)[1, 1] == pytest.approx(0)


# ── SIGPAC vector tiles ────────────────────────────────────────────────────────────────


def test_a_real_sigpac_tile_gives_its_irrigated_enclosures_in_web_mercator() -> None:
    irrigated = polygons_at_least(TILE_BYTES, TILE, "recinto", "coef_regadio", 1)
    every = polygons_at_least(TILE_BYTES, TILE, "recinto", "coef_regadio", 0)
    assert 0 < len(irrigated) < len(every)
    west, south, east, north = tile_bounds(*TILE)
    first = irrigated[0]
    rings = first["coordinates"][0] if first["type"] == "Polygon" else first["coordinates"][0][0]
    margin = 0.1 * (east - west)
    assert all(west - margin <= x <= east + margin for x, _ in rings)
    assert all(south - margin <= y <= north + margin for _, y in rings)
    assert polygons_at_least(TILE_BYTES, TILE, "no-such-layer", "coef_regadio", 1) == []
    assert polygons_at_least(b"", TILE, "recinto", "coef_regadio", 1) == []
    with pytest.raises(VectorTileError, match="not a readable vector tile"):
        polygons_at_least(b"<html>404</html>", TILE, "recinto", "coef_regadio", 1)


def test_a_point_or_a_line_among_the_enclosures_is_left_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pyogrio.raw

    polygon = b"\x01" + struct.pack("<I", 3) + _ring("<")
    point = b"\x01" + struct.pack("<Idd", 1, 0.0, 0.0)
    line = b"\x01" + struct.pack("<II4d", 2, 2, 0.0, 0.0, 1.0, 1.0)
    answer = ({}, None, [polygon, point, line, None], [[100.0, 100.0, 100.0, 100.0]])
    monkeypatch.setattr(pyogrio.raw, "read", lambda *_args, **_kwargs: answer)
    found = polygons_at_least(TILE_BYTES, TILE, "recinto", "coef_regadio", 1)
    assert [g["type"] for g in found] == ["Polygon"]
    broken = ({}, None, [polygon[:-8]], [[100.0]])
    monkeypatch.setattr(pyogrio.raw, "read", lambda *_args, **_kwargs: broken)
    with pytest.raises(VectorTileError, match="truncated"):
        polygons_at_least(TILE_BYTES, TILE, "recinto", "coef_regadio", 1)


def _ring(order: str) -> bytes:
    points = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)]
    body = struct.pack(order + "II", 1, len(points))
    return body + b"".join(struct.pack(order + "dd", *p) for p in points)


def test_wkb_polygons_read_in_either_byte_order_and_anything_else_is_refused() -> None:
    little = b"\x01" + struct.pack("<I", 3) + _ring("<")
    big = b"\x00" + struct.pack(">I", 3) + _ring(">")
    assert wkb_polygon(little) == wkb_polygon(big)
    assert wkb_polygon(little)["coordinates"][0][2] == [1.0, 1.0]
    multi = b"\x01" + struct.pack("<II", 6, 2) + little + big
    assert wkb_polygon(multi)["type"] == "MultiPolygon"
    point = b"\x01" + struct.pack("<Idd", 1, 0.0, 0.0)
    with pytest.raises(VectorTileError, match="not a 2D polygon"):
        wkb_polygon(point)
    with pytest.raises(VectorTileError, match="non-polygon"):
        wkb_polygon(b"\x01" + struct.pack("<II", 6, 1) + point)
    with pytest.raises(VectorTileError, match="truncated"):
        wkb_polygon(little[:-8])


# ── Sentinel-2 scenes ──────────────────────────────────────────────────────────────────


def _item(
    scene_id: str, tile: str = "MGRS-30SVJ", cloud: float = 5.0, when: str = "2025-08-20"
) -> dict[str, Any]:
    base = f"{COGS}/{scene_id}"
    scale = [{"nodata": 0, "scale": 0.0001, "offset": -0.1}]
    return {
        "type": "Feature",
        "id": scene_id,
        "properties": {
            "grid:code": tile,
            "eo:cloud_cover": cloud,
            "datetime": f"{when}T11:00:00Z",
        },
        "assets": {
            "red": {"href": f"{base}/B04.tif", "raster:bands": scale},
            "nir": {"href": f"{base}/B08.tif", "raster:bands": scale},
            "scl": {"href": f"{base}/SCL.tif"},
        },
    }


BANDS = ("red", "nir", "scl")


def test_a_search_page_keeps_the_complete_scenes_and_its_next_link() -> None:
    no_nir = _item("b")
    del no_nir["assets"]["nir"]
    plain_http = _item("c")
    plain_http["assets"]["red"]["href"] = "http://example.org/B04.tif"
    no_tile = _item("d")
    del no_tile["properties"]["grid:code"]
    page = {
        "type": "FeatureCollection",
        "features": [_item("a"), no_nir, plain_http, no_tile, "junk"],
        "links": [
            {"rel": "self", "href": "https://earth-search.aws.element84.com/v1/search"},
            {"rel": "next", "href": "https://example.org/post", "method": "POST"},
            {"rel": "next", "href": "https://earth-search.aws.element84.com/v1/search?p=2"},
        ],
    }
    parsed = parse_scene_page(json.dumps(page).encode(), BANDS)
    (scene,) = parsed.scenes
    assert scene.id == "a"
    assert scene.acquired == datetime(2025, 8, 20, 11, tzinfo=UTC)
    assert scene.bands["red"].scale == 0.0001
    assert scene.bands["red"].offset == -0.1
    assert (scene.bands["scl"].scale, scene.bands["scl"].offset) == (1.0, 0.0)
    assert parsed.next_url == "https://earth-search.aws.element84.com/v1/search?p=2"
    last = parse_scene_page(json.dumps({"type": "FeatureCollection"}).encode(), BANDS)
    assert (last.scenes, last.next_url) == ([], None)
    with pytest.raises(SceneParseError, match="not JSON"):
        parse_scene_page(b"<html>", BANDS)
    with pytest.raises(SceneParseError, match="FeatureCollection"):
        parse_scene_page(json.dumps({"type": "Feature"}).encode(), BANDS)


def test_a_search_asks_for_the_box_and_the_whole_days() -> None:
    params = search_params(
        "sentinel-2-l2a", (-3.5, 39.0, -3.25, 39.125), "2025-07-15", "2025-09-15", 100
    )
    assert params == {
        "collections": "sentinel-2-l2a",
        "bbox": "-3.500000,39.000000,-3.250000,39.125000",
        "datetime": "2025-07-15T00:00:00Z/2025-09-15T23:59:59Z",
        "limit": "100",
    }


def test_each_tile_and_summer_keeps_its_least_cloudy_scenes_once() -> None:
    page = {
        "type": "FeatureCollection",
        "features": [
            _item("a", cloud=20.0),
            _item("b", cloud=2.0),
            _item("c", cloud=10.0),
            _item("d", cloud=45.0),
            _item("e", cloud=1.0, when="2024-08-01"),
            _item("f", tile="MGRS-30SWJ", cloud=3.0),
        ],
    }
    scenes = parse_scene_page(json.dumps(page).encode(), BANDS).scenes
    chosen = select_scenes([*scenes, *scenes], 2, 30.0)
    assert {
        tile: {y: [s.id for s in v] for y, v in years.items()} for tile, years in chosen.items()
    } == {
        "MGRS-30SVJ": {2024: ["e"], 2025: ["b", "c"]},
        "MGRS-30SWJ": {2025: ["f"]},
    }
    assert list(chosen["MGRS-30SVJ"]) == [2024, 2025]


async def test_a_band_on_a_host_outside_the_catalogue_is_never_opened(settings: Settings) -> None:
    band = Band(href="https://example.org/B04.tif", scale=1.0, offset=0.0, nodata=0)
    async with CatalogueClient(
        settings.sources, __version__, httpx.MockTransport(_never)
    ) as client:
        with pytest.raises(HostNotAllowedError):
            read_band(client, band, 80.0, Resampling.average)


def _band_file(path: Path, crs: str | None) -> None:
    import rasterio

    data = np.arange(100 * 60, dtype=np.uint16).reshape(100, 60)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=60,
        height=100,
        count=1,
        dtype="uint16",
        crs=crs,
        transform=from_origin(500_000, 4_300_000, 10, 10),
    ) as dataset:
        dataset.write(data, 1)


async def test_a_band_is_read_at_the_coarser_cell_with_its_transform_scaled(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import rasterio

    from subphora.sources import sentinel

    _band_file(tmp_path / "B04.tif", "EPSG:32630")
    _band_file(tmp_path / "SCL.tif", None)
    opened: list[str] = []
    real_open = rasterio.open

    def local(name: str, *args: Any, **kwargs: Any) -> Any:
        # GDAL's range reader stands in for a local file named like the band.
        opened.append(name)
        return real_open(tmp_path / name.rsplit("/", 1)[-1], *args, **kwargs)

    monkeypatch.setattr(sentinel.rasterio, "open", local)
    async with CatalogueClient(
        settings.sources, __version__, httpx.MockTransport(_never)
    ) as client:
        read = read_band(client, Band(f"{COGS}/x/B04.tif", 1.0, 0.0, 0), 80.0, Resampling.average)
        assert read.data.shape == (13, 8)
        assert read.crs == "EPSG:32630"
        assert read.transform.a == pytest.approx(60 * 10 / 8)
        assert read.transform.e == pytest.approx(-100 * 10 / 13)
        assert (read.transform.c, read.transform.f) == (500_000, 4_300_000)
        # A finer cell than the band's own reads it as it is.
        assert read_band(
            client, Band(f"{COGS}/x/B04.tif", 1.0, 0.0, 0), 5.0, Resampling.nearest
        ).data.shape == (100, 60)
        with pytest.raises(BandReadError, match="no CRS"):
            read_band(client, Band(f"{COGS}/x/SCL.tif", 1.0, 0.0, 0), 80.0, Resampling.nearest)
        with pytest.raises(BandReadError, match=r"B08\.tif"):
            read_band(client, Band(f"{COGS}/x/B08.tif", 1.0, 0.0, 0), 80.0, Resampling.average)
    assert opened[0] == f"/vsicurl/{COGS}/x/B04.tif"


def _never(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected request {request.url}")


# ── A tile's composite and the fetcher ─────────────────────────────────────────────────

# The synthetic scenes cover this box (EPSG:25830) around the real SIGPAC tile.
_TO_UTM = Transformer.from_crs("EPSG:3857", "EPSG:25830", always_xy=True)
_BOUNDS = tile_bounds(*TILE)
_CENTRE = _TO_UTM.transform((_BOUNDS[0] + _BOUNDS[2]) / 2, (_BOUNDS[1] + _BOUNDS[3]) / 2)


class FakeBands:
    """A band reader that makes up each band: NDVI 0.5 west of the centre, 0.2 east of it,
    the first scene's bands one row taller than the others."""

    def __init__(self, fail: bool = False) -> None:
        self.read: list[str] = []
        self.fail = fail

    def __call__(
        self, client: CatalogueClient, band: Band, cell_m: float, _resampling: Resampling
    ) -> BandRead:
        client.ensure_allowed(httpx.URL(band.href))
        if self.fail:
            raise BandReadError(f"{band.href}: HTTP 403")
        self.read.append(band.href)
        west, north = _CENTRE[0] - 5000, _CENTRE[1] + 5000
        size = round(10_000 / cell_m)
        rows = size + (1 if "/a/" in band.href else 0)
        columns = np.arange(size)
        name = band.href.rsplit("/", 1)[-1]
        if name == "SCL.tif":
            data = np.full((rows, size), 4, dtype=np.uint8)
        elif name == "B04.tif":
            data = np.full((rows, size), 2000, dtype=np.uint16)
        else:
            data = np.broadcast_to(np.where(columns < size // 2, 4000, 2500), (rows, size))
        return BandRead(
            data=np.array(data),
            transform=from_origin(west, north, cell_m, cell_m),
            crs="EPSG:25830",
        )


def _scenes(*ids: str, year: int = 2025) -> list[Scene]:
    page = {"type": "FeatureCollection", "features": [_item(i, when=f"{year}-08-20") for i in ids]}
    return parse_scene_page(json.dumps(page).encode(), BANDS).scenes


def test_a_tile_composite_is_a_geotiff_of_its_scenes(
    settings: Settings, dataset: VegetationDataset, tmp_path: Path
) -> None:
    import rasterio

    one = dataset.model_copy(update={"min_years": 1})
    reader = FakeBands()

    class Client:
        def ensure_allowed(self, url: httpx.URL) -> None:
            assert url.host == "sentinel-cogs.s3.us-west-2.amazonaws.com"

    content = tile_composite(Client(), {2025: _scenes("a", "b")}, one, reader)  # type: ignore[arg-type]
    path = tmp_path / "composite.tif"
    path.write_bytes(content)
    with rasterio.open(path) as tif:
        values = tif.read(1)
        assert str(tif.crs) == "EPSG:25830"
    # The first scene's extra row has nothing to pair with in the second scene: it keeps
    # only the first scene's value. Both scenes agree elsewhere.
    assert values[0, 0] == pytest.approx(0.5, abs=1e-4)
    assert values[0, -1] == pytest.approx(0.2, abs=1e-4)
    assert len(reader.read) == 6
    with pytest.raises(ValueError, match="at least one scene"):
        tile_composite(Client(), {}, one, reader)  # type: ignore[arg-type]


class FakeServices:
    """Earth Search over two pages per summer, and SIGPAC's tiles: 404 at the zoom asked,
    the real tile among the children, 404 for every other child."""

    def __init__(self, tile: bytes = TILE_BYTES) -> None:
        self.tile = tile
        self.requests: list[httpx.URL] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request.url)
        if request.url.host == "earth-search.aws.element84.com":
            year = (
                int(request.url.params.get("datetime", "2025")[:4])
                if "datetime" in request.url.params
                else 0
            )
            if year:
                page = {
                    "type": "FeatureCollection",
                    "features": [_item(f"s{year}a", when=f"{year}-08-01")],
                    "links": [
                        {
                            "rel": "next",
                            "href": f"https://earth-search.aws.element84.com/v1/search?page=2&year={year}",
                        }
                    ],
                }
            else:
                year = int(request.url.params["year"])
                page = {
                    "type": "FeatureCollection",
                    "features": [_item(f"s{year}b", cloud=9.0, when=f"{year}-08-11")],
                }
            return httpx.Response(200, json=page)
        if request.url.host == "sigpac-hubcloud.es":
            if request.url.path.endswith("/15/16054/12510.pbf"):
                return httpx.Response(200, content=self.tile)
            return httpx.Response(404, content=b"<html>404 - File or directory not found.</html>")
        raise AssertionError(f"unexpected request {request.url}")


def _window() -> GridWindow:
    return GridWindow(
        crs="EPSG:25830",
        cell_m=100,
        west=_CENTRE[0] - 1500,
        north=_CENTRE[1] + 1500,
        width=30,
        height=30,
    )


async def _fetch(
    settings: Settings,
    dataset: VegetationDataset,
    root: Path,
    services: FakeServices,
    reader: FakeBands,
) -> vegetation_service.VegetationInput:
    async with CatalogueClient(
        settings.sources, __version__, httpx.MockTransport(services)
    ) as client:
        inputs = InputFetcher(client, settings, FileCache(root / "cache"))
        return await VegetationFetcher(client, inputs, reader).fetch(
            dataset, _window(), date(2026, 11, 27)
        )


@pytest.fixture
def shallow(dataset: VegetationDataset) -> VegetationDataset:
    """Three summers, the irrigation asked at zoom 14 so that the real tile is a child."""
    irrigation = dataset.irrigation.model_copy(update={"zoom": 14, "deepest_zoom": 15})
    return dataset.model_copy(
        update={"years": 3, "min_years": 3, "neighbourhood_m": 500.0, "irrigation": irrigation}
    )


async def test_the_fetcher_composites_each_tile_once_and_masks_the_irrigated_land(
    settings: Settings, shallow: VegetationDataset, tmp_path: Path
) -> None:
    services, reader = FakeServices(), FakeBands()
    found = await _fetch(settings, shallow, tmp_path, services, reader)
    assert found.summers == [2024, 2025, 2026]
    # One tile, two scenes (one per page) in each of three summers, three bands each.
    assert len(found.composites) == 1
    assert len(reader.read) == 3 * 2 * 3
    share = found.irrigated_share
    assert share.shape == (30, 30)
    assert 0 < float(share.max()) <= 1.0
    assert float(share.min()) == 0.0
    # The 404 at zoom 14 was asked again at zoom 15, never deeper.
    zooms = {
        int(u.path.split("/")[-3]) for u in services.requests if u.host == "sigpac-hubcloud.es"
    }
    assert zooms == {14, 15}
    # A second fetch reuses the composite and the tiles: no band is read again.
    asked = len(services.requests)
    again = await _fetch(settings, shallow, tmp_path, services, reader)
    assert len(reader.read) == 18
    assert again.composites == found.composites
    assert np.array_equal(again.irrigated_share, share)
    assert not [u for u in services.requests[asked:] if u.host == "sigpac-hubcloud.es"]
    # The cache holds each tile's burnt raster, never the tile itself.
    kept = [path.read_bytes() for path in (tmp_path / "cache").rglob("*.bin")]
    assert kept
    assert TILE_BYTES not in kept


async def test_the_fetcher_fails_honestly(
    settings: Settings, shallow: VegetationDataset, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(InputFailure, match="HTTP 403"):
        await _fetch(settings, shallow, tmp_path / "a", FakeServices(), FakeBands(fail=True))
    with pytest.raises(InputFailure, match="tile 15/16054/12510"):
        await _fetch(
            settings, shallow, tmp_path / "b", FakeServices(b"\x1a\x07garbage"), FakeBands()
        )
    monkeypatch.setattr(vegetation_service, "_MAX_PAGES", 1)
    with pytest.raises(InputFailure, match="more than 1 pages"):
        await _fetch(settings, shallow, tmp_path / "c", FakeServices(), FakeBands())
