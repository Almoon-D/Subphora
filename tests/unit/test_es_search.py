# Copyright (c) 2026 Almoon-D. All rights reserved.
"""What the search box reads: SIGPAC references, coordinates, and which is which."""

import pytest

from subphora.countries.es.coordinates import CoordinateReading, parse_coordinates
from subphora.countries.es.crs import latitude_band, utm_crs
from subphora.countries.es.search import Cadastral, Coordinates, Name, Sigpac, recognise
from subphora.countries.es.sigpac import SigpacReference, parse_sigpac
from subphora.domain.aoi import SearchError, SearchFailure

ZONES = (28, 29, 30, 31)


def _failure(call: object) -> SearchFailure:
    assert callable(call)
    with pytest.raises(SearchError) as caught:
        call()
    return caught.value.failure


# ── SIGPAC ───────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "parts"),
    [
        ("34:48:0:0:13:12:1", (34, 48, 0, 0, 13, 12, 1)),
        ("34/48/0/0/13/12", (34, 48, 0, 0, 13, 12)),
        ("34-48-0-0-13-12-1", (34, 48, 0, 0, 13, 12, 1)),
        (" 34 48 0 0 13 12 1 ", (34, 48, 0, 0, 13, 12, 1)),
        ("34 : 48 : 0 : 0 : 13 : 12 : 1", (34, 48, 0, 0, 13, 12, 1)),
        # Short forms, without aggregate and zone.
        ("34:48:13:12:1", (34, 48, 0, 0, 13, 12, 1)),
        ("29:15:167:21", (29, 15, 0, 0, 167, 21)),
        ("08:019:000:00:005:00012:00003", (8, 19, 0, 0, 5, 12, 3)),
    ],
)
def test_sigpac_references_in_every_form(text: str, parts: tuple[int, ...]) -> None:
    reference = parse_sigpac(text)
    assert reference.parts == parts
    assert reference.code == ":".join(str(p) for p in parts)
    assert (reference.enclosure is None) == (len(parts) == 6)


def test_a_short_parcel_has_no_enclosure() -> None:
    assert parse_sigpac("34:48:0:13") == SigpacReference(34, 48, 0, 0, 0, 13, None)


@pytest.mark.parametrize(
    "text",
    [
        "34:48:13",  # three numbers
        "34:48:0:0:13:12:1:5",  # eight
        "34:48:0:0:13:a:1",  # a letter
        "34:48:0:0:13:12.5:1",  # a decimal
        "60:48:0:0:13:12:1",  # no province 60
        "00:48:0:0:13:12:1",
        "34:0:0:0:13:12:1",  # municipality 0
        "34:48:0:0:13:0:1",  # parcel 0
        "34:48:0:0:13:12:0",  # enclosure 0
        "34:4800:0:0:13:12:1",  # a four-digit municipality
        "34:48:0:0:13:123456:1",  # a six-digit parcel
        "",
    ],
)
def test_malformed_sigpac_references(text: str) -> None:
    assert _failure(lambda: parse_sigpac(text)) == SearchFailure.MALFORMED_SIGPAC


# ── coordinates ──────────────────────────────────────────────────────────────────────────

MADRID = (-3.7038, 40.4168)


def _one(text: str) -> CoordinateReading:
    readings = parse_coordinates(text, ZONES)
    assert len(readings) == 1, readings
    return readings[0]


@pytest.mark.parametrize(
    "text",
    [
        "40.4168N 3.7038W",
        "40.4168 N, 3.7038 W",
        "N40.4168 W3.7038",
        "3.7038W 40.4168N",
        "40,4168 N 3,7038 O",  # decimal comma, O for oeste
        "lat: 40.4168 N, lon: 3.7038 W",
        "40.4168N -3.7038",
    ],
)
def test_decimal_degrees_with_a_hemisphere(text: str) -> None:
    reading = _one(text)
    assert (reading.x, reading.y) == pytest.approx(MADRID)
    assert reading.zone is None
    assert reading.stated


@pytest.mark.parametrize(
    "text",
    [
        "40°25'0.48\"N 3°42'13.68\"W",
        "40º 25' 0,48'' N, 3º 42' 13,68'' O",
        "40°25\u20320.48\u2033N 3°42\u203213.68\u2033W",  # prime and double prime
        "N 40 25 0.48 W 3 42 13.68",
        "40 25 0.48 N 3 42 13.68 W",
        "40°25.008'N 3°42.228'W",
    ],
)
def test_degrees_minutes_and_seconds(text: str) -> None:
    reading = _one(text)
    assert (reading.x, reading.y) == pytest.approx(MADRID, abs=1e-6)


@pytest.mark.parametrize(
    "text",
    [
        "40.4168, -3.7038",
        "40,4168 -3,7038",
        "40,4168,-3,7038",
        "40.4168;-3.7038",
        "40.4168 -3.7038",
    ],
)
def test_unlabelled_degrees_give_both_orders(text: str) -> None:
    readings = parse_coordinates(text, ZONES)
    assert len(readings) == 2
    assert (readings[0].x, readings[0].y) == pytest.approx(MADRID)
    assert (readings[1].x, readings[1].y) == pytest.approx((40.4168, -3.7038))
    assert not any(r.stated for r in readings)


def test_an_order_that_cannot_be_a_latitude_is_not_offered() -> None:
    readings = parse_coordinates("100.5, 40.2", ZONES)
    assert [(r.x, r.y) for r in readings] == [(100.5, 40.2)]


@pytest.mark.parametrize(
    ("text", "zone", "band"),
    [
        ("30 440000 4474000", 30, None),
        ("30T 440000 4474000", 30, "T"),
        ("30N 440000 4474000", 30, "N"),
        ("UTM huso 30 X: 440000 Y: 4474000", 30, None),
        ("440000 4474000 30", 30, None),
        ("30 4474000 440000", 30, None),  # northing first: told apart by size
        ("30 E 440000 N 4474000", 30, None),
        ("30 440000 m 4474000 m ETRS89", 30, None),
        ("30 440000,5 4474000,25", 30, None),
        ("28R 457439 3110202", 28, "R"),
    ],
)
def test_utm_with_a_zone(text: str, zone: int, band: str | None) -> None:
    reading = _one(text)
    assert (reading.zone, reading.band) == (zone, band)
    assert 400_000 < reading.x < 500_000
    assert reading.y > 3_000_000


def test_utm_without_a_zone_gives_every_zone() -> None:
    readings = parse_coordinates("440000 4474000", ZONES)
    assert [r.zone for r in readings] == list(ZONES)
    assert not any(r.stated for r in readings)
    assert [r.zone for r in parse_coordinates("440000,4474000", ZONES)] == list(ZONES)


@pytest.mark.parametrize(
    "text",
    [
        "40.4168",  # one value
        "40.4 -3.7 1.2",  # three
        "40°61'N 3°W",  # 61 minutes
        "40°25'61\"N 3°W",  # 61 seconds
        "-40.4N 3.7W",  # a sign and a letter
        "40.4N 3.7S",  # both latitudes
        "40.5°25'N 3°W",  # decimals before the minutes
        "40°-25'N 3°W",  # a negative minute
        "40'25°N 3°W",  # marks out of order
        "95N 3W",  # latitude above 90
        "40N 190W",
        "N 40 S",  # a letter without a value
        "40 N N 3",  # two letters in a row
        "N S 40 3",
        '40"N 3W',  # seconds where the degrees go
        "40 3 N W S",  # a letter left without a value
        "40.4 Q 3.7",  # not a hemisphere
        "40 25 3",  # an odd count of unmarked numbers
        "1 2 3 4 5 6 7 8",
        "°40 3",  # a mark without a value
        "100 200",  # neither order is a latitude
        "40 25 0 0 N 3 W",  # four parts
        "30 44000 4474000",  # a five-digit easting
        "30 440000 447400",  # a six-digit northing
        "30 440000",  # one UTM value
        "30 440000 4474000 5",  # two small numbers
        "30°440000 4474000",  # marks in UTM
        "-440000 4474000",
        "30 440000 Q 4474000",  # a word that is no label
        "30 440000 4474000 Z",
        "30I 440000 4474000",  # I is no band
        "75 440000 4474000",  # no UTM zone 75
        "40 25 0 1e3",
        "40.4 # -3.7",
    ],
)
def test_malformed_coordinates(text: str) -> None:
    assert _failure(lambda: parse_coordinates(text, ZONES)) == SearchFailure.MALFORMED_COORDINATES


@pytest.mark.parametrize(
    "text", ["33 440000 4474000", "27 440000 4474000", "30C 440000 4474000", "30M 440000 4474000"]
)
def test_a_zone_or_band_outside_spain_is_a_wrong_zone(text: str) -> None:
    assert _failure(lambda: parse_coordinates(text, ZONES)) == SearchFailure.WRONG_UTM_ZONE


def test_utm_crs_and_bands() -> None:
    assert [utm_crs(zone) for zone in ZONES] == [
        "EPSG:4083",
        "EPSG:25829",
        "EPSG:25830",
        "EPSG:25831",
    ]
    with pytest.raises(ValueError, match="no Spanish territory"):
        utm_crs(32)
    assert (latitude_band(28.1), latitude_band(37.0), latitude_band(42.0)) == ("R", "S", "T")
    assert latitude_band(84.0) == "X"
    for bad in (-81.0, 85.0, float("nan")):
        with pytest.raises(ValueError, match="no UTM band"):
            latitude_band(bad)


# ── what the text is ─────────────────────────────────────────────────────────────────────


def test_a_cadastral_reference_is_recognised() -> None:
    (reading,) = recognise(" 7279701nh3477g ", ZONES)
    assert isinstance(reading, Cadastral)
    assert reading.reference.parcel == "7279701NH3477G"


def test_a_malformed_cadastral_reference_says_so() -> None:
    # Twenty characters of a reference, with wrong control letters.
    failure = _failure(lambda: recognise("7279701NH3477G0001XX", ZONES))
    assert failure == SearchFailure.MALFORMED_REFERENCE


def test_a_sigpac_reference_is_recognised() -> None:
    (reading,) = recognise("34:48:0:0:13:12:1", ZONES)
    assert isinstance(reading, Sigpac)


def test_six_numbers_are_a_sigpac_parcel_and_coordinates_alike() -> None:
    readings = recognise("40 25 0 3 42 13", ZONES)
    assert [type(r) for r in readings] == [Sigpac, Coordinates]


def test_coordinates_are_recognised() -> None:
    (reading,) = recognise("30T 440000 4474000", ZONES)
    assert isinstance(reading, Coordinates)
    assert reading.readings[0].zone == 30


@pytest.mark.parametrize(
    "text", ["Daimiel", "Calle Mayor 1, Zaragoza", "A-4 200", "13250", "Camino 5 3"]
)
def test_names_go_to_the_geocoder(text: str) -> None:
    assert recognise(text, ZONES) == (Name(text),)


def test_an_empty_search() -> None:
    assert _failure(lambda: recognise("   ", ZONES)) == SearchFailure.EMPTY


def test_a_malformed_sigpac_reference_is_reported_when_nothing_else_fits() -> None:
    assert _failure(lambda: recognise("99:48:0:0:13:12:1", ZONES)) == SearchFailure.MALFORMED_SIGPAC


def test_malformed_coordinates_are_reported() -> None:
    assert _failure(lambda: recognise("40°61'N 3°W", ZONES)) == SearchFailure.MALFORMED_COORDINATES
