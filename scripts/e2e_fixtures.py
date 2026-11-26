# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Regenerate the API answers in web/e2e/fixtures/ that come from the synthetic Spain of
tests/national_support.py (no network): ``uv run python scripts/e2e_fixtures.py``.

- A national build of two synthetic boxes, in Madrid and around Daimiel, with productive
  boreholes along their valley floors: ``national.json`` and ``explain-madrid.json``.
- Synthetic piezometric levels near Daimiel (made-up values, public place).
- The detailed maps of the Daimiel point and the Campos enclosure on that synthetic Spain:
  ``parcel-queued.json``, ``parcel-daimiel.json``, ``explain-parcel-daimiel.json`` and
  ``parcel-campos.json``. Campos lies outside both boxes and far from every piezometer.
- The cross-section under a 1.2 km line running east through the Daimiel point, across the
  synthetic fault: ``section-daimiel.json``.

The fixtures recorded from real services (areas, search, map) are not touched.
"""

import asyncio
import json
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
from pyproj import Transformer  # noqa: E402

from subphora import __version__  # noqa: E402
from subphora.api import create_app  # noqa: E402
from subphora.domain.depth import LevelsSource  # noqa: E402
from subphora.domain.piezometry import Piezometer, PiezometryDataset  # noqa: E402
from subphora.services.national import NationalBuilder, resolve_region  # noqa: E402
from subphora.sources import CatalogueClient  # noqa: E402
from subphora.store import FileCache  # noqa: E402
from subphora.store.piezometry import write_piezometry  # noqa: E402
from tests.national_support import FakeSpain, small_settings, terrain_elevation  # noqa: E402

FIXTURES = ROOT / "web" / "e2e" / "fixtures"
BOXES = ("-3.80,40.30,-3.55,40.55", "-3.75,38.85,-3.50,39.30")
# The water table under the synthetic terrain (tests/national_support.py's valley).
DEPTH_BELOW_GROUND_M = 45.0
WELL_SPACING_M = 700.0
# A 1.2 km line running east through the Daimiel point (area-point-daimiel.json).
SECTION_LINE = {"start": [-3.6184, 39.0675], "end": [-3.6046, 39.0675]}


def _levels(root: Path, path: Path) -> None:
    to_valley = Transformer.from_crs("EPSG:4326", "EPSG:25830", always_xy=True)

    def piezometer(key: int, lon: float, lat: float) -> Piezometer:
        x, y = to_valley.transform(lon, lat)
        level = terrain_elevation(x, y) - DEPTH_BELOW_GROUND_M
        return Piezometer(
            id=str(key),
            code=f"SYN.{key}",
            name="Synthetic piezometer",
            body="ES030MSBT000",
            body_label="Synthetic body",
            longitude=lon,
            latitude=lat,
            ground_m=None,
            level_m=level,
            level_low_m=level - 1.5,
            level_high_m=level + 1.5,
            measurements=24,
            first=date(2023, 1, 15),
            last=date(2024, 12, 15),
            sources=("miteco-piezometry-db",),
        )

    write_piezometry(
        root / path,
        PiezometryDataset(
            sources=(
                LevelsSource(
                    service_id="miteco-piezometry-db",
                    publisher=(
                        "Ministerio para la Transición Ecológica y el Reto Demográfico (MITECO)"
                    ),
                    attribution="© MITECO, Red de seguimiento del estado cuantitativo",
                    file_name="basedatospiezometria.zip",
                    imported_at=datetime(2026, 11, 26, tzinfo=UTC),
                    levels_from=date(2023, 1, 15),
                    levels_to=date(2024, 12, 15),
                    sha256="0" * 64,
                ),
            ),
            piezometers_read=2,
            levels_read=48,
            left_out=0,
            piezometers=(
                piezometer(1, -3.625, 39.06),
                piezometer(2, -3.60, 39.075),
            ),
        ),
    )


def _write(name: str, body: Any) -> None:
    (FIXTURES / name).write_text(
        json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


async def _settle(client: httpx.AsyncClient, area_id: str) -> dict[str, Any]:
    while True:
        body: dict[str, Any] = (await client.get(f"/api/parcel/{area_id}")).json()
        if body["job"]["state"] in {"done", "failed"}:
            return body
        await asyncio.sleep(0.05)


async def section(api: httpx.AsyncClient) -> None:
    answer = await api.post("/api/section", json=SECTION_LINE)
    answer.raise_for_status()
    _write("section-daimiel.json", answer.json())


async def main(root: Path) -> None:
    settings = small_settings()
    spain = FakeSpain(wells=WELL_SPACING_M)
    regions = [r for spec in BOXES for r in resolve_region(settings, spec)]
    async with CatalogueClient(settings.sources, __version__, spain.transport()) as client:
        builder = NationalBuilder(client, settings, FileCache(root / "cache"), root)
        with ThreadPoolExecutor(max_workers=2) as executor:
            report = await builder.build(regions, executor, 2)
    if report.failed:
        raise SystemExit(f"the build failed: {report.failed}")
    _levels(root, settings.piezometry.output)
    point = json.loads((FIXTURES / "area-point-daimiel.json").read_text(encoding="utf-8"))
    campos = json.loads((FIXTURES / "area-sigpac-campos.json").read_text(encoding="utf-8"))
    transport = FakeSpain(whole_body=True).transport()
    with ThreadPoolExecutor(max_workers=1) as executor:
        app = create_app(settings, root=root, transport=transport, executor=executor)
        async with app.router.lifespan_context(app):
            asgi = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=asgi, base_url="http://test") as api:
                _write("national.json", (await api.get("/api/national")).json())
                explained = await api.get(
                    "/api/national/explain", params={"lon": -3.70, "lat": 40.42}
                )
                _write("explain-madrid.json", explained.json())
                queued = (await api.post("/api/parcel", json=point)).json()
                _write("parcel-queued.json", queued)
                daimiel = await _settle(api, queued["job"]["id"])
                _write("parcel-daimiel.json", daimiel)
                first = daimiel["job"]["analysis"]["candidates"][0]
                tapped = await api.get(
                    f"/api/parcel/{queued['job']['id']}/explain",
                    params={"lon": first["longitude"], "lat": first["latitude"]},
                )
                _write("explain-parcel-daimiel.json", tapped.json())
                started = (await api.post("/api/parcel", json=campos)).json()
                _write("parcel-campos.json", await _settle(api, started["job"]["id"]))
                await section(api)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as folder:
        asyncio.run(main(Path(folder)))
