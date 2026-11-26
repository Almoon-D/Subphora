# 0031 — Depth to water from the national piezometry database; cost as a Decimal range

- Date: 2026-11-26 · Status: accepted · MASTER_PLAN §4.3 (depth, cost)
- Decision: `subphora piezometry import` reads the hand-downloaded Access file with
  `mdb-export` (median of each piezometer's last 5 years, 10-90 % range). Water table: an
  inverse-distance mean of the spot's own body's piezometers within 5 km, widened 2 m/km to
  the nearest; else "unknown" with its reason. Depth = MDT ground − table, flagged in karst.
  Cost = (depth + 20 m) × €/m + fixed, in Decimal, from `drilling.yaml` (sources, date).
- Rejected: `access-parser` (misaligned text, empty levels on this file); interpolating
  across bodies; basin spreadsheets now (unreachable from the cloud, formats unverified).

Copyright (c) 2026 Almoon-D. All rights reserved.
