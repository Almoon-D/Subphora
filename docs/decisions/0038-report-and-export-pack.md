# 0038 — The report: one shared catalogue, WeasyPrint with no fetching, GDAL for the pack

- Date: 2026-11-26 · Status: accepted · MASTER_PLAN §4.6, hard rules 1, 2, 4
- Decision: the Spanish catalogue moves to `web/src/i18n/es.json`, read by the browser and by
  `report/` alike, so a message is written once. `report/` (above `services`, below `api`)
  builds the PDF as HTML printed by WeasyPrint, whose fetcher accepts only embedded `data:`
  images; its maps are the detailed map's own grids, north up in the area's CRS, with no
  base map. The pack is a ZIP: the PDF, `layers.gpkg` (area, candidates, observations) and
  COGs of index, confidence and depth written by GDAL (pyogrio, rasterio), CSV tables, a
  manifest listing what is missing and why; field photos only when the owner ticks them.
- Cost: CI installs Pango and HarfBuzz-subset with apt, about 15 s a run (~5 min a month).
- Rejected: a separate Python catalogue (two copies drift); a browser-printed PDF (no
  control of pages); hand-written GeoPackage SQL; PNOA under the maps (a network call).

Copyright (c) 2026 Almoon-D. All rights reserved.
