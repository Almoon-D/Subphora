# Session 07 — Validation, calibration, depth and drilling cost

Model and effort: Opus 5.5, high.

## Goal

The owner sees how well the model actually discriminates against known wells in each area,
including an explicit "no better than chance here"; where enough wells exist the index
becomes a probability with an interval; candidates show an estimated depth to water and a
drilling-cost range.

## Read

- `docs/MASTER_PLAN.md` § 4.3 (validation, depth and cost).
- `docs/knowledge/`: IGME water points, MITECO and basin piezometry (`water-authorities.md`).
- Decision 0029 and the detailed map it extends: `subphora.services.parcel_compute` (where
  candidates are made), `subphora.domain.parcel_map` (`Candidate.depth` is "not_estimated"
  until this session), and the confidence's `skill` component in `subphora.model`.

## Build

1. Labelled points from public water points (productive, dry where recorded), with their
   source; spatial block cross-validation; AUC with a bootstrap interval per hydrogeological
   domain; thresholds in `config/`. Results shown on the map and in tap-to-explain.
2. Calibration where labelled wells pass the threshold; elsewhere the index stays an index.
3. Import piezometric levels: the national piezometry database the owner downloads by hand
   into `data/` (its form is human-only: never automate it) and the basin spreadsheets
   catalogued in session 01 (`chguadiana-piezometry`, `chebro-piezometry`, `chj-piezometry`),
   after `VERIFY-LIVE(piezometric-levels)` and `VERIFY-LIVE(basin-terms)`. Water-table surface per
   groundwater body from piezometric levels, uncertainty growing
   with distance, "unknown" past the maximum distance; depth = ground elevation − water table,
   flagged in karst.
4. Drilling cost: depth range × cost per metre plus fixed costs, `Decimal`, values in
   `config/` with source and date (the owner can override with local quotes).
5. Tests: validation on synthetic data with known skill (including chance level), the
   no-better-than-chance flag, calibration refused below the threshold, depth across a
   body boundary refused, cost arithmetic in `Decimal`.

## DO NOT BUILD

- The legal filter; learning from the owner's wells (session 14).

## Done when

- `make check` is green and in `make dev` each area shows its validation result, and each
  candidate its depth and cost range or an explicit "unknown".

Copyright (c) 2026 Almoon-D. All rights reserved.
