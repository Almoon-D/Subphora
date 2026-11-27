# 0041 — The late-summer vegetation anomaly enters only where validation admits it

- Date: 2026-11-27 · Status: accepted · MASTER_PLAN §4.3 (Criteria); 0003, 0030
- Decision: Sentinel-2 L2A through Earth Search and its public AWS COGs (no account; GDAL
  reads the 80 m overview). Per tile, the 2 least cloudy scenes of each of the last 5
  summers (15 Jul-15 Sep), clear-land classes only; the median per summer, then over at
  least 3 summers. The anomaly is a cell minus the mean of the non-irrigated land within
  2 km; SIGPAC enclosures with `coef_regadio` ≥ 1 mask it (share ≥ 0.25). The criterion
  (`admission: validated`) is tried per domain on the same wells and background; it enters
  only where the paired bootstrap gain in AUC has its lower bound above 0. EGMS (owner's
  downloads) and SIMPA recharge and rainfall (MITECO) are context layers only.
- Rejected: CDSE (needs an account and full-resolution reads); a temporal anomaly (needs
  per-year baselines, and drought years swamp it); entering everywhere on the literature's
  word; AEMET for recharge (it publishes none; recent rainfall waits for the owner's key).

Copyright (c) 2026 Almoon-D. All rights reserved.
