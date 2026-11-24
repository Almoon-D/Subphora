# Session 12 — Per-parcel report and professional pack

Model and effort: Opus 5.5, medium.

## Goal

From an area, the owner exports a PDF that a hydrogeologist or the water authority can read,
and a ZIP with the underlying layers and tables.

## Read

- `docs/MASTER_PLAN.md` § 4.6, § 3 (Licences).

## Build

1. `report/` (WeasyPrint), its import-linter contract: map images, candidates with score,
   confidence, depth, cost and legal status, explanations, validation skill, every source
   with date and attribution, the limitations, and the legal disclaimer. Spanish text from
   the translation catalogue.
2. The export pack: the PDF plus GeoPackage (area, candidates, observations without private
   media unless the owner ticks it) and COGs (index, confidence, depth).
3. Tests: the PDF contains every required section and attribution; a missing input appears
   as missing, not blank; the pack opens and its CRS is declared.

## DO NOT BUILD

- Sending reports anywhere; deployment.

## Done when

- `make check` is green and in `make dev` the owner downloads the PDF and the ZIP for an area.

Copyright (c) 2026 Almoon-D. All rights reserved.
