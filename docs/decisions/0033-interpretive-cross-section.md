# 0033 — The cross-section: a straight line, MAGNA units and dips, unknown below the evidence

- Date: 2026-11-26 · Status: accepted · MASTER_PLAN §4.4, decisions 0006, 0011, 0029, 0031
- Decision: `POST /api/section` takes a straight line (100 m to 5 km), samples MDT05 every
  5 m, reads MAGNA units (layer 11, `DLO`) and projects each contact with the apparent dip
  tan δ·cos(α − θ) of the nearest bedding measurement within 1.5 km (`DIRECCION` read as dip
  direction); with none it stays vertical, "not projected". Faults split it into blocks that
  nothing crosses. Cells carry a confidence falling with depth and distance to a dip or
  borehole, "unknown" below the evidence (map 30 m, dip 150 m, a borehole its depth).
- Rejected: polylines (bends blur the apparent dip); guessing a fault's dip or throw;
  borehole logs (the inventory has depths only); a job (it takes seconds).

Copyright (c) 2026 Almoon-D. All rights reserved.
