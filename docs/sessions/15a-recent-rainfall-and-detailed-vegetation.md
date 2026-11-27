# Session 15a — Recent rainfall and the vegetation anomaly on the detailed map

Model and effort: Opus 5.5, high.

## Goal

The map shows recent rainfall from AEMET (the last hydrological year against the normal)
as a context layer, read with the owner's key, and the detailed map reads the late-summer
vegetation anomaly at 10 m where its domain admitted it.

## Read

- `docs/MASTER_PLAN.md` § 4.3 (Criteria), decisions 0003, 0041.
- `docs/knowledge/aemet.md`, `docs/knowledge/copernicus.md` (Earth Search route).
- `src/subphora/services/vegetation.py`, `src/subphora/services/parcel_compute.py`.

## Build

1. Before anything else, ask the owner for `AEMET_API_KEY` in the environment (never in the
   repository). Without it, stop: report in the PR and build nothing of item 2.
2. AEMET recent rainfall: the stations' monthly totals of the last hydrological year
   (October-September) against their normal, as points or a context grid on the map; not a
   model input. Record the two-step answers and the rate limit in `aemet.md`.
3. The vegetation anomaly on the detailed map: the same composite at 10 m around the
   parcel (bands at full resolution, the area only), its anomaly and irrigation mask, used
   only where the area's domain admitted the criterion on the national map.
4. Tests: AEMET answers from recorded fixtures (no key in tests), the detailed anomaly on
   synthetic bands, and the domain's admission carried over.

## DO NOT BUILD

- GRACE or other coarse products (decision 0003); a temporal NDVI anomaly.

## Done when

- `make check` is green, the rainfall layer shows on the map with the owner's key, and a
  detailed map in an admitting domain lists the vegetation among its inputs.

Copyright (c) 2026 Almoon-D. All rights reserved.
