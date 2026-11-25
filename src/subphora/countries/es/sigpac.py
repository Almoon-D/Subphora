# Copyright (c) 2026 Almoon-D. All rights reserved.
"""SIGPAC references (docs/knowledge/sigpac.md).

A parcel is province:municipality:aggregate:zone:polygon:parcel, and an enclosure adds its
number. The SIGPAC viewer and the farmers' paperwork also write the short forms without
aggregate and zone (both zero then): province:municipality:polygon:parcel[:enclosure].

- 7 numbers: an enclosure; 6: a parcel; 5: an enclosure, short; 4: a parcel, short.
- Separators: colons, slashes, hyphens or spaces (one kind or mixed).

Validation runs before any call to SIGPAC, so a malformed reference never leaves the
server.
"""

import re
from dataclasses import dataclass

from subphora.countries.es.areas import province_by_code
from subphora.domain.aoi import SearchError, SearchFailure

_SEPARATORS = re.compile(r"\s*[:/\-]\s*|\s+")
_NUMBER = re.compile(r"^\d+$")
_FULL_PARCEL = 6
_FULL_ENCLOSURE = 7
_SHORT_PARCEL = 4
_SHORT_ENCLOSURE = 5
# The most digits each part has: municipality, aggregate, zone and polygon have three,
# parcel and enclosure five.
_SHORT_PART_DIGITS = 3
_LONG_PART_DIGITS = 5
_PART_NAMES = ("province", "municipality", "aggregate", "zone", "polygon", "parcel", "enclosure")


@dataclass(frozen=True, slots=True)
class SigpacReference:
    province: int
    municipality: int
    aggregate: int
    zone: int
    polygon: int
    parcel: int
    # None: the whole parcel, every enclosure of it.
    enclosure: int | None

    @property
    def parts(self) -> tuple[int, ...]:
        head = (
            self.province,
            self.municipality,
            self.aggregate,
            self.zone,
            self.polygon,
            self.parcel,
        )
        return head if self.enclosure is None else (*head, self.enclosure)

    @property
    def code(self) -> str:
        """The full form, colon-separated: 34:48:0:0:13:12:1."""
        return ":".join(str(part) for part in self.parts)


def _malformed(detail: str) -> SearchError:
    return SearchError(SearchFailure.MALFORMED_SIGPAC, detail)


def split_parts(text: str) -> list[str] | None:
    """The parts of a text made only of whole numbers and SIGPAC separators, else None."""
    parts = _SEPARATORS.split(text.strip())
    if not parts or not all(_NUMBER.match(part) for part in parts):
        return None
    return parts


def looks_like_sigpac(text: str) -> bool:
    parts = split_parts(text)
    return parts is not None and _SHORT_PARCEL <= len(parts) <= _FULL_ENCLOSURE


def parse_sigpac(text: str) -> SigpacReference:
    """A validated reference; raise SearchError(MALFORMED_SIGPAC) when it is not one."""
    parts = split_parts(text)
    if parts is None:
        raise _malformed("a SIGPAC reference holds only numbers and separators")
    count = len(parts)
    if count in (_SHORT_PARCEL, _SHORT_ENCLOSURE):
        parts = [*parts[:2], "0", "0", *parts[2:]]
    elif count not in (_FULL_PARCEL, _FULL_ENCLOSURE):
        raise _malformed(f"a SIGPAC reference has 4 to 7 numbers, not {count}")
    for name, part in zip(_PART_NAMES, parts, strict=False):
        limit = _LONG_PART_DIGITS if name in ("parcel", "enclosure") else _SHORT_PART_DIGITS
        if len(part.lstrip("0") or "0") > limit:
            raise _malformed(f"the {name} has more than {limit} digits")
    values = [int(part) for part in parts]
    if province_by_code(f"{values[0]:02d}") is None:
        raise _malformed(f"{values[0]} is not a Spanish province code")
    if values[1] == 0 or values[5] == 0 or (len(values) == _FULL_ENCLOSURE and values[6] == 0):
        raise _malformed("municipality, parcel and enclosure numbers start at 1")
    return SigpacReference(
        province=values[0],
        municipality=values[1],
        aggregate=values[2],
        zone=values[3],
        polygon=values[4],
        parcel=values[5],
        enclosure=values[6] if len(values) == _FULL_ENCLOSURE else None,
    )
