# Session 17 — Water levels in the field

Model and effort: Opus 5.5, high.

## Goal

The owner types a water level for one of their wells at the well head with no coverage
(their own reading, a driller's or a contractor's: decision 0042 buys no instrument), and
the reading reaches the well registry and the depth to water without being lost.

## Read

- `docs/MASTER_PLAN.md` § 4.7 (Field mode and offline), § 4.3 (Learning); decisions 0031,
  0036, 0040, 0042.
- `src/subphora/store/wells.py`, `src/subphora/services/wells.py`, `src/subphora/model/depth.py`,
  `web/src/wells/`, `web/src/field/outbox.ts`, `web/src/field/db.ts`.
- ROADMAP → Follow-ups from session 14.

## Build

1. A reading typed in the well panel with no connection is written to IndexedDB first and
   travels through the outbox (client-generated id, server upsert, append-only), as field
   records do (hard rule 5). Today the panel refuses it.
2. A reading records depth to water below a stated reference (top of casing or ground), the
   reference's height above ground, the time, who measured it (owner, driller, contractor),
   and whether the pump was running or stopped (and for how long), since a pumping well
   reads low.
3. The owner's readings enter depth to water as private levels inside their groundwater
   body, apart from the public piezometry, with their dates; a reading taken while pumping
   never does.
4. Tests: offline entry, reload mid-sync and retry (browser), the pumping flag kept out of
   depth, privacy (no reading in logs or unticked exports).

## DO NOT BUILD

- Instrument code of any kind, loggers or any automatic reading (decision 0042).

## Done when

- `make check` is green, and a reading typed offline in the browser test appears in the
  registry after the connection returns, and moves the depth to water at that well.

Copyright (c) 2026 Almoon-D. All rights reserved.
