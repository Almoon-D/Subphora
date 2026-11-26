# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The interpretive cross-section's geometry and confidence (MASTER_PLAN §4.4).

Everything is in line coordinates: ``distance`` along the line from its start, ``offset``
perpendicular to it (positive to the right looking along it), elevations in metres.

- **Apparent dip.** A bed of true dip d dipping toward azimuth a, cut by a section of
  azimuth t, shows the apparent dip tan(d') = tan(d)·cos(a - t): positive where it deepens
  toward the line's end, 0 where the section runs along its strike.
- **Contacts.** Where the surface unit changes along the line, the contact is projected
  downward with the apparent dip of the nearest bedding measurement within reach; with
  none it is drawn vertical and marked "not projected"; on a fault crossed it follows the
  fault (vertical: a fault's dip is not mapped).
- **Fault blocks.** Faults cut the section into blocks. A contact is projected only within
  its own block: a fault's throw is not mapped, so nothing is carried across it.
- **Cells.** A cell takes the unit of its block that its depth and the projected contacts
  put it in. Its confidence is (map_only + (1 - map_only)·evidence)·depth·fault: evidence
  falls with the plan distance to the nearest bedding measurement or borehole, depth with
  the depth below ground. Below the deepest reach of the evidence at its column it is
  "unknown".
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

from subphora.config.model import ConfidenceSettings
from subphora.config.section import SectionSettings
from subphora.domain.section import (
    BeddingMeasurement,
    Borehole,
    Contact,
    ContactState,
    EvidenceKind,
    FaultCrossing,
    SectionCell,
    SectionColumn,
    SurfaceUnit,
)
from subphora.model.evaluate import label

# Below this, a tangent is a horizontal bed (its contact never reaches another column).
_FLAT = 1e-9


@dataclass(frozen=True, slots=True)
class Line:
    """A straight line in a projected CRS."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def length(self) -> float:
        return math.hypot(self.x1 - self.x0, self.y1 - self.y0)

    @property
    def azimuth_deg(self) -> float:
        """Clockwise from grid north, from start to end, in [0, 360)."""
        return math.degrees(math.atan2(self.x1 - self.x0, self.y1 - self.y0)) % 360

    def point_at(self, distance: float) -> tuple[float, float]:
        share = distance / self.length
        return (self.x0 + share * (self.x1 - self.x0), self.y0 + share * (self.y1 - self.y0))

    def place(self, x: float, y: float) -> tuple[float, float]:
        """(distance along, offset to the right) of a point."""
        ux, uy = (self.x1 - self.x0) / self.length, (self.y1 - self.y0) / self.length
        dx, dy = x - self.x0, y - self.y0
        return (dx * ux + dy * uy, dx * uy - dy * ux)

    def crossings(self, polyline: Sequence[tuple[float, float]]) -> list[float]:
        """The distances along the line where ``polyline`` crosses it."""
        found = []
        ax, ay, bx, by = self.x0, self.y0, self.x1, self.y1
        for (cx, cy), (dx, dy) in pairwise(polyline):
            denominator = (bx - ax) * (dy - cy) - (by - ay) * (dx - cx)
            if denominator == 0:
                continue
            t = ((cx - ax) * (dy - cy) - (cy - ay) * (dx - cx)) / denominator
            u = ((cx - ax) * (by - ay) - (cy - ay) * (bx - ax)) / denominator
            if 0 <= t <= 1 and 0 <= u <= 1:
                found.append(t * self.length)
        return found


def apparent_dip_deg(dip_deg: float, direction_deg: float, azimuth_deg: float) -> float:
    """The apparent dip along a section of ``azimuth_deg`` of a bed dipping ``dip_deg``
    toward ``direction_deg``: positive where it deepens toward the section's end."""
    along = math.cos(math.radians(direction_deg - azimuth_deg))
    if dip_deg >= 90:
        return 90.0 if along >= 0 else -90.0
    return math.degrees(math.atan(math.tan(math.radians(dip_deg)) * along))


def surface_units(
    distances: Sequence[float], labels: Sequence[str | None], length: float
) -> tuple[list[SurfaceUnit], list[float]]:
    """The runs of one label along the sampled line, and the contacts between runs (half
    way between the samples either side)."""
    units: list[SurfaceUnit] = []
    contacts: list[float] = []
    start = 0.0
    for index in range(1, len(labels) + 1):
        if index < len(labels) and labels[index] == labels[index - 1]:
            continue
        end = length if index == len(labels) else (distances[index - 1] + distances[index]) / 2
        units.append(SurfaceUnit(index=len(units), from_m=start, to_m=end, label=labels[index - 1]))
        if index < len(labels):
            contacts.append(end)
        start = end
    return units, contacts


@dataclass(frozen=True, slots=True)
class BeddingPoint:
    """A bedding measurement in the line's CRS."""

    x: float
    y: float
    dip_deg: float
    direction_deg: float | None
    kind: str


def place_bedding(line: Line, points: Sequence[BeddingPoint]) -> list[BeddingMeasurement]:
    placed = []
    for p in points:
        distance, offset = line.place(p.x, p.y)
        placed.append(
            BeddingMeasurement(
                distance_m=distance,
                offset_m=offset,
                dip_deg=p.dip_deg,
                direction_deg=p.direction_deg,
                kind=p.kind,
            )
        )
    return placed


def _usable(measurement: BeddingMeasurement) -> bool:
    """A measurement gives an apparent dip: it has a direction, or it is horizontal."""
    return measurement.direction_deg is not None or measurement.dip_deg == 0


def _ground_at(
    distances: Sequence[float], grounds: Sequence[float | None], at: float
) -> float | None:
    index = min(range(len(distances)), key=lambda i: abs(distances[i] - at))
    return grounds[index]


def contacts_of(
    line: Line,
    positions: Sequence[float],
    distances: Sequence[float],
    grounds: Sequence[float | None],
    bedding: Sequence[BeddingMeasurement],
    faults: Sequence[FaultCrossing],
    settings: SectionSettings,
) -> list[Contact]:
    """Each contact's state, with the apparent dip of the nearest usable measurement."""
    usable = [m for m in bedding if _usable(m)]
    contacts = []
    for index, at in enumerate(positions):
        ground = _ground_at(distances, grounds, at)

        def contact(
            state: ContactState,
            at: float = at,
            ground: float | None = ground,
            index: int = index,
            **dip: Any,
        ) -> Contact:
            return Contact(
                distance_m=at, ground_m=ground, before=index, after=index + 1, state=state, **dip
            )

        if any(abs(f.distance_m - at) <= settings.confidence.fault_zone_m for f in faults):
            contacts.append(contact(ContactState.AT_FAULT))
            continue
        near = sorted(
            ((math.hypot(m.distance_m - at, m.offset_m), m) for m in usable),
            key=lambda pair: pair[0],
        )
        if not near or near[0][0] > settings.dip_max_distance_m or ground is None:
            contacts.append(contact(ContactState.NOT_PROJECTED))
            continue
        distance, measurement = near[0]
        apparent = apparent_dip_deg(
            measurement.dip_deg, measurement.direction_deg or 0.0, line.azimuth_deg
        )
        contacts.append(
            contact(
                ContactState.PROJECTED,
                apparent_dip_deg=apparent,
                measurement=measurement,
                measurement_m=distance,
            )
        )
    return contacts


def boundary_at(contact: Contact, elevation: float) -> float:
    """Where the contact lies at ``elevation`` (a distance along the line; ±inf for a
    horizontal one that never reaches that elevation)."""
    if contact.state is not ContactState.PROJECTED or contact.ground_m is None:
        return contact.distance_m
    tangent = math.tan(math.radians(contact.apparent_dip_deg or 0.0))
    depth = contact.ground_m - elevation
    if abs(tangent) < _FLAT:
        if depth == 0:
            return contact.distance_m
        return math.inf if depth > 0 else -math.inf
    return contact.distance_m + depth / tangent


def unit_at(
    distance: float,
    elevation: float,
    units: Sequence[SurfaceUnit],
    contacts: Sequence[Contact],
    faults: Sequence[FaultCrossing],
) -> int:
    """The surface unit a point of the section is interpreted as, within its fault block."""
    edges = sorted(f.distance_m for f in faults)
    low = max((e for e in edges if e <= distance), default=-math.inf)
    high = min((e for e in edges if e > distance), default=math.inf)
    block = [c for c in contacts if low <= c.distance_m < high]
    first = next((u.index for u in units if u.from_m <= max(low, 0.0) < u.to_m), units[0].index)
    # Within the block the units are consecutive; each contact passed adds one.
    passed = sum(1 for c in block if boundary_at(c, elevation) <= distance)
    return min(first + passed, units[-1].index)


@dataclass(frozen=True, slots=True)
class Evidence:
    kind: EvidenceKind
    distance_m: float
    reach_m: float


def column_evidence(
    distance: float,
    bedding: Sequence[BeddingMeasurement],
    boreholes: Sequence[Borehole],
    settings: SectionSettings,
) -> tuple[Evidence | None, float]:
    """The nearest evidence to a column, and how deep the evidence within range reaches."""
    confidence = settings.confidence
    found: list[Evidence] = [
        Evidence(
            EvidenceKind.BEDDING,
            math.hypot(m.distance_m - distance, m.offset_m),
            confidence.dip_reach_m,
        )
        for m in bedding
    ]
    found.extend(
        Evidence(EvidenceKind.BOREHOLE, math.hypot(b.distance_m - distance, b.offset_m), b.depth_m)
        for b in boreholes
    )
    within = [e for e in found if e.distance_m <= confidence.evidence_range_m]
    reach = max([confidence.map_reach_m, *(e.reach_m for e in within)])
    nearest = min(found, key=lambda e: e.distance_m, default=None)
    return nearest, reach


def columns_of(
    line: Line,
    distances: Sequence[float],
    grounds: Sequence[float | None],
    units: Sequence[SurfaceUnit],
    contacts: Sequence[Contact],
    faults: Sequence[FaultCrossing],
    bedding: Sequence[BeddingMeasurement],
    boreholes: Sequence[Borehole],
    settings: SectionSettings,
    thresholds: ConfidenceSettings,
) -> list[SectionColumn]:
    """The section's cells, column by column."""
    confidence = settings.confidence
    rows = max(1, math.ceil(settings.depth_m / settings.row_m))
    count = max(1, math.floor(line.length / settings.column_m))
    centres = [min(line.length, (k + 0.5) * line.length / count) for k in range(count)]
    columns = []
    for centre in centres:
        ground = _ground_at(distances, grounds, centre)
        nearest, reach = column_evidence(centre, bedding, boreholes, settings)
        evidence = (
            0.0
            if nearest is None
            else max(0.0, 1 - nearest.distance_m / confidence.evidence_range_m)
        )
        near_fault = any(abs(f.distance_m - centre) <= confidence.fault_zone_m for f in faults)
        fault = confidence.fault_factor if near_fault else 1.0
        cells = []
        for row in range(rows):
            top = row * settings.row_m
            if ground is None or top >= reach or not units:
                cells.append(SectionCell(top_m=top, state="unknown"))
                continue
            middle = top + settings.row_m / 2
            depth_factor = max(0.0, 1 - middle / confidence.depth_range_m)
            value = (confidence.map_only + (1 - confidence.map_only) * evidence) * depth_factor
            value *= fault
            cells.append(
                SectionCell(
                    top_m=top,
                    state="interpreted",
                    unit=unit_at(centre, ground - middle, units, contacts, faults),
                    depth_factor=depth_factor,
                    confidence=value,
                    label=label(value, thresholds),
                )
            )
        columns.append(
            SectionColumn(
                distance_m=centre,
                ground_m=ground,
                evidence=None if nearest is None else nearest.kind,
                evidence_m=None if nearest is None else nearest.distance_m,
                evidence_factor=evidence,
                fault_factor=fault,
                reach_m=reach,
                cells=tuple(cells),
            )
        )
    return columns


@dataclass(frozen=True, slots=True)
class BoreholePoint:
    """A water point with a recorded depth, in the line's CRS."""

    x: float
    y: float
    kind: str
    depth_m: float
    ground_m: float | None


def select_boreholes(
    line: Line, points: Sequence[BoreholePoint], settings: SectionSettings
) -> list[Borehole]:
    """The boreholes within ``max_distance_m`` of the line (its segment, not beyond its
    ends), the nearest ``max_count``, in order along the line."""
    boreholes = settings.boreholes
    near = []
    for p in points:
        distance, offset = line.place(p.x, p.y)
        clamped = min(max(distance, 0.0), line.length)
        gap = math.hypot(distance - clamped, offset)
        if gap <= boreholes.max_distance_m and p.depth_m > 0:
            near.append((gap, distance, offset, p))
    near.sort(key=lambda item: item[0])
    chosen = sorted(near[: boreholes.max_count], key=lambda item: item[1])
    return [
        Borehole(
            distance_m=distance,
            offset_m=offset,
            kind=p.kind,
            depth_m=p.depth_m,
            ground_m=p.ground_m,
        )
        for _, distance, offset, p in chosen
    ]


__all__ = [
    "BeddingPoint",
    "BoreholePoint",
    "Evidence",
    "Line",
    "apparent_dip_deg",
    "boundary_at",
    "column_evidence",
    "columns_of",
    "contacts_of",
    "place_bedding",
    "select_boreholes",
    "surface_units",
    "unit_at",
]
