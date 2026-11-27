# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Areas of interest and settings for the detailed-map tests, on the synthetic Spain of
``national_support`` (public, made-up places: hard rule 6)."""

from collections.abc import AsyncIterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from pyproj import Transformer

from subphora.api import create_app
from subphora.config import Settings
from subphora.domain.aoi import AoiOrigin, AreaOfInterest
from subphora.domain.provenance import Provenance
from tests.national_support import FakeSpain, small_settings
from tests.support import signed_in

SOURCE = Provenance(
    service_id="sigpac-queries",
    publisher="Test",
    attribution="Test",
    retrieved_at=datetime(2026, 11, 25, tzinfo=UTC),
)


def parcel_settings(**parcel: Any) -> Settings:
    """The real configuration with no waiting, at 10 m (fewer cells), a 100 m disc around
    a point, and the page asked to poll at once."""
    settings = small_settings()
    current = settings.parcel
    update: dict[str, Any] = {
        "resolution_m": 10.0,
        "point_radius_m": 100.0,
        "jobs": current.jobs.model_copy(update={"poll_after_s": 0.01}),
        **parcel,
    }
    return settings.model_copy(update={"parcel": current.model_copy(update=update)})


def _local(lon: float, lat: float, crs: str) -> dict[str, Any]:
    x, y = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform(lon, lat)
    return {"crs": crs, "x": x, "y": y}


def point_area(
    lon: float = -3.70, lat: float = 40.42, crs: str = "EPSG:25830", region: str = "ES-MD"
) -> AreaOfInterest:
    return AreaOfInterest.model_validate(
        {
            "origin": AoiOrigin.COORDINATES,
            "label": f"{lat}, {lon}",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "bbox": [lon, lat, lon, lat],
            "centre": [lon, lat],
            "centre_local": _local(lon, lat, crs),
            "area_m2": None,
            "municipality": None,
            "province": "Test",
            "province_code": "ES-M",
            "region_code": region,
            "land_checked": True,
            "sources": [SOURCE.model_dump()],
        }
    )


def polygon_area(
    ring: Sequence[tuple[float, float]],
    area_m2: float,
    crs: str = "EPSG:25830",
    region: str = "ES-MD",
) -> AreaOfInterest:
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    centre = ((min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2)
    return AreaOfInterest.model_validate(
        {
            "origin": AoiOrigin.DRAWN_POLYGON,
            "label": None,
            "geometry": {"type": "MultiPolygon", "coordinates": [[[list(p) for p in ring]]]},
            "bbox": [min(lons), min(lats), max(lons), max(lats)],
            "centre": list(centre),
            "centre_local": _local(*centre, crs),
            "area_m2": area_m2,
            "municipality": None,
            "province": "Test",
            "province_code": "ES-M",
            "region_code": region,
            "land_checked": True,
            "sources": [SOURCE.model_dump()],
        }
    )


@asynccontextmanager
async def serve(
    settings: Settings, root: Path, spain: FakeSpain | None = None
) -> AsyncIterator[httpx.AsyncClient]:
    """The API on the synthetic Spain, its detailed maps computed in a thread."""
    transport = (spain or FakeSpain()).transport()
    with ThreadPoolExecutor(max_workers=1) as executor:
        app = create_app(settings, root=root, transport=transport, executor=executor)
        async with app.router.lifespan_context(app), signed_in(app, settings, root) as client:
            yield client


def write_levels(settings: Settings, root: Path) -> None:
    """Two piezometers of the synthetic body near Madrid, and one of another body nearer."""
    from datetime import UTC, date, datetime

    from subphora.domain.depth import LevelsSource
    from subphora.domain.piezometry import Piezometer, PiezometryDataset
    from subphora.store.piezometry import write_piezometry

    def piezometer(key: int, lon: float, level: float, body: str) -> Piezometer:
        return Piezometer(
            id=str(key),
            code=str(key),
            name="Synthetic",
            body=body,
            body_label="Synthetic body",
            longitude=lon,
            latitude=40.42,
            ground_m=None,
            level_m=level,
            level_low_m=level - 1,
            level_high_m=level + 1,
            measurements=12,
            first=date(2024, 1, 1),
            last=date(2024, 12, 1),
            sources=("miteco-piezometry-db",),
        )

    write_piezometry(
        settings.piezometry.output_path(root),
        PiezometryDataset(
            sources=(
                LevelsSource(
                    service_id="miteco-piezometry-db",
                    publisher="MITECO",
                    attribution="MITECO",
                    file_name="basedatospiezometria.zip",
                    imported_at=datetime(2026, 11, 26, tzinfo=UTC),
                    levels_from=date(2024, 1, 1),
                    levels_to=date(2024, 12, 1),
                    sha256="0" * 64,
                ),
            ),
            piezometers_read=3,
            levels_read=36,
            left_out=0,
            piezometers=(
                piezometer(1, -3.71, 560.0, "ES030MSBT000"),
                piezometer(2, -3.69, 570.0, "ES030MSBT000"),
                piezometer(3, -3.7001, 300.0, "ES099MSBT999"),
            ),
        ),
    )
