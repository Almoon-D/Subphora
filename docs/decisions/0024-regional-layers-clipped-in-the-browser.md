# 0024 — Regional layers: the rule as data, official boundaries on one grid, clipped in the browser

- Date: 2026-11-24 · Status: accepted · MASTER_PLAN §4.1, decisions 0021 and 0023
- Context: three regional layers qualify; each must be drawn and asked only inside its area.
- Decision: the rule of 0023 is data (`regional.yaml`); the settings refuse a layer that
  fails it, and an unstated national edition qualifies nothing over it. Areas come from the
  IGN (communities) and MITECO (districts), every vertex rounded to one 0.0001° grid so
  shared borders stay shared. The browser clips regional tiles to their areas over the
  national layer; a tap uses the same boundaries in the API, regional first, national when
  the regional has nothing, fails or times out, saying which answered.
- Rejected: masking tiles on the server (an imaging library, every tile through the API);
  simplifying each boundary alone (neighbours gap or overlap); asking the IGN per tap.

Copyright (c) 2026 Almoon-D. All rights reserved.
