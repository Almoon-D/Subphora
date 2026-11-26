# IGN / CNIG

Hosts `www.ign.es`, `servicios.idee.es`, `www.cartociudad.es`, `centrodedescargas.cnig.es`.
Catalogue ids: `ign-pnoa-wmts`, `ign-pnoa-wms`, `ign-base-wmts`, `ign-mdt-wcs`,
`cartociudad`, `cnig-downloads`. Findings observed on 2026-11-24.

## PNOA orthophoto

- WMTS `https://www.ign.es/wmts/pnoa-ma`: layer `OI.OrthoimageCoverage`; tile matrix sets
  `GoogleMapsCompatible`, `EPSG:3857`, `EPSG:4326`, `EPSG:4258`, `EPSG:25828`–`25831`,
  `InspireCRS84Quad`; JPEG and PNG. `(GetCapabilities, 2026-11-24)`
- A KVP GetTile (`tilematrixset=GoogleMapsCompatible&tilematrix=12&tilerow=1525&tilecol=2037`,
  over Zaragoza) returns a JPEG with `Access-Control-Allow-Origin: *` and
  `Cache-Control: max-age=31536000`. MapLibre can use it directly; no proxy needed.
  `(GetTile, 2026-11-24)`
- Over open sea off Lanzarote, some GoogleMapsCompatible tiles near zoom 13 drew as a dark
  block while the neighbouring ones showed water: PNOA has no imagery there.
  `(GetTile, browser, 2026-11-24)`
- Tile sizes for offline packs: 30 GoogleMapsCompatible JPEG tiles at zooms 12, 14, 16, 17
  and 18 over Daimiel, Zaragoza and Sevilla averaged 19.2 KB, the largest 24.3 KB
  (`config/defaults/packs.yaml` estimates 24,000 bytes a tile). A real pack over Santiago's
  Praza do Obradoiro stored 202 tiles (zooms 10-18) in 3.3 MB, 16.5 KB a tile; every tile
  carried CORS, so the browser stores and counts it. `(GetTile, browser, 2026-11-26)`
- WMS `https://www.ign.es/wms-inspire/pnoa-ma`: layers `OI.OrthoimageCoverage`,
  `OI.MosaicElement`, `fondo`; EPSG:3857 offered; CORS `*`. `(GetCapabilities, 2026-11-24)`

## IGN base maps

- WMTS `https://www.ign.es/wmts/ign-base`: layers `IGNBaseTodo`, `IGNBase-gris`,
  `IGNBaseOrto`, `IGNBaseTodo-nofondo`, `IGNBaseSimplificado`; GoogleMapsCompatible;
  PNG tiles with CORS `*` and a one-year cache header. `(GetCapabilities, GetTile, 2026-11-24)`
- WMTS `https://www.ign.es/wmts/mapa-raster`: layers `MTN`, `MTN_Fondo` (the scanned
  national topographic map); access constraint "CC BY 4.0 ign.es". Not catalogued: no
  session needs it yet. `(GetCapabilities, 2026-11-24)`

## Terrain models (MDT)

- WCS 2.0.1 `https://servicios.idee.es/wcs-inspire/mdt`: coverages `Elevacion25830_{1000,500,200,25,5}`,
  `Elevacion4083_{1000,500,200,25,5}` (Canaries), `Elevacion4258_{1000,500,200,25,5}` and
  `Elevacion4326_{1000,500}`. The number is the cell size in metres: **5 m and 25 m are
  served; 2 m is not** (MDT02 is a download only). `(GetCapabilities, 2026-11-24)`
- `Elevacion25830_5` covers x −19,452.5 … 1,140,352.5, y 3,901,197.5 … 4,865,682.5 (EPSG:25830)
  at 5 m: mainland Spain and the Balearics in one coverage. `(DescribeCoverage, 2026-11-24)`
- `Elevacion4083_5` (the Canaries at 5 m) covers x 188,197.5 … 662,002.5, y 3,060,497.5 …
  3,255,102.5 (EPSG:4083). `(DescribeCoverage, 2026-11-25)`
- The detailed map of an area (session 06) reads `Elevacion25830_5` / `Elevacion4083_5` by
  5 km windows: a point's 250 m disc plus a 2 km buffer took 9-19 s in all (every input,
  computed), its MDT05 windows a few MB; the same areas again come from the file cache.
  `(GetCoverage, 2026-11-25)`
- A GetCoverage of a 500 m square (`subset=x(676500,677000)&subset=y(4613000,4613500)`,
  near Zaragoza, `format=image/tiff`) returns a small GeoTIFF. The national grid (session 05) and the
  parcel grid (06) can read the terrain from this WCS by windows instead of downloading
  sheets. `(GetCoverage, 2026-11-24)`
- **Editions**: the IDEE catalogue holds two MDT25 records, "Modelo Digital del Terreno de
  1ª cobertura (2009-2015)" (`spaignMDT25`) and "de 2º cobertura (2015-2021)"
  (`spaignMDT25-2`). The WCS capabilities say only "procedentes de sensores LiDAR
  aerotransportados del proyecto PNOA-LiDAR", not which coverage `Elevacion25830_25` and
  `Elevacion4083_25` serve: `VERIFY-LIVE(national-editions)`. `(GetCapabilities, IDEE CSW
  GetRecords, 2026-11-25)`
- MDT means bare ground (the LiDAR points classified as ground); the IGN's surface model
  (MDS) keeps trees and roofs and would give false slopes and channels, so the model reads
  the MDT only.
- WMS `https://servicios.idee.es/wms-inspire/mdt`: layers `EL.ElevationGridCoverage`,
  `EL.ContourLine`, `EL.SpotElevation`; EPSG:3857 offered. `(GetCapabilities, 2026-11-24)`
- The download centre `https://centrodedescargas.cnig.es/CentroDescargas/` is a JavaScript
  application (the landing page is 5 KB of HTML); product lists and file sizes for MDT02,
  MDT05 and MDT25 were not readable without a browser. MDT02 (second LiDAR coverage) is
  downloaded by sheet; its coverage and the existence of a bulk route stay unverified:
  `VERIFY-LIVE(cnig-mdt02-coverage)`. Until then the detailed map reads MDT05 everywhere
  and says so. `(GET /CentroDescargas/, 2026-11-24)`

## CartoCiudad geocoder

- `https://www.cartociudad.es/geocoder/api/geocoder/candidates?q=Zaragoza&limit=1` returns
  JSON (`candidatesJsonp` the same as JSONP): `id`, `province`, `provinceCode`, `muni`,
  `muniCode` (50297), `type` (`poblacion`, `Municipio`, `callejero`…), `address`, `lat`,
  `lng`, `refCatastral`. For a place-name candidate `lat`/`lng` are 0.0: a second call
  (`find`) resolves it. CORS `*`. `(GET /candidates, 2026-11-24)`
- Candidate types observed: `Municipio`, `poblacion` (towns and industrial estates),
  `callejero` (streets, roads by name), `portal` (a doorway, with `portalNumber` and
  `refCatastral`), `Codpost` (a postal code). Nothing found: `[]`. A municipality's id may
  lose its leading zero (Badajoz: `"6015"`, its `muniCode` `"06015"`).
  `(GET /candidates, 2026-11-25)`
- `find?id=&type=` answers one object with a WKT `geom`: a municipality or town as
  `MULTIPOLYGON` (Daimiel 20 KB, Zaragoza 91 KB, Cáceres 103 KB, the town of Daimiel
  150 KB), a street as `MULTILINESTRING`, a doorway as `POINT`; `lat` and `lng` are its
  centre and `provinceCode` its INE province. The id must be the candidate's exactly:
  `id=06015&type=Municipio` answers HTTP 500; an unknown id answers HTTP 204 with no body;
  `type=provincia` answers HTTP 500. `(GET /find, 2026-11-25)`
- `reverseGeocode?lon=&lat=` finds only an address near the point: it answered HTTP 204 for
  a rural point in Granada (37.0 N, 3.0 W) as for Lisbon, so it cannot tell whether a
  point is in Spain. `(GET /reverseGeocode, 2026-11-25)`

## Licence and attribution

- Every IGN service above declares "CC BY 4.0 scne.es" (or "ign.es") in its capabilities.
  `(GetCapabilities, 2026-11-24)`
- The IGN licence conditions (`https://www.ign.es/resources/licencia/Condiciones_licenciaUso_IGN.pdf`)
  require the attribution "<product> <date> CC-BY 4.0 <producers>" visible at the foot of
  the map, e.g. "PNOA CC-BY 4.0 scne.es"; a derived work says "Obra derivada de MDT05
  CC-BY 4.0 scne.es". `(Condiciones_licenciaUso_IGN.pdf, 2026-11-24)`
- CC BY 4.0 allows copying and storing: **caching PNOA and the base maps for offline packs
  is allowed** with the attribution kept (session 11). The same licence covers CartoCiudad,
  so a pack keeps an area found by it. `sources.yaml` marks these `offline: allowed`.

Copyright (c) 2026 Almoon-D. All rights reserved.
