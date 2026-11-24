# MITECO and the basin authorities

Host `gis.miteco.gob.es` (GeoServer: `https://gis.miteco.gob.es/geoserver/agua/<service>/wms`,
WFS at `…/<service>/ows`). Catalogue ids: `miteco-gw-bodies`, `miteco-gw-status`
(WFS), `miteco-gw-status-wms`, `miteco-gw-at-risk`, `miteco-piezometers`,
`miteco-public-water-domain`, `miteco-rivers`, `miteco-springs`,
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
- Example, around Daimiel (Guadiana, ES040): **Mancha Occidental I** and **Campo de
  Calatrava** — quantitative status *Malo*, chemical *Malo*, at quantitative risk. In
  `masas_aguasub_riesgo_2027` both carry `situacion` "Declaración de riesgo" (2014-12-21 and
  2017-03-26), `tipo_riesgo`, `org_cuenca` "CH Guadiana" and a `link_decl` to the
  declaration. Other bodies carry "Declaración provisional sobreexplotació[n]" with older
  dates. `(GetFeature, 2026-11-24)`
- The bodies carry `cod_ddhh` (ES040 Guadiana, ES050 Guadalquivir, ES060 Cuencas
  Mediterráneas Andaluzas…); `demarhidro_2027` gives the river-basin districts. A point near
  a district boundary can fall in either: the authority follows the exact location.

## Piezometric network

- `RedPiezometrica`: `pie_cod_eu`, `pie_nombre`, `pie_descri`, `pie_xutm30_et`,
  `pie_yutm30_et`, `pie_z` (ground elevation), `pie_prof` (depth), `pie_estado`
  (Activo…), `cod_masa`. Example: 24 piezometers around Daimiel, such as ES040ESBT000404013
  "La Mancha" (115 m deep, active). **No levels**: the service gives the network, not the
  measurements. `(GetFeature, 2026-11-24)`
- Level series: MITECO publishes a national piezometry database (18.5 MB) behind a
  human-only download form, and several basins publish their own (Guadiana, Ebro, Júcar):
  routes and terms in `water-authorities.md`. The WMS/WFS above give the network only.
- `sondeos` ("Catálogo de Sondeos"): `n_sondeo`, `x`, `y`, `z`, `nom_demar`, `mun_nom` — a
  borehole catalogue without depth or result fields in the map service. `(GetFeature, 2026-11-24)`

## Rivers, public water domain and zona de policía

- `DPH_Estimado` (public water domain, mapped estimate) and `DPH_Deslindado` (formally
  surveyed), visible from 1:1,000,000; `redhidrografica_2027`, `rios_mdt100`; flood zones
  (`ZI_Laminas_ZFP` preferential-flow zone, `Zi_laminas_q10/q50/q100/q500`) and vector
  tiles `https://wmts.mapama.gob.es/sig/tiles/DPHCartografico/{z}/{x}/{y}` (not catalogued).
  `(GET agua.html, 2026-11-24)`
- `DPH_Estimado` draws, **for the stretches the SNCZI has studied**, three kinds of
  polygon told apart by `Tipo Zona`: "DPH Cartográfico", "Zona de Servidumbre" and **"Zona
  de Policía"** (its legend lists the three; a tap on the Azuer near Manzanares returns one
  of each, study "Sistema Nacional de Cartografía de Zonas Inundables", 2023). Elsewhere no
  service draws the zona de policía. By law it is a 100 m band measured horizontally from
  the channel (TRLA art. 6.1.b; RDPH art. 9), widened where the preferential-flow zone is
  wider: where `DPH_Estimado` has no polygon, session 09 derives it as a buffer of the
  channel plus the `ZI_Laminas_ZFP` polygons, and says which it used (see
  `legal-groundwater.md`). `(GetFeatureInfo, GetLegendGraphic, 2026-11-24)`
- `redhidrografica_2027` (rivers of the plans, lines with `Nombre` and the water-body code)
  and `manantiales` (the spring gauging network, "Red Hidrométrica de Manantiales": code,
  name, district, condition, elevation, controlled groundwater body, municipality, a link
  to its record) are WMS with EPSG:3857 and CORS `*`. `(GetCapabilities, 2026-11-24)`
- Recharge and climate grids of the hydrological evaluation (`rechid_recarga`,
  `rechid_precipitacion`…), drainage directions `MDD25` and accumulation `Sup25x25` (25 m)
  are also served. `(GET agua.html, 2026-11-24)`

## Feature info (GetFeatureInfo)

- Every MITECO WMS answers GetFeatureInfo as GeoJSON (`INFO_FORMAT=application/json`), its
  properties named by **readable Spanish aliases**, not the column names: "Nombre masa de
  agua", "Estado cuantitativo", "Cód. Piezómetro", "Profundidad obra (m)"… The column names
  of the WFS (`nom_masa`, `est_cu_desc`) do not appear. `(GetFeatureInfo, 2026-11-24)`
- Numbers come as text in English format ("2,004.27", "619.458010"); dates of the at-risk
  declarations as "Dec 22, 2014, 12:00:00 AM". Several services add a link to MITECO's
  record viewer (`…/geoportal-ws/visor-fichas/Default?nombre=…`). `(GetFeatureInfo, 2026-11-24)`
- The answer carries each feature's full geometry: 1 KB for a piezometer, 45 KB for a
  groundwater body, 254 KB for three `DPH_Estimado` polygons. `(GetFeatureInfo, 2026-11-24)`
- No scale range on any of these layers: they draw at every zoom. `(GetCapabilities, 2026-11-24)`

## Basin authorities

- Every basin authority and regional water agency of Spain, with what it publishes and how
  it is reached, is in `water-authorities.md`.
- **Guadalquivir (CHG, ES050):** the plan states that its water bodies are defined in the
  IDE-CHG (`idechg.chguadalquivir.es`). From the cloud session every path tried on that host
  redirected to an error page (`http://www.chguadalquivir.es/error404?`), so no CHG OGC
  endpoint is catalogued. MITECO's national services carry the CHG's bodies, status and
  risk. `VERIFY-LIVE(chg-ide)`. `(GET idechg.chguadalquivir.es/inspire/wms, 2026-11-24)`
- **Cuencas Mediterráneas Andaluzas (ES060):** the competent authority is the Junta de
  Andalucía; REDIAM publishes its bodies (see `junta-andalucia.md`), and MITECO's national
  services include them (`namespace` juntadeandalucia.es).
- Every other district appears in the same national MITECO services with its `cod_ddhh`;
  their own portals are surveyed in `water-authorities.md`.

## Terms

- "Sin limitaciones al acceso público" in every capabilities document. MITECO's legal
  notice allows reuse of its information citing the source; attribution used:
  "© Ministerio para la Transición Ecológica y el Reto Demográfico".

Copyright (c) 2026 Almoon-D. All rights reserved.
