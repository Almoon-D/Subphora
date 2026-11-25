# Nationwide inputs for the national map (session 05)

Which inputs cover all of Spain, at what scale, how they are reached, and what is still
unknown. Details and evidence in each service's knowledge file. Observed on 2026-11-24.

| Input | Source and route | Coverage | Scale or cell | Format and size | Date of the data |
|---|---|---|---|---|---|
| Permeability | IGME `IGME_Permeabilidad_200`, REST query on `mapas.igme.es` (paged, 1,000 per page) | mainland, Balearics, Canaries | 1:200,000 | 122,260 polygons as GeoJSON or PBF pages: about 123 requests | not stated in the service |
| Lithology | IGME `IGME_Litoestratigrafico_200`, REST query | the same extent | 1:200,000 | polygons, paged likewise | not stated |
| Geology (detail) | IGME MAGNA 1:50,000 / GEODE | 1,114 MAGNA sheets; GEODE continuous | 1:50,000 | REST query per area; GEODE vector download route unverified | per sheet |
| Bedding dip | IGME MAGNA REST layer 5 | ≥ 1,000 of 1,114 sheets | points per sheet | 251,654 measurements, paged | per sheet |
| Terrain | IGN WCS `servicios.idee.es/wcs-inspire/mdt` | mainland + Balearics (`Elevacion25830_*`), Canaries (`Elevacion4083_*`) | 5 m, 25 m, 200 m, 500 m, 1,000 m | GeoTIFF windows on request; no bulk download needed for a 100 m grid | PNOA-LiDAR, first (2009-2015) or second (2015-2021) coverage: the WCS does not say which |
| Groundwater bodies, status, risk | MITECO WFS `estado_masas_aguasub_2027`, `masas_aguasub_riesgo_2027` | all districts | body polygons | GeoJSON by bbox | plan cycle 2022-2027, status assessed 2016-2019 |
| Water points | IGME `IGME_PuntosAgua` REST layers 0 and 1 | all of Spain | points | 139,699 points per layer, paged | 1966 to now; no levels or dry flag |
| Historical boreholes with level | IGME `IGME_SondeosIRYDA` | areas studied by IRYDA | points | REST query | historical |
| Piezometric network | MITECO `RedPiezometrica` | all districts | points | WFS, network only | current |
| Piezometric levels | MITECO national piezometry database (hand download, 18.5 MB); basin spreadsheets (Guadiana, Ebro, Júcar) | inter-community districts, about 2,500 piezometers; regional agencies partly | point series, mostly monthly | ZIP / XLS / XLSX | contents unverified |
| Recharge | MITECO `rechid_recarga` (WMS raster) | all of Spain | not stated | WMS image only; numeric download unverified | 1980-2005 series and a later one |
| Soil | SoilGrids 2.0 WCS (decision 0013) | world | 250 m | GeoTIFF windows per property and depth | SoilGrids 2.0 (2020) |
| River-basin districts | MITECO `demarhidro_2027` | all of Spain | polygons | WFS | 2022-2027 |

## Observed by the national build (session 05)

What `subphora national build` met, building Zaragoza (ES-Z) and Las Palmas (ES-GC) on
2026-11-25 (decisions 0027, 0028). Behaviour the code relies on is also in
`src/subphora/sources/national.py`.

- IGME REST `query` takes `inSR` and `outSR` 3035 and **5635** (REGCAN95-LAEA) and answers
  GeoJSON in them, easting first; `maxAllowableOffset=25` (metres) cuts a 1,000-polygon
  permeability page from 5.1 MB to 1.1 MB. ES-Z plus 10 km: 7,474 permeability polygons (8
  pages), 9,112 water points (10 pages). `(query, 2026-11-25)`
- Permeability `CODIGO` is lithology and class (`C-A`: carbonatadas, alta); lithologies C,
  D, Q (Quaternary detrital), V, M, I, E; `DCO` names both ("CARBONATADAS-ALTA"); one class
  is blank: "Masa de agua superficial". `(query returnDistinctValues, 2026-11-25)`
- Under two concurrent queries IGME answered HTTP 200 `{"error": "Failed to execute
  query."}` for a page that answered on its own a minute later: the build asks such a page
  again (client retries and backoff). `(build, query, 2026-11-25)`
- Water points: `Caudal_Referencia_L_s` is 0 on every one of the first 1,000 points around
  Zaragoza; `Naturaleza` includes "Cauce superficial" (a stream), left out as not groundwater.
  `(query, 2026-11-25)`
- IGN MDT WCS: `Elevacion25830_25` spans x −19,487.5…1,140,387.5, y 3,901,187.5…4,865,712.5;
  `Elevacion4083_25` x 188,162.5…662,037.5, y 3,060,462.5…3,255,112.5. A 20 km window is a
  1.3 MB int16 GeoTIFF (2.6 s); the sea is 0 with no nodata declared; a window outside the
  extent answers HTTP 400 `ExtentError`. `scalefactor=0.25` answers a 100 m GeoTIFF, but its
  resampling is not stated, so the build averages 25 m cells itself. `(GetCoverage,
  DescribeCoverage, 2026-11-25)`
- SoilGrids WCS answers `long`/`lat` subsets in EPSG:4326 (int16 g/kg, about 0.0023° cells,
  no nodata declared); 0 where it masks water and built-up land (the Ebro in Zaragoza).
  `(GetCoverage, 2026-11-25)`
- MITECO WFS refuses an `srsName` it does not list (EPSG:3035: HTTP 400); EPSG:3857 is
  unambiguous (x first). 79 bodies around Zaragoza at full detail: 6.9 MB, so the service's
  cap is 40 MB. Overlapping horizons exist (Duero). `(GetFeature, 2026-11-25)`
- IGN administrative units: a province is `au:nationalCode` 34, the INE community code, the
  province code and five zeros (Zaragoza `34025000000`). `(GetFeature, 2026-11-25)`
- Sizes: ES-Z is 1,727,469 cells (a 60 MB grid stack); ES-GC 406,957 (13 MB). The file
  cache held 476 MB of MDT windows for both (ES-GC's box is mostly sea). The tiles: 74 per
  layer for ES-GC alone, 255 for both; ES-Z rebuilt in 1 minute, its inputs mostly cached.
- Still open: `VERIFY-LIVE(igme-geode-download)` (the national model uses the 1:200,000
  permeability map and needs no GEODE download; session 08 may), the MDT25's edition and the
  groundwater bodies' scale (neither stated: their confidence components use the
  "unknown" value).

Copyright (c) 2026 Almoon-D. All rights reserved.
