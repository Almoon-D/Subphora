# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Spanish cadastral references: format and control letters (docs/knowledge/catastro.md).

- Rustic, 14 characters: province (2 digits), municipality (3 digits), sector (1 letter),
  polygon (3 digits), parcel (5 digits).
- Urban, 14 characters: 7 digits, then the 7 alphanumerics of the map sheet.
- Full, 20 characters: the 14 above, the property within the parcel (4 digits, the
  "cargo") and 2 control letters computed from the rest.

Validation runs before any call to Catastro, so a malformed reference never leaves the
server.
"""

import re

from subphora.countries.es.areas import province_by_code
from subphora.domain.parcels import (
    CadastralReference,
    LookupFailure,
    ParcelLookupError,
    ReferenceKind,
)

PARCEL_LENGTH = 14
FULL_LENGTH = 20
_CARGO_LENGTH = 4

# The control letters, verified against Catastro on five references (knowledge file).
_WEIGHTS = (13, 15, 12, 5, 4, 17, 9, 21, 3, 7, 1)
_CONTROL_ALPHABET = "MQWERTYUIOPASDFGHJKLBZX"
_LETTER_VALUES = {
    letter: value for value, letter in enumerate("ABCDEFGHIJKLMNÑOPQRSTUVWXYZ", start=1)
}

_RUSTIC = re.compile(r"^\d{5}[A-ZÑ]\d{8}$")
_URBAN = re.compile(r"^\d{7}[A-ZÑ0-9]{7}$")
_CARGO = re.compile(r"^\d{4}$")
_CONTROL = re.compile(r"^[A-Z]{2}$")
# Spaces are accepted as separators ("7279701 NH3477G 0001 SJ"); nothing else is.
_ALLOWED = re.compile(r"^[A-ZÑ0-9 ]+$")


def _malformed(detail: str) -> ParcelLookupError:
    return ParcelLookupError(LookupFailure.MALFORMED, detail)


def _value(char: str) -> int:
    if char.isdigit():
        return int(char)
    return _LETTER_VALUES[char]


def control_letters(parcel: str, cargo: str) -> str:
    """The two control letters of a 14-character parcel reference and a 4-digit cargo."""
    if len(parcel) != PARCEL_LENGTH or not _CARGO.match(cargo):
        raise ValueError("control letters need a 14-character parcel and a 4-digit cargo")
    letters = ""
    for half in (parcel[:7], parcel[7:]):
        chars = half + cargo
        total = sum(w * _value(c) for w, c in zip(_WEIGHTS, chars, strict=True))
        letters += _CONTROL_ALPHABET[total % len(_CONTROL_ALPHABET)]
    return letters


def parse_reference(raw: str) -> CadastralReference:
    """Validate a reference typed by a person; raise ParcelLookupError(MALFORMED) if bad."""
    text = raw.strip().upper()
    if not text:
        raise _malformed("the reference is empty")
    if not _ALLOWED.match(text):
        raise _malformed("a reference holds only letters, digits and spaces")
    compact = text.replace(" ", "")
    if len(compact) not in (PARCEL_LENGTH, FULL_LENGTH):
        raise _malformed(
            f"a reference has {PARCEL_LENGTH} or {FULL_LENGTH} characters, not {len(compact)}"
        )
    parcel = compact[:PARCEL_LENGTH]
    if _RUSTIC.match(parcel):
        province = province_by_code(parcel[:2])
        if province is None:
            raise _malformed(f"{parcel[:2]} is not a Spanish province code")
        reference = CadastralReference(
            parcel=parcel, kind=ReferenceKind.RUSTIC, province_code=province.code
        )
    elif _URBAN.match(parcel):
        reference = CadastralReference(parcel=parcel, kind=ReferenceKind.URBAN)
    else:
        raise _malformed("the first 14 characters are neither a rustic nor an urban reference")
    if len(compact) == FULL_LENGTH:
        cargo, control = compact[PARCEL_LENGTH:18], compact[18:]
        if not _CARGO.match(cargo):
            raise _malformed("characters 15 to 18 of a full reference are digits")
        if not _CONTROL.match(control):
            raise _malformed("the last 2 characters of a full reference are letters")
        expected = control_letters(parcel, cargo)
        if control != expected:
            raise _malformed("the control letters do not match the reference")
    return reference
