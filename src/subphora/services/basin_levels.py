# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The basin authorities' piezometric spreadsheets, hand downloads into ``data/`` that
``subphora piezometry import`` joins to the national database (MASTER_PLAN §4.3, depth;
docs/knowledge/water-authorities.md).

- CH Júcar (``chj_f71``): a zip with the control points (code, name, ETRS89 UTM, the body
  of the 2022 plan) and several workbooks of field measurements; the static level, in m
  above sea level, is read.
- CH Guadiana (``guadiana_monthly_depths``): one row per piezometer and one column per
  month holding the depth to water below the ground; the stations sheet's ground elevation
  turns it into a level. A cell that is not a number (a note, an empty month) is skipped.

Each reader returns its stations and levels by piezometer code; nothing is filled in.
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from subphora.config.depth import BasinSettings, ChjBasin, GuadianaBasin
from subphora.sources.piezometry import PiezometryReadError, workbook_rows, zip_members


@dataclass(frozen=True, slots=True)
class BasinStation:
    code: str
    name: str
    x: float
    y: float
    ground_m: float | None
    # The EU code of its body when the file states one; else only the body's name.
    body: str | None
    body_label: str


@dataclass(slots=True)
class BasinLevels:
    stations: dict[str, BasinStation] = field(default_factory=dict)
    levels: dict[str, list[tuple[date, float]]] = field(default_factory=lambda: defaultdict(list))
    # Measurement rows (Júcar) or filled month cells (Guadiana) read.
    rows_read: int = 0


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            value = float(value.strip().replace(",", "."))
        except ValueError:
            return None
    number = float(value)
    return number if math.isfinite(number) else None


def _day(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _header(row: tuple[object, ...]) -> dict[str, int]:
    return {_text(cell): index for index, cell in enumerate(row) if _text(cell)}


def _columns(header: dict[str, int], wanted: dict[str, str], where: str) -> dict[str, int]:
    missing = sorted(column for column in wanted.values() if column not in header)
    if missing:
        raise PiezometryReadError(f"{where} lacks the columns {missing}")
    return {key: header[column] for key, column in wanted.items()}


def read_basin(basin: BasinSettings, path: Path) -> BasinLevels:
    """The stations and levels of one basin file; raises PiezometryReadError when it
    cannot be read as configured."""
    if isinstance(basin, ChjBasin):
        return _read_chj(basin, path)
    return _read_guadiana(basin, path)


def _read_chj(basin: ChjBasin, path: Path) -> BasinLevels:
    names = {k: v for k, v in basin.columns.model_dump().items() if k not in {"date", "level"}}
    result = BasinLevels()
    rows = workbook_rows(path, member=basin.stations_member)
    index = _columns(_header(next(rows, ())), names, basin.stations_member)
    for row in rows:
        code = _text(row[index["code"]])
        x, y = _number(row[index["x"]]), _number(row[index["y"]])
        if not code or x is None or y is None:
            continue
        body = _text(row[index["body"]])
        result.stations[code] = BasinStation(
            code=code,
            name=_text(row[index["name"]]),
            x=x,
            y=y,
            ground_m=None,
            body=basin.body_prefix + body if body else None,
            body_label=_text(row[index["body_label"]]),
        )
    members = zip_members(path, basin.levels_members)
    if not members:
        raise PiezometryReadError(f"{path.name} holds no {basin.levels_members!r}")
    wanted = {"code": basin.columns.code, "date": basin.columns.date, "level": basin.columns.level}
    for member in members:
        rows = workbook_rows(path, member=member)
        index = _columns(_header(next(rows, ())), wanted, member)
        for row in rows:
            result.rows_read += 1
            code, when = _text(row[index["code"]]), _day(row[index["date"]])
            level = _number(row[index["level"]])
            if code and when is not None and level is not None:
                result.levels[code].append((when, level))
    return result


def _read_guadiana(basin: GuadianaBasin, path: Path) -> BasinLevels:
    columns = basin.columns
    result = BasinLevels()
    rows = workbook_rows(path, sheet=basin.stations_sheet)
    wanted = {
        "code": columns.station_code,
        "x": columns.x,
        "y": columns.y,
        "ground": columns.ground,
        "body_label": columns.body_label,
    }
    index = _columns(_header(next(rows, ())), wanted, basin.stations_sheet)
    for row in rows:
        code = _text(row[index["code"]])
        x, y = _number(row[index["x"]]), _number(row[index["y"]])
        if not code or x is None or y is None:
            continue
        result.stations[code] = BasinStation(
            code=code,
            name="",
            x=x,
            y=y,
            ground_m=_number(row[index["ground"]]),
            body=None,
            body_label=_text(row[index["body_label"]]),
        )
    rows = workbook_rows(path, sheet=basin.levels_sheet)
    header: tuple[object, ...] = ()
    for _ in range(basin.header_row):
        header = next(rows, ())
    code_at = _columns(_header(header), {"code": columns.code}, basin.levels_sheet)
    months = [(i, d) for i, cell in enumerate(header) if (d := _day(cell)) is not None]
    if not months:
        raise PiezometryReadError(f"{basin.levels_sheet}: row {basin.header_row} has no months")
    for row in rows:
        code = _text(row[code_at["code"]]) if len(row) > code_at["code"] else ""
        station = result.stations.get(code)
        if station is None:
            continue
        for column, month in months:
            if column >= len(row):
                break
            if row[column] is None:
                continue
            result.rows_read += 1
            depth = _number(row[column])
            # A depth needs the ground elevation to become a level; none is guessed.
            if depth is not None and station.ground_m is not None:
                result.levels[code].append((month, station.ground_m - depth))
    return result
