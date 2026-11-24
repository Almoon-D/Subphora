# Session 14 — Satellite and climate layers

Model and effort: Opus 5.5, high.

## Goal

The late-summer vegetation anomaly (Sentinel-2 NDVI, with irrigated land masked) becomes a
model input where it adds skill, and ground motion (EGMS) and rainfall and recharge (AEMET)
appear as context layers.

## Read

- `docs/MASTER_PLAN.md` § 4.3 (Criteria), decision 0003.
- `docs/knowledge/` Copernicus, AEMET, SIGPAC (irrigation attribute).

## Build

1. The NDVI anomaly per area for late summer against a multi-year baseline, masking
   irrigated enclosures; added to the model only if validation (session 07) improves.
2. EGMS and AEMET context layers; not model inputs.
3. Tests on synthetic rasters, the mask, and the add-only-if-it-helps rule.

## DO NOT BUILD

- GRACE or other coarse products (decision 0003).

## Done when

- `make check` is green and the new layers show on the map, with the validation result
  that decided whether NDVI enters the model.
