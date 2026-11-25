# Session 05 — National water-potential map v0

Model and effort: Opus 5.5, high.

## Goal

When the app opens, all of Spain is coloured by the water-potential index with a confidence
layer next to it, both computed from nationwide public data by a batch command. The owner
can zoom from Spain to a parcel and tap any point for the index, confidence and inputs.

## Read

- `docs/MASTER_PLAN.md` §§ 3, 4.3 (in full), 5.
- `docs/decisions/` 0006.
- `docs/knowledge/`: the nationwide-inputs findings from session 01, IGME, MITECO, IGN/CNIG.

## Build

1. `model/`: criteria, suitability lookups and weights in `config/` (each weight and class
   with its source), the weighted score with renormalisation over present inputs, and the
   confidence components of §4.3. The domain models enforce hard rule 1.
2. `geo/`: the national grid (EPSG:3035, a separate Canaries grid), resolution from
   `config/`, terrain derivatives at that resolution.
3. `subphora national build [--region <province|bbox>|--all]`: downloads the nationwide
   inputs politely to `data/`, computes index and confidence grids, and writes raster tiles
   (PMTiles) for display. CPU work in a process pool. `--region` takes an ISO 3166-2 code
   (a province such as ES-Z, or a region). Run it in this session for two provinces in
   different hydrogeological settings; the owner runs `--all` on a machine with enough disk.
   Nothing in the code or config names a test area (decision 0014).
4. The slope, drainage and wetness-index grids are also published as map layers with legends
   (the owner asked to see them, not only to have them in the model).
5. The front end shows the index and the confidence layer (legend says "index", not
   "probability"), and tap-to-explain on the national grid.
6. Tests: scoring and confidence on synthetic grids (all inputs, some missing, none),
   renormalisation, the "index" label, the build command on a tiny synthetic region, and
   failure of a download.

## DO NOT BUILD

- The parcel-scale grid, candidates, validation, calibration, depth or cost; the legal filter.

## Done when

- `make check` is green, `subphora national build --region <province code>` produces tiles, and in
  `make dev` the map shows the index and confidence over that region with tap-to-explain.

Copyright (c) 2026 Almoon-D. All rights reserved.
