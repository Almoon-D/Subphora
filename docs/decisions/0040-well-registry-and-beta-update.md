# 0040 — The owner's wells: a private registry and a Beta update shown as its own layer

- Date: 2026-11-27 · Status: accepted · MASTER_PLAN §4.3 (Learning), §3 (Privacy); 0030
- Decision: wells and their water levels live in `data/wells/` (SQLite; in the nightly
  backup; never logged; in an export pack only with `wells=true`). The map's value at a cell
  (the calibrated probability where its domain is calibrated, else the index, still labelled
  an index) is a Beta prior worth `prior_strength` wells; each productive or dry well adds a
  weight of 1, halving every `half_weight_m` and 0 beyond `range_m` (`wells.yaml`; starting
  judgements, not measured). The updated layer is computed when asked, beside the unchanged
  map. The owner's wells grade the national index per domain, productive against dry, with
  0030's thresholds, reported apart from IGME's.
- Rejected: changing the stored map (no comparison, no undo); kriging the outcomes (needs a
  fitted variogram from far more wells); a machine-learning model (later, past a threshold).

Copyright (c) 2026 Almoon-D. All rights reserved.
