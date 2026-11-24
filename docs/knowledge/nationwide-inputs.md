# Nationwide inputs for the national map (session 05)

Which inputs cover all of Spain, at what scale, how they are reached, and what is still
unknown. Details and evidence in each service's knowledge file. Observed on 2026-11-24.

| Input | Source and route | Coverage | Scale or cell | Format and size | Date of the data |
|---|---|---|---|---|---|
| Permeability | IGME `IGME_Permeabilidad_200`, REST query on `mapas.igme.es` (paged, 1,000 per page) | mainland, Balearics, Canaries | 1:200,000 | 122,260 polygons as GeoJSON or PBF pages: about 123 requests | not stated in the service |
| Lithology | IGME `IGME_Litoestratigrafico_200`, REST query | the same extent | 1:200,000 | polygons, paged likewise | not stated |
| Geology (detail) | IGME MAGNA 1:50,000 / GEODE | 1,114 MAGNA sheets; GEODE continuous | 1:50,000 | REST query per area; GEODE vector download route unverified | per sheet |
| Bedding dip | IGME MAGNA REST layer 5 | ≥ 1,000 of 1,114 sheets | points per sheet | 251,654 measurements, paged | per sheet |
| Terrain | IGN WCS `servicios.idee.es/wcs-inspire/mdt` | mainland + Balearics (`Elevacion25830_*`), Canaries (`Elevacion4083_*`) | 5 m, 25 m, 200 m, 500 m, 1,000 m | GeoTIFF windows on request; no bulk download needed for a 100 m grid | MDT05 from the first LiDAR coverage |
| Groundwater bodies, status, risk | MITECO WFS `estado_masas_aguasub_2027`, `masas_aguasub_riesgo_2027` | all districts | body polygons | GeoJSON by bbox | plan cycle 2022-2027, status assessed 2016-2019 |
| Water points | IGME `IGME_PuntosAgua` REST layers 0 and 1 | all of Spain | points | 139,699 points per layer, paged | 1966 to now; no levels or dry flag |
| Historical boreholes with level | IGME `IGME_SondeosIRYDA` | areas studied by IRYDA | points | REST query | historical |
| Piezometric network | MITECO `RedPiezometrica` | all districts | points | WFS, network only | current |
| Piezometric levels | MITECO national piezometry database (hand download, 18.5 MB); basin spreadsheets (Guadiana, Ebro, Júcar) | inter-community districts, about 2,500 piezometers; regional agencies partly | point series, mostly monthly | ZIP / XLS / XLSX | contents unverified |
| Recharge | MITECO `rechid_recarga` (WMS raster) | all of Spain | not stated | WMS image only; numeric download unverified | 1980-2005 series and a later one |
| Soil | SoilGrids 2.0 WCS (decision 0013) | world | 250 m | GeoTIFF windows per property and depth | SoilGrids 2.0 (2020) |
| River-basin districts | MITECO `demarhidro_2027` | all of Spain | polygons | WFS | 2022-2027 |

## Open questions for session 05

- `VERIFY-LIVE(piezometric-levels)`: the columns and dates of the national piezometry
  database and the basin spreadsheets (`water-authorities.md`).
- `VERIFY-LIVE(igme-geode-download)`: the GEODE vector download route and size.
- `VERIFY-LIVE(cnig-mdt02-coverage)`: MDT02 coverage and download (only the parcel grid of
  session 06 needs 2 m).
- Paging the IGME REST services for all of Spain is a polite batch (one request every
  half second, a few hundred requests for permeability and lithology together); session 05
  stores the result in `data/` and refreshes it rarely (cache lifetime 30 days).

Copyright (c) 2026 Almoon-D. All rights reserved.
