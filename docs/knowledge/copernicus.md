# Copernicus (Sentinel-2, EGMS)

Hosts `stac.dataspace.copernicus.eu`, `egms.land.copernicus.eu`. Catalogue ids:
`copernicus-stac`, `egms`. Access route and licence only: these are used in session 15.
Findings observed on 2026-11-24.

## Sentinel-2 — Copernicus Data Space Ecosystem

- The STAC catalogue `https://stac.dataspace.copernicus.eu/v1` is public: the collection
  `sentinel-2-l2a` and searches answer without an account, with CORS `*`.
  `(GET /collections/sentinel-2-l2a, 2026-11-24)`
- A search over Antequera for August 2026 returned
  `S2C_MSIL2A_20260830T105621_N0512_R094_T30SUG_20260830T144012` (tile T30SUG); its assets
  (`B04_10m`, `B08_10m`, `SCL_20m`…) point to `s3://eodata/…`: reading the pixels needs a
  free CDSE account (S3 keys or an OAuth token), which session 15 requests from the owner.
  `(GET /search, 2026-11-24)`
- Licence: the collection links the Sentinel data legal notice
  (`https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice`):
  free and open use; attribution "Contains modified Copernicus Sentinel data [year]".
  `(GET /collections/sentinel-2-l2a, 2026-11-24)`

## European Ground Motion Service (EGMS)

- `https://egms.land.copernicus.eu/` is a viewer; it offers levels Basic (2A), Calibrated
  (2B) and Ortho (3) and says "Log in with EU Login to access search of the product
  archive": downloads need a free EU Login account. `(GET /, 2026-11-24)`
- Licence: the Copernicus Land Monitoring Service data policy (free and open, with
  attribution). The policy page `land.copernicus.eu/en/data-policy` did not answer from the
  cloud session; `VERIFY-LIVE(egms-terms)` before session 15 uses the data.

Copyright (c) 2026 Almoon-D. All rights reserved.
