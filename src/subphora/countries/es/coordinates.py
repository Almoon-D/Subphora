# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Coordinates as people in Spain type them: degrees or UTM, decimal point or comma.

- Degrees: decimal (``40.4168, -3.7038`` or ``40,4168 -3,7038``), degrees and minutes, or
  degrees, minutes and seconds (``40°25'0.5"N 3°42'13.7"W``), the hemisphere as a sign or
  a letter before or after (N, S, E, and W or O for "oeste"). Without letters the order
  is unknown: both readings are returned, and the caller keeps those that fall in Spain.
- UTM: the zone, its latitude band if any (``30S``, ``30T``; ``N`` for north), an easting of
  six digits and a northing of seven, in either order. Without a zone every zone is
  returned, and the caller keeps those that fall in Spain. Words such as UTM, huso, X or Y
  are ignored.
- A comma is a decimal comma between two digits, unless a point is used for decimals, the
  text holds a semicolon, or one comma alone separates two numbers.

Degrees are WGS 84, as a GPS gives them (ETRS89 differs by less than a metre). Parsing
raises ``SearchError`` with MALFORMED_COORDINATES or WRONG_UTM_ZONE; whether the point is
in Spain is the caller's check, after conversion.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from subphora.countries.es.crs import UTM_BANDS
from subphora.domain.aoi import SearchError, SearchFailure

# Longitude, latitude in WGS 84 (GeoJSON order); pyproj's name for it.
LON_LAT = "OGC:CRS84"
# A UTM easting lies within 500 km of the zone's false easting: six digits. A northing in
# Spain (27° N and up) has seven. A value at or above this is a UTM value, not degrees.
_PROJECTED_MIN = 1000.0
_EASTING_RANGE = (100_000.0, 999_999.0)
_NORTHING_MIN = 1_000_000.0
_UTM_ZONE_RANGE = (1, 60)
_MINUTES = 60
# Minutes and seconds as fractions of a degree.
_DIVISORS = (60.0, 3600.0)
_MAX_LATITUDE = 90.0
_MAX_LONGITUDE = 180.0
_MAX_PARTS = 3  # degrees, minutes, seconds
# Two values: a latitude and a longitude, or an easting and a northing.
_PAIR = 2
_HEMISPHERES: dict[str, tuple[str, int]] = {
    "N": ("lat", 1),
    "S": ("lat", -1),
    "E": ("lon", 1),
    "W": ("lon", -1),
    "O": ("lon", -1),
}
# The band letter "N" written after a zone means "north", as people in Spain use it.
_NORTH = "N"
_SOUTHERN_BANDS = UTM_BANDS[: UTM_BANDS.index("N")]
_IGNORED_WORDS = frozenset(
    {
        "UTM",
        "HUSO",
        "ZONA",
        "ZONE",
        "X",
        "Y",
        "LAT",
        "LON",
        "LNG",
        "LATITUD",
        "LONGITUD",
        "LATITUDE",
        "LONGITUDE",
    }
)
# UTM labels E (easting) and N (northing) may precede the values, and M (metres) follow
# them. E is never read as a band: band E lies in the southern hemisphere.
_UTM_LABELS = frozenset({"E", "N"})
_METRES = "M"
_EASTING_LABEL = "E"
_MARKS = {"°": 0, "'": 1, '"': 2}
# What people and keyboards write for the marks: the ordinal º and ring ˚ for degrees;
# prime, right quote and acute accent for minutes; double prime and quotes for seconds.
_TRANSLATE = str.maketrans(
    {
        "º": "°",
        "\u02da": "°",
        "\u2032": "'",
        "\u2019": "'",
        "\u00b4": "'",
        "\u2033": '"',
        "\u201d": '"',
        "\u201c": '"',
    }
)
_TOKEN = re.compile(
    r"(?P<num>[-+]?\d+(?:\.\d+)?)\s*(?P<mark>[°'\"])?"
    r"|(?P<word>[A-Z]+)"
    r"|(?P<sep>[,;])"
    r"|(?P<space>[\s:=]+)"
)
# Datum names hold digits; they say nothing the parser needs.
_DATUMS = re.compile(r"\b(?:ETRS89|WGS84|ETRS|WGS)\b")
_DECIMAL_COMMA = re.compile(r"(?<=\d),(?=\d)")
_ALLOWED = re.compile(r"^[\d\s.,;:=+\-°'\"A-Z]+$")


@dataclass(frozen=True, slots=True)
class CoordinateReading:
    """One reading of the text: (x, y) in ``crs``'s own axis order.

    ``crs`` is ``LON_LAT`` for degrees (x longitude, y latitude) or a UTM CRS's zone for
    UTM (x easting, y northing); the caller maps the zone to its CRS.
    """

    x: float
    y: float
    # None for degrees.
    zone: int | None = None
    # The band letter written after the zone (R, S, T…), or "N" for north; None if none.
    band: str | None = None
    # Whether the text named the zone (or the axis order, for degrees).
    stated: bool = True


@dataclass(slots=True)
class _Number:
    value: float
    text: str
    mark: int | None


@dataclass(slots=True)
class _Group:
    numbers: list[_Number] = field(default_factory=list)
    hemisphere: str | None = None


def _malformed(detail: str) -> SearchError:
    return SearchError(SearchFailure.MALFORMED_COORDINATES, detail)


def _wrong_zone(detail: str) -> SearchError:
    return SearchError(SearchFailure.WRONG_UTM_ZONE, detail)


def _normalise(text: str) -> str:
    s = text.strip().upper().translate(_TRANSLATE).replace("''", '"')
    s = _DATUMS.sub(" ", s)
    one_separating_comma = s.count(",") == 1 and not re.search(r"\s", s)
    if ";" in s or not ("." in s or one_separating_comma):
        s = _DECIMAL_COMMA.sub(".", s)
    return s


def _tokens(text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    position = 0
    while position < len(text):
        match = _TOKEN.match(text, position)
        if match is None:
            raise _malformed(f"unexpected character {text[position]!r}")
        # lastgroup names the mark when a number carries one: test the number first.
        kind = "num" if match.group("num") is not None else match.lastgroup or ""
        if kind == "num":
            tokens.append(("num", match.group("num")))
            if match.group("mark"):
                tokens.append(("mark", match.group("mark")))
        elif kind != "space":
            tokens.append((kind, match.group(kind)))
        position = match.end()
    return tokens


def looks_like_coordinates(text: str) -> bool:
    """Whether the text is made of numbers, marks, separators and coordinate words only."""
    s = _normalise(text)
    if not s or not _ALLOWED.match(s):
        return False
    words = re.findall(r"[A-Z]+", s)
    known = all(
        w in _IGNORED_WORDS or w in _HEMISPHERES or (len(w) == 1 and w in UTM_BANDS) or w == _METRES
        for w in words
    )
    return known and len(re.findall(r"\d+", s)) >= _PAIR


def parse_coordinates(text: str, zones: Sequence[int]) -> tuple[CoordinateReading, ...]:
    """Every reading of the text; ``zones`` are the UTM zones a zone-less UTM pair is read
    in. Raises SearchError when the text is not coordinates."""
    tokens = [
        (kind, value)
        for kind, value in _tokens(_normalise(text))
        if not (kind == "word" and value in _IGNORED_WORDS)
    ]
    numbers = [float(value) for kind, value in tokens if kind == "num"]
    if any(abs(value) >= _PROJECTED_MIN for value in numbers):
        return _utm(tokens, zones)
    return _degrees(tokens)


def _utm(tokens: list[tuple[str, str]], zones: Sequence[int]) -> tuple[CoordinateReading, ...]:
    if any(kind == "mark" for kind, _ in tokens):
        raise _malformed("UTM coordinates carry no degree, minute or second marks")
    zone: int | None = None
    band: str | None = None
    big: list[float] = []
    for index, (kind, value) in enumerate(tokens):
        if kind == "num":
            number = float(value)
            if abs(number) >= _PROJECTED_MIN:
                big.append(number)
            elif zone is None and value.isdigit():
                zone = int(value)
            else:
                raise _malformed(f"{value} is neither a UTM zone nor a coordinate")
        elif kind == "word":
            after_zone = index > 0 and tokens[index - 1] == ("num", str(zone))
            after_value = index > 0 and tokens[index - 1][0] == "num" and not after_zone
            if after_zone and len(value) == 1 and band is None and value != _EASTING_LABEL:
                band = value
            elif value == _METRES and after_value:
                continue
            elif value not in _UTM_LABELS:
                raise _malformed(f"{value!r} is not part of a UTM coordinate")
    if len(big) != _PAIR:
        raise _malformed("UTM coordinates are one easting and one northing")
    if any(value < 0 for value in big):
        raise _malformed("UTM coordinates are never negative")
    easting, northing = sorted(big)
    if not (_EASTING_RANGE[0] <= easting <= _EASTING_RANGE[1]) or northing < _NORTHING_MIN:
        raise _malformed("a UTM easting has six digits and a northing seven")
    if band is not None:
        _check_band(band)
    if zone is None:
        return tuple(CoordinateReading(x=easting, y=northing, zone=z, stated=False) for z in zones)
    if not _UTM_ZONE_RANGE[0] <= zone <= _UTM_ZONE_RANGE[1]:
        raise _malformed(f"{zone} is not a UTM zone")
    if zone not in zones:
        raise _wrong_zone(f"UTM zone {zone} holds no Spanish territory")
    return (CoordinateReading(x=easting, y=northing, zone=zone, band=band),)


def _check_band(band: str) -> None:
    if band == _NORTH:
        return
    if band not in UTM_BANDS:
        raise _malformed(f"{band!r} is not a UTM latitude band")
    if band in _SOUTHERN_BANDS:
        raise _wrong_zone(f"band {band} is in the southern hemisphere")


def _degrees(tokens: list[tuple[str, str]]) -> tuple[CoordinateReading, ...]:
    groups = _groups(tokens)
    if len(groups) == 1 and groups[0].hemisphere is None:
        groups = _halve(groups[0])
    if len(groups) != _PAIR:
        raise _malformed("coordinates are two values: a latitude and a longitude")
    first, second = (_value(group) for group in groups)
    axes = [_HEMISPHERES[g.hemisphere][0] if g.hemisphere else None for g in groups]
    if axes[0] is not None and axes[0] == axes[1]:
        raise _malformed("both values name the same axis")
    if axes == [None, None]:
        readings = [
            CoordinateReading(x=lon, y=lat, stated=False)
            for lat, lon in ((first, second), (second, first))
            if abs(lat) <= _MAX_LATITUDE and abs(lon) <= _MAX_LONGITUDE
        ]
        if not readings:
            raise _malformed("no value is a latitude")
        unique = {(r.x, r.y): r for r in readings}
        return tuple(unique.values())
    lat_first = axes[0] == "lat" or axes[1] == "lon"
    lat, lon = (first, second) if lat_first else (second, first)
    if abs(lat) > _MAX_LATITUDE or abs(lon) > _MAX_LONGITUDE:
        raise _malformed("a latitude is at most 90° and a longitude at most 180°")
    return (CoordinateReading(x=lon, y=lat),)


def _groups(tokens: list[tuple[str, str]]) -> list[_Group]:
    groups: list[_Group] = []
    current = _Group()
    pending: str | None = None  # a hemisphere letter written before its numbers

    def close() -> None:
        nonlocal current
        if current.numbers:
            groups.append(current)
        elif current.hemisphere is not None:
            raise _malformed("a hemisphere letter without a value")
        current = _Group()

    for kind, value in tokens:
        if kind == "num":
            if not current.numbers and pending is not None:
                current.hemisphere, pending = pending, None
            current.numbers.append(_Number(float(value), value, None))
        elif kind == "mark":
            # The tokenizer emits a mark only right after its number.
            mark = _MARKS[value]
            if mark == 0 and len(current.numbers) > 1:
                # A new degree value starts the second coordinate.
                last = current.numbers.pop()
                close()
                current.numbers.append(last)
            current.numbers[-1].mark = mark
        elif kind == "word":
            if value not in _HEMISPHERES:
                raise _malformed(f"{value!r} is not a hemisphere letter")
            if current.numbers and current.hemisphere is None:
                current.hemisphere = value
                close()
            elif pending is None:
                close()
                pending = value
            else:
                raise _malformed("two hemisphere letters in a row")
        else:  # a comma or semicolon between the two values
            close()
    if pending is not None:
        raise _malformed("a hemisphere letter without a value")
    close()
    return groups


def _halve(group: _Group) -> list[_Group]:
    """Six, four or two unmarked numbers: degrees (and minutes, seconds) of each value."""
    count = len(group.numbers)
    if count % 2 or count > 2 * _MAX_PARTS:
        raise _malformed(f"{count} numbers are not two coordinates")
    half = count // 2
    return [_Group(group.numbers[:half]), _Group(group.numbers[half:])]


def _value(group: _Group) -> float:
    parts = group.numbers
    if len(parts) > _MAX_PARTS:
        raise _malformed("a coordinate is degrees, minutes and seconds at most")
    for position, part in enumerate(parts):
        if part.mark is not None and part.mark != position:
            raise _malformed("degrees, minutes and seconds are written in that order")
    for part in parts[:-1]:
        if "." in part.text:
            raise _malformed("only the last of degrees, minutes and seconds has decimals")
    for part in parts[1:]:
        if part.text.startswith(("-", "+")):
            raise _malformed("only the degrees carry a sign")
        if not 0 <= part.value < _MINUTES:
            raise _malformed("minutes and seconds are below 60")
    degrees = parts[0].value
    negative = parts[0].text.startswith("-")
    if group.hemisphere is not None and parts[0].text.startswith(("-", "+")):
        raise _malformed("a value has a sign or a hemisphere letter, not both")
    magnitude = abs(degrees) + sum(
        part.value / divisor for part, divisor in zip(parts[1:], _DIVISORS, strict=False)
    )
    sign = -1 if negative else 1
    if group.hemisphere is not None:
        sign = _HEMISPHERES[group.hemisphere][1]
    return sign * magnitude
