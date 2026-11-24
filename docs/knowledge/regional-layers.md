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
| Springs and water points | MITECO `manantiales`; IGME water points | not stated | not stated | MITECO's records unreachable; IGME's dated only by creation (below) |
| Piezometers and levels | MITECO `RedPiezometrica` (network only, no levels) | not stated | not stated | MITECO's record unreachable (below) |
| Hydrogeology | IGME hydrogeological map; permeability | 1:200,000 | 2010; 2009 | CODSI record (publication 2010-10-25); permeability 2nd edition, revised 2009-08-05 |
| Geology | IGME GEODE (MAGNA 1:50,000 sheets 1972-2003 beside it); lithostratigraphic | 1:50,000 mainland, 1:25,000 islands; 1:200,000 | per GEODE zone, 2007-2014 (`igme.md`); 2009 | IDEE records per zone; lithostratigraphic 2nd edition, revised 2009-08-05 |
| Soils | SoilGrids 2.0 clay 0-5 cm | 250 m cells | 2021 | SoilGrids 2.0 release (ISRIC) |
| Public water domain | MITECO `DPH_Estimado` | not stated | per study | SNCZI studies, dated per stretch; the record's own dates disagree (below) |

National editions searched on 2026-11-24 `(IDEE INSPIRE CSW GetRecords and record XML,
CODSI search, ArcGIS service metadata)`:

- **GEODE** has no single edition: each zone is its own dataset in the IDEE INSPIRE
  catalogue (`ESPIGMEGEODE50Z<zone>…`), published 2007 (1000, 1100, 1300, the Canary
  islands) to 2014 (2600, 2800). A regional geology layer is compared with the newest zone
  over its area (`national_edition` in `regional.yaml`, decision 0025).
- **IGME water points**: "Base de datos de Puntos de Agua del IGME" (`ESPIGMEPUNTOSAGUA20190723`)
  gives only a creation date, 1970; the service says "desde 1966 hasta la actualidad".
- **MITECO springs and piezometers**: their capabilities name records on
  `catalogo.datosabiertos.miteco.gob.es` (ids `320c3e32…`, `78f8661b…`), whose certificate
  chain the cloud cannot verify; the IDEE catalogue does not hold them (404).
  `VERIFY-LIVE(national-network-editions)`: until they and the IGME water points state an
  edition, no regional springs, water-point or piezometer layer qualifies.
- **MITECO public water domain**: the record "Cauces con DPH cartográfico" (`88e3e8c0…`, in
  IDEE) dates creation 2026-07-10 after publication 2026-05-25, revision 2012-03-02; each
  stretch carries its study's date.

## Verdicts

Q qualifies (catalogued) · V waits on the VERIFY-LIVE item its note names · K a clip or
copy of the national layer · S neither finer nor richer · O older than the national edition
· L legal theme, publisher not the competent authority · N no service found · U the hosts
did not answer from the cloud.

| Territory | Bodies & status | Rivers | Springs & points | Piezometers | Hydrogeology | Geology | Soils | Public water domain |
|---|---|---|---|---|---|---|---|---|
| Andalucía (ES-AN) | **Q** preventive control (ES060, ES063, ES064); K bodies | K | V | N | O | S | O | N |
| Aragón (ES-AR) | U | U | U | U | U | U | U | U |
| Asturias (ES-AS) | U | U | U | U | U | U | U | U |
| Illes Balears (ES-IB) | K | O | V | V | N | O | N | K |
| Canarias (ES-CN) | N | N | N | N | N | S | N | N |
| Cantabria (ES-CB) | N | V | N | N | N | V | S | N |
| Castilla y León (ES-CL) | U | U | U | U | U | U | U | U |
| Castilla-La Mancha (ES-CM) | U | U | U | U | U | U | U | U |
| Cataluña (ES-CT) | U | V | V | V | **Q** | S | **Q** | U |
| Comunitat Valenciana (ES-VC) | N | N | N | N | N | **Q** | N | N |
| Extremadura (ES-EX) | U | U | U | U | U | U | U | U |
| Galicia (ES-GA) | U | U | U | U | U | U | U | U |
| Comunidad de Madrid (ES-MD) | N | N | N | N | N | S | O | N |
| Región de Murcia (ES-MC) | U | U | U | U | U | U | U | U |
| Navarra (ES-NC) | N | O | V | V | O | **Q** | **Q** | L |
| País Vasco (ES-PV) | K | O | V | N | S | N | N | L |
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
  2005 (O). `REDIAM_plan_conservacion_manantiales` → `manantiales_lih`: springs and sites
  of hydrogeological interest of the Consejería's 2011 conservation plan, with a *proposed*
  protection zoning; a tap near Granada answers "Fuente Grande de Alfacar", "ZONA TIPO A"
  (V: `national-network-editions`).
  `(GetCapabilities, GetFeatureInfo, CSW GetRecordById, 2026-11-24)`
- **Illes Balears** (`ideib.caib.es/geoserveis`, ArcGIS; CORS echoes the origin; CC BY-SA):
  `GOIB_Masses_Aigua_IB` (plans 2019 and 2022: K). `GOIB_AutCon_AigSubter_IB`: the
  provisional groundwater census ("sin validez jurídica, subjecte a revisió"; points
  labelled by their concession or catalogue file, private rights: never shown) and the
  piezometric control points (`CODI`, `NOM_IDENTI`, `TIPUS`, `COTA_TERRE`, `MAS`,
  `XARXA_PIEZ`; a tap at EI0001, Sant Miquel, answers "Sondeig", "Actiu"): V
  (`national-network-editions`). `GOIB_Aigua_DPH_IB` → `Domini Públic Hidràulic
  Cartogràfic`: 79 stretches of the SNCZI study "Zonas inundables Islas Baleares", dated
  2021-11-17 to 2024-01-19; MITECO's `DPH_Estimado` in Mallorca answers the same study with
  "Organismo: Gobierno de las Islas Baleares": K. Its `Xarxa Hidrogràfica Provisional`
  carries MTIB editions 1995 to 2006 (O). `GOIB_Geologia_IB`: the geological map 1:25,000
  "de 2004" (service description), units such as "Cuaternario, Limos, arcillas y gravas"
  over 547 km²; GEODE's island zones are 1:25,000 too and were published 2009-2010 (O).
  `(REST layer metadata and statistics, GetFeatureInfo, 2026-11-24)`
- **Canarias** (GRAFCAN `idecan2.grafcan.es/ServicioWMS/Geologico`; CORS `*`; EPSG:3857):
  lithology per island; GEODE is 1:25,000 on the islands too (S). Its terms: "Prohibido el
  uso comercial y la descarga masiva" (`docs/commercial-use.md`). No island water council
  service found.
- **Cantabria** (`geoservicios.cantabria.es/inspire`, ArcGIS; CORS echoes the origin):
  `Serie_Geologico_Raster`, the 1:25,000 geological map made with IGME: 57 scanned sheets,
  each with its own memoir (sheet 58-III: "Diciembre 2009"); a tap on the map answers only
  the pixel's colour (`RGB.Red`…), one on the sheet layer the links to its legend and
  sections. `VERIFY-LIVE(cantabria-geology-editions)`: the oldest sheet's date (each memoir
  is 7-17 MB) decides it against GEODE zones 1000, 1600 and 2300 (2007-2010); downloads
  under a non-commercial licence (Decree 87/2013). `Hidrografia`: the Government's river
  network, "aproximada", which "no sustituye a los datos de dichas Confederaciones", no
  edition stated: `VERIFY-LIVE(regional-editions)`.
  `Suelos_y_Edafologia`, an agro-ecological zoning, "a very general diagnosis" (S);
  `Directiva_Marco_del_Agua_DMA`, coastal and transitional waters only.
- **Cataluña** (ICGC `geoserveis.icgc.cat`, CORS `*`, public with full access):
  `hidrogeologia/wms` → `unitats_hidrogeologiques_tipus`, the continuous 1:25,000
  hydrogeological map (revised 2022-12), with name, type, hydraulic behaviour, porosity,
  nature per unit; a tap near Manresa answers "Aqüitard… Doble porositat": **Q**,
  `catalonia-hydrogeology`. The same service's `punts_aigua_pou` answered nothing even at
  a drawn well near Girona; `piezometries_quaternaris` answers isolines of a June-July 2012
  campaign ("Cota_isopieza" 70 m): V (`national-network-editions`). `edafologia/wms` →
  `sols-25000`: the soil map of Catalonia 1:25,000 v1.1, December 2025 (IDEC record
  `sols-25000-v1r1-202512`), soil series with Soil Taxonomy class and description; drawn
  only at scales of 1:23,000 and smaller (to zoom 14), partial cover (agricultural areas),
  a tap answers at any zoom ("Comapregona", "Haploxerepts fluvèntics"): **Q**,
  `catalonia-soils`. `geologia-territorial/wms`: 1:50,000, as GEODE, and no EPSG:3857 (S).
  The ACA's `sig.gencat.cat/ows/AIGUA/wms`, the river network's authority, answered 403:
  rivers V (`regional-hosts-unreached`). ICGC legal notice: reuse worldwide, commercial
  included, citing the source and its last update. `(GetCapabilities, GetFeatureInfo, IDEC
  CSW, 2026-11-24)`
- **Comunitat Valenciana** (ICV `terramapas.icv.gva.es/29_GeoCV25`; CORS `*`; CC BY 4.0):
  `GeoCV25.UnidadesGeologicas`, the geological map 1:25,000 made by the ICV and IGME, still
  being extended (Alicante drawn, inland Valencia not yet), created 2023-04-04, revised
  2024-04-10 (ICV record `spaicv29_geocv25`); GetFeatureInfo only in GML (`msGMLOutput`):
  near Alicante "Gravas, arenas y pelitas… Piedemonte", PLEISTOCENO SUPERIOR; empty where
  unmapped. GEODE zones 1700, 1800, 2100, 2400, 2600 and 2800 cover the region, the newest
  published in 2014: **Q**, `valencia-geology`. No hydrogeological, soil or water service
  in its catalogue. `(GetCapabilities, GetFeatureInfo, ICV CSW, 2026-11-24)`
- **Comunidad de Madrid** (`idem.comunidad.madrid/geoidem`; CORS `*`; CC BY 4.0):
  lithology 1:50,000 (S); soil associations (FAO) and Soil Taxonomy maps of the former CSIC
  institute, older than SoilGrids (O).
- **Navarra** (IDENA `idena.navarra.es/ogc/wms`; CORS `*`; CC BY 4.0): `EDAFOL_Pol_Suelos25m`,
  soil map 1:25,000 revised 2023-01-15, series by Soil Taxonomy with textural and family
  classes; a tap near Tafalla answers "Lithic Xeric Torriorthent, Franco arcillosa": **Q**,
  `navarra-soils`. `GEOLOG_Pol_Litologia`, geology 1:25,000 published 2011-09-29, units
  with era, age, stage and sheet; near Tafalla "359 Areniscas, limolitas y arcillas",
  Ageniense. GEODE zones 1600, 1700 and 2700 cover Navarra, the newest published in 2010:
  **Q**, `navarra-geology`. `GEOLOG_Sym_Manantiales` (spring inventory 1:5,000, revised
  2026-06; a tap answers spring M15610, Araitz) and `HIDROG_Sym_AforoPiezo` (the
  Government's piezometric network, revised 2024-10; a tap answers IRANETA R2, Aralar): V
  (`national-network-editions`). `HIDROG_Lin_CorrienteNatural` (rivers 1:5,000, published
  2022-02-28): older than MITECO's 2023 (O). `HIDROG_Pol_AspHidroGeo` ("aspectos
  hidrogeológicos", 1:50,000): record published 2025-03-01, but every unit dated
  2003-06-12, some over 1,900 km², with a vulnerability class: older than IGME's 2010 (O).
  `HIDROG_Pol_DphZsZp` (public water domain): the Government of Navarra is not the water
  authority there (CH Ebro, CH Cantábrico): L. `(GetFeatureInfo, WFS, metadata, 2026-11-24)`
- **País Vasco** (`www.geo.euskadi.eus`; CORS `*`): `WMS_URA` → `hasub_masas_agua` (K);
  `puntos_agua_CAPV`, an inventory of wells named after their owners or businesses (never
  shown): V (`national-network-editions`); `has_rios`, URA's river network, features
  loaded 2017-05-24 and none later (O); `cp_dominio_publico_hidraulico` (URA is competent
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
| CH Guadiana (ES040) | `geoguadiana.chguadiana.es/geoserver/wms` (GeoServer, CORS `*`): `limitacionesph2022:norm_apend_11_1_objetos`, 516 perimeters (600 or 1,200 m) around wetlands, springs, piezometers and drains where no new groundwater abstraction is authorised (plan 2022-2027, normative appendix 11.1); a tap at the Laguna de las Yeguas answers its name, type, appendix clause, perimeter and body. The basin authority is competent: | **Q** `guadiana-abstraction-limits` |
| | `redescontrol:Piezometria` (V, `national-network-editions`); `hidrografia_redhidro_rios0`, extracted from MTN25, no edition stated, "no debe ser tenida en cuenta nunca como representación…" (V, `regional-editions`) | |
| CH Duero (ES020) | `mirame.chduero.es/geoserver/mirame/wms` (`/duerowfd` redirects there; CORS `*`): `Zona_No_Autorizada_2021_horizonte_general`, the zoning of the plan 2022-2027 (BOE 2023-02-10, annex IV art. 33: "zona no autorizada", "con limitaciones específicas", "sin restricciones"…, "establecidas en el sistema de información Mírame-IDEDuero"), per sector of the 52 bodies of the general horizon; near Medina del Campo "Zona No Autorizada". The basin authority is competent: | **Q** `duero-groundwater-zoning` |
| | `…_horizonte_superior` (the 12 upper-horizon bodies: a second layer, not shown yet, follow-up); piezometric surfaces of 2009 and 2017 (V, `national-network-editions`) | |
| CH Ebro, CH Júcar | No OGC endpoint found (`water-authorities.md`) | N |
| CH Guadalquivir, Segura, Tajo, Miño-Sil, Cantábrico | Hosts redirect, reset or refuse (403) from the cloud | U |
| URA, ACA, Augas de Galicia, Govern balear, Canary councils | See their territories above | — |

## Boundaries

- **Autonomous communities**: IGN, `https://www.ign.es/wfs-inspire/unidades-administrativas`,
  `au:AdministrativeUnit`, filtered by `au:nationalCode` (34, the INE community code, then
  zeros: Navarra `34150000000`, Catalonia `34090000000`, Valencian Community
  `34100000000`); GeoJSON in EPSG:4326, longitude first; full detail: Navarra 1.4 MB,
  Catalonia 15 MB (150,000 vertices, 745 polygons), Valencian Community 6.8 MB;
  no CORS; CC BY 4.0 ign.es. `(GetFeature, 2026-11-24)`
- **River-basin districts**: MITECO, `https://gis.miteco.gob.es/geoserver/agua/demarhidro_2027/ows`,
  `agua:demarhidro_2027` filtered by `cod_ddhh`; coordinates already rounded to four
  decimals (ES060 1.4 MB, ES040 3.6 MB, ES020 3.4 MB). `(GetFeature, 2026-11-24)`
- Both take a standard WFS 2.0 `PropertyIsEqualTo` filter. Rounded to a 0.0001° grid, a
  boundary keeps every shared vertex shared: Navarra 10,200 vertices, Catalonia 61,000,
  ES060 38,600. `(subphora geo.areas, 2026-11-24)`

## Live check

`(LayerService.info, 2026-11-24)`: Tafalla, soils → IDENA 1:25,000 (2023); near Manresa,
hydrogeology → ICGC 1:25,000 (2022); Campo de Dalías, bodies at risk → REDIAM (2023); Málaga
(inside ES060, outside any body under control) → REDIAM empty, MITECO answers; Granada
(ES050) and Zaragoza → the national layers; Logroño, inside Navarra's box but not Navarra
→ SoilGrids, which answers no value.

`(LayerService.info, 2026-11-24)`, the layers added later: near Vallbona de les Monges (Catalonia), soils
→ ICGC 1:25,000 (2025) "Comapregona"; Manresa, outside its cover → ICGC, nothing (SoilGrids
has no tap); Tafalla, geology → IDENA 1:25,000 (2011); Alicante → ICV 1:25,000 (2024)
"Calcarenitas y calcirruditas bioclásticas"; inland Valencia, not yet mapped → ICV empty,
GEODE answers; Laguna de las Yeguas, bodies at risk → CH Guadiana (2023); Daimiel, outside
every perimeter → CH Guadiana empty, MITECO answers; Medina del Campo → CH Duero (2023)
"Zona No Autorizada"; Ourense (Miño-Sil) → MITECO.

Copyright (c) 2026 Almoon-D. All rights reserved.
