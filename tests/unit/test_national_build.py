# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The national build on a tiny synthetic region, its failures, and the map it serves."""

from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import numpy as np
import pytest
import rasterio

from subphora import __main__ as cli
from subphora import __version__
from subphora.api import create_app
from subphora.config import Settings
from subphora.domain.potential import Variable
from subphora.domain.validation import NO_BODY, ValidationState
from subphora.services.national import (
    BuildReport,
    NationalBuilder,
    RegionSpecError,
    all_regions,
    resolve_region,
)
from subphora.sources import CatalogueClient
from subphora.store import FileCache
from subphora.store.national import read_manifests, read_map, region_tif, tiles_path
from tests.national_support import MADRID, FakeSpain, small_settings

BOX = ",".join(str(v) for v in MADRID)


@pytest.fixture
def settings() -> Settings:
    return small_settings()


async def build(settings: Settings, root: Path, spain: FakeSpain, spec: str = BOX) -> BuildReport:
    async with CatalogueClient(settings.sources, __version__, spain.transport()) as client:
        builder = NationalBuilder(client, settings, FileCache(root / "cache"), root)
        with ThreadPoolExecutor(max_workers=2) as executor:
            return await builder.build(resolve_region(settings, spec), executor, 2)


def output(settings: Settings, root: Path) -> Path:
    return settings.national.build.output_path(root)


# ── Regions ────────────────────────────────────────────────────────────────────────────


def test_a_region_is_a_province_a_region_or_a_box(settings: Settings) -> None:
    (zaragoza,) = resolve_region(settings, "es-z")
    assert (zaragoza.id, zaragoza.name, zaragoza.grid.id) == ("ES-Z", "Zaragoza", "mainland")
    assert zaragoza.boundary_code == "34025000000"
    assert [r.id for r in resolve_region(settings, "ES-AR")] == ["ES-HU", "ES-TE", "ES-Z"]
    assert {r.grid.id for r in resolve_region(settings, "ES-CN")} == {"canaries"}
    (box,) = resolve_region(settings, BOX)
    assert box.grid.id == "mainland"
    assert box.boundary_code is None
    (canary_box,) = resolve_region(settings, "-15.6,27.9,-15.4,28.1")
    assert canary_box.grid.id == "canaries"
    assert len(all_regions(settings)) == 52


@pytest.mark.parametrize("spec", ["ES-XX", "1,2,3", "a,b,c,d", "2,2,1,1", "-9.5,38.0,-9.0,38.5"])
def test_a_region_that_is_not_in_spain_is_refused(settings: Settings, spec: str) -> None:
    with pytest.raises(RegionSpecError):
        resolve_region(settings, spec)


# ── The build ──────────────────────────────────────────────────────────────────────────


async def test_the_build_writes_grids_tiles_and_the_map(settings: Settings, tmp_path: Path) -> None:
    spain = FakeSpain()
    report = await build(settings, tmp_path, spain)
    assert report.failed == []
    (built,) = report.built
    assert built.cells > 0
    assert built.scored == built.cells
    root = output(settings, tmp_path)
    (manifest,) = read_manifests(root)
    assert manifest.grid == "mainland"
    assert manifest.crs == "EPSG:3035"
    assert manifest.cell_m == 100
    assert [c.cls for c in manifest.categories[Variable.PERMEABILITY_CLASS]] == ["ALTA"]
    assert [c.cls for c in manifest.categories[Variable.GROUNDWATER_STATUS]] == ["Malo"]
    # Every criterion with a nationwide input; the faults and dips are parcel-scale only.
    assert set(manifest.sources) == {
        c.id for c in settings.model.criteria if c.variable is not None
    } - {"lineaments", "bedding_dip"}
    with rasterio.open(region_tif(root, manifest.region_id)) as dataset:
        bands = dict(zip(dataset.descriptions, dataset.read(), strict=True))
    inside = ~np.isnan(bands["index"])
    assert inside.sum() == built.cells
    assert np.all((bands["index"][inside] >= 0) & (bands["index"][inside] <= 1))
    assert np.allclose(bands["clay_pct"][inside], 25.0)
    # The stream is not groundwater: the nearest point is a spring or a borehole.
    assert np.nanmin(bands["water_point_distance_m"]) == 0
    # The valley floor drains: some cell is a channel.
    assert np.nanmin(bands["drainage_distance_m"]) == 0
    published = read_map(root)
    assert published is not None
    assert [r.region_id for r in published.regions] == [manifest.region_id]
    # The synthetic water points record no yield: every domain lacks labelled wells, says
    # so, and has no skill to draw.
    assert {v.domain: v.state for v in manifest.validation} == {
        "ES030MSBT000": ValidationState.NOT_ENOUGH_LABELS,
        NO_BODY: ValidationState.NOT_ENOUGH_LABELS,
    }
    assert (built.validated, built.chance, built.unmeasured) == (0, 0, 2)
    assert np.isnan(bands["skill"]).all()
    for layer in settings.national.tiles.layers:
        if layer.variable is not Variable.SKILL:
            assert report.tiles[layer.id] > 0
            assert tiles_path(root, layer.id).exists()
    # Paged: the permeability layer was asked for its second page.
    offsets = [
        r.url.params["resultOffset"] for r in spain.requests if "Permeabilidad" in r.url.path
    ]
    assert offsets == ["0", "1000"]


async def test_a_province_is_clipped_to_its_official_boundary(
    settings: Settings, tmp_path: Path
) -> None:
    report = await build(settings, tmp_path, FakeSpain(), "ES-M")
    (built,) = report.built
    (manifest,) = read_manifests(output(settings, tmp_path))
    assert manifest.region_id == "ES-M"
    assert manifest.name == "Madrid"
    # The window holds the buffer; only the boundary's cells are scored.
    assert built.cells < manifest.width * manifest.height
    assert manifest.bbox == MADRID


async def test_a_failed_download_fails_its_region_and_writes_nothing(
    settings: Settings, tmp_path: Path
) -> None:
    report = await build(settings, tmp_path, FakeSpain(fail={"servicios.idee.es": 500}))
    assert report.built == []
    assert report.tiles == {}
    (failure,) = report.failed
    assert "HTTP 500" in failure.detail
    assert read_manifests(output(settings, tmp_path)) == []
    assert read_map(output(settings, tmp_path)) is None


async def test_an_answer_that_is_not_a_raster_fails_the_region(
    settings: Settings, tmp_path: Path
) -> None:
    class NotTiff(FakeSpain):
        @staticmethod
        def _terrain(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"<ExceptionReport>ExtentError</ExceptionReport>")

    report = await build(settings, tmp_path, NotTiff())
    (failure,) = report.failed
    assert "not a GeoTIFF" in failure.detail


async def test_a_service_error_inside_a_page_is_asked_again(
    settings: Settings, tmp_path: Path
) -> None:
    refused = {"count": 0}

    class Flaky(FakeSpain):
        def _water_points(self, request: httpx.Request) -> httpx.Response:
            if refused["count"] == 0:
                refused["count"] += 1
                return httpx.Response(200, json={"error": {"message": "Failed to execute query."}})
            return super()._water_points(request)

    report = await build(settings, tmp_path, Flaky())
    assert report.failed == []
    assert len(report.built) == 1


async def test_a_service_error_that_persists_fails_the_region(
    settings: Settings, tmp_path: Path
) -> None:
    class Refusing(FakeSpain):
        def _water_points(self, _request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"error": {"message": "Failed to execute query."}})

    report = await build(settings, tmp_path, Refusing())
    (failure,) = report.failed
    assert "refused the query" in failure.detail


async def test_a_second_build_reads_its_inputs_from_the_cache(
    settings: Settings, tmp_path: Path
) -> None:
    first = FakeSpain()
    await build(settings, tmp_path, first)
    second = FakeSpain()
    await build(settings, tmp_path, second)
    assert first.requests
    assert second.requests == []


# ── The command ────────────────────────────────────────────────────────────────────────


def test_the_command_refuses_a_region_outside_spain(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["national", "build", "--region", "PT-11"]) == cli.EXIT_USAGE
    assert "neither" in capsys.readouterr().out


def test_the_command_needs_a_region_or_all() -> None:
    with pytest.raises(SystemExit):
        cli.main(["national", "build"])


# ── The served map ─────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def serve(settings: Settings, root: Path) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings, root=root, transport=FakeSpain().transport())
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


async def test_before_any_build_the_map_says_it_is_not_built(
    settings: Settings, tmp_path: Path
) -> None:
    async with serve(settings, tmp_path) as client:
        described = (await client.get("/api/national")).json()
        explained = await client.get("/api/national/explain", params={"lon": -3.7, "lat": 40.42})
        tile = await client.get("/api/national/tiles/potential-index/9/250/193")
    assert described["built"] is False
    assert described["kind"] == "index"
    assert [layer["id"] for layer in described["layers"]][:2] == [
        "potential-index",
        "potential-confidence",
    ]
    assert explained.status_code == 404
    assert explained.json()["code"] == "not_built"
    assert tile.status_code == 404
    assert tile.json()["code"] == "not_built"


async def test_the_built_map_serves_tiles_and_explains_a_cell(
    settings: Settings, tmp_path: Path
) -> None:
    await build(settings, tmp_path, FakeSpain())
    async with serve(settings, tmp_path) as client:
        described = (await client.get("/api/national")).json()
        index = next(layer for layer in described["layers"] if layer["id"] == "potential-index")
        explained = await client.get("/api/national/explain", params={"lon": -3.70, "lat": 40.42})
        outside = await client.get("/api/national/explain", params={"lon": -3.0, "lat": 40.0})
        tile = await client.get("/api/national/tiles/potential-index/9/250/193")
        empty = await client.get("/api/national/tiles/potential-index/9/0/0")
        unknown = await client.get("/api/national/tiles/nothing/9/250/193")
        invalid = await client.get("/api/national/tiles/potential-index/2/9/9")
    assert described["built"] is True
    assert described["regions"][0]["bbox"] == list(MADRID)
    assert index["tiles"] == ["/api/national/tiles/potential-index/{z}/{x}/{y}"]
    assert index["legend"][0] == {"min": None, "max": 0.2, "colour": "#ffffcc"}
    assert index["legend"][-1]["max"] is None
    body = explained.json()
    assert explained.status_code == 200
    assert body["region_id"].startswith("box")
    assert body["cell_m"] == 100
    estimate = body["estimate"]
    assert estimate["kind"] == "index"
    assert 0 <= estimate["score"] <= 1
    assert estimate["confidence"]["label"] in {"low", "medium", "high"}
    assert {m["criterion"] for m in estimate["missing"]} >= {
        "lineaments",
        "bedding_dip",
        "piezometric_depth",
    }
    assert outside.status_code == 404
    assert outside.json()["code"] == "outside_built_area"
    assert tile.status_code == 200
    assert tile.content.startswith(b"\x89PNG")
    assert tile.headers["cache-control"] == "public, max-age=300"
    assert empty.status_code == 200
    assert empty.content.startswith(b"\x89PNG")
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "unknown_layer"
    assert invalid.status_code == 400
    assert invalid.json()["code"] == "invalid_tile"


async def test_an_unreadable_region_is_reported(settings: Settings, tmp_path: Path) -> None:
    await build(settings, tmp_path, FakeSpain())
    root = output(settings, tmp_path)
    (manifest,) = read_manifests(root)
    (root / "regions" / f"{manifest.region_id}.json").write_text("{}")
    (root / "map.json").touch()
    async with serve(settings, tmp_path) as client:
        explained = await client.get("/api/national/explain", params={"lon": -3.70, "lat": 40.42})
    assert explained.status_code == 500
    assert explained.json()["code"] == "unreadable"
