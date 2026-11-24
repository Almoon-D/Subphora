# Soil maps

Hosts `maps.isric.org` (SoilGrids), `www.juntadeandalucia.es` (REDIAM soil map),
`esdac.jrc.ec.europa.eu` (European Soil Database). Catalogue ids: `soilgrids-wcs`,
`rediam-soils`, `esdb`. Findings observed on 2026-11-24.

## Options

| Source | Coverage | Scale | Attributes for infiltration | Access | Licence |
|---|---|---|---|---|---|
| SoilGrids 2.0 (ISRIC) | world, all of Spain | 250 m grid | clay, sand, silt, bulk density, coarse fragments, organic carbon at 6 depths, each with 5 %, 50 %, 95 % quantiles and mean | WCS per property | CC BY 4.0 |
| Mapa de Suelos de Andalucía (REDIAM) | Andalusia | 1:400,000 | 64 soil associations (FAO 1974 classes), no texture values | WMS | free, citing the authors |
| European Soil Database v2.0 (JRC) | Europe | 1:1,000,000 | soil typological units with texture class, water regime, impermeable layer depth | download after a registration form | free after registration |

- SoilGrids WCS: `https://maps.isric.org/mapserv?map=/map/<property>.map` (e.g. `clay.map`),
  WCS 2.0.1, coverages `clay_0-5cm_mean`, `clay_0-5cm_Q0.05`, `clay_0-5cm_Q0.5`,
  `clay_0-5cm_Q0.95`, … (30 per property); CORS `*`. `(GetCapabilities, 2026-11-24)`
- The SoilGrids REST point API `https://rest.isric.org/soilgrids/v2.0/properties/query`
  answered **503** ("Service Temporarily Unavailable"). Do not depend on it; the WCS works.
  `(GET /properties/query, 2026-11-24)`
- SoilGrids licence: CC BY 4.0 (ISRIC data policy,
  `https://www.isric.org/about/data-policy`). Attribution: "SoilGrids 2.0, ISRIC World Soil
  Information, CC BY 4.0".
- REDIAM soil WMS `https://www.juntadeandalucia.es/medioambiente/mapwms/REDIAM_Suelos_Andalucia`:
  layer `unidades_edaficas`; the abstract says it was made in 2005 from the 1989 map of the
  Consejería de Agricultura and CSIC, units are second-order associations (FAO 1974 and the
  1985 EU soil map). EPSG:3857 offered; **no CORS** (proxy needed). `(GetCapabilities, GetMap, 2026-11-24)`
- ESDB: "freely available to the public after user registration" through an online form;
  the 1 km raster library likewise. `(GET the dataset page, 2026-11-24)`

## Regional detail

- Navarra publishes a **soil map at 1:25,000** in IDENA, WMS `https://idena.navarra.es/ogc/wms`:
  `EDAFOL_Pol_Suelos25m` (soil units), `EDAFOL_Pol_Suelos25m_` (phases),
  `EDAFOL_Sym_RedObSuelos` (observation network), `EDAFOL_Pol_Suelos25mMI` (index of the
  municipalities covered); EPSG:3857; CORS `*`; licence CC BY 4.0 (capabilities).
  Catalogue id `idena-wms`. `(GetCapabilities, 2026-11-24)`
- Other regions' soil maps were not surveyed. Where a region publishes one, it is a context
  layer for that region; SoilGrids stays the nationwide model input (decision 0013).

## Recommendation

**SoilGrids 2.0** as the model input and the soil layer for all of Spain: it is the only
option with numeric texture (clay and sand fractions drive infiltration), a quantified
uncertainty per cell (the 5–95 % quantiles feed the confidence layer, hard rule 1),
nationwide coverage, an open licence with no registration, and a working WCS. Its 250 m
cells are coarse at parcel scale, so the parcel view labels it as regional. In Andalusia the
REDIAM 1:400,000 map is shown as a second, qualitative layer for context. ESDB adds nothing
SoilGrids lacks and needs a registration: not used.

Copyright (c) 2026 Almoon-D. All rights reserved.
