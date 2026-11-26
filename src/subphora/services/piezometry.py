# Copyright (c) 2026 Almoon-D. All rights reserved.
"""``subphora piezometry import``: the national piezometry database (a hand download in
``data/``) summarised per piezometer, and the imported levels as the detailed map reads
them (MASTER_PLAN §4.3, depth).

- A level is the water-table elevation (m a.s.l.) of a measurement; rows without one,
  without a date or for an unknown piezometer are skipped.
- A piezometer keeps the median of its levels over the ``recent_years`` before its last
  measurement, with the configured quantiles as its seasonal range; it is left out with
  too few measurements there, a last one older than ``max_age_years``, no monitored body
  or no coordinates in a known UTM zone. Nothing is filled in.
- Coordinates follow the row's UTM zone (30 or 31), whatever the column names say.
"""

import logging
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

from subphora.config import Settings
from subphora.config.depth import PiezometrySettings
from subphora.domain.depth import LevelsSource
from subphora.domain.piezometry import Piezometer, PiezometryDataset
from subphora.geo.grid import transform_xy
from subphora.model.depth import PiezometerPoint
from subphora.sources.piezometry import access_file, export_table, sha256_of
from subphora.store.piezometry import write_piezometry

_log = logging.getLogger(__name__)
_LON_LAT = "EPSG:4326"
_DAYS_PER_YEAR = 365.25


def _number(text: str | None) -> float | None:
    if text is None or not text.strip():
        return None
    try:
        value = float(text.strip().replace(",", "."))
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _date(text: str | None) -> date | None:
    if not text:
        return None
    try:
        return date.fromisoformat(text.strip()[:10])
    except ValueError:
        return None


def _id(text: str | None) -> int | None:
    value = _number(text)
    return None if value is None or not value.is_integer() else int(value)


def _text(row: dict[str, str], column: str) -> str:
    return (row.get(column) or "").strip()


@dataclass(frozen=True, slots=True)
class _Summary:
    level: float
    low: float
    high: float
    count: int
    first: date
    last: date


def summarise(
    levels: list[tuple[date, float]], settings: PiezometrySettings, today: date
) -> _Summary | None:
    """A piezometer's recent median level and seasonal range, or None (left out)."""
    if not levels:
        return None
    summary = settings.summary
    last = max(d for d, _ in levels)
    if (today - last).days > summary.max_age_years * _DAYS_PER_YEAR:
        return None
    start = last - timedelta(days=summary.recent_years * _DAYS_PER_YEAR)
    recent = [(d, v) for d, v in levels if d > start]
    if len(recent) < summary.min_measurements:
        return None
    values = np.array([v for _, v in recent], dtype=np.float64)
    low, median, high = np.quantile(values, [summary.low_quantile, 0.5, summary.high_quantile])
    return _Summary(
        level=float(median),
        low=float(low),
        high=float(high),
        count=len(recent),
        first=min(d for d, _ in recent),
        last=last,
    )


def import_piezometry(settings: Settings, root: Path, now: datetime) -> PiezometryDataset:
    """Read the database, summarise each piezometer and write the result; raises
    PiezometryReadError when the file cannot be read."""
    piezometry = settings.piezometry
    columns = piezometry.columns
    path = piezometry.input_path(root)
    with access_file(path) as database:
        digest = sha256_of(path)
        stations = list(
            export_table(database, piezometry.tables.piezometers, piezometry.mdb_export)
        )
        by_id: dict[int, list[tuple[date, float]]] = defaultdict(list)
        levels_read = 0
        for row in export_table(database, piezometry.tables.levels, piezometry.mdb_export):
            levels_read += 1
            key, when, level = (
                _id(row.get(columns.level_id)),
                _date(row.get(columns.date)),
                _number(row.get(columns.level)),
            )
            if key is not None and when is not None and level is not None:
                by_id[key].append((when, level))
    today = now.date()
    kept: list[Piezometer] = []
    for row in stations:
        piezometer = _piezometer(row, by_id, piezometry, today)
        if piezometer is not None:
            kept.append(piezometer)
    if not kept:
        raise ValueError("no piezometer has enough recent levels: check the file and summary")
    service = settings.sources.service(piezometry.service)
    dataset = PiezometryDataset(
        source=LevelsSource(
            service_id=service.id,
            publisher=service.publisher,
            attribution=service.attribution,
            file_name=path.name,
            imported_at=now,
            levels_from=min(p.first for p in kept),
            levels_to=max(p.last for p in kept),
        ),
        sha256=digest,
        piezometers_read=len(stations),
        levels_read=levels_read,
        left_out=len(stations) - len(kept),
        piezometers=tuple(kept),
    )
    write_piezometry(piezometry.output_path(root), dataset)
    _log.info("%d piezometers kept of %d", len(kept), len(stations))
    return dataset


def _piezometer(
    row: dict[str, str],
    levels: dict[int, list[tuple[date, float]]],
    settings: PiezometrySettings,
    today: date,
) -> Piezometer | None:
    columns = settings.columns
    key = _id(row.get(columns.id))
    body = _text(row, columns.body)
    zone = _id(row.get(columns.zone))
    crs = settings.zones.get(str(zone)) if zone is not None else None
    x, y = _number(row.get(columns.x)), _number(row.get(columns.y))
    if key is None or not body or body == "-" or crs is None or x is None or y is None:
        return None
    summary = summarise(levels.get(key, []), settings, today)
    if summary is None:
        return None
    lon, lat = transform_xy(x, y, crs, _LON_LAT)
    return Piezometer(
        id=key,
        code=_text(row, columns.code) or str(key),
        name=_text(row, columns.name),
        body=body,
        body_label=_text(row, columns.body_label),
        longitude=lon,
        latitude=lat,
        ground_m=_number(row.get(columns.ground)),
        level_m=summary.level,
        level_low_m=summary.low,
        level_high_m=summary.high,
        measurements=summary.count,
        first=summary.first,
        last=summary.last,
    )


def piezometer_points(
    dataset: PiezometryDataset, crs: str, bounds: tuple[float, float, float, float], reach_m: float
) -> list[PiezometerPoint]:
    """The piezometers within ``reach_m`` of ``bounds`` (in ``crs``), projected there."""
    west, south, east, north = bounds
    points = []
    for p in dataset.piezometers:
        x, y = transform_xy(p.longitude, p.latitude, _LON_LAT, crs)
        if west - reach_m <= x <= east + reach_m and south - reach_m <= y <= north + reach_m:
            points.append(
                PiezometerPoint(
                    x=x,
                    y=y,
                    body=p.body,
                    level_m=p.level_m,
                    low_m=p.level_low_m,
                    high_m=p.level_high_m,
                )
            )
    return points
