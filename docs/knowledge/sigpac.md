# SIGPAC (FEGA)

Host `sigpac-hubcloud.es`. Catalogue ids: `sigpac-wms`, `sigpac-queries`, `sigpac-ogcapi`.
Findings observed on 2026-11-24.

## Where SIGPAC is served

- The service catalogue at `https://sigpac-hubcloud.es/` lists: a codes-list service, vector
  tiles (MVT, EPSG:3857, current and previous campaign), a WMS, query services (JSON and
  GeoJSON), an OGC API Features service, a graphic-output service and per-province GeoPackage
  downloads. It states the data are published under **CC BY 4.0**. `(GET /, 2026-11-24)`
- The older hosts did not answer from the cloud session: `sigpac.mapa.gob.es` and
  `www.fega.gob.es` (TLS tunnel failed), `wms.mapa.gob.es/sigpac/wms` (HTTP 502). Whether
  they still serve SIGPAC is unknown; the hubcloud services are the ones catalogued.
  `(GET /, 2026-11-24)`
- Every response is gzip-compressed and carries `Access-Control-Allow-Origin: *`.
- The national service covers every region, Navarra included (an enclosure at 42.75 N,
  1.70 W answered with province 31), unlike Catastro. Regional SIGPAC viewers were not
  probed; nothing in the plan needs them. `(recinfobypoint, 2026-11-24)`

## Query services — `https://sigpac-hubcloud.es/servicioconsultassigpac/query/…`

- By code, one enclosure: `recinfo/{pr}/{mu}/{ag}/{zo}/{po}/{pa}/{re}.json` (or `.geojson`);
  all enclosures of a parcel: `recinfoparc/{pr}/{mu}/{ag}/{zo}/{po}/{pa}.json`; at a point:
  `recinfobypoint/4258/{lon}/{lat}.json`; the cadastral reference of a parcel:
  `refcatparcela/{pr}/{mu}/{ag}/{zo}/{po}/{pa}.json`. The reference is
  province:municipality:aggregate:zone:polygon:parcel:enclosure.
  `(recinfo, recinfobypoint, refcatparcela, 2026-11-24)`
- Fields: `provincia, municipio, agregado, zona, poligono, parcela, recinto, superficie`
  (ha), `pendiente_media` (%), `coef_regadio`, `admisibilidad`, `incidencias`, `uso_sigpac`,
  `region`, `altitud`, `srid` (4258) and `wkt`. Example: 34:48:0:0:13:12:1 in Tierra de
  Campos, 6.2744 ha, use `TA` (arable). `(recinfo, 2026-11-24)`
- Not found: HTTP 200 with an empty list `[]`. `(recinfo 29/15/0/0/167/99999/1, 2026-11-24)`
- `refcatparcela` returned `34048A013000120000UQ` for 34:48:0:0:13:12, but an empty
  `"referencia_cat": ""` for 29:15:0:0:167:21, a rustic parcel Catastro does have: the link
  SIGPAC → Catastro is not always filled. Session 04 must not rely on it.
  `(refcatparcela, 2026-11-24)`

## WMS — `https://sigpac-hubcloud.es/wms`

- Layers `AU.Sigpac:recinto`, `AU.Sigpac:cultivo_declarado`, `AU.Sigpac:e_paisaje`
  (and line and point variants); EPSG:3857 offered; `AccessConstraints` "none". A GetMap of
  `AU.Sigpac:recinto` in EPSG:3857 returns a PNG. `(GetCapabilities, GetMap, 2026-11-24)`

## OGC API Features — `https://sigpac-hubcloud.es/ogcapi`

- Collections `recintos`, `cultivo_declarado`, `elementos_paisaje_area`,
  `elementos_paisaje_linea`, `elementos_paisaje_punto`; geometry in WGS 84, longitude-latitude
  order. Items by id: `/collections/recintos/items/{id}?f=json`. `(GET /collections, 2026-11-24)`

## Terms

- CC BY 4.0, per the catalogue page. Attribution used: "SIGPAC, FEGA, CC BY 4.0". No
  published rate limit; the catalogue sets two requests at a time, half a second apart.

Copyright (c) 2026 Almoon-D. All rights reserved.
