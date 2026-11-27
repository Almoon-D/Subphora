# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Reading the owner's existing well records from a CSV file (decision 0040).

- A file holds one row per well, or one per water-level reading with the well's columns
  repeated; rows of the same well (the same id, or else the same name) must agree on what
  they both state about it.
- Columns are found by any of their configured names, ignoring case, spaces and accents,
  so a Spanish spreadsheet's headers work as they are. The delimiter is sniffed (comma,
  semicolon or tab); with a semicolon, numbers may use a decimal comma.
- A position is longitude and latitude in degrees, or x and y in the CRS whose EPSG code
  the row gives.
- A reading's level is below the ground unless its reference column names the top of the
  casing, whose height above the ground is given; who read it and the pump's state are
  read from their words, and are "unknown" when blank.
- Ids are stable: a well without one gets a UUID made from its name, and a reading one made
  from its well and time, so importing the same file again changes nothing.
- An error names the row and the column, never the value (a record is private).
"""

import csv
import io
import math
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from pyproj.exceptions import ProjError

from subphora.config.wells import CsvSettings, WellsSettings
from subphora.domain.wells import (
    LevelReference,
    MeasuredBy,
    PumpState,
    Well,
    WellOutcome,
    WellReading,
    WellsError,
    WellsFailure,
)
from subphora.geo.grid import transform_xy

# The namespace of the ids made for wells and readings that come without one.
_NAMESPACE = uuid.UUID("6f1c2b0e-8f4a-5d6e-9b7c-3a2d1e0f4c5b")
_LON_LAT = "EPSG:4326"
_DELIMITERS = ",;\t"
_SAMPLE = 8192
# The well's own columns (the rest are a reading's).
_WELL_COLUMNS = ("longitude", "latitude", "depth_m", "flow_l_s", "outcome", "drilled_on", "note")
# A reading's columns besides its date and level.
_READING_DETAILS = ("reference", "reference_height_m", "measured_by", "pump", "pump_minutes")


@dataclass(slots=True)
class ParsedImport:
    rows: int = 0
    wells: list[tuple[int, Well]] = field(default_factory=list)
    readings: list[tuple[int, WellReading]] = field(default_factory=list)


def normalise(text: str) -> str:
    """Lower case, no accents, single underscores for spaces and hyphens."""
    decomposed = unicodedata.normalize("NFKD", text.strip().casefold())
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return "_".join(plain.replace("-", " ").split())


def stable_id(*parts: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, "/".join(parts)))


def _decode(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Spreadsheets saved as CSV on Windows in Spain write Windows-1252.
        return content.decode("cp1252", errors="strict")


def _delimiter(text: str) -> str:
    try:
        return csv.Sniffer().sniff(text[:_SAMPLE], delimiters=_DELIMITERS).delimiter
    except csv.Error:
        return ","


class _Row:
    def __init__(
        self, number: int, values: dict[str, str], settings: CsvSettings, decimal_comma: bool
    ) -> None:
        self.number = number
        self._values = values
        self._settings = settings
        self._decimal_comma = decimal_comma

    def fail(self, column: str, what: str) -> WellsError:
        return WellsError(WellsFailure.INVALID_CSV, f"row {self.number}: {column} {what}")

    def text(self, column: str) -> str | None:
        value = self._values.get(column, "").strip()
        return value or None

    def number_of(self, column: str) -> float | None:
        value = self.text(column)
        if value is None:
            return None
        if self._decimal_comma and "," in value:
            value = value.replace(".", "").replace(",", ".")
        try:
            number = float(value)
        except ValueError as exc:
            raise self.fail(column, "is not a number") from exc
        if not math.isfinite(number):
            raise self.fail(column, "is not a finite number")
        return number

    def date_of(self, column: str) -> date | None:
        value = self.text(column)
        if value is None:
            return None
        for pattern in self._settings.date_formats:
            try:
                return datetime.strptime(value, pattern).date()
            except ValueError:
                continue
        raise self.fail(column, "is not a date in a known format")

    def time_of(self, column: str) -> datetime | None:
        value = self.text(column)
        if value is None:
            return None
        zone = ZoneInfo(self._settings.timezone)
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            parsed = None
            for pattern in self._settings.datetime_formats:
                try:
                    parsed = datetime.strptime(value, pattern)
                    break
                except ValueError:
                    continue
        if parsed is None:
            day = self.date_of(column)
            if day is None:  # pragma: no cover - text() was not None
                return None
            parsed = datetime(day.year, day.month, day.day)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=zone)

    def outcome(self) -> WellOutcome:
        word = self.text("outcome")
        if word is None:
            flow = self.number_of("flow_l_s")
            if flow is None:
                return WellOutcome.UNKNOWN
            if flow > self._settings.productive_above_l_s:
                return WellOutcome.PRODUCTIVE
            return WellOutcome.DRY if flow == 0 else WellOutcome.UNKNOWN
        key = normalise(word)
        words = self._settings.outcomes
        for outcome, names in (
            (WellOutcome.PRODUCTIVE, words.productive),
            (WellOutcome.DRY, words.dry),
            (WellOutcome.UNKNOWN, words.unknown),
        ):
            if key in {normalise(n) for n in names}:
                return outcome
        raise self.fail("outcome", "is not a known outcome")

    def word_of[T](self, column: str, words: dict[T, list[str]]) -> T | None:
        """The value a column's word stands for; None when it is blank."""
        word = self.text(column)
        if word is None:
            return None
        key = normalise(word)
        for value, names in words.items():
            if key in {normalise(n) for n in names}:
                return value
        raise self.fail(column, "is not a known word")

    def position(self) -> tuple[float, float]:
        lon, lat = self.number_of("longitude"), self.number_of("latitude")
        if lon is not None and lat is not None:
            return lon, lat
        x, y, crs = self.number_of("x"), self.number_of("y"), self.text("crs")
        if x is None or y is None or crs is None:
            raise self.fail("position", "is missing: longitude and latitude, or x, y and crs")
        code = crs.upper().removeprefix("EPSG:").strip()
        if not code.isdigit():
            raise self.fail("crs", "is not an EPSG code")
        try:
            return transform_xy(x, y, f"EPSG:{code}", _LON_LAT)
        except ProjError as exc:
            raise self.fail("position", "cannot be read in that CRS") from exc


def _columns(header: list[str], settings: CsvSettings) -> dict[int, str]:
    """Each header's column, by its index; refuses a file without a name or a position."""
    names = {normalise(n): column for column, aliases in settings.columns.items() for n in aliases}
    found: dict[int, str] = {}
    for index, title in enumerate(header):
        column = names.get(normalise(title))
        if column is not None and column not in found.values():
            found[index] = column
    present = set(found.values())
    if "name" not in present and "id" not in present:
        raise WellsError(WellsFailure.INVALID_CSV, "the file has no column for the well's name")
    if not ({"longitude", "latitude"} <= present or {"x", "y", "crs"} <= present):
        raise WellsError(
            WellsFailure.INVALID_CSV,
            "the file has no position columns: longitude and latitude, or x, y and crs",
        )
    return found


def parse_wells_csv(content: bytes, settings: WellsSettings) -> ParsedImport:
    """The wells and readings of a CSV file; raises WellsError naming the first bad row."""
    options = settings.csv
    if len(content) > options.max_bytes:
        raise WellsError(WellsFailure.TOO_LARGE, f"a file has at most {options.max_bytes} bytes")
    try:
        text = _decode(content)
    except UnicodeDecodeError as exc:
        raise WellsError(WellsFailure.INVALID_CSV, "the file is not text") from exc
    delimiter = _delimiter(text)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration as exc:
        raise WellsError(WellsFailure.INVALID_CSV, "the file is empty") from exc
    columns = _columns(header, options)
    parsed = ParsedImport()
    seen: dict[str, tuple[int, dict[str, Any]]] = {}
    try:
        for number, cells in enumerate(reader, start=2):
            if not any(cell.strip() for cell in cells):
                continue
            parsed.rows += 1
            if parsed.rows > options.max_rows:
                raise WellsError(
                    WellsFailure.TOO_LARGE, f"a file has at most {options.max_rows} rows"
                )
            values = {columns[i]: cell for i, cell in enumerate(cells) if i in columns}
            _read_row(_Row(number, values, options, delimiter == ";"), settings, seen, parsed)
    except csv.Error as exc:
        raise WellsError(WellsFailure.INVALID_CSV, f"row {reader.line_num}: not valid CSV") from exc
    return parsed


def _read_row(
    row: _Row,
    settings: WellsSettings,
    seen: dict[str, tuple[int, dict[str, Any]]],
    parsed: ParsedImport,
) -> None:
    name = row.text("name")
    given_id = row.text("id")
    if name is None and given_id is None:
        raise row.fail("name", "is missing")
    if name is not None and len(name) > settings.name_max_chars:
        raise row.fail("name", f"is longer than {settings.name_max_chars} characters")
    note = row.text("note")
    if note is not None and len(note) > settings.note_max_chars:
        raise row.fail("note", f"is longer than {settings.note_max_chars} characters")
    well_id = given_id.lower() if given_id is not None else stable_id("well", normalise(name or ""))
    longitude, latitude = row.position()
    fields: dict[str, Any] = {
        "id": well_id,
        "name": name or well_id,
        "longitude": round(longitude, 7),
        "latitude": round(latitude, 7),
        "depth_m": row.number_of("depth_m"),
        "flow_l_s": row.number_of("flow_l_s"),
        "outcome": row.outcome(),
        "drilled_on": row.date_of("drilled_on"),
        "note": note,
    }
    earlier = seen.get(well_id)
    if earlier is None:
        try:
            well = Well.model_validate(fields)
        except ValidationError as exc:
            where = ".".join(str(part) for part in exc.errors()[0]["loc"])
            raise row.fail(where or "the well", "is not valid") from exc
        seen[well_id] = (row.number, fields)
        parsed.wells.append((row.number, well))
    else:
        first_row, first = earlier
        for column in ("name", *_WELL_COLUMNS):
            stated = row.text(column) is not None or column in {"longitude", "latitude"}
            if stated and fields[column] != first[column]:
                raise row.fail(column, f"differs from row {first_row} for the same well")
    measured_at = row.time_of("measured_at")
    level = row.number_of("depth_to_water_m")
    if (measured_at is None) != (level is None):
        raise row.fail("reading", "needs both its date and its level")
    if measured_at is not None and level is not None:
        parsed.readings.append(
            (row.number, _reading(row, settings.csv, well_id, measured_at, level))
        )
    elif any(row.text(c) is not None for c in _READING_DETAILS):
        raise row.fail("reading", "has details but no date and level")


def _reading(
    row: _Row, options: CsvSettings, well_id: str, measured_at: datetime, level: float
) -> WellReading:
    reference = row.word_of(
        "reference",
        {
            LevelReference.GROUND: options.references.ground,
            LevelReference.CASING_TOP: options.references.casing_top,
        },
    )
    measured_by = row.word_of(
        "measured_by",
        {
            MeasuredBy.OWNER: options.measured_by.owner,
            MeasuredBy.DRILLER: options.measured_by.driller,
            MeasuredBy.CONTRACTOR: options.measured_by.contractor,
        },
    )
    pump = row.word_of(
        "pump", {PumpState.STOPPED: options.pump.stopped, PumpState.RUNNING: options.pump.running}
    )
    minutes = row.number_of("pump_minutes")
    if minutes is not None and (minutes < 0 or minutes != int(minutes)):
        raise row.fail("pump_minutes", "is not a whole number of minutes")
    try:
        return WellReading(
            id=stable_id("reading", well_id, measured_at.astimezone(UTC).isoformat()),
            well_id=well_id,
            measured_at=measured_at,
            depth_to_water_m=level,
            reference=reference or LevelReference.GROUND,
            reference_height_m=row.number_of("reference_height_m") or 0.0,
            measured_by=measured_by or MeasuredBy.UNKNOWN,
            pump=pump or PumpState.UNKNOWN,
            pump_minutes=None if minutes is None else int(minutes),
        )
    except ValidationError as exc:
        raise row.fail("reading", "states its reference or pump inconsistently") from exc
