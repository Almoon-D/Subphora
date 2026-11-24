# 0012 — Google base maps through the Map Tiles API in MapLibre

- Date: 2026-11-24 · Status: accepted · Follows 0005 · MASTER_PLAN §3, §4.1
- Context: 0005 left the route to session 01: Map Tiles API in MapLibre, or the Maps
  JavaScript API. Session 01 read the current terms (`docs/knowledge/google-maps.md`).
- Decision: the Map Tiles API (2D `satellite` and `roadmap`) as a MapLibre raster source.
  Its policy allows third-party renderers and overlays if the Google Maps logo and data
  attribution stay visible and apart from the others; tiles are never cached, packed or
  analysed; the key comes from the environment, the owner sets a daily quota (a hard cap)
  in the Cloud console, sized to stay inside the 100,000 free requests a month.
- Rejected: the Maps JavaScript API (its own renderer: a second map library beside MapLibre,
  and 10,000 free loads a month against 100,000 tiles).

Copyright (c) 2026 Almoon-D. All rights reserved.
