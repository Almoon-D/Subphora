# Copyright (c) 2026 Almoon-D. All rights reserved.
"""``subphora piezometry import``: the national piezometry database and the basin
authorities' spreadsheets (hand downloads in ``data/``) summarised per piezometer, and the
imported levels as the detailed map reads them (MASTER_PLAN §4.3, depth).

- A basin file's levels join the national piezometer of the same code; a piezometer only
  the basin file holds is added with its own coordinates and body (Júcar's code, or
  Guadiana's body name matched to a national one; unmatched, it is left out). A date
  measured by both keeps the national level.

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
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

from subphora.config import Settings
from subphora.config.depth import LevelSummary, PiezometrySettings
from subphora.domain.depth import LevelsSource
from subphora.domain.piezometry import Piezometer, PiezometryDataset
from subphora.geo.grid import transform_xy
from subphora.model.depth import PiezometerPoint
from subphora.services.basin_levels import BasinLevels, read_basin
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
class LevelsSummary:
    level: float
    low: float
    high: float
    count: int
    first: date
    last: date


def summarise(
    levels: list[tuple[date, float]], summary: LevelSummary, today: date
) -> LevelsSummary | None:
    """A piezometer's (or a well's) recent median level and seasonal range, or None (left
    out: too old, or too few recent measurements)."""
    if not levels:
        return None
    last = max(d for d, _ in levels)
    if (today - last).days > summary.max_age_years * _DAYS_PER_YEAR:
        return None
    start = last - timedelta(days=summary.recent_years * _DAYS_PER_YEAR)
    recent = [(d, v) for d, v in levels if d > start]
    if len(recent) < summary.min_measurements:
        return None
    values = np.array([v for _, v in recent], dtype=np.float64)
    low, median, high = np.quantile(values, [summary.low_quantile, 0.5, summary.high_quantile])
    return LevelsSummary(
        level=float(median),
        low=float(low),
        high=float(high),
        count=len(recent),
        first=min(d for d, _ in recent),
        last=last,
    )


@dataclass(slots=True)
class _Station:
    """A piezometer before its summary: where it is, its body, and its tagged levels."""

    id: str
    code: str
    name: str
    body: str
    body_label: str
    longitude: float
    latitude: float
    ground_m: float | None
    levels: dict[date, tuple[float, str]]

    def add(self, levels: list[tuple[date, float]], service: str) -> None:
        for day, value in levels:
            # A date measured twice keeps the first source's value (the national one).
            self.levels.setdefault(day, (value, service))


def _fold(text: str) -> str:
    """A body name compared without accents, case, spaces, punctuation or a leading
    number ("6-Mancha Occidental II") and a trailing note ("(AC. SUP)")."""
    plain = unicodedata.normalize("NFKD", text.split("(")[0]).encode("ascii", "ignore").decode()
    return "".join(ch for ch in plain.lower().lstrip("0123456789-. ") if ch.isalnum())


def import_piezometry(settings: Settings, root: Path, now: datetime) -> PiezometryDataset:
    """Read the national database and the basin files present, summarise each piezometer
    and write the result; raises PiezometryReadError when a file cannot be read."""
    piezometry = settings.piezometry
    path = piezometry.input_path(root)
    stations, read, levels_read, national = _national(piezometry, path)
    services = [piezometry.service]
    files = {piezometry.service: (path.name, national)}
    for basin in piezometry.basins:
        basin_path = basin.input if basin.input.is_absolute() else root / basin.input
        if not basin_path.is_file():
            _log.info("%s: %s not found, skipped", basin.service, basin_path)
            continue
        found = read_basin(basin, basin_path)
        files[basin.service] = (basin_path.name, sha256_of(basin_path))
        services.append(basin.service)
        levels_read += found.rows_read
        read += _join(stations, found, basin.service, basin.crs, piezometry)
    today = now.date()
    summaries = [_summarised(s, piezometry, today) for s in stations.values()]
    kept = [p for p, _ in (x for x in summaries if x is not None)]
    periods: dict[str, list[date]] = defaultdict(list)
    for _, used in (x for x in summaries if x is not None):
        for service_id, days in used.items():
            periods[service_id].extend(days)
    if not kept:
        raise ValueError("no piezometer has enough recent levels: check the files and summary")
    sources = []
    for service_id in services:
        if not periods[service_id]:
            continue
        service = settings.sources.service(service_id)
        name, digest = files[service_id]
        sources.append(
            LevelsSource(
                service_id=service.id,
                publisher=service.publisher,
                attribution=service.attribution,
                file_name=name,
                sha256=digest,
                imported_at=now,
                levels_from=min(periods[service_id]),
                levels_to=max(periods[service_id]),
            )
        )
    dataset = PiezometryDataset(
        sources=tuple(sources),
        piezometers_read=read,
        levels_read=levels_read,
        left_out=read - len(kept),
        piezometers=tuple(kept),
    )
    write_piezometry(piezometry.output_path(root), dataset)
    _log.info("%d piezometers kept of %d", len(kept), read)
    return dataset


def _national(
    settings: PiezometrySettings, path: Path
) -> tuple[dict[str, _Station], int, int, str]:
    """The national database's placed stations by code, the stations and levels read, and
    the file's sha256."""
    columns = settings.columns
    with access_file(path) as database:
        digest = sha256_of(path)
        rows = list(export_table(database, settings.tables.piezometers, settings.mdb_export))
        by_id: dict[int, list[tuple[date, float]]] = defaultdict(list)
        levels_read = 0
        for row in export_table(database, settings.tables.levels, settings.mdb_export):
            levels_read += 1
            key, when, level = (
                _id(row.get(columns.level_id)),
                _date(row.get(columns.date)),
                _number(row.get(columns.level)),
            )
            if key is not None and when is not None and level is not None:
                by_id[key].append((when, level))
    stations: dict[str, _Station] = {}
    for row in rows:
        key = _id(row.get(columns.id))
        body = _text(row, columns.body)
        zone = _id(row.get(columns.zone))
        crs = settings.zones.get(str(zone)) if zone is not None else None
        x, y = _number(row.get(columns.x)), _number(row.get(columns.y))
        if key is None or not body or body == "-" or crs is None or x is None or y is None:
            continue  # read and left out: no body or no place
        lon, lat = transform_xy(x, y, crs, _LON_LAT)
        code = _text(row, columns.code) or str(key)
        station = _Station(
            id=str(key),
            code=code,
            name=_text(row, columns.name),
            body=settings.body_code(body),
            body_label=_text(row, columns.body_label),
            longitude=lon,
            latitude=lat,
            ground_m=_number(row.get(columns.ground)),
            levels={},
        )
        station.add(by_id.get(key, []), settings.service)
        stations[code] = station
    return stations, len(rows), levels_read, digest


def _join(
    stations: dict[str, _Station],
    found: BasinLevels,
    service: str,
    crs: str,
    settings: PiezometrySettings,
) -> int:
    """Add a basin file's levels to the stations of the same code, and its other stations
    with their own place and body; returns how many new stations were read."""
    bodies = {_fold(s.body_label): s.body for s in stations.values() if s.body_label and s.body}
    added = 0
    for code, station in found.stations.items():
        levels = found.levels.get(code, [])
        known = stations.get(code)
        if known is not None:
            known.add(levels, service)
            continue
        added += 1
        body = station.body or bodies.get(_fold(station.body_label))
        if not levels or body is None:
            continue  # read and left out: no level, or a body named nowhere else
        lon, lat = transform_xy(station.x, station.y, crs, _LON_LAT)
        new = _Station(
            id=f"{service}:{code}",
            code=code,
            name=station.name,
            body=settings.body_code(body),
            body_label=station.body_label,
            longitude=lon,
            latitude=lat,
            ground_m=station.ground_m,
            levels={},
        )
        new.add(levels, service)
        stations[f"{service}:{code}"] = new
    return added


def _summarised(
    station: _Station, settings: PiezometrySettings, today: date
) -> tuple[Piezometer, dict[str, tuple[date, date]]] | None:
    """The piezometer's summary and, per source, the first and last day it gives in the
    summarised window; None when it is left out."""
    levels = [(day, value) for day, (value, _) in station.levels.items()]
    summary = summarise(levels, settings.summary, today)
    if summary is None:
        return None
    days: dict[str, list[date]] = defaultdict(list)
    for day, (_, service_id) in station.levels.items():
        if summary.first <= day <= summary.last:
            days[service_id].append(day)
    order = [settings.service, *(b.service for b in settings.basins)]
    piezometer = Piezometer(
        id=station.id,
        code=station.code,
        name=station.name,
        body=station.body,
        body_label=station.body_label,
        longitude=station.longitude,
        latitude=station.latitude,
        ground_m=station.ground_m,
        level_m=summary.level,
        level_low_m=summary.low,
        level_high_m=summary.high,
        measurements=summary.count,
        first=summary.first,
        last=summary.last,
        sources=tuple(s for s in order if s in days),
    )
    return piezometer, {s: (min(d), max(d)) for s, d in days.items()}


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
                    sources=p.sources,
                )
            )
    return points
