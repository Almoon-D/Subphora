# Session 14 — Well registry and learning from the field

Model and effort: Opus 5.5, high.

## Goal

The owner records their wells (location, depth, flow, water levels over time, dry or
productive) and drilled-well results, and the potential map updates locally from them.

## Read

- `docs/MASTER_PLAN.md` § 4.3 (Learning), § 3 (Privacy).

## Build

1. A private well registry (`store/`, `data/` only) with water-level readings over time and
   CSV import of existing records.
2. Bayesian update of the calibrated probability (or index) with a spatially decaying
   likelihood, range in `config/`, shown as a separate "updated with your wells" layer so
   the owner can compare.
3. The owner's wells added to the validation of session 07, reported separately.
4. Tests: the update on synthetic wells (one productive, one dry), range limits, privacy (no
   registry data in logs or exports unless chosen).

## DO NOT BUILD

- A machine-learning model (only past the `config/` threshold, in a later session); sensor
  dashboards.

## Done when

- `make check` is green and a logged well changes the nearby probabilities visibly in the
  updated layer.

Copyright (c) 2026 Almoon-D. All rights reserved.
