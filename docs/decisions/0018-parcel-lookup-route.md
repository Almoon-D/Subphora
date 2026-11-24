# 0018 — Parcel lookup: the WFS in EPSG:4326, places from the non-protected data service

- Date: 2026-11-24 · Status: accepted · MASTER_PLAN §3 (Coordinates), §4.2
- Decision: ask the WFS in EPSG:4326 and reproject from each answer's own `srsName`; name the
  place with `Consulta_DNPRC` (the WFS has no municipality); cache both for the catalogue's
  lifetime, only once they parse. Choose the local CRS from the reference point afterwards
  (an urban reference does not say where it is). Refuse a rustic reference in an excluded
  province before any call. No access log: paths carry references that may be the owner's.
- Rejected: asking in the local CRS (unknown before the answer; EPSG:4083 is ignored);
  caching "not found" (a new parcel would stay invisible for a week).

Copyright (c) 2026 Almoon-D. All rights reserved.
