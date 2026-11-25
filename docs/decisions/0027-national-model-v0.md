# 0027 — The national model v0: nine criteria, seven with nationwide data, confidence that says so

- Date: 2026-11-25 · Status: accepted · MASTER_PLAN §4.3, decision 0006, hard rule 1
- Decision: `model.yaml` holds the nine criteria of §4.3, expert-default weights (sum 1) and
  lookups, each with its source. Seven have nationwide grids (IGME permeability; slope,
  wetness and drainage from MDT25; SoilGrids clay; MITECO body status; distance to IGME water
  points); structure and piezometric depth have none, so coverage stays at most 0.80, and
  skill is "not measured" (0) until session 07: no cell reaches "high" confidence yet.
- An estimate refuses a missing confidence, source or criterion, a score that is not the sum
  of its contributions, and any kind but "index". A tap is explained with the settings stored
  with its region's build, so it agrees with the tiles. Overlapping bodies: worse status wins.
- Rejected: dropping criteria without data from the weights (hides what is missing); water
  points only for validation (the plan lists them as a criterion; session 07 keeps them out
  of its own folds).

Copyright (c) 2026 Almoon-D. All rights reserved.
