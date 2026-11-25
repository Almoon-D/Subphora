# Copyright (c) 2026 Almoon-D. All rights reserved.
"""What a text typed in the search box is: a cadastral reference, a SIGPAC reference,
coordinates, or a name for the geocoder.

A cadastral reference starts with five digits and has letters; a SIGPAC reference is four
to seven whole numbers; coordinates are two values (with a UTM zone, three numbers), with
marks, letters or separators of their own; anything else is a name or an address. Some
texts are two things at once (``40 25 0 3 42 13`` is a SIGPAC parcel and two values in
degrees, minutes and seconds): every valid reading is returned, for the person to choose.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from subphora.countries.es.coordinates import (
    CoordinateReading,
    looks_like_coordinates,
    parse_coordinates,
)
from subphora.countries.es.references import parse_reference
from subphora.countries.es.sigpac import SigpacReference, looks_like_sigpac, parse_sigpac
from subphora.domain.aoi import SearchError, SearchFailure
from subphora.domain.parcels import CadastralReference, ParcelLookupError

# Fourteen or twenty letters and digits, spaces aside, starting with digits: what a person
# typing a cadastral reference writes. Validation then decides whether it is one.
_CADASTRAL_SHAPE = re.compile(r"^\d{5}[A-Z0-9Ñ ]+$")
_CADASTRAL_LENGTHS = (14, 20)


@dataclass(frozen=True, slots=True)
class Cadastral:
    reference: CadastralReference


@dataclass(frozen=True, slots=True)
class Sigpac:
    reference: SigpacReference


@dataclass(frozen=True, slots=True)
class Coordinates:
    readings: tuple[CoordinateReading, ...]


@dataclass(frozen=True, slots=True)
class Name:
    text: str


type Recognised = Cadastral | Sigpac | Coordinates | Name


def _looks_cadastral(text: str) -> bool:
    upper = text.upper()
    compact = upper.replace(" ", "")
    return (
        bool(_CADASTRAL_SHAPE.match(upper))
        and len(compact) in _CADASTRAL_LENGTHS
        and any(char.isalpha() for char in compact)
    )


def recognise(raw: str, utm_zones: Sequence[int]) -> tuple[Recognised, ...]:
    """Every valid reading of the text; raises SearchError when it has the shape of a
    reference or of coordinates and no shape it has is valid."""
    text = " ".join(raw.split())
    if not text:
        raise SearchError(SearchFailure.EMPTY, "the search is empty")
    if _looks_cadastral(text):
        try:
            return (Cadastral(parse_reference(text)),)
        except ParcelLookupError as exc:
            raise SearchError(SearchFailure.MALFORMED_REFERENCE, exc.detail) from exc
    readings: list[Recognised] = []
    errors: list[SearchError] = []
    if looks_like_sigpac(text):
        try:
            readings.append(Sigpac(parse_sigpac(text)))
        except SearchError as exc:
            errors.append(exc)
    if looks_like_coordinates(text):
        try:
            readings.append(Coordinates(parse_coordinates(text, utm_zones)))
        except SearchError as exc:
            errors.append(exc)
    if readings:
        return tuple(readings)
    if errors:
        raise errors[0]
    return (Name(text),)
