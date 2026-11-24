# Session 08 — Interpretive geological cross-section

Model and effort: Opus 5.5, high.

## Goal

The owner draws a line on the map and sees an interpretive section of the ground below it:
the surface profile, the geological units the line crosses, their dips projected downward,
nearby borehole logs, and the estimated water table, with confidence falling with depth and
distance from evidence, and "unknown" where there is none.

## Read

- `docs/MASTER_PLAN.md` § 4.4 (in full), § 4.3 (depth).
- `docs/decisions/` 0006 and 0011.
- `docs/knowledge/`: IGME (MAGNA units, structural data, borehole logs), IGN/CNIG (MDT).

## Build

1. A section service in `model/`: sample the LiDAR profile along the line; intersect the
   geological units; project each unit's boundary downward with the nearest recorded dip
   (apparent dip along the line's direction); place borehole logs within a distance from
   `config/`; add the water-table estimate from session 07 where it exists.
2. Confidence per section cell from depth and distance to the nearest dip measurement or
   borehole (parameters in `config/`); below the deepest evidence, "unknown", drawn as such.
3. The front end: draw a line, then a section panel with vertical exaggeration shown, a
   legend, the "interpretation" label always visible, and tap-to-explain on any part.
4. Tests: apparent-dip arithmetic, a line with no dip data (units drawn without projection,
   confidence low), a line crossing a fault, borehole selection by distance, the "unknown"
   zone.

## DO NOT BUILD

- A 3D model of the subsurface; any inversion of geophysical data (hardware, session 16).

## Done when

- `make check` is green and in `make dev` a line drawn on the owner's test area shows its
  section with confidence and the "interpretation" label.

Copyright (c) 2026 Almoon-D. All rights reserved.
