# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Spanish cadastral references: every accepted form and every failure branch."""

import pytest

from subphora.countries.es import control_letters, parse_reference, province_by_code
from subphora.countries.es.areas import all_provinces
from subphora.countries.es.crs import local_crs, utm_zone
from subphora.domain.parcels import LookupFailure, ParcelLookupError, ReferenceKind

# Full references read from Catastro's non-protected data service on 2026-11-24 (public
# places: knowledge/catastro.md and tests/fixtures/parcels/README.md).
VERIFIED = [
    "7279701NH3477G0001SJ",
    "0910001QD3101S0001LR",
    "35029A032003140000HL",
    "1380321VK4718A0001EU",
    "6839401XM7163H0001YZ",
    "1532704VK4713C0001GO",
    "1532704VK4713C0002HP",
]


@pytest.mark.parametrize("full", VERIFIED)
def test_control_letters_match_catastro(full: str) -> None:
    assert control_letters(full[:14], full[14:18]) == full[18:]


@pytest.mark.parametrize("full", VERIFIED)
def test_a_verified_full_reference_parses_to_its_parcel(full: str) -> None:
    assert parse_reference(full).parcel == full[:14]


def test_a_rustic_reference_carries_its_province() -> None:
    reference = parse_reference("35029A03200314")
    assert reference.kind is ReferenceKind.RUSTIC
    assert reference.province_code == "35"


def test_an_urban_reference_carries_no_province() -> None:
    reference = parse_reference("7279701NH3477G")
    assert reference.kind is ReferenceKind.URBAN
    assert reference.province_code is None


@pytest.mark.parametrize(
    "typed", ["  7279701nh3477g  ", "7279701 NH3477G", "7279701 NH3477G 0001 SJ"]
)
def test_case_and_spaces_are_forgiven(typed: str) -> None:
    assert parse_reference(typed).parcel == "7279701NH3477G"


@pytest.mark.parametrize(
    ("typed", "reason"),
    [
        ("", "empty"),
        ("   ", "empty"),
        ("7279701NH3477G\x00", "only letters"),
        ("7279701\nNH3477G", "only letters"),
        ("7279701\tNH3477G", "only letters"),
        ("7279701-NH3477G", "only letters"),
        ("7279701NH3477G;DROP", "only letters"),
        ("7279701NH3477", "14 or 20"),
        ("7279701NH3477G0001S", "14 or 20"),
        ("7279701NH3477G0001SJX", "14 or 20"),
        ("ABCDEFGHIJKLMN", "neither"),
        ("123456A1234567", "neither"),
        ("12345A1234567X", "neither"),
        ("99001A00100001", "province code"),
        ("00001A00100001", "province code"),
        ("7279701NH3477GAB01SJ", "digits"),
        ("7279701NH3477G000112", "letters"),
        ("7279701NH3477G0001JS", "control letters"),
        ("7279701NH3477G0002SJ", "control letters"),
    ],
)
def test_malformed_references_are_refused(typed: str, reason: str) -> None:
    with pytest.raises(ParcelLookupError) as caught:
        parse_reference(typed)
    assert caught.value.failure is LookupFailure.MALFORMED
    assert reason in caught.value.detail


@pytest.mark.parametrize(("parcel", "cargo"), [("7279701NH3477", "0001"), ("7279701NH3477G", "01")])
def test_control_letters_need_whole_parts(parcel: str, cargo: str) -> None:
    with pytest.raises(ValueError, match="14-character"):
        control_letters(parcel, cargo)


def test_ñ_counts_as_fifteen() -> None:
    # Ñ sits between N (14) and O (16): moving one sheet letter from N to Ñ to O shifts
    # the second sum by its weight each time.
    letters = [control_letters(f"1234567AB12{c}4C", "0001")[1] for c in "NÑO"]
    assert len(set(letters)) == 3


def test_every_province_has_unique_codes() -> None:
    provinces = all_provinces()
    assert len(provinces) == 52
    assert len({p.code for p in provinces}) == 52
    assert len({p.iso for p in provinces}) == 52
    assert all(p.iso.startswith("ES-") and p.region.startswith("ES-") for p in provinces)


@pytest.mark.parametrize(
    ("code", "region"),
    [("01", "ES-PV"), ("20", "ES-PV"), ("48", "ES-PV"), ("31", "ES-NC"), ("35", "ES-CN")],
)
def test_province_regions(code: str, region: str) -> None:
    province = province_by_code(code)
    assert province is not None
    assert province.region == region


def test_an_unknown_province_is_none() -> None:
    assert province_by_code("53") is None


@pytest.mark.parametrize(
    ("region", "longitude", "crs"),
    [
        ("ES-GA", -8.54, "EPSG:25829"),  # Santiago de Compostela
        ("ES-EX", -6.34, "EPSG:25829"),  # Mérida, west of 6° W
        ("ES-MD", -3.69, "EPSG:25830"),  # Madrid
        ("ES-AR", -0.88, "EPSG:25830"),  # Zaragoza
        ("ES-CT", 2.17, "EPSG:25831"),  # Barcelona
        ("ES-IB", 4.26, "EPSG:25831"),  # Menorca
        ("ES-CN", -13.77, "EPSG:4083"),  # Lanzarote
        ("ES-CN", -17.99, "EPSG:4083"),  # El Hierro, west of zone 28: still 28N
    ],
)
def test_the_crs_follows_the_location(region: str, longitude: float, crs: str) -> None:
    assert local_crs(region, longitude) == crs


def test_a_zone_boundary_belongs_to_the_eastern_zone() -> None:
    assert utm_zone(-6.0) == 30
    assert utm_zone(180.0) == 60


@pytest.mark.parametrize("longitude", [-200.0, 181.0, float("nan")])
def test_an_impossible_longitude_is_refused(longitude: float) -> None:
    with pytest.raises(ValueError, match="out of range"):
        utm_zone(longitude)


def test_a_place_outside_spains_zones_is_refused() -> None:
    with pytest.raises(ValueError, match="outside Spain"):
        local_crs("ES-AN", 20.0)
