# 0025 — A national layer published in parts is compared by its parts over the area

- Date: 2026-11-24 · Status: accepted · MASTER_PLAN §4.1, decisions 0023 and 0024
- Context: GEODE states no single edition; each of its zones has its own (2007-2014). Under
  0024 nothing would qualify over it, though Navarra's and the Valencian 1:25,000 geology
  are newer than every GEODE zone over them. One service draws only to zoom 14.
- Decision: a regional layer may state `national_edition`, the newest edition of the
  national layer's parts over its areas, read from the publisher's metadata; only when the
  national layer states none. A regional layer may state `max_zoom`; the browser enlarges
  that level beyond it.
- Rejected: giving GEODE one edition (a tap would show a year that is wrong in most
  zones); the oldest zone's year (lets a regional layer older than its own zone qualify).

Copyright (c) 2026 Almoon-D. All rights reserved.
