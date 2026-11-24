# IGME (Instituto Geológico y Minero de España, CN IGME-CSIC)

Host `mapas.igme.es` (ArcGIS Server: `…/gis/services/<folder>/<service>/MapServer/WMSServer`
for WMS, `…/gis/rest/services/<folder>/<service>/MapServer/<layer>/query` for queries).
Catalogue ids: `igme-magna-wms`, `igme-geode-wms`, `igme-permeability-wms`,
`igme-lithostrat-wms`, `igme-hydrogeo-wms`, `igme-rest`. Findings observed on 2026-11-24.

## The host

- REST folders: `Cartografia_Geologica`, `Cartografia_Tematica`, `BasesDatos`,
  `oneGeology`, `Referencias`, `Copernicus`, `UGeoHaz` and others. `(GET /gis/rest/services?f=json, 2026-11-24)`
- CORS: the server echoes the request's `Origin` in `Access-Control-Allow-Origin` (WMS and
  REST). `(GetCapabilities, query, 2026-11-24)`
- **WMS layer names are not the REST layer ids**: the WMS numbers layers in reverse drawing
  order. In MAGNA, WMS `0` is "Litologías color" while REST layer 0 is "Hojas 1:50.000";
  WMS `6` and REST layer 5 are both "Medidas estructurales". Read titles, never assume.
  `(GetCapabilities, GET /MapServer?f=json, 2026-11-24)`
- REST queries return at most `maxRecordCount` features (1,000 or 2,000) and support
  pagination (`resultOffset`), JSON, GeoJSON and PBF. `(GET /MapServer/0?f=json, 2026-11-24)`

## Geological maps

- MAGNA 1:50,000 (`Cartografia_Geologica/IGME_MAGNA_50`): WMS layers `0` lithology colour,
  `1` lithology patterns, `2` contacts and faults, `3` folds, `6` structural measurements,
  `11` sheets; EPSG:3857 offered. 1,114 sheets. `(GetCapabilities, query count, 2026-11-24)`
- The MAGNA WMS `AccessConstraints`: "No está permitido implementar un servicio de valor
  añadido no gratuito sin establecer contacto con el IGME" (a paid value-added service needs
  IGME's consent). Subphora is free and private: no conflict. `(GetCapabilities, 2026-11-24)`
- GEODE continuous 1:50,000 (`Cartografia_Geologica/IGME_Geode_50`): WMS layers `0` zones,
  `1` geology polygons, `2` contacts, `3`/`4` Quaternary, `5` axes…; EPSG:3857 offered.
  `(GetCapabilities, 2026-11-24)` Vector downloads: the page
  `https://info.igme.es/cartografiadigital/geologica/Geode.aspx` answers; the download
  route behind it was not traced: `VERIFY-LIVE(igme-geode-download)`.
- Geological 1:200,000 (`IGME_Geologico_200`), 1:1,000,000 (`IGME_Geologico_1M`), regional
  maps (Murcia, Valencia, Alicante…) also exist. `(GET /Cartografia_Geologica?f=json, 2026-11-24)`

## Bedding dip and strike — digital

- MAGNA REST layer 5 "Medidas estructurales MAGNA50" (polylines) is **queryable**: fields
  `HOJA`, `ID`, `NOMBRE` (the measurement type: "Estratificación", "Estratificación
  invertida", "Esquistosidad…", "Diaclasado"…), `DIRECCION` (strike direction, degrees),
  `BUZAMIENTO` (dip, degrees). 251,654 measurements; the distinct-sheet query stops at its
  1,000-row limit, so at least 1,000 of the 1,114 sheets carry them. Near Antequera,
  sheet 1023: "Estratificación", direction 49°, dip 30°.
  `(GET /IGME_MAGNA_50/MapServer/5/query, 2026-11-24)`
- GEODE layer 3 "Buzamientos" (points) is drawn but its query is refused ("Requested
  operation is not supported by this service"). `(GET /IGME_Geode_50/MapServer/3/query, 2026-11-24)`
- The 1:200,000 geological and lithostratigraphic maps have "Medidas estructurales" and
  "Estructuras" layers too. `(GET /MapServer?f=json, 2026-11-24)`
- Conclusion for sessions 03, 05, 08: dip is digital for (almost) all MAGNA sheets through
  the REST query; it is a measurement at a point, so a dip layer is an interpolation and
  must carry its own confidence.

## Hydrogeology and permeability

- Permeability of Spain 1:200,000 (`Cartografia_Tematica/IGME_Permeabilidad_200`): one
  WMS layer `0`; REST fields `PERME`, `CODIGO`, `DCO`, `CLPERM`; classes MUY ALTA, ALTA,
  MEDIA, BAJA, MUY BAJA; 122,260 polygons; the extent covers the mainland, the Balearics
  and the Canaries. `(GET /MapServer/0/query, 2026-11-24)`
- Lithostratigraphic map 1:200,000 (`IGME_Litoestratigrafico_200`): WMS layers `0`
  lithostratigraphy, `1` contacts and fractures, `2` structures. **No EPSG:3857 in its WMS**
  (CRS 4258, 4326, 25828–25831, 23028–23031, CRS:84): MapLibre needs the server's proxy or
  the REST export (the REST service itself is in Web Mercator, wkid 102100).
  `(GetCapabilities, GET /MapServer?f=json, 2026-11-24)`
- Hydrogeological map 1:200,000 (`IGME_Hidrogeologico_200`, WMS layer `0`) and 1:1,000,000
  (`IGME_Hidrogeologico_1M`); permeability 1:1,000,000 (`IGME_Permeabilidad_1M`); karst
  (`IGME_Karst_1M`); tectonic and neotectonic 1:1,000,000; faults database `QAFI`
  (`BasesDatos/IGME_QAFI_v4`). `(GET /Cartografia_Tematica?f=json, 2026-11-24)`

## Water points and boreholes

- Water-point inventory (`BasesDatos/IGME_PuntosAgua`, REST layers 0 and 1, 139,699 points
  each): `Id`, `HOJA`, `Octante`, `PUNTO`, `Cuenca_Hidrografica`, `Unidad_Hidrogeologica`,
  `Sistema_Acuifero`, `Provincia`, `Municipio`, `Caudal_Referencia_L_s`, `TOPONIMIA`,
  `COTA_msnm`, `Naturaleza` (pozo, sondeo, manantial…), `PROF_m` (depth), `Metodo_Perforacion`,
  `FECHA_OBRA`, `Motobomba`, `Usos_Agua`, `Organismo`, `URLDetalle`. **No water level, no
  dry/productive flag and no lithology log** in the map service; many `Caudal_Referencia_L_s`
  are 0.0 (unknown, not dry). `(GET /IGME_PuntosAgua/MapServer/0/query, 2026-11-24)`
- `URLDetalle` points to `http://info.igme.es/bdaguas/PointInfo.aspx?id=…`, which answers
  404. The current "BD Puntos Agua v2.0" web application (`https://info.igme.es/BDAguas/`)
  shows levels, analyses and charts, but has no documented API; calling its internal
  endpoints would be scraping (hard rule 4). Levels per point need IGME's permission or a
  documented download: `VERIFY-LIVE(igme-water-levels)`. `(GET /BDAguas/, 2026-11-24)`
- IRYDA boreholes (`BasesDatos/IGME_SondeosIRYDA`): `NIVEL_AGUA`, `F_NIVEL`, `TRANSMISIV`,
  `PROFUNDIDA`, `Z`, `NATUR_SOND`, `MET_PERFOR`, `url_inform` (scanned report): historical
  boreholes with a water level and transmissivity — useful labels for session 07.
  `(GET /IGME_SondeosIRYDA/MapServer/0?f=json, 2026-11-24)`
- MITECO's "Catálogo de sondeos" is in `miteco-basins.md`.

## 3D geological models

- No downloadable IGME 3D model was found for Antequera or the Guadalquivir. IGME runs a 3D
  modelling programme and is harmonising its models (FAIR); none is served on `mapas.igme.es`.
- The Junta de Andalucía published (September 2024) a presentation on the groundwater body
  ES060MSBT060.033 Llanos de Antequera-Vega de Archidona with a 3D geological model
  section: `https://juntadeandalucia.es/sites/default/files/inline-files/2024/09/Presentacion_hidrogeo_ES060MSBT060_033_Llanos.pdf`.
  It is a document, not data; session 08 can cite it.

## Licence

- IGME generic licence 2022 (`https://info.igme.es/media/Pdfs/LicUsoIGME_GENERICA_2022.pdf`,
  English `…_EN_2022.pdf`), linked from `https://www.igme.es/condiciones-de-uso/`: free
  reuse for commercial and non-commercial purposes; the meaning must not be altered; the
  credit is **"Origen de los datos: © CN Instituto Geológico y Minero de España (IGME)"**
  (English: "Source: © NC Geological Survey of Spain (IGME)"); no suggestion that IGME
  endorses the product. Caching for offline use is reuse and is allowed with the credit.
  `(LicUsoIGME_GENERICA_2022.pdf, 2026-11-24)`

Copyright (c) 2026 Almoon-D. All rights reserved.
