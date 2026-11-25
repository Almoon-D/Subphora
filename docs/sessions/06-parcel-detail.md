# Session 06 — Parcel-scale detail, explanation and candidate spots

Model and effort: Opus 5.5, high.

## Goal

For a selected area the app computes a detailed potential map (default 5 m), explains any
point when tapped, ranks candidate spots, and compares several selected areas side by side.

## Read

- `docs/MASTER_PLAN.md` § 4.3 (in full), § 4.2.
- `docs/decisions/` 0006, 0027 (the model v0) and 0028 (the national build).
- The session-05 code to reuse, not duplicate: `subphora.model` (`evaluate`, `explain_cell`,
  `dataset_quality`), `config/defaults/model.yaml`, `subphora.geo.terrain` and
  `subphora.geo.raster`, and the domain estimate `subphora.domain.potential`.
- `docs/knowledge/`: IGN/CNIG (MDT02/MDT05), IGME (MAGNA, faults).
- `src/subphora/domain/aoi.py` (decision 0026): a selected area is an `AreaOfInterest`, an
  outline or a point (an address, coordinates, a drawn point); the session's list of them
  lives in the browser (`web/src/search/areas.ts`).

## Build

1. A per-area job: clip the detailed inputs (MDT02 where the download covers the area, else
   MDT05 from the IGN WCS — `VERIFY-LIVE(cnig-mdt02-coverage)`; MAGNA 1:50,000, faults, water
   points, digital dip measurements, the soil map), derive slope, wetness index, drainage and
   lineament density, and the dip of permeable layers as a structural input; publish the slope,
   drainage and wetness layers at parcel resolution; and compute index and
   confidence with the session-05 model at parcel resolution; cached per area; job status
   visible in the UI.
2. Tap-to-explain at parcel scale: score, each input's value, contribution, source, date and
   resolution, missing inputs, confidence breakdown.
3. Candidates by the §4.3 rule, each with legal status "not evaluated" (hard rule 2).
4. Comparison of selected areas: area, best candidates, mean index and confidence.
5. Tests: clipping at area edges and across UTM zones, a missing detailed input lowering
   confidence, candidate separation and minimum confidence, the job's failure states.

## DO NOT BUILD

- Validation, calibration, depth or cost; the legal filter; reports.

## Done when

- `make check` is green and in `make dev` a selected parcel shows its detailed map, tap-to-explain
  and ranked candidates, and two parcels can be compared.

Copyright (c) 2026 Almoon-D. All rights reserved.
