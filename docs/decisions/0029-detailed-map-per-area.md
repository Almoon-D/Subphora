# 0029 — The detailed map of an area: a cached job at 5 m, structure from MAGNA

- Date: 2026-11-25 · Status: accepted · MASTER_PLAN §4.3 (parcel scale), decisions 0006, 0027
- Decision: `POST /api/parcel` runs one job per area (id: hash of outline, settings, version),
  `jobs.workers` at a time, computing in a process pool; the result is cached on disk. The
  grid: the area's UTM zone (REGCAN95 in the Canaries) at 5 m, read over the area plus 2 km,
  kept inside the area. Terrain is MDT05 (MDT02 is a download whose route is unverified).
  Structure splits into MAGNA fault density (0.06) and nearest bedding dip (0.04): missing
  nationally, present here. Candidates need "medium" confidence, carry "not evaluated".
- Rejected: MAGNA lithology for permeability (free-text legends, no class); one structure
  grid hiding which input counted; a buffer under the drainage lookup's last break (a capped
  distance would read as near); tiles per area (one image each is enough).

Copyright (c) 2026 Almoon-D. All rights reserved.
