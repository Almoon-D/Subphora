# 0043 — The owner's water levels: typed offline, kept at rest, private beside the public

- Date: 2026-11-27 · Status: accepted · MASTER_PLAN §4.3, §4.7; 0031, 0036, 0040, 0042
- Decision: a reading states its reference (ground, or casing top and its height), who read
  it, and the pump (stopped, running, unknown) with its minutes. It goes to IndexedDB with an
  outbox entry, then in batches to `POST /api/wells/readings`; the device keeps the registry
  as last read. Only readings stopped `min_rest_minutes` or more (or for an unstated time)
  make a well's level, summarised as piezometers are, ground and body from the area's grid.
  A tap gets the depth public and with them, computed when asked; maps, candidates, report
  and pack keep the public one.
- Rejected: a field record kind (two stores); levels written into the piezometry file; an
  unknown pump counted as at rest; recomputing every area on each reading.

Copyright (c) 2026 Almoon-D. All rights reserved.
