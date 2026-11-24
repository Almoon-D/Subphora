# Catastro (Dirección General del Catastro)

Host `ovc.catastro.meh.es` for every service below. Catalogue ids: `catastro-wms`,
`catastro-wfs-parcels`, `catastro-ovc`. All findings observed on 2026-11-24 from the cloud
session with the `subphora/0.1.0` User-Agent.

## Behaviour of the host

- The host rejects curl's default User-Agent: `curl/8.x` gets HTTP 400 with an HTML page
  "No se puede procesar su petición"; the same request with `subphora/0.1.0` gets 200, three
  times out of three. A `Mozilla/5.0` User-Agent got a connection reset once.
  `(GET /cartografia/INSPIRE/spadgcwms.aspx?SERVICE=WMS&REQUEST=GetCapabilities, 2026-11-24)`
- About one request in three ends in a connection reset or an empty reply on every path of
  the host, then succeeds when retried a few seconds later. The client retries transport
  errors (`config/defaults/sources.yaml` → `client.retries`). `(all routes, 2026-11-24)`
- Every response tested carries `Access-Control-Allow-Origin: *`: a browser can call the
  WMS, the WFS and the JSON services directly. WMS images carry `Cache-Control: private`.
  `(GetMap, GetFeature, Consulta_DNPRC, 2026-11-24)`

## INSPIRE WMS — `https://ovc.catastro.meh.es/cartografia/INSPIRE/spadgcwms.aspx`

- WMS 1.3.0. Layers: `CP.CadastralParcel` (styles Default, LabelOnReferencePoint,
  BoundariesOnly, ReferencePointOnly, ElfCadastre), `CP.CadastralZoning`, `AD.Address`,
  `BU.Building`, `BU.BuildingPart`, `AU.AdministrativeUnit`, `AU.AdministrativeBoundary`.
  `(GetCapabilities, 2026-11-24)`
- CRS offered: EPSG:3857, 4326, 4258, 25829, 25830, 25831, 3035, 23029–23031, 32627–32631,
  3785, CRS:84. A 256-pixel GetMap in EPSG:3857 returns a PNG. `(GetMap, 2026-11-24)`
- `AccessConstraints`: "Free access, but it is not allowed massive downloads of cartography
  portions and tiled petitions". **Tiled requests are not allowed**: MapLibre's raster
  tiles over this WMS would break that condition. Session 02 must request one untiled image
  per view (a MapLibre `image` source refreshed on move) or ask Catastro. `(GetCapabilities, 2026-11-24)`
- The older non-INSPIRE WMS `https://ovc.catastro.meh.es/Cartografia/WMS/ServidorWMS.aspx`
  (layers `Catastro`, `PARCELA`, `TXTPARCELA`, `CONSTRU`, `MASA`, `EJES`, `LIMITES`…) also
  answers, with EPSG:3857. Not catalogued: the INSPIRE one is the documented service.
  `(GetCapabilities, 2026-11-24)`

## INSPIRE WFS for cadastral parcels — `https://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx`

- WFS 2.0.0. Feature types `cp:CadastralParcel`, `cp:CadastralZoning`. Stored queries:
  `GetParcel`, `GetNeighbourParcel`, `GetZoning`, `GetParcelsByZoning`, `GetFeatureById`.
  `(ListStoredQueries, 2026-11-24)`
- Query by reference: `request=GetFeature&STOREDQUERY_ID=GetParcel&refcat=<ref>&srsname=EPSG::25830`.
  The misspelt `STOREDQUERIE_ID` found in older examples also works. `refcat` takes the
  14-character parcel reference or the full 20-character reference; both return the parcel.
  `(GetFeature GetParcel, 2026-11-24)`
- Output CRS: any of EPSG 4326, 4258, 25829, 25830, 25831, 3857, 3035 and others; the
  service reprojects across UTM zones (a parcel in Santiago de Compostela, zone 29, came back
  in 25830 and 25829). With `EPSG::4326` and `EPSG::4258` the coordinates are in
  **latitude, longitude** order. `(GetFeature GetParcel, 2026-11-24)`
- **Canaries:** `srsname=EPSG::4083` (REGCAN95 / UTM 28N) is not honoured: a parcel in
  Tinajo (Lanzarote) came back in EPSG:4326 with `srsName` saying so. The client must read
  the `srsName` of the response and reproject with `pyproj`, never assume the requested CRS.
  `(GetFeature GetParcel refcat=35029A03200314, 2026-11-24)`
- **Foral territories:** `Consulta_RCCOOR` at points in Pamplona and Bilbao answers error 16
  "PARA ESAS COORDENADAS NO HAY REFERENCIA DISPONIBLE": Navarra and the Basque Country are
  outside the national cadastre (decision 0010; `coverage_excludes` in the catalogue).
  `(Consulta_RCCOOR, 2026-11-24)`
- Response: GML 3.2, `cp:CadastralParcel` with `areaValue` (m²), `beginLifespanVersion`,
  `label`, `nationalCadastralReference`, `referencePoint` and a `MultiSurface` geometry. A
  comment states the geometry's precision is nominally that of the capture scale
  ("La precisión es la que corresponde nominalmente a la escala de captura de la
  cartografía"): it is a cadastral map outline, not a survey. `(GetFeature, 2026-11-24)`
- Not found: HTTP **200** with an OWS `ExceptionReport`, code `OperationProcessingFailed`,
  text "No se ha encontrado la parcela 29015A16799999 para el huso 25830". A malformed
  reference: the same, text "Invalid length of REFCAT parameter". The client must read the
  body, not the status. `(GetFeature GetParcel, 2026-11-24)`
- With `srsname=EPSG::4326` positions come with 6 decimals (about 10 cm), latitude first;
  Tinajo's parcel is one `PolygonPatch` with 16 `interior` rings. `(GetFeature GetParcel,
  2026-11-24)`
- A bounding-box GetFeature works (`typenames=cp:CadastralParcel&srsname=EPSG::25830&bbox=…`).
  `(GetFeature bbox, 2026-11-24)`

## Non-protected data — `https://ovc.catastro.meh.es/OVCServWeb/OVCWcfCallejero/…`

- The free web services (document `https://www.catastro.hacienda.gob.es/ws/Webservices_Libres.pdf`)
  return "datos catastrales no protegidos": everything except **owner (titularidad) and
  value**. JSON variants: `COVCCallejero.svc/json/Consulta_DNPRC?RefCat=` (data of a property
  by reference: use, built area, year, locality), `COVCCoordenadas.svc/json/Consulta_RCCOOR?CoorX=&CoorY=&SRS=EPSG:4326`
  (reference at a point). SOAP and WSDL also exist. `(Consulta_DNPRC, Consulta_RCCOOR, 2026-11-24)`
- `Consulta_DNPRC` with a 14-character reference: one property comes back as
  `consulta_dnprcResult.bico.bi`, several (Estación Puerta de Atocha, 1532704VK4713C) as
  `lrcdnp.rcdnp[]`; each carries `dt.nm` (municipality), `dt.np` (province) and
  `dt.loine.cp` (INE province code: 15, 06, 35, 28…). A missing reference answers HTTP 200
  with `lerr[].cod` "5" ("NO EXISTE NINGÚN INMUEBLE…"). `(Consulta_DNPRC, 2026-11-24)`
- Owner and value data are only in the authenticated services of the Sede Electrónica
  (electronic certificate, "datos protegidos"). Subphora never calls them (hard rule 6); no
  catalogued route returns them.

## Public references used in fixtures

| Reference | Place | Use | Area of the parcel |
|---|---|---|---|
| 7279701NH3477G0001SJ | Praza do Obradoiro 3, Santiago de Compostela (UTM zone 29) | Religioso | 13,352 m² |
| 0910001QD3101S0001LR | the Roman theatre, Mérida | Espectáculos | 43,337 m² |
| 35029A03200314 (0000HL) | Polígono 32, parcela 314, Volcán Montaña Tinga, Tinajo, Lanzarote (rustic) | Agrario | 23,614,448 m² |

`(Consulta_DNPRC, Consulta_RCCOOR, 2026-11-24)`

## Reference format and control characters

- A rustic reference: province (2) + municipality (3) + sector (1 letter) + polygon (3) +
  parcel (5) = 14; an urban one: 7 digits + 7 alphanumerics (sheet) = 14. The full reference
  adds 4 digits for the property (cargo) and 2 control letters = 20.
- Control letters, verified against the service on seven references (the three above,
  Torre Picasso, the Basílica del Pilar and two properties of Atocha station):
  weights `[13, 15, 12, 5, 4, 17, 9, 21, 3, 7, 1]` over 11 characters; the first letter
  from characters 1–7 plus the cargo, the second from characters 8–14 plus the cargo.
  Digits count their value; letters A–N count 1–14, Ñ 15, O–Z 16–27 (the full value,
  not modulo 10). The sum modulo 23 indexes `MQWERTYUIOPASDFGHJKLBZX`.
  `(Consulta_DNPRC, 2026-11-24)`

## Terms

- Licence: `https://www.catastro.hacienda.gob.es/webinspire/documentos/Licencia.pdf`
  (English: `…/Licencia_en.pdf`), linked from the WFS capabilities. Access by automatic
  licence; use for one's own purposes or for value-added products **after transformation**;
  the original information may not be redistributed untransformed; products must not be
  called "cartografía catastral" or anything that could be confused with Catastro's;
  Catastro may suspend a user whose intensity or frequency harms others. No fixed
  attribution text is given: cite "Dirección General del Catastro". `(Licencia.pdf, 2026-11-24)`
- No published rate limit. The catalogue sets one request at a time, one second apart.

Copyright (c) 2026 Almoon-D. All rights reserved.
