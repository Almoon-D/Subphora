# MITECO and the basin authorities

Host `gis.miteco.gob.es` (GeoServer: `https://gis.miteco.gob.es/geoserver/agua/<service>/wms`,
WFS at `…/<service>/ows`). Catalogue ids: `miteco-gw-bodies`, `miteco-gw-status`,
`miteco-gw-at-risk`, `miteco-piezometers`, `miteco-public-water-domain`,
`miteco-river-basin-districts`. Findings observed on 2026-11-24.

## The service directory

- The list of water services is the page
  `https://www.miteco.gob.es/es/cartografia-y-sig/ide/directorio_datos_servicios/agua.html`;
  every service is its own GeoServer path under `/geoserver/agua/`. Every one probed
  offers EPSG:3857, answers with `Access-Control-Allow-Origin: *`, and declares
  `AccessConstraints` "Sin limitaciones al acceso público". `(GET agua.html, GetCapabilities, 2026-11-24)`
- The older `https://wms.mapama.gob.es/sig/Agua/MasaAguaSubterranea/wms.aspx` answers with a
  .NET `NullReferenceException`: dead. `(GetCapabilities, 2026-11-24)`

## Groundwater bodies, status and risk (current cycle 2022-2027)

| Service | Content |
|---|---|
| `masas_aguasub_2027` | Groundwater bodies PHC 2022-2027 |
| `horizontes_masas_aguasub_2027` | Their horizons |
| `estado_masas_aguasub_2027` | Quantitative status (with chemical and global fields) |
| `estado_masas_aguasub_2027_qui` | Chemical status |
| `estado_masas_aguasub_2027_global` | Global status |
| `masas_aguasub_riesgo_2027` | Bodies **declared** at risk or overexploited |
| `masas_aguasub_nbec_2027` | Bodies not reaching good status for quantitative reasons |
| `redseg_masas_agua_2027_sub` | Groundwater monitoring networks |

`(GET agua.html, 2026-11-24)`

- WFS `estado_masas_aguasub_2027` (feature type `agua:estado_masas_aguasub_2027`, GeoJSON
  with `outputFormat=application/json`): `cod_masa`, `nom_masa`, `cod_demarc`, `riesgo_cu`,
  `est_cu_desc` (quantitative: Bueno/Malo), `est_qu_desc` (chemical), `est_global`,
  `niv_conf_cu`, `an_val_cu` (assessment period), `f_bue_est_cu` (target date), pressure
  and impact flags. Default CRS EPSG:4258; EPSG:3857 among the others. With a 4326 bbox the
  axis order is latitude, longitude. `(GetFeature, 2026-11-24)`
- Around Antequera: **ES060MSBT060-033 Llanos de Antequera-Vega de Archidona** — quantitative
  status *Malo*, chemical *Malo*, at quantitative risk, global *Malo*, assessed 2016-2019,
  good status expected 2022-2027 (quantitative) and after 2027 (chemical). ES060MSBT060-034
  Fuente de Piedra — the same, and in `masas_aguasub_riesgo_2027` with `situacion`
  "Declaración provisional sobreexplotació[n]", declared 2005-06-15 (`link_decl` to the BOP
  of Málaga), authority "Junta Andalucía". `(GetFeature, 2026-11-24)`
- The bodies carry `cod_ddhh`: ES050 Guadalquivir, ES060 Cuencas Mediterráneas Andaluzas,
  etc. `demarhidro_2027` gives the river-basin districts (both found at Antequera).

## Piezometric network

- `RedPiezometrica`: `pie_cod_eu`, `pie_nombre`, `pie_descri`, `pie_xutm30_et`,
  `pie_yutm30_et`, `pie_z` (ground elevation), `pie_prof` (depth), `pie_estado`
  (Activo…), `cod_masa`. Two active piezometers in Llanos de Antequera (06.33.004 "Parque
  de Bomberos", 160 m deep; 06.33.005 "Cueva Romeral", 156 m). **No levels**: the service
  gives the network, not the measurements. `(GetFeature, 2026-11-24)`
- Level series per piezometer were not found as an API on this host. MITECO publishes the
  piezometric data through its monitoring-network viewer and the SIA; the route for
  levels is open: `VERIFY-LIVE(piezometric-levels)`. Session 07 (depth to water) depends on
  it; until then depth stays "not available" (hard rule 1).
- `sondeos` ("Catálogo de Sondeos"): `n_sondeo`, `x`, `y`, `z`, `nom_demar`, `mun_nom` — a
  borehole catalogue without depth or result fields in the map service. `(GetFeature, 2026-11-24)`

## Rivers, public water domain and zona de policía

- `DPH_Estimado` (public water domain, mapped estimate) and `DPH_Deslindado` (formally
  surveyed), visible from 1:1,000,000; `redhidrografica_2027`, `rios_mdt100`; flood zones
  (`ZI_Laminas_ZFP` preferential-flow zone, `Zi_laminas_q10/q50/q100/q500`) and vector
  tiles `https://wmts.mapama.gob.es/sig/tiles/DPHCartografico/{z}/{x}/{y}` (not catalogued).
  `(GET agua.html, 2026-11-24)`
- No service draws the **zona de policía** itself. By law it is a 100 m band measured
  horizontally from the channel (TRLA art. 6.1.b; RDPH art. 9), widened where the
  preferential-flow zone is wider: session 09 derives it as a buffer of the DPH line plus
  the `ZI_Laminas_ZFP` polygons, and says so (see `legal-groundwater.md`).
- Recharge and climate grids of the hydrological evaluation (`rechid_recarga`,
  `rechid_precipitacion`…), drainage directions `MDD25` and accumulation `Sup25x25` (25 m)
  are also served. `(GET agua.html, 2026-11-24)`

## Basin authorities

- **Guadalquivir (CHG, ES050):** the plan states that its water bodies are defined in the
  IDE-CHG (`idechg.chguadalquivir.es`). From the cloud session every path tried on that host
  redirected to an error page (`http://www.chguadalquivir.es/error404?`), so no CHG OGC
  endpoint is catalogued. MITECO's national services carry the CHG's bodies, status and
  risk. `VERIFY-LIVE(chg-ide)`. `(GET idechg.chguadalquivir.es/inspire/wms, 2026-11-24)`
- **Cuencas Mediterráneas Andaluzas (ES060):** the competent authority is the Junta de
  Andalucía; REDIAM publishes its bodies (see `junta-andalucia.md`), and MITECO's national
  services include them (`namespace` juntadeandalucia.es).
- Other basins (Segura, Júcar, Ebro, Tajo, Guadiana, Duero, Miño-Sil, Cantábrico, the
  internal basins of Catalonia, the Balearics, the Canaries…) appear in the same national
  MITECO services with their `cod_ddhh`; their own portals were not probed.

## Terms

- "Sin limitaciones al acceso público" in every capabilities document. MITECO's legal
  notice allows reuse of its information citing the source; attribution used:
  "© Ministerio para la Transición Ecológica y el Reto Demográfico".

Copyright (c) 2026 Almoon-D. All rights reserved.
