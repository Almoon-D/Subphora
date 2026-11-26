# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The detailed map of an area as a job, on the synthetic Spain: its analysis, candidates,
layers and taps; clipping at the area's edge and across UTM zones; a missing detailed
input; and every way a job is refused or fails."""

import asyncio
import math
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pytest
import rasterio

from subphora.config import Settings
from subphora.domain.aoi import AreaOfInterest
from subphora.services import parcel as parcel_service
from subphora.store.national import region_tif
from tests.national_support import FakeSpain
from tests.parcel_support import parcel_settings, point_area, polygon_area, serve, write_levels

# A square of about 300 m by 300 m in Madrid.
SQUARE = [(-3.702, 40.418), (-3.6985, 40.418), (-3.6985, 40.4207), (-3.702, 40.4207)]
# The same size astride the meridian, where UTM zones 30 and 31 meet: its centre is in 31.
ASTRIDE = [(-0.0015, 40.418), (0.002, 40.418), (0.002, 40.4207), (-0.0015, 40.4207)]
# How long a job may take, in seconds: a loaded CI runner computes the small test areas
# in several seconds, and a count of polls at the test settings' 0.01 s was too short.
_DEADLINE_S = 120.0


@pytest.fixture
def settings() -> Settings:
    return parcel_settings()


async def start(client: httpx.AsyncClient, area: AreaOfInterest) -> httpx.Response:
    return await client.post("/api/parcel", content=area.model_dump_json())


async def settle(client: httpx.AsyncClient, area_id: str) -> dict[str, Any]:
    """The job once it is done or failed, asked as the page asks."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + _DEADLINE_S
    while loop.time() < deadline:
        body: dict[str, Any] = (await client.get(f"/api/parcel/{area_id}")).json()
        if body["job"]["state"] in {"done", "failed"}:
            return body
        await asyncio.sleep(body["job"]["poll_after_s"])
    raise AssertionError("the job did not finish")


async def analyse(
    client: httpx.AsyncClient, area: AreaOfInterest
) -> tuple[dict[str, Any], dict[str, Any]]:
    started = await start(client, area)
    assert started.status_code in {200, 202}
    body = await settle(client, started.json()["job"]["id"])
    return started.json(), body


def square_m2(ring: list[tuple[float, float]]) -> float:
    from pyproj import Geod

    lons, lats = zip(*ring, strict=True)
    area, _ = Geod(ellps="GRS80").polygon_area_perimeter(lons, lats)
    return abs(area)


# ── A finished map ─────────────────────────────────────────────────────────────────────


async def test_a_point_gets_its_map_candidates_and_layers(
    settings: Settings, tmp_path: Path
) -> None:
    async with serve(settings, tmp_path) as client:
        started, body = await analyse(client, point_area())
        job = body["job"]
        area_id = job["id"]
        candidates = job["analysis"]["candidates"]
        first = candidates[0]
        explained = await client.get(
            f"/api/parcel/{area_id}/explain",
            params={"lon": first["longitude"], "lat": first["latitude"]},
        )
        outside = await client.get(
            f"/api/parcel/{area_id}/explain", params={"lon": -3.60, "lat": 40.42}
        )
        image = await client.get(body["layers"][0]["image"])
        again = await start(client, point_area())
    assert started["job"]["state"] == "queued"
    assert started["layers"] == []
    assert job["state"] == "done"
    analysis = job["analysis"]
    assert analysis["crs"] == "EPSG:25830"
    assert analysis["cell_m"] == 10
    assert analysis["terrain_model"] == "MDT05"
    assert analysis["area_m2"] == pytest.approx(math.pi * 100**2, rel=0.01)
    # Candidates: ranked, separated, confident enough, each with its legal status.
    candidate_settings = settings.parcel.candidates
    assert 1 <= len(candidates) <= candidate_settings.count
    assert [c["rank"] for c in candidates] == list(range(1, len(candidates) + 1))
    scores = [c["estimate"]["score"] for c in candidates]
    assert scores == sorted(scores, reverse=True)
    for candidate in candidates:
        assert candidate["estimate"]["confidence"]["value"] >= candidate_settings.min_confidence
        # Assessed by the legal filter at the spot, with the distances measured there.
        legal = candidate["legal"]
        assert legal["state"] != "not_evaluated"
        assert legal["disclaimer"].startswith("Guidance, not legal advice")
        assert legal["source"]
        assert legal["authority"]["district"] == "ES030"
        assert legal["body"]["quantitative_status"] == "Malo"
        # The Tajo plan's distance replaces the national one: 250 m at 7,000 m³/year.
        distance = next(f for f in legal["findings"] if f["rule_id"] == "pht-22-distance")
        point = candidate["site"]["water_point"]["metres"]
        assert distance["outcome"] == ("blocks" if point is not None and point < 250 else "clear")
        # No levels imported: the depth is unknown and says why; no depth, no cost.
        assert candidate["depth"]["state"] == "unknown"
        assert candidate["depth"]["reason"] == "not_imported"
        assert candidate["cost"] is None
    xy = [(c["local"]["x"], c["local"]["y"]) for c in candidates]
    for i, a in enumerate(xy):
        for b in xy[i + 1 :]:
            assert math.dist(a, b) >= candidate_settings.min_separation_m
    # Every criterion with a detailed input is present; the summary adds up.
    summary = analysis["summary"]
    present = {c["criterion"] for c in summary["contributions"]}
    assert {"lineaments", "bedding_dip", "slope", "permeability"} <= present
    assert [m["criterion"] for m in summary["missing"]] == ["piezometric_depth"]
    assert summary["kind"] == "index"
    assert summary["mean_index"] == pytest.approx(
        sum(c["mean_contribution"] for c in summary["contributions"]), abs=1e-4
    )
    assert summary["scored_cells"] == summary["cells"] > 0
    # Layers: one image per layer, with the national legend.
    assert [layer["id"] for layer in body["layers"]] == settings.parcel.layers
    assert body["layers"][0]["image"] == f"/api/parcel/{area_id}/layers/potential-index"
    assert body["layers"][0]["legend"][0] == {"min": None, "max": 0.2, "colour": "#ffffcc"}
    assert image.status_code == 200
    assert image.content.startswith(b"\x89PNG")
    # A tap at a candidate explains the same estimate; outside the area there is none.
    assert explained.status_code == 200
    assert explained.json()["estimate"] == first["estimate"]
    assert explained.json()["cell_m"] == 10
    assert outside.status_code == 404
    assert outside.json()["code"] == "outside_grid"
    # The same area asked again is the same finished job.
    assert again.status_code == 200
    assert again.json()["job"]["id"] == area_id


async def test_the_lineaments_and_dip_come_from_magna(settings: Settings, tmp_path: Path) -> None:
    async with serve(settings, tmp_path) as client:
        _, body = await analyse(client, point_area())
    first = body["job"]["analysis"]["candidates"][0]["estimate"]
    by_id = {c["criterion"]: c for c in first["contributions"]}
    # The fault through the window's centre counts; the contact does not.
    assert by_id["lineaments"]["value"]["number"] > 0
    assert by_id["lineaments"]["value"]["unit"] == "km_km2"
    assert by_id["lineaments"]["source"]["detail"]["scale_denominator"] == 50000
    # The bedding dip (20°), not the cleavage beside it (80°).
    assert by_id["bedding_dip"]["value"]["number"] == 20
    assert by_id["water_points"]["value"]["at_least"] is False


async def test_a_missing_detailed_input_lowers_confidence(
    settings: Settings, tmp_path: Path
) -> None:
    async with serve(settings, tmp_path / "with") as client:
        _, full = await analyse(client, point_area())
    async with serve(settings, tmp_path / "without", FakeSpain(bedding=False)) as client:
        _, partial = await analyse(client, point_area())
    with_dip = full["job"]["analysis"]["summary"]
    without = partial["job"]["analysis"]["summary"]
    assert {m["criterion"]: m["reason"] for m in without["missing"]} == {
        "bedding_dip": "no_data",
        "piezometric_depth": "no_dataset",
    }
    assert without["mean_confidence"]["value"] < with_dip["mean_confidence"]["value"]
    coverage = {c["id"]: c["value"] for c in without["mean_confidence"]["components"]}
    full_coverage = {c["id"]: c["value"] for c in with_dip["mean_confidence"]["components"]}
    weight = settings.model.criterion("bedding_dip").weight
    assert coverage["coverage"] == pytest.approx(full_coverage["coverage"] - weight)


async def test_the_map_is_clipped_to_the_area(settings: Settings, tmp_path: Path) -> None:
    area = polygon_area(SQUARE, square_m2(SQUARE))
    async with serve(settings, tmp_path) as client:
        _, body = await analyse(client, area)
        area_id = body["job"]["id"]
        inside = await client.get(
            f"/api/parcel/{area_id}/explain", params={"lon": -3.7002, "lat": 40.4193}
        )
        beyond = await client.get(
            f"/api/parcel/{area_id}/explain", params={"lon": -3.7030, "lat": 40.4193}
        )
    analysis = body["job"]["analysis"]
    summary = analysis["summary"]
    # The cells whose centre is inside the outline: its area in 10 m cells, give or take
    # the cells along its edge.
    expected = square_m2(SQUARE) / 100
    assert summary["cells"] == pytest.approx(expected, rel=0.05)
    west, south, east, north = analysis["bbox"]
    assert west == pytest.approx(-3.702, abs=2e-4)
    assert east == pytest.approx(-3.6985, abs=2e-4)
    assert south == pytest.approx(40.418, abs=2e-4)
    assert north == pytest.approx(40.4207, abs=2e-4)
    root = settings.parcel.jobs.output_path(tmp_path)
    with rasterio.open(region_tif(root, area_id)) as dataset:
        index = dataset.read(list(dataset.descriptions).index("index") + 1)
    assert int((~np.isnan(index)).sum()) == summary["cells"]
    assert inside.status_code == 200
    assert beyond.status_code == 404
    assert beyond.json()["code"] == "outside_grid"


async def test_an_area_astride_two_utm_zones_is_one_grid_in_its_centres_zone(
    settings: Settings, tmp_path: Path
) -> None:
    area = polygon_area(ASTRIDE, square_m2(ASTRIDE), crs="EPSG:25831", region="ES-VC")
    async with serve(settings, tmp_path) as client:
        _, body = await analyse(client, area)
        area_id = body["job"]["id"]
        west_of_meridian = await client.get(
            f"/api/parcel/{area_id}/explain", params={"lon": -0.001, "lat": 40.4193}
        )
        east_of_meridian = await client.get(
            f"/api/parcel/{area_id}/explain", params={"lon": 0.0015, "lat": 40.4193}
        )
    analysis = body["job"]["analysis"]
    assert analysis["crs"] == "EPSG:25831"
    assert analysis["summary"]["cells"] == pytest.approx(square_m2(ASTRIDE) / 100, rel=0.05)
    assert analysis["summary"]["scored_cells"] == analysis["summary"]["cells"]
    # The terrain is read from the zone-30 coverage and warped onto the zone-31 grid.
    assert west_of_meridian.status_code == 200
    assert east_of_meridian.status_code == 200
    slope = next(
        c for c in west_of_meridian.json()["estimate"]["contributions"] if c["criterion"] == "slope"
    )
    assert slope["value"]["number"] >= 0


async def test_no_cell_reaching_the_minimum_confidence_gives_no_candidates(
    tmp_path: Path,
) -> None:
    settings = parcel_settings()
    strict = settings.parcel.candidates.model_copy(update={"min_confidence": 0.99})
    settings = parcel_settings(candidates=strict)
    async with serve(settings, tmp_path) as client:
        _, body = await analyse(client, point_area())
    analysis = body["job"]["analysis"]
    assert analysis["candidates"] == []
    assert analysis["no_candidates"] == "low_confidence"
    assert analysis["summary"]["mean_index"] is not None


# ── Refusals and failures ──────────────────────────────────────────────────────────────


async def test_an_area_too_large_is_refused(tmp_path: Path) -> None:
    settings = parcel_settings(max_cells=1000)
    async with serve(settings, tmp_path) as client:
        refused = await start(client, point_area())
    assert refused.status_code == 422
    assert refused.json()["code"] == "too_large"


async def test_an_area_outside_the_terrain_coverage_is_refused(
    settings: Settings, tmp_path: Path
) -> None:
    # A point placed in the Canaries' region but far from that coverage's extent.
    area = point_area(lon=-3.70, lat=40.42, crs="EPSG:4083", region="ES-CN")
    async with serve(settings, tmp_path) as client:
        refused = await start(client, area)
        invalid = await client.post("/api/parcel", content=b'{"origin": "nowhere"}')
    assert refused.status_code == 422
    assert refused.json()["code"] == "outside_coverage"
    assert invalid.status_code == 400
    assert invalid.json()["code"] == "invalid_area"


@pytest.mark.parametrize(
    ("spain", "failure"),
    [
        (FakeSpain(fail={"mapas.igme.es": 500}), "upstream_error"),
        (FakeSpain(timeout=frozenset({"servicios.idee.es"})), "upstream_timeout"),
    ],
)
async def test_a_failed_download_fails_the_job_and_asking_again_retries(
    settings: Settings, tmp_path: Path, spain: FakeSpain, failure: str
) -> None:
    async with serve(settings, tmp_path, spain) as client:
        _, body = await analyse(client, point_area())
        area_id = body["job"]["id"]
        not_ready = await client.get(
            f"/api/parcel/{area_id}/explain", params={"lon": -3.70, "lat": 40.42}
        )
        image = await client.get(f"/api/parcel/{area_id}/layers/potential-index")
        spain.fail.clear()
        spain.timeout = frozenset()
        retried = await start(client, point_area())
        done = await settle(client, area_id)
    assert body["job"]["state"] == "failed"
    assert body["job"]["failure"] == failure
    assert body["job"]["detail"]
    assert body["job"]["analysis"] is None
    assert not_ready.status_code == 409
    assert not_ready.json()["code"] == "not_ready"
    assert image.status_code == 409
    assert retried.status_code == 202
    assert done["job"]["state"] == "done"


async def test_a_computing_failure_fails_the_job(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_spec: object) -> None:
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(parcel_service, "compute_parcel", broken)
    async with serve(settings, tmp_path) as client:
        _, body = await analyse(client, point_area())
    assert body["job"]["state"] == "failed"
    assert body["job"]["failure"] == "computing_failed"
    assert "synthetic failure" in body["job"]["detail"]


async def test_unknown_jobs_and_layers_are_refused(settings: Settings, tmp_path: Path) -> None:
    async with serve(settings, tmp_path) as client:
        _, body = await analyse(client, point_area())
        area_id = body["job"]["id"]
        unknown = await client.get("/api/parcel/0123456789abcdef")
        malformed = await client.get("/api/parcel/nothing")
        layer = await client.get(f"/api/parcel/{area_id}/layers/nothing")
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "unknown_job"
    assert malformed.status_code == 422
    assert layer.status_code == 404
    assert layer.json()["code"] == "unknown_layer"


async def test_a_finished_map_is_read_from_disk_after_a_restart(
    settings: Settings, tmp_path: Path
) -> None:
    async with serve(settings, tmp_path) as client:
        _, body = await analyse(client, point_area())
    area_id = body["job"]["id"]
    # No service answers now: the result comes from disk.
    offline = FakeSpain(fail={"mapas.igme.es": 500, "servicios.idee.es": 500})
    async with serve(settings, tmp_path, offline) as client:
        job = await client.get(f"/api/parcel/{area_id}")
        again = await start(client, point_area())
    assert job.json()["job"]["state"] == "done"
    assert again.status_code == 200
    assert again.json()["job"]["analysis"] == body["job"]["analysis"]
    assert offline.requests == []


async def test_an_unreadable_result_is_reported(settings: Settings, tmp_path: Path) -> None:
    async with serve(settings, tmp_path) as client:
        _, body = await analyse(client, point_area())
    area_id = body["job"]["id"]
    root = settings.parcel.jobs.output_path(tmp_path)
    (root / "analyses" / f"{area_id}.json").write_text("{}")
    async with serve(settings, tmp_path) as client:
        unreadable = await client.get(f"/api/parcel/{area_id}")
    assert unreadable.status_code == 500
    assert unreadable.json()["code"] == "unreadable"


# ── Validation, depth and cost from the national map and the imported levels ──────────


async def test_a_map_takes_the_national_skill_and_gives_each_candidate_depth_and_cost(
    settings: Settings, tmp_path: Path
) -> None:
    from tests.unit.test_national_build import build

    national = await build(settings, tmp_path, FakeSpain(wells=700), "-3.80,40.30,-3.55,40.55")
    (region,) = national.built
    assert region.validated == 1
    write_levels(settings, tmp_path)
    async with serve(settings, tmp_path, FakeSpain(whole_body=True)) as client:
        _, body = await analyse(client, point_area())
        analysis = body["job"]["analysis"]
        first = analysis["candidates"][0]
        explained = await client.get(
            f"/api/parcel/{body['job']['id']}/explain",
            params={"lon": first["longitude"], "lat": first["latitude"]},
        )
    (validation,) = analysis["summary"]["validation"]
    assert validation["domain"] == "ES030MSBT000"
    assert validation["state"] == "validated"
    for candidate in analysis["candidates"]:
        estimate = candidate["estimate"]
        assert estimate["validation"] == validation
        skill = next(c for c in estimate["confidence"]["components"] if c["id"] == "skill")
        assert skill["measured"]
        assert skill["value"] > 0
        depth = candidate["depth"]
        assert depth["state"] == "estimated"
        # Only the body's own piezometers, never the nearer one of another body.
        assert 560 < depth["water_table"]["elevation_m"] < 570
        assert depth["water_table"]["body"] == "ES030MSBT000"
        assert depth["depth_m"] == pytest.approx(
            depth["ground_m"] - depth["water_table"]["elevation_m"]
        )
        assert depth["karst"]  # the synthetic permeability is CARBONATADAS-ALTA
        cost = candidate["cost"]
        assert cost["currency"] == "EUR"
        assert float(cost["low"]) < float(cost["high"])
    assert explained.json()["estimate"] == first["estimate"]


async def test_a_new_import_or_build_makes_the_area_a_new_job(
    settings: Settings, tmp_path: Path
) -> None:
    async with serve(settings, tmp_path) as client:
        before = (await start(client, point_area())).json()["job"]["id"]
        write_levels(settings, tmp_path)
        after = (await start(client, point_area())).json()["job"]["id"]
    assert before != after


async def test_a_failing_legal_filter_leaves_the_map_with_candidates_not_evaluated(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken(*_args: object) -> object:
        raise RuntimeError("synthetic failure of the legal filter")

    monkeypatch.setattr("subphora.services.legal.LegalService.candidates", broken)
    async with serve(settings, tmp_path) as client:
        _started, body = await analyse(client, point_area())
    assert body["job"]["state"] == "done"
    for candidate in body["job"]["analysis"]["candidates"]:
        assert candidate["legal"]["state"] == "not_evaluated"
        assert candidate["legal"]["disclaimer"].startswith("Guidance, not legal advice")
