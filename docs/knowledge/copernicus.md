# Copernicus (Sentinel-2, EGMS)

Hosts `stac.dataspace.copernicus.eu`, `earth-search.aws.element84.com`,
`sentinel-cogs.s3.us-west-2.amazonaws.com`, `egms.land.copernicus.eu`. Catalogue ids:
`copernicus-stac`, `earth-search`, `sentinel-cogs`, `egms`. The build reads Sentinel-2
through Earth Search (decision 0041). Findings observed on 2026-11-24 and 2026-11-27.

## Sentinel-2 — Copernicus Data Space Ecosystem

- The STAC catalogue `https://stac.dataspace.copernicus.eu/v1` is public: the collection
  `sentinel-2-l2a` and searches answer without an account, with CORS `*`.
  `(GET /collections/sentinel-2-l2a, 2026-11-24)`
- A search over Daimiel (Ciudad Real) for August 2026 returned
  `S2C_MSIL2A_20260830T105621_N0512_R094_T30SVJ_20260830T144012` (tile T30SVJ); its assets
  (`B04_10m`, `B08_10m`, `SCL_20m`…) point to `s3://eodata/…`: reading the pixels needs a
  free CDSE account (S3 keys or an OAuth token), which session 15 requests from the owner.
  `(GET /search, 2026-11-24)`
- Licence: the collection links the Sentinel data legal notice
  (`https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice`):
  free and open use; attribution "Contains modified Copernicus Sentinel data [year]".
  `(GET /collections/sentinel-2-l2a, 2026-11-24)`

## Sentinel-2 — Earth Search on AWS Open Data (the route used)

- `https://earth-search.aws.element84.com/v1` is a public STAC API (Element 84): no
  account, no key. `GET /search?collections=sentinel-2-l2a&bbox=…&datetime=…&limit=…`
  answers a GeoJSON `FeatureCollection`; the next page is the `links` entry with
  `rel: next` and `method: GET`. `(GET /search, 2026-11-27)`
- Each item states `grid:code` (`MGRS-30SVJ`), `eo:cloud_cover`, `datetime` and
  `s2:processing_baseline` (`05.11` for August 2025). Assets `red` (B04), `nir` (B08)
  and `scl` are cloud-optimised GeoTIFFs on
  `https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/30/S/VJ/2025/8/S2B_30SVJ_20250830_0_L2A/B04.tif`,
  readable over HTTPS range requests without credentials. `(GET /search, 2026-11-27)`
- `raster:bands` gives `scale: 0.0001`, `offset: -0.1`, `nodata: 0` for B04 and B08
  (the baseline-04.00 offset applied); `scl` has `nodata: 0` and no scale. Reflectance =
  DN × scale + offset. `(GET /search, 2026-11-27)`
- A band file is a 10,980 × 10,980 tile at 10 m (SCL at 20 m) in WGS 84 / UTM
  (`EPSG:32630` for zone 30), 1024-pixel blocks, overviews ×2, ×4, ×8, ×16: a read at
  80 m fetches only the ×8 overview. `(GDAL /vsicurl/ B04.tif, 2026-11-27)`
- Scene classification classes used as clear land: 4 (vegetation) and 5 (not vegetated);
  clouds, shadows, water and snow are left out (ESA's L2A product definition).
- A late-summer composite over Daimiel (5 summers, 2 scenes each) shows the Tablas wetland
  and the riparian strip of the Guadiana as positive anomalies, as expected.
  `(smoke run, 2026-11-27)`
- Licence: the collection's `license` link is the Sentinel data legal notice
  (`https://sentinel.esa.int/documents/247904/690755/Sentinel_Data_Legal_Notice`), the
  same terms as CDSE. `(GET /collections/sentinel-2-l2a, 2026-11-27)`
- The landing page ("Earth Search by Element 84: a STAC API of public datasets on AWS")
  links its OpenAPI description and stac-server, and no terms of use or rate limit; the
  catalogue sets two requests at a time. `(GET /v1/, 2026-11-27)`

## European Ground Motion Service (EGMS)

- `https://egms.land.copernicus.eu/` is a viewer; it offers levels Basic (2A), Calibrated
  (2B) and Ortho (3) and says "Log in with EU Login to access search of the product
  archive": downloads need a free EU Login account. `(GET /, 2026-11-24)`
- Licence: the Copernicus Land Monitoring Service data policy (free and open, with
  attribution). The policy page `land.copernicus.eu/en/data-policy` did not answer from the
  cloud session; `VERIFY-LIVE(egms-terms)`.
- The build reads the Ortho (level 3) vertical product the owner downloads: one GeoTIFF
  per 100 km tile, named `EGMS_L3_<tile>_100km_U_<period>.tif`, mean vertical velocity in
  mm/year at 100 m in `EPSG:3035`. This is ESA's published product description; no file
  was downloaded from the cloud session (EU Login): `VERIFY-LIVE(egms-format)`.

Copyright (c) 2026 Almoon-D. All rights reserved.
