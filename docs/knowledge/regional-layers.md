# Regional layers: the survey of decision 0023

Every autonomous community, Ceuta, Melilla and every basin authority, surveyed under one
rule for each map theme: does a regional, provincial or basin service add detail over the
national layer? Observed on 2026-11-24 from the cloud session (GetCapabilities with an
`Origin` header, GetFeatureInfo at a point inside the area, metadata records). The rule is
data in `config/defaults/regional.yaml`; the layers that qualify are catalogued there and in
`config/defaults/sources.yaml`.

## The rule (decision 0023)

A regional layer qualifies when it is **official**, its edition is **at least as recent**
as the national one, and it is **finer** in scale (a map at 1:N resolves about N × 0.5 mm:
1:25,000 ≈ 12.5 m against SoilGrids' 250 m cells) **or richer** in attributes; a **clip** of
the national layer never qualifies; for a **legal status** (bodies at risk, public water
domain) only the **competent authority** counts. A national layer whose edition its
publisher does not state cannot be compared, so nothing qualifies over it until it is known.

## National baselines

| Theme | National layer | Scale | Edition | Evidence |
|---|---|---|---|---|
| Groundwater bodies and status | MITECO `masas_aguasub_2027`, `estado_…`, `…_riesgo_2027` | not stated | 2023 | Plans 2022-2027 (RD 35/2023) |
| Rivers | MITECO `redhidrografica_2027` | not stated | 2023 | Plans 2022-2027 |
| Springs and water points | MITECO `manantiales`; IGME water points | not stated | not stated | Living networks and database |
| Piezometers and levels | MITECO `RedPiezometrica` (network only, no levels) | not stated | not stated | `miteco-basins.md` |
| Hydrogeology | IGME hydrogeological map; permeability | 1:200,000 | 2010; not stated | CODSI record, publication 2010-10-25 |
| Geology | IGME GEODE (MAGNA 1:50,000 sheets 1972-2003 beside it) | 1:50,000 mainland, 1:25,000 islands | not stated | GEODE service metadata (version 3.5.0, no date); plan begun 2004 |
| Soils | SoilGrids 2.0 clay 0-5 cm | 250 m cells | 2021 | SoilGrids 2.0 release (ISRIC) |
| Public water domain | MITECO `DPH_Estimado` | not stated | per study | SNCZI studies, dated per stretch |

## Verdicts

Q qualifies (catalogued) · E evidence still missing (scale, date or tap not verified: the
remainder session) · K a clip or copy of the national layer · S neither finer nor richer ·
O older than the national edition · L legal theme, publisher not the competent authority ·
N no service found · U the hosts did not answer from the cloud.

| Territory | Bodies & status | Rivers | Springs & points | Piezometers | Hydrogeology | Geology | Soils | Public water domain |
|---|---|---|---|---|---|---|---|---|
| Andalucía (ES-AN) | **Q** preventive control (ES060, ES063, ES064); K bodies | K | E | N | O | S | O | N |
| Aragón (ES-AR) | U | U | U | U | U | U | U | U |
| Asturias (ES-AS) | U | U | U | U | U | U | U | U |
| Illes Balears (ES-IB) | K | E | E | E | N | E | N | E |
| Canarias (ES-CN) | N | N | N | N | N | S | N | N |
| Cantabria (ES-CB) | N | E | N | N | N | E | S | N |
| Castilla y León (ES-CL) | U | U | U | U | U | U | U | U |
| Castilla-La Mancha (ES-CM) | U | U | U | U | U | U | U | U |
| Cataluña (ES-CT) | U | E | E | E | **Q** | S | E | U |
| Comunitat Valenciana (ES-VC) | N | N | N | N | N | E | N | N |
| Extremadura (ES-EX) | U | U | U | U | U | U | U | U |
| Galicia (ES-GA) | U | U | U | U | U | U | U | U |
| Comunidad de Madrid (ES-MD) | N | N | N | N | N | S | O | N |
| Región de Murcia (ES-MC) | U | U | U | U | U | U | U | U |
| Navarra (ES-NC) | N | E | E | E | E | E | **Q** | L |
| País Vasco (ES-PV) | K | E | E | N | S | N | N | L |
| La Rioja (ES-RI) | U | U | U | U | U | U | U | U |
| Ceuta (ES-CE) | U | U | U | U | U | U | U | U |
| Melilla (ES-ML) | N | N | N | N | N | N | N | N |

## What was found, per territory

- **Andalucía** (REDIAM, `www.juntadeandalucia.es/medioambiente/mapwms/…`; EPSG:3857; **no
  CORS**; free use citing the authors; GetFeatureInfo in MapServer GML):
  `REDIAM_masas_subt_intracomunitarias_control_prevent` (`masas_agua_subt_intracom`): the
  bodies of ES060, ES063 and ES064 under **preventive control** (Andalusian Water Law, art.
  51), each with `thematicIdIdentifier`, `nametext`, `control_preventivo` ("Sometida a
  control preventivo"); bodies versioned 2023-02-07, metadata published 2023-07-21; a tap
  in Campo de Dalías answers ES060MSBT060-013, one in Madrid an empty `msGMLOutput`. The
  Junta is the competent authority there: **Q**, `andalusia-preventive-control`.
  `REDIAM_masas_agua_andalucia_phc_2022_27`: the plans' bodies and rivers, which MITECO
  also serves (K). `REDIAM_Geologico_Andalucia` and `REDIAM_Litologico_Andalucia`:
  1:400,000 (S). `REDIAM_Suelos_Andalucia`: 1:400,000, 2005 (O). `REDIAM_Vulnerabilidad_Acuiferos`:
  2005 (O). `REDIAM_plan_conservacion_manantiales`: springs and hydrogeological sites of a
  conservation plan, scale and date not read (E).
  `(GetCapabilities, GetFeatureInfo, CSW GetRecordById, 2026-11-24)`
- **Illes Balears** (`ideib.caib.es/geoserveis`, ArcGIS; CORS echoes the origin; CC BY-SA):
  `GOIB_Masses_Aigua_IB` (plans 2019 and 2022: K); `GOIB_AutCon_AigSubter_IB` (provisional
  groundwater census "sin validez legal", piezometric control points, EPSG:3857: E, taps not
  probed); `GOIB_Aigua_DPH_IB` (public water domain by the Govern, the competent authority
  of ES110; its WMS lacks EPSG:3857, so the ArcGIS export would draw it: E);
  `GOIB_Geologia_IB` (scale not read; GEODE is 1:25,000 on the islands: E).
- **Canarias** (GRAFCAN `idecan2.grafcan.es/ServicioWMS/Geologico`; CORS `*`; EPSG:3857):
  lithology per island; GEODE is 1:25,000 on the islands too (S). Its terms: "Prohibido el
  uso comercial y la descarga masiva" (`docs/commercial-use.md`). No island water council
  service found.
- **Cantabria** (`geoservicios.cantabria.es/inspire`, ArcGIS; CORS echoes the origin):
  `Serie_Geologico_Raster`, the 1:25,000 geological map made with IGME, a raster (taps not
  probed; GEODE's edition unstated: E; downloads under a non-commercial licence);
  `Suelos_y_Edafologia`, an agro-ecological zoning, "a very general diagnosis" (S);
  `Directiva_Marco_del_Agua_DMA`, coastal and transitional waters only.
- **Cataluña** (ICGC `geoserveis.icgc.cat`, CORS `*`, public with full access):
  `hidrogeologia/wms` → `unitats_hidrogeologiques_tipus`, the continuous 1:25,000
  hydrogeological map (revised 2022-12), with name, type, hydraulic behaviour, porosity,
  nature per unit; a tap near Manresa answers "Aqüitard… Doble porositat": **Q**,
  `catalonia-hydrogeology`. The same service's `punts_aigua*` and `piezometries_*` (drawn
  from 1:47,000) answered nothing at the points probed (E). `edafologia/wms` → `sols-25000`
  (1:25,000, drawn from 1:23,000; empty at the point probed; date not read: E).
  `geologia-territorial/wms`: 1:50,000, as GEODE, and no EPSG:3857 (S). The ACA's
  `sig.gencat.cat/ows/AIGUA/wms` answered 403 (U).
- **Comunitat Valenciana** (ICV `terramapas.icv.gva.es/29_GeoCV25`; CORS `*`; CC BY 4.0):
  geology 1:25,000; GetFeatureInfo answered an empty `msGMLOutput` at the points probed and
  GEODE's edition is unstated (E). No hydrogeological, soil or water service in its catalogue.
- **Comunidad de Madrid** (`idem.comunidad.madrid/geoidem`; CORS `*`; CC BY 4.0):
  lithology 1:50,000 (S); soil associations (FAO) and Soil Taxonomy maps of the former CSIC
  institute, older than SoilGrids (O).
- **Navarra** (IDENA `idena.navarra.es/ogc/wms`; CORS `*`; CC BY 4.0): `EDAFOL_Pol_Suelos25m`,
  soil map 1:25,000 revised 2023-01-15, series by Soil Taxonomy with textural and family
  classes; a tap near Tafalla answers "Lithic Xeric Torriorthent, Franco arcillosa": **Q**,
  `navarra-soils`. `GEOLOG_Pol_Litologia`, geology 1:25,000 published 2011 (GEODE's edition
  unstated: E); `GEOLOG_Sym_Manantiales` (spring inventory 1:5,000, revised 2026-06) and
  `HIDROG_Lin_CorrienteNatural` (rivers 1:5,000, 2022) answered nothing at the points probed
  (E); `HIDROG_Sym_AforoPiezo` (the Government's piezometric network) and
  `HIDROG_Pol_AspHidroGeo` not probed (E); `HIDROG_Pol_DphZsZp` (public water domain): the
  Government of Navarra is not the water authority there (CH Ebro, CH Cantábrico): L.
- **País Vasco** (`www.geo.euskadi.eus`; CORS `*`): `WMS_URA` → `hasub_masas_agua` (K),
  `puntos_agua_CAPV` and the rivers (E), `cp_dominio_publico_hidraulico` (URA is competent
  only in the internal basins, which no national service bounds: L); `WMS_INGURUMENA` →
  aquifer vulnerability (S). The EVE 1:25,000 geology was not found on the WMS endpoints
  tried (N).
- **Melilla**: no spatial data service found (`www.melilla.es` answers).
- **Unreachable from the cloud (U)**: `idearagon.aragon.es` (ICEARAGON answers but serves
  reference maps only), `ideas.asturias.es`, `idecyl.jcyl.es` (reset), `ide.castillalamancha.es`
  (TLS handshake failure), `www.ideextremadura.com`, `mapas.xunta.gal` (`ideg.xunta.gal`
  answers, with no geology or water folder), `iderm.imida.es`, `inspire.larioja.org`
  (Cloudflare challenge), `ogc.larioja.org` (522), `www.ideceuta.es`.
  `VERIFY-LIVE(regional-hosts-unreached)`.

## Basin authorities

| Authority | Finding | Verdict |
|---|---|---|
| Junta de Andalucía (ES060, ES063, ES064) | Bodies under preventive control (above) | **Q** |
| CH Guadiana (ES040) | `geoguadiana.chguadiana.es/geoserver/wms` (CORS `*`): piezometric network, groundwater-body sectors, a high-density river network, "zones not authorised for new abstractions"; taps not probed | E |
| CH Duero (ES020) | `mirame.chduero.es/duerowfd` (CORS `*`): piezometric surfaces `Piezometria_200`, `Piezometria_40_100`, extractions; taps and dates not probed | E |
| CH Ebro, CH Júcar | No OGC endpoint found (`water-authorities.md`) | N |
| CH Guadalquivir, Segura, Tajo, Miño-Sil, Cantábrico | Hosts redirect, reset or refuse (403) from the cloud | U |
| URA, ACA, Augas de Galicia, Govern balear, Canary councils | See their territories above | — |

## Boundaries

- **Autonomous communities**: IGN, `https://www.ign.es/wfs-inspire/unidades-administrativas`,
  `au:AdministrativeUnit`, filtered by `au:nationalCode` (34, the INE community code, then
  zeros: Navarra `34150000000`, Catalonia `34090000000`); GeoJSON in EPSG:4326, longitude
  first; full detail: Navarra 1.4 MB, Catalonia 15 MB (150,000 vertices, 745 polygons);
  no CORS; CC BY 4.0 ign.es. `(GetFeature, 2026-11-24)`
- **River-basin districts**: MITECO, `https://gis.miteco.gob.es/geoserver/agua/demarhidro_2027/ows`,
  `agua:demarhidro_2027` filtered by `cod_ddhh`; coordinates already rounded to four
  decimals (ES060 1.4 MB). `(GetFeature, 2026-11-24)`
- Both take a standard WFS 2.0 `PropertyIsEqualTo` filter. Rounded to a 0.0001° grid, a
  boundary keeps every shared vertex shared: Navarra 10,200 vertices, Catalonia 61,000,
  ES060 38,600. `(subphora geo.areas, 2026-11-24)`

## Live check

`(LayerService.info, 2026-11-24)`: Tafalla, soils → IDENA 1:25,000 (2023); near Manresa,
hydrogeology → ICGC 1:25,000 (2022); Campo de Dalías, bodies at risk → REDIAM (2023); Málaga
(inside ES060, outside any body under control) → REDIAM empty, MITECO answers; Granada
(ES050) and Zaragoza → the national layers; Logroño, inside Navarra's box but not Navarra
→ SoilGrids, which answers no value.

Copyright (c) 2026 Almoon-D. All rights reserved.
