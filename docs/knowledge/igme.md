# IGME (Instituto Geológico y Minero de España, CN IGME-CSIC)

Host `mapas.igme.es` (ArcGIS Server: `…/gis/services/<folder>/<service>/MapServer/WMSServer`
for WMS, `…/gis/rest/services/<folder>/<service>/MapServer/<layer>/query` for queries).
Catalogue ids: `igme-magna-wms`, `igme-geode-wms`, `igme-permeability-wms`,
`igme-lithostrat-wms`, `igme-hydrogeo-wms`, `igme-water-points-wms`, `igme-rest`. Findings observed on 2026-11-24.

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
- **GEODE's editions are per zone**: the service states none (version 3.5.0); each zone
  is a dataset in the IDEE INSPIRE catalogue (`https://www.idee.es/csw-inspire-idee`, ids
  `ESPIGMEGEODE50Z<zone>…`), with its own dates (publication, or the latest of
  publication, revision and edition): 1000 Cantábrica, 1100 Asturoccidental-Leonesa, 1300
  Ollo de Sapo and the seven Canary islands 2007 (the islands' edition date 2009); 1200
  Galicia occidental 2009; 1400 Esquisto-grauváquico 2013; 1500 Ossa-Morena 2009; 1600
  Vasco-Cantábrica y Pirineos 2008 (edition 2009); 1700 Cordillera Ibérica 2010 (revision);
  1800 Prebético 2011; 2100 Béticas internas 2010; 2210 Mallorca-Cabrera 2009; 2211
  Ibiza-Formentera 2010; 2300 Duero-Almazán 2010 (edition); 2400 Tajo-Mancha 2009; 2500
  Obejo-Valsequillo 2010; 2600 Guadalquivir 2014; 2700 Ebro 2010; 2800 Valenciana 2014;
  3100 Sudportuguesa 2009; 2212 Menorca not read (the catalogue answered empty twice). The
  zone at a point is the "Código zona GEODE" a tap returns; the zones layer cannot be
  queried by area (REST query refused), so the zones over a region are sampled by taps on
  a grid. `(IDEE CSW GetRecords, record XML, GetFeatureInfo, 2026-11-24)`
- The 1:200,000 lithostratigraphic and permeability maps: **second edition**, created
  2005-09-18, published 2007-09-30, revised 2009-08-05 (IDEE records
  `ESPIGMELITOESTRATIGRAFICO200…`, `ESPIGMEPERMEABILIDADES200…`). The water-point database
  (`ESPIGMEPUNTOSAGUA20190723`) states only a creation date, 1970: no edition.
  `(record XML, 2026-11-24)`
- Geological 1:200,000 (`IGME_Geologico_200`), 1:1,000,000 (`IGME_Geologico_1M`), regional
  maps (Murcia, Valencia, Alicante…) also exist. `(GET /Cartografia_Geologica?f=json, 2026-11-24)`

## Bedding dip and strike — digital

- MAGNA REST layer 5 "Medidas estructurales MAGNA50" (polylines) is **queryable**: fields
  `HOJA`, `ID`, `NOMBRE` (the measurement type: "Estratificación", "Estratificación
  invertida", "Esquistosidad…", "Diaclasado"…), `DIRECCION` (dip direction, degrees: the
  WMS feature info names it "Dirección de buzamiento", `tests/fixtures/layers/igme_magna_dip.json`),
  `BUZAMIENTO` (dip, degrees). 251,654 measurements; the distinct-sheet query stops at its
  1,000-row limit, so at least 1,000 of the 1,114 sheets carry them. Example, sheet 1023:
  "Estratificación", direction 49°, dip 30°.
  `(GET /IGME_MAGNA_50/MapServer/5/query, 2026-11-24)`
- MAGNA REST layers (2026-11-25): 0 sheets, 1 structural-measurement annotations, 5
  "Medidas estructurales" (polylines: each measurement is a short symbol line, e.g. two
  vertices 200 m apart, its middle at the measurement), 8 folds, **9 "Contactos y fallas"**
  (polylines, fields `HOJA`, `ID`, `TIPO`), 10 and 11 lithology (polygons, `DLO`: a
  free-text description per sheet, no permeability class). `(GET /MapServer?f=json,
  /9?f=json, /11?f=json, 2026-11-25)`
- Layer 9 `TIPO` counts over Spain (`outStatistics` grouped by `TIPO`): contacts dominate
  (discordant 851,880, concordant 301,132), then "Falla conocida" 477,521, "Borde de hoja"
  132,406, "Contacto mecánico" 86,242, "Masas de agua" 58,772, "Falla supuesta" 54,931,
  "Cabalgamiento conocido" 47,819, many fault, thrust and fracture variants, and
  "Contacto mecánico por solifluxión" / "…Bloques deslizados" (landslides). The detailed
  map counts as faults the types that start with Falla, Fractura, Cabalgamiento,
  Retrocabalgamiento, Contacto mecánico or "Diaclasas y fallas", less those two
  (`config/defaults/parcel.yaml`). `(query outStatistics, 2026-11-25)`
- Layer 5 `NOMBRE`: 349 measurement types; bedding is "Estratificación" 122,210,
  "…invertida" 6,887, "…subvertical" 5,974, "…subhorizontal" 3,453 and a few more; the
  rest are cleavages, foliations, lineations, joints, photogeology classes and
  palaeocurrents. Density is low: 55 measurements in a 20 km square of the Pre-Pyrenees
  (x 700-720 km, y 4,660-4,680 km, EPSG:25830), 48 of them bedding. Both layers answer
  `inSR`/`outSR` 25830 GeoJSON with x first, like the other IGME layers.
  `(query, 2026-11-25)`
- GEODE layer 3 "Buzamientos" (points) is drawn but its query is refused ("Requested
  operation is not supported by this service"). `(GET /IGME_Geode_50/MapServer/3/query, 2026-11-24)`
- The 1:200,000 geological and lithostratigraphic maps have "Medidas estructurales" and
  "Estructuras" layers too. `(GET /MapServer?f=json, 2026-11-24)`
- The cross-section (session 08) reads `DIRECCION` as the azimuth, clockwise from north,
  toward which the bed dips, and layer 11's `DLO` as each unit's label. Neither was checked
  against a live answer from the cloud (IGME answered 403): `VERIFY-LIVE(magna-section)`.
  `(feature info alias, 2026-11-24; read 2026-11-26)`
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

- No downloadable 3D geological model was found. IGME runs a 3D modelling programme and is
  harmonising its models (FAIR); none is served on `mapas.igme.es`.
- Some water authorities publish hydrogeological presentations per groundwater body with a
  3D model section (the Junta de Andalucía, 2024). They are documents, not data: session 08
  may cite one for an area, never use it as an input.

## Drawing, legends and feature info (WMS)

- Every ArcGIS layer has a scale range (`MaxScaleDenominator`), below which it draws
  nothing: MAGNA lithology, contacts and faults 1:283,482 (zoom 11 with 256-pixel tiles),
  structural measurements 1:94,494 (zoom 13), the 1:200,000 permeability, hydrogeological
  and lithostratigraphic maps 1:472,470 (zoom 11), the water points 1:23,624 (zoom 15).
  `(GetCapabilities, 2026-11-24)`
- Water points as a map: WMS `BasesDatos/IGME_PuntosAgua/MapServer/WMSServer`, layers `0`
  "Puntos Acuíferos II" (with `Procedencia`) and `1` "Puntos Acuíferos I", EPSG:3857, CORS.
  `(GetCapabilities, 2026-11-24)`
- GetFeatureInfo formats: MAGNA and the water points offer `application/geo+json` (fields
  under their aliases: "descripción litológica", "Dirección de buzamiento", "Ángulo de
  buzamiento", "Profundidad m"…); the 1:200,000 maps offer `text/xml` (ArcGIS
  `FeatureInfoResponse`, one `FIELDS` element per feature, the fields as attributes:
  `Permeabilidad`, `Código`, `Descripción`, `Descripciónlitológica`, `Era`…). Asked for
  `text/xml`, MAGNA answers HTTP 200 with a `ServiceExceptionReport` "InvalidXslTemplate".
  `(GetFeatureInfo, 2026-11-24)`
- A MAGNA bedding measurement read by tap: sheet 610, "Estratificación", dip direction
  178°, dip 10° (the same values as the REST query). `(GetFeatureInfo, 2026-11-24)`
- Legends: MAGNA's are lists of symbol codes without words (REST `legend`: 254 lithology
  colours labelled "1", "2"…; GetLegendGraphic a strip cut at 4,096 pixels): unusable as a
  legend; a tap reads the unit instead. The 1:200,000 maps name static legend images in
  their capabilities (`https://mapas.igme.es/servicios/WMS/Legends/…png`): permeability
  760×530, hydrogeology 893×166, lithostratigraphy 3,648×4,423 (800 KB).
  `(GetLegendGraphic, GET /MapServer/legend?f=json, 2026-11-24)`
- The lithostratigraphic map (no EPSG:3857 in its WMS) is drawn in Web Mercator by its
  ArcGIS REST export (`…/IGME_Litoestratigrafico_200/MapServer/export?bbox=…&bboxSR=3857&imageSR=3857&format=png32&transparent=true&layers=show:0&f=image`),
  which answers with CORS. Its WMS also answered a GetMap in EPSG:3857 with the same
  image, although its capabilities omit it: not relied upon. Its GetFeatureInfo works in
  EPSG:4258 (latitude, longitude order). `(export, GetMap, GetFeatureInfo, 2026-11-24)`
- **Coverage across Spain** (a tap at one point per region, zoom 13: Lugo, Oviedo, Vitoria,
  Tafalla, Lleida, Zaragoza, Valladolid, Alcalá, Daimiel, Mérida, Requena, Lorca, Granada,
  Mallorca, Gran Canaria, Tenerife, Melilla): the 1:200,000 lithostratigraphic, permeability
  and hydrogeological maps and GEODE answer everywhere; **MAGNA has no lithology polygon in
  parts of the Canaries** (La Orotava, La Laguna and Los Cristianos on Tenerife, a point on
  Fuerteventura; its sheet index covers them). GEODE (`IGME_Geode_50`, WMS layer `1`
  "Recintos geología", scale range 1:283,482, `application/geo+json` with "Descripción Unidad
  Geológica", "Edad Inferior", "Edad Superior", "Código zona GEODE") covers every point
  probed, Tenerife included; its legend is a strip of symbol codes, like MAGNA's.
  `(GetFeatureInfo, REST identify, 2026-11-24)`
- `BasesDatos/IGME_QAFI_v4/MapServer/WMSServer` answers "ArcGIS Server Error": the faults
  database has no WMS; MAGNA's "Contactos y fallas" layer draws the mapped faults.
  `(GetCapabilities, 2026-11-24)`

## Licence

- IGME generic licence 2022 (`https://info.igme.es/media/Pdfs/LicUsoIGME_GENERICA_2022.pdf`,
  English `…_EN_2022.pdf`), linked from `https://www.igme.es/condiciones-de-uso/`: free
  reuse for commercial and non-commercial purposes; the meaning must not be altered; the
  credit is **"Origen de los datos: © CN Instituto Geológico y Minero de España (IGME)"**
  (English: "Source: © NC Geological Survey of Spain (IGME)"); no suggestion that IGME
  endorses the product. Caching for offline use is reuse and is allowed with the credit.
  `(LicUsoIGME_GENERICA_2022.pdf, 2026-11-24)`

Copyright (c) 2026 Almoon-D. All rights reserved.
