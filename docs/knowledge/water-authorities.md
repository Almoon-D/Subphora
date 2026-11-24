# Water authorities of Spain: basins and regions

Every river-basin authority and regional water agency, what it publishes for groundwater,
and how Subphora can reach it. The national MITECO services (`miteco-basins.md`) cover the
groundwater bodies, their status and risk, the piezometric network and the public water
domain of **every** district; the sources here add detail, level series and the rules each
authority applies. Observed on 2026-11-24 from the cloud session.

Hosts catalogued from this file: `geoguadiana.chguadiana.es`, `www.chguadiana.es`,
`mirame.chduero.es`, `www.chebro.es`, `www.chj.es`, `www.geo.euskadi.eus`,
`geoserveis.icgc.cat`, `ideib.caib.es`.

## Who manages groundwater where

- **The State** (a Confederación Hidrográfica under MITECO) in the inter-community
  districts: Miño-Sil (ES010), Cantábrico Occidental (ES018) and the State part of Cantábrico
  Oriental (ES017), Duero (ES020), Tajo (ES030), Guadiana (ES040), Guadalquivir (ES050, also
  Ceuta ES150 and Melilla ES160), Segura (ES070), Júcar (ES080), Ebro (ES091).
- **A regional agency** in the intra-community districts: Galicia-Costa (ES014, Augas de
  Galicia), the Basque internal basins inside Cantábrico Oriental (ES017, URA), Catalonia's
  internal basins (ES100, Agència Catalana de l'Aigua), the Andalusian districts (ES060,
  ES063, ES064, Junta de Andalucía: `junta-andalucia.md`), the Balearic Islands (ES110,
  Govern de les Illes Balears) and each Canary island (ES120 Gran Canaria, ES122
  Fuerteventura, ES123 Lanzarote, ES124 Tenerife, ES125 La Palma, ES126 La Gomera, ES127 El
  Hierro, each with its Consejo Insular de Aguas).
- The 25 district codes above are those of MITECO's `demarhidro_2027`, which gives the
  district of any point; the legal rules of session 09 are keyed by that code (decision
  0014). `(GetFeature demarhidro_2027, 2026-11-24)`

## What each one publishes

| Authority | Map services found | Level series | Catalogue |
|---|---|---|---|
| CH Guadiana | GeoServer WMS `https://geoguadiana.chguadiana.es/geoserver/wms`: 65 layers incl. `redescontrol:Piezometria` and `limitacionesph2022:norm_apend_11_1_objetos` (perimeters closed to new abstractions, plan 2022-2027; drawn as `guadiana-abstraction-limits`, `regional-layers.md`); EPSG:3857; CORS `*`; AccessConstraints "none" | Monthly spreadsheet of the official network linked from the piezometry page (`Red Oficial Guadiana OCTUBRE 2026.xlsx`, 2.8 MB) | `chguadiana-wms`, `chguadiana-piezometry` |
| CH Duero | MÍRAME-IDEDuero WMS `https://mirame.chduero.es/duerowfd`, which answers 302 (with CORS `*`) to `https://mirame.chduero.es/geoserver/mirame/wms`, the catalogued URL: 271 layers incl. `Red_oficial_control_nivel`, `Piezometria_200`, `Piezometria_40_100`, `Piezometria_2017_*`, `Masa_Subterranea_Superior/Inferior`, `Extracciones_Aguas_Subterraneas`, `Zona_No_Autorizada_2021_horizonte_general/superior` (the plan's groundwater zoning; drawn as `duero-groundwater-zoning`, `regional-layers.md`); EPSG:3857; CORS `*`; AccessConstraints "NONE" | Piezometric surfaces drawn as layers; series not found | `chduero-wms` |
| CH Ebro | No OGC endpoint found | One spreadsheet per piezometer (`https://www.chebro.es/documents/…/p1706-8-0017.xls`) and a summary list, linked from `https://www.chebro.es/web/guest/red-piezometrica-oficial` | `chebro-piezometry` |
| CH Júcar | No OGC endpoint found; SIA Júcar web application `https://aps.chj.es/siajucar/` | Yearly level reports (PDF) and a download `https://aps.chj.es/down/CSV/F71_Puntos_de_control_piezometrico.zip` (9.2 MB) holding the control points and their field measurements (`F71_D7_Medida en campo_1.xlsx`, `…_2.xlsx`) | `chj-piezometry` |
| CH Guadalquivir | IDE-CHG (`idechg.chguadalquivir.es`, its documented WMS `…/inspire/wms` with a `Piezometros` layer) redirects to an error page from the cloud | Not reached | none: `VERIFY-LIVE(chg-ide)` |
| CH Segura | Viewer CHSIC (export of piezometers to CSV, per its page); `www.chsegura.es` reset the connection from the cloud | "Consulta de series de piezometría" page | none: `VERIFY-LIVE(water-authorities-unreached)` |
| CH Tajo | The piezometry page linked by MITECO redirects to the home page | Not found | none: `VERIFY-LIVE(water-authorities-unreached)` |
| CH Miño-Sil | IDE Miño-Sil (WMS per layer on `siams2.chminosil.es`, per its page); `www.chminosil.es` and `saih.chminosil.es` did not answer from the cloud, `siams2` answered 403 | SAIH piezometry page, not reached | none: `VERIFY-LIVE(water-authorities-unreached)` |
| CH Cantábrico | SAIH viewer `https://visor.saichcantabrico.es/` (a web application) | In the SAIH viewer | none: no data service found |
| URA (Basque Country) | WMS `https://www.geo.euskadi.eus/WMS_URA`: 95 layers incl. `hasub_masas_agua`, `hasub_sectores_masas_agua`, `ecea_masas_subterraneas`, `egma_subterraneas`, `eqma_subterraneas`, `ecds_zonas_de_Interes_Hidrogeologico`; EPSG:3857; CORS `*` | Not found (Álava publishes gauging stations at `geo.araba.eus`) | `ura-wms` |
| ACA (Catalonia) | No ACA endpoint found; the Generalitat's `sig.gencat.cat/ows/AIGUA/wms` answered 403. The ICGC hydrogeology WMS `https://geoserveis.icgc.cat/servei/catalunya/hidrogeologia/wms`: hydrogeological units, porosity and permeability, `punts_aigua` (wells, springs), `piezometries_quaternaris`, `piezometries_basament`, flow lines; EPSG:3857; CORS `*`; "public, total right of access (level A)" | Piezometric surfaces as layers | `icgc-hydrogeology-wms` |
| Augas de Galicia | A page on its piezometer network (hourly loggers in 25–33 municipalities, monthly extraction); no data link or map service found | Not published as data | none: `VERIFY-LIVE(water-authorities-unreached)` |
| Govern de les Illes Balears | ArcGIS REST `https://ideib.caib.es/geoserveis/rest/services/public/GOIB_AutCon_AigSubter_IB/MapServer` (provisional groundwater census, piezometric and quality control points, authorisation zones of the 2022 plan) and `…/GOIB_Masses_Aigua_IB/MapServer` (bodies and status, plans 2019 and 2022); CORS echoes the Origin. The census is labelled provisional, "sin validez legal" | Control points only | `ideib-groundwater` |
| Canary island councils | No OGC service found; GRAFCAN's IDECanarias is said to show hydrogeological maps; the councils keep their own inventories of wells and galleries | Not found | none: `VERIFY-LIVE(water-authorities-unreached)` |
| Junta de Andalucía | See `junta-andalucia.md` | — | `rediam-*` |

`(GetCapabilities and page fetches listed above, 2026-11-24)`

## National level series

- MITECO's download page for the quantitative monitoring network
  (`https://www.miteco.gob.es/es/cartografia-y-sig/ide/descargas/agua/red-seguimiento-estado-cuantitativo.html`)
  offers the network (`red_piezometrica.rar`), springs (`manantiales.zip`) and a
  **"Base de datos con los datos de piezometría" (18.5 MB)**:
  `https://gis.miteco.gob.es/descargas/app/DescargaFichero?f=basedatospiezometria.zip`.
  The link opens a form protected by an ALTCHA proof-of-work challenge: it is meant for a
  person. Subphora does not automate it (that would defeat the challenge); the owner
  downloads the file by hand and session 07 imports it from `data/`. `(GET DescargaFichero, 2026-11-24)`
- MITECO's page "Información y consulta de niveles piezométricos" links the viewer
  `https://sig.mapama.gob.es/redes-seguimiento/` and every basin's piezometry page (the links
  used in the table above). About 2,500 piezometers in the inter-community districts, mostly
  measured monthly. `(GET informacion-y-consulta-niveles-piezometricos.html, 2026-11-24)`

## Behaviour worth knowing

- **CH Júcar's firewall rejects any request with an `Origin` header**: the same GET returns
  the 64 KB page without it and a 247-byte "Request Rejected" page with it. A browser can
  never call it; the server can. `subphora sources check` therefore sends the capabilities
  and sample requests without `Origin` and checks CORS with a separate request.
  `(GET /es-es/medioambiente/redescontrol/Paginas/Piezometria.aspx, 2026-11-24)`
- `www.chj.es`, `aps.chj.es` and `www.chsegura.es` reset some connections from the cloud;
  the client retries.

## Terms

- The OGC services above state no access constraint ("none") or full public access (ICGC).
  The basin pages with spreadsheets and downloads (Guadiana, Ebro, Júcar) and the Balearic
  service state no licence: `VERIFY-LIVE(basin-terms)` before session 07 imports them, and a
  row in `docs/commercial-use.md`. Ley 37/2007 sets the general framework for reusing
  public-sector information; each body may attach its own conditions.

Copyright (c) 2026 Almoon-D. All rights reserved.
