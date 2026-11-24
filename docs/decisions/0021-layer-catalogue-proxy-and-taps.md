# 0021 — Official layers: one catalogue, a tile proxy only where needed, taps through the API

- Date: 2026-11-24 · Status: accepted · MASTER_PLAN §4.1, hard rules 4 and 6
- Context: session 03 draws 17 official WMS layers; 14 offer CORS and EPSG:3857, REDIAM's
  two lack CORS and IGME's lithostratigraphic map lacks EPSG:3857. Taps must never show
  protected data, and the services answer in three formats (GeoJSON, ArcGIS XML, MapServer GML).
- Decision: `config/defaults/map.yaml` lists every layer (service, zoom range, opacity,
  legend, tap fields); `/api/map` serves it. A layer is drawn by the browser from its
  service when it has CORS and EPSG:3857, otherwise through `/api/layers/{id}/tiles`, which
  asks a layer without EPSG:3857 for its ArcGIS export (same map service, in 3857). Every
  tap goes through `/api/layers/{id}/info`, which keeps only the fields the catalogue lists.
- Rejected: proxying every layer (load and delay on our server for no gain); reprojecting
  WMS images on the server (an imaging library for one layer); using the lithostratigraphic
  WMS in EPSG:3857, which works but is not advertised; taps from the browser where CORS
  allows (no field allowlist, three parsers in the front end).

Copyright (c) 2026 Almoon-D. All rights reserved.
