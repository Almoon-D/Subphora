# Roadmap

## What runs next

| Session | Prompt | Model and effort | Status |
|---|---|---|---|
| 00 | `docs/sessions/done/00-plan.md` | Opus 5.5 | done |
| 01 | `docs/sessions/done/01-verify-sources.md` | Opus 5.5, high | done |
| 02 | `docs/sessions/done/02-first-slice.md` | Opus 5.5, high | done |
| 03 | `docs/sessions/done/03-official-layers.md` | Opus 5.5, high | done |
| 03b | `docs/sessions/done/03b-regional-detail.md` | Opus 5.5, high | done |
| 03ba | `docs/sessions/done/03ba-regional-evidence.md` | Opus 5.5, high | done |
| 04 | `docs/sessions/done/04-search.md` | Opus 5.5, medium | done |
| 05 | `docs/sessions/done/05-national-map.md` | Opus 5.5, high | done |
| 06 | `docs/sessions/done/06-parcel-detail.md` | Opus 5.5, high | done |
| 07 | `docs/sessions/done/07-validation-depth-cost.md` | Opus 5.5, high | done |
| 08 | `docs/sessions/done/08-cross-section.md` | Opus 5.5, high | done |
| 09 | `docs/sessions/09-legal-filter.md` | Opus 5.5, high | next |
| 10 | `docs/sessions/10-field-mode.md` | Opus 5.5, high | planned |
| 11 | `docs/sessions/11-offline-packs.md` | Opus 5.5, high | planned |
| 12 | `docs/sessions/12-report.md` | Opus 5.5, medium | planned |
| 13 | `docs/sessions/13-deployment.md` | Opus 5.5, high | planned — version 1 |
| 14 | `docs/sessions/14-well-registry-learning.md` | Opus 5.5, high | planned |
| 15 | `docs/sessions/15-satellite-climate.md` | Opus 5.5, high | planned |
| 16 | `docs/sessions/16-hardware-planning.md` | Opus 5.5, high | planned |

## Live verification queue

<!-- VERIFY-LIVE(<what>) items: the check, the session that queued it, the condition that
     unblocks it. Removed when verified. -->

- VERIFY-LIVE(magna-section): draw a section in `make dev` on the owner's test area and check
  that MAGNA layer 11 answers `DLO` per unit and that a contact's projected dip matches the
  dip symbols on the MAGNA WMS (`DIRECCION` read as dip direction). Queued by 08; IGME
  answers 403 from the cloud, so it needs the owner's machine.

- VERIFY-LIVE(dependabot-merge): the first green minor or patch Dependabot PR merges by
  itself, including a github-actions one (it changes `.github/workflows/`, which the
  default token may not be allowed to merge). If that one fails, the maintenance session
  merges it by hand and this line records the outcome. Queued by the template.
- VERIFY-LIVE(chg-ide): every path on `idechg.chguadalquivir.es` redirected to an error page
  from the cloud session; find the CHG's OGC endpoints (MITECO's national services cover
  the bodies meanwhile). Queued by 01; unblocked by a browser look at the CHG geoportal.
- VERIFY-LIVE(dry-wells): a public record of dry or failed boreholes (IGME BDAguas, basin
  registers). Until one exists, validation is presence-background and no domain is
  calibrated into a probability (decision 0030). Queued by 07; IGME or the owner's wells (14).
- VERIFY-LIVE(piezometer-body-codes): that `MAS_CONTROL` in the national piezometry database
  (and CH Júcar's 2022-plan codes) match MITECO's groundwater-bodies layer, on a real build
  with levels; the files disagree with each other in places (`water-authorities.md`).
  Queued by 07; the owner's next `national build` and detailed map show it.
- VERIFY-LIVE(drilling-prices): the €/m and fixed costs in `config/defaults/drilling.yaml`
  come from three consumer price pages (2023-2026), not quotes; a local driller's quote
  overrides them in `config/owner.yaml`. Queued by 07; the owner.
- VERIFY-LIVE(basin-terms): the licence of the basin spreadsheets and downloads (Guadiana,
  Ebro, Júcar) and of the Balearic service, not stated on their pages. Queued by 01; the
  owner allows them for private testing (07); a paid product asks first.
- VERIFY-LIVE(water-authorities-unreached): CH Guadalquivir, Segura, Tajo, Miño-Sil, Augas de
  Galicia and the Canary island councils published no reachable data service from the cloud;
  find their endpoints from a browser. Queued by 01; session 07 (levels) and 09 (rules).
- VERIFY-LIVE(igme-water-levels): levels per IGME water point exist only in the BDAguas web
  app, with no documented API; ask IGME or find a download. Queued by 01; still open after 07.
- VERIFY-LIVE(igme-geode-download): the GEODE vector download route and size. Queued by 01;
  the national model (05) needed none; session 06 or 08 if it reads GEODE in bulk.
- VERIFY-LIVE(cnig-mdt02-coverage): MDT02 coverage and download route (the CNIG download
  centre is a JavaScript app). Queued by 01; session 06 reads MDT05 from the WCS meanwhile
  (`parcel.yaml` terrain `model`); unblocked by a browser look at the download centre, then
  a session that reads MDT02 where it covers the area.
- VERIFY-LIVE(egms-terms): the Copernicus Land data-policy page did not answer from the
  cloud; read it before session 15 uses EGMS. Queued by 01.
- VERIFY-LIVE(regional-hosts-unreached): the spatial data services of Aragón, Asturias,
  Castilla y León, Castilla-La Mancha, Extremadura, Galicia, Murcia, La Rioja and Ceuta, the
  ACA and five basin authorities did not answer from the cloud (resets, TLS failures, a
  Cloudflare challenge); find their geology, soil and water endpoints from a browser in
  Spain and survey them under decision 0023 (`docs/knowledge/regional-layers.md`); the
  Catalan rivers wait on the ACA's. Queued by 03b; still open after 03ba; the owner.
- VERIFY-LIVE(national-network-editions): the editions of MITECO's springs and piezometer
  networks (their records sit on `catalogo.datosabiertos.miteco.gob.es`, whose certificate
  chain the cloud cannot verify) and of the IGME water points (its record gives only a 1970
  creation date). Until known, no regional springs, water-point or piezometer layer
  qualifies: Navarra, Catalonia, the Balearics, the Basque Country, Andalusia, CH Guadiana
  and CH Duero wait on it. Queued by 03ba; the owner (a browser) or IGME and MITECO.
- VERIFY-LIVE(regional-editions): the Cantabrian river network and CH Guadiana's
  high-density network state no edition; ask their publishers. Queued by 03ba.
- VERIFY-LIVE(cantabria-geology-editions): the date of each of the 57 sheets of Cantabria's
  1:25,000 geological map (sheet 58-III: December 2009) against GEODE's zones there
  (2007-2010); its tap answers only a pixel colour, so a qualifying version needs the
  sheet layer's links too. Queued by 03ba.
- VERIFY-LIVE(national-all): the owner runs `uv run subphora national build --all` on a
  machine with ~5 GB free (estimate: ~2 GB of grids, 2-3 GB of cached terrain windows) and
  records the time, the size and any region that failed. Two provinces were built live (05).
- VERIFY-LIVE(national-editions): which MDT25 coverage the IGN WCS serves (the IDEE
  catalogue holds the first, 2009-2015, and the second, 2015-2021; the WCS names neither)
  and the groundwater bodies' scale; their confidence uses the "unknown" value until a
  record states them (IGN, MITECO). Queued by 05; unblocked by the IGN's answer or the
  WCS's metadata naming its coverage.
- VERIFY-LIVE(keyed-services): `aemet-opendata` is "not checked"
  until the owner's key exists (session 15). Queued by 01.

## Follow-ups

<!-- Out-of-scope findings: one line each, with the session that found it. -->

- The section's answer is about 170 KB per kilometre of line (every cell spelled out); a
  compact encoding would help phones on mobile data. (08)
- IGME's IRYDA boreholes hold a water level and transmissivity per borehole: the section
  could show them beside the water-point depths once their fields are verified live. (08)

- CH Ebro's per-piezometer sheets end in 2021 and add 30 piezometers; worth importing only
  if the CHE publishes newer series. Other basins (Segura, Tajo, Miño-Sil) still publish no
  reachable series. (07b)
- Probability tiles: no domain is calibrated today (no dry wells); when one is, the national
  map can draw a probability layer beside the index for it. (07)
- The `piezometric_depth` criterion of the national model still has no grid: the imported
  levels could build one per body where piezometers are dense enough. (07)
- Karst is flagged from the permeability map's "CARBONATADAS" classes; IGME's karst map
  would be more precise. (07)
- The validation's background cells and wells use the 100 m national grid: the detailed
  map's candidates inherit their domain's result, not one measured at 5 m. (07)
- Every external endpoint, licence, price and legal rule in the plan was written from memory:
  session 01 verifies them before code depends on them. (00)
- Node 27's stable release is due in April 2027 (only alphas exist): move `.nvmrc` to 27
  then, in the maintenance session or the session running then (0011, 0016). (00, 02)
- Commercial use: no sale before the owner has tested the finished project on his land
  (decision 0015); whom to contact then is kept in `docs/commercial-use.md`. (01)
- Legal: the mining-safety rules for water boreholes and municipal licences were not read;
  session 09 reads them at the source before "drilling permits" leaves "not evaluated". (01)
- The old SIGPAC hosts (`sigpac.mapa.gob.es`, `wms.mapa.gob.es/sigpac`) did not answer
  from the cloud; the catalogue uses `sigpac-hubcloud.es`. (01)
- Google Maps dropped by the owner (decision 0020): no card, no key; PNOA and the IGN maps
  are the base maps. (02)
- Starlette 1.10 deprecates its TestClient over `httpx` in favour of `httpx2` (pydantic's
  fork); API tests use httpx's ASGI transport instead. The maintenance session decides
  whether the client moves to `httpx2`. (02)
- TypeScript 7.1 (late, due 2026-11-24): the first session that starts after it is stable
  moves the compiler and ESLint's parser to it and drops `typescript` 6.0 (decision 0019,
  owner ruling). (02)
- A parcel larger than the view at zoom 15 (big rustic ones) shows no cadastral layer until
  the owner zooms in; the hint says so. (02)
- The lithostratigraphic legend is a 3,648×4,423 image (800 KB) shown scaled in the panel
  with a link to full size; a better legend (by unit, from the tap) is still open: the
  detailed map (06) did not need one. (03, 06)
- The file cache never deletes an expired entry; with the tile proxy it grows with every
  view. Session 13 (deployment) adds a size cap or a sweep. (03)
- `/api/layers/*` answers anyone who reaches the server: fine on `localhost`; session 13
  puts the whole API behind the owner's access control before it is exposed. (03)
- SoilGrids gives no value on a tap; the detailed map (06) reads its clay from the WCS over
  the area and explains it per cell; sand is not a criterion of the model. (03, 06)
- Regional layers: eight qualify and are drawn (03b, 03ba); every surveyed cell has a
  verdict; the open ones wait on the VERIFY-LIVE items above. (03, 03b, 03ba)
- CH Duero zones its groundwater bodies in two horizons; only the general one (52 bodies,
  the whole district) is drawn. The upper horizon (12 bodies) needs its own layer and a tap
  that says which horizon answered. (03ba)
- Catalonia's 1:25,000 soil map and the Valencian GeoCV25 cover part of their regions:
  elsewhere a tap says the regional map has nothing there (soils) or GEODE answers
  (geology). (03ba)
- The Balearic, Basque and Catalan water-point inventories name private owners or their
  businesses: if a later session adds one, its tap must never show those fields. (03ba)
- The Navarra soil map covers only the municipalities surveyed so far (IDENA's index
  layer): elsewhere in Navarra the regional layer draws nothing, SoilGrids shows beneath,
  and a tap says the regional map has nothing there. (03b)
- A regional layer is drawn over the national one at the theme's opacity, so where the
  regional is partly transparent both show; a later session may hide the national layer
  inside the area once it is sure the regional one covers it. (03b)
- The file cache keeps each area's rounded boundary (up to ~1 MB) for 30 days: the size cap
  of session 13 covers it too. (03b)
- Ceuta and Melilla have no SIGPAC: a typed or drawn point there is placed by the
  territory's box alone (which holds a strip of Morocco beside Ceuta) and the card says it
  was not checked on land. A finer check needs an official boundary per click. (04)
- CartoCiudad candidate types not yet observed (place names, roads, kilometre points) are
  dropped until a session records their answers and maps them in `search.yaml`. (04)
- A drawn polygon is one ring without holes, at most 200 vertices; the detailed map takes
  areas up to its window limit (`parcel.yaml` `max_cells`). (04, 06)
- The session's areas are kept in sessionStorage; several large municipalities (up to
  ~150 KB each) can fill it, and then the list lives only until the tab reloads. (04)
- National model: structure and piezometric depth have no nationwide grid, so confidence
  never reaches "high"; a nationwide lineament or fault-density grid (IGME QAFI or MAGNA
  faults) could fill structure in a later session. (05)
- Wetness and drainage are computed per province with a 10 km buffer: a large river's
  catchment beyond it is not counted, so its floodplain's wetness index is lower than a
  whole-basin computation would give. (05)
- `data/cache` grows with every build's terrain windows (476 MB for two provinces): the size
  cap of session 13 covers it. (05)
- No elevation or relief layer is drawn: the IGN publishes its MDT as a map (WMS
  `EL.ElevationGridCoverage`, `servicios.idee.es/wms-inspire/mdt`); a hillshade layer could
  join the terrain layers in a later session. (05, owner)
- The detailed map reuses the 100 m wetness classes at 5 m, though the index depends on the
  DEM's cell (Sørensen and Seibert 2007); session 07's calibration should test them. (06)
- The detailed map's flow sees 2 km beyond the area: a channel fed from farther upstream may
  be missed near its edge, as on the national map (05). (06)
- Areas larger than the window limit (`parcel.yaml` `max_cells`, about 4 km across with the
  buffer) are refused: a municipality has only the national map. (06)
- MAGNA lithology (free text per sheet) could refine permeability at 1:50,000 once a
  classification of its legends exists; the detailed map uses the 1:200,000 classes. (06)
- `data/parcels` keeps every area's result and images; the size cap of session 13 covers it.
  The jobs' state lives in the server's memory: a restart forgets a failed or running job
  (a finished one is read from disk), and the page asks again. (06)

## Session log

<!-- Newest first. At most 15 lines per entry: landed, deferred, live findings, VERIFY-LIVE.
     When this section passes ~300 lines, move the oldest entries to docs/archive/. -->

### 08 — Interpretive geological cross-section (2026-11-26, version 0.11.0)

- Landed: `POST /api/section` and "Dibujar un corte": a straight line's MDT05 profile, the
  MAGNA units it crosses, contacts projected with the nearest bedding's apparent dip (or
  vertical, "not projected"), faults as block edges, public boreholes within 500 m with
  their depth, session 07's water table, and per-cell confidence with an "unknown" zone
  below the evidence (decision 0033); a bottom sheet draws it with the "interpretation"
  label, vertical exaggeration, legend and tap-to-explain.
- Live: none from the cloud (IGME 403); the device bridge was offline.
- Deferred: borehole lithology logs (not public), IRYDA levels, a compact answer.
- VERIFY-LIVE: magna-section (new).

### 07b — Basin piezometry spreadsheets (2026-11-26, version 0.10.0)

- Landed: `subphora piezometry import` also reads CH Júcar's F71 zip and CH Guadiana's
  monthly sheet from `data/piezometry/basins/` (decision 0032): their levels join the
  national piezometers by code, piezometers only they hold are added, body codes are
  normalised, and each piezometer and depth names its sources (openpyxl added).
- Live: the owner's files imported: 4,486 piezometers (142 new), levels to 2026-11;
  basin and national levels agree within decimetres (`water-authorities.md`).
- Deferred: CH Ebro (series end 2021). VERIFY-LIVE(piezometric-levels) closed for the two
  basins; piezometer-body-codes widened.

### 07 — Validation, depth to water and drilling cost (2026-11-26, version 0.9.0)

- Landed: per-body validation in every national build (IGME productive wells vs background
  cells, 10 km block bootstrap AUC, the water-points criterion left out; decision 0030),
  its skill in the confidence and a `model-skill` layer; calibration code, refused today
  (no dry wells); `subphora piezometry import` of the national database with mdbtools; the
  water table per body, depth with its range or "unknown" and why, karst flag, and the
  drilling cost in Decimal (decision 0031); all on candidates, summaries and explanations.
- Live: the owner's national database imported (4,342 of 4,658 piezometers, 1.24 M levels,
  2007-2024; `water-authorities.md`). Basin hosts and IGME answered 403 from the cloud.
- Deferred: basin spreadsheets (VERIFY-LIVE(piezometric-levels)); probability (dry-wells).
- VERIFY-LIVE: dry-wells, piezometer-body-codes, drilling-prices (new); piezometric-levels
  narrowed to the basin sheets; basin-terms (owner: private testing allowed).

### 06 — Parcel-scale detail, explanation and candidate spots (2026-11-25, version 0.8.0)

- Landed: `/api/parcel` jobs (queued, running, done, failed with the reason; cached per
  area; process pool); the 5 m grid in the area's UTM zone from MDT05, MAGNA faults (lineament
  density) and bedding dips, and the national inputs; structure split into `lineaments` and
  `bedding_dip` (decision 0029); the area's mean with its contributions; ranked candidates
  with "not evaluated" legal status (`domain/legal.py`); the panel, layer images, numbered
  markers, tap-to-explain and the comparison table.
- Live: four real areas (Daimiel, Huesca, Tierra de Campos, Santiago) computed in 9-19 s
  each, through `subphora serve` too; findings in `igme.md` and `ign-cnig.md`.
- Deferred: MDT02 (VERIFY-LIVE(cnig-mdt02-coverage)); depth on candidates (07).
- Prompt edits: 07 (reads the detailed map's candidates and decision 0029).

### 05 — National water-potential map v0 (2026-11-25, version 0.7.0)

- Landed: `subphora national build --region <province|region|box> | --all`; the model
  (`model.yaml`, `subphora.model`): nine criteria, renormalised index, five-part confidence;
  the 100 m grids (EPSG:3035, Canaries EPSG:5635), terrain derivatives; PMTiles for index,
  confidence, slope, drainage and wetness; `/api/national`, its tiles and tap-to-explain;
  the panel's legends ("índice", never "probabilidad"); decisions 0027, 0028.
- Live: ES-Z (sedimentary Ebro basin) and ES-GC (volcanic islands, Canaries grid) built
  from the real services; `make dev` shows both with tap-to-explain.
- Live findings: IGME refuses a page now and then under concurrent queries (retried); MDT
  sea is 0 and outside-extent windows answer 400; MITECO refuses unlisted CRSs
  (`docs/knowledge/nationwide-inputs.md`).
- VERIFY-LIVE: national-all (the owner), national-editions.
- Prompt edits: 06 (reads decisions 0027-0028; reuses `subphora.model`, `geo.terrain`).

### 04 — More ways to search (2026-11-25, version 0.6.0)

- Landed: one search box (`GET /api/search`) that reads cadastral and SIGPAC references,
  addresses and municipalities (CartoCiudad), and coordinates in degrees, DMS or UTM, with
  an explicit choice when a text reads several ways; drawn points and polygons; every
  result is one `AreaOfInterest` (`/api/aoi/…`); the session's areas listed in the browser
  to switch between; `/api/parcels` folded into `/api/aoi/cadastral`; decision 0026.
- Live (real services, `make dev`): each search type and a drawn polygon land on the map;
  zone-less UTM keeps only the zone on land; Lisbon is refused by the SIGPAC land check.
- Live findings: SIGPAC's point query covers all of Spain but Ceuta and Melilla;
  CartoCiudad's `find` needs the candidate's id verbatim and answers 204 when unknown; its
  reverse geocoder and the IGN's administrative-units WFS cannot check a point per click.
- Prompt edits: 06 (reads the area of interest).
- No VERIFY-LIVE items: every new behaviour was checked against the live services.

### 03ba — The regional layers still waiting for evidence (2026-11-24, version 0.5.0)

- Landed: a verdict for every E cell (`docs/knowledge/regional-layers.md`); national
  editions from the publishers' records (GEODE per zone 2007-2014, IGME permeability and
  lithostratigraphy 2009); five new regional layers: Catalonia soils 1:25,000 (2025),
  Navarra geology 1:25,000 (2011), Valencian geology 1:25,000 (2024), CH Guadiana's
  perimeters closed to new abstractions and CH Duero's groundwater zoning (plans 2022-2027);
  areas ES-VC, ES020, ES040; decision 0025 (`national_edition`, `max_zoom`).
- Verdicts: Balearic geology, rivers O and DPH K; Navarra rivers and hydrogeological
  aspects O; Basque rivers O; springs, water points and piezometers everywhere V.
- Live (real API): each new layer answers inside its area with its scale and date, and
  where it maps nothing the national layer answers.
- VERIFY-LIVE: national-network-editions, regional-editions, cantabria-geology-editions;
  regional-hosts-unreached stays open.

### 03b — Regional detail over the national layers (2026-11-24, version 0.4.0)

- Landed: the survey of every community, Ceuta, Melilla and basin authority, with a
  verdict per theme (`docs/knowledge/regional-layers.md`); the rule as data and checked when
  the settings load (`regional.yaml`); official boundaries from the IGN and MITECO on one
  grid (`/api/areas/{id}`); regional tiles clipped in the browser; taps regional first with
  the national fallback, naming the source, scale and date; the GetMap proxy and GML parser
  back for REDIAM; decision 0024. Qualify: Navarra soils 1:25,000, Catalonia
  hydrogeology 1:25,000, Andalusian bodies under preventive control.
- Deferred: the services with evidence missing (verdict E) to 03ba.
- Live (`make dev`): one tap per community, Ceuta and Melilla on soils, hydrogeology and
  bodies at risk; the regional layer answers in Navarra, Catalonia and Dalías, the national
  one elsewhere; ICGC clipped at the Aragón border.
- VERIFY-LIVE: regional-hosts-unreached, national-editions.

### 03 — Owner ruling: regional detail, national baseline (2026-11-24, version 0.3.2)

- Landed: decision 0023 (a regional service is used where it qualifies, the national one
  stays as baseline and fallback); prompt `03b-regional-detail.md`, next before 04;
  MASTER_PLAN §3 reworded.

### 03 — Owner ruling: the same product everywhere (2026-11-24, version 0.3.1)

- Landed: decision 0022 (no regional layers, every basin's rules, no region in prompts);
  the two REDIAM layers out of the map, GEODE in; the proxy draws only ArcGIS exports and
  the MapServer GML parser is gone with REDIAM; MASTER_PLAN §3 and §4.5 reworded.
- Live: a tap at 17 points, one per region, Canaries, Balearics and Melilla included: every
  national layer answers everywhere, except MAGNA lithology in parts of Tenerife (GEODE
  covers it) and groundwater bodies where no body is mapped (correct).
- Prompt edits: 09 (rules for every district and regional water law; no region named).

### 03 — Official water and geology layers (2026-11-24, version 0.3.0)

- Landed: the layer catalogue in `map.yaml` (3 base maps, the cadastre, 17 water, geology
  and soil layers) served by `/api/map`; `/api/layers/{id}/tiles` (proxy for REDIAM and the
  lithostratigraphic map, via its ArcGIS export) and `/api/layers/{id}/info` (GetFeatureInfo
  in GeoJSON, ArcGIS XML or MapServer GML, field allowlist); the panel with toggles,
  opacity, legends, zoom and coverage notes, sources; the base-map switch; tap results;
  5 catalogue entries (MITECO status WMS, rivers, springs; IGME water points; SoilGrids
  WMS); decision 0021.
- Live (`make dev`): every layer drawn and tapped over real services; MAGNA dip read by tap.
  `DPH_Estimado` draws "Zona de Policía" polygons where the SNCZI has studied the river (the
  prompt said no service draws it); SoilGrids' GetFeatureInfo answers no value; MAGNA's
  legends are symbol codes.
- Prompt edits: 04 (a map click already belongs to the tap; drawing must take it).
- VERIFY-LIVE: none new.

### 02 — Owner rulings: TypeScript 7.1, no Google Maps (2026-11-24, version 0.2.1)

- Landed: decisions 0019 (TypeScript 7.1 for ESLint once stable, no TypeScript 6) and 0020
  (no Google Maps; supersedes 0005 and 0012); `google-map-tiles` removed from the catalogue;
  MASTER_PLAN, AGENTS.md hard rule 4, the PR template and prompts 03 and 11 reworded.
- Prompt edits: 03 (an IGN base-map switch instead of Google), 11 (no Google exclusion).

### 02 — First end-to-end slice: a cadastral reference on the map (2026-11-24, version 0.2.0)

- Landed: `subphora serve` (FastAPI) with `GET /api/parcels/{reference}` and `GET /api/map`;
  `countries/es/` (reference format, control letters checked on 7 real references, provinces
  to ISO 3166-2, CRS by location), `geo/`, `store/` (file cache), `services/`, `api/` under
  one layers contract; `web/` (Vite 8, React 19.3, MapLibre 6.19, TypeScript 7) with PNOA,
  Catastro as one image per view, the outline, Spanish catalogue; `make dev`; web checks in
  `make check` and CI; decisions 0016 (Node 26, TypeScript 7/6), 0017 (CI minutes), 0018.
- Live: Mérida, Santiago, Atocha and Tinajo (16 holes, EPSG:4083) found and drawn from
  `make dev`; Navarra refused before any call; Node 27 is alpha only; MapLibre 6 needs its
  worker URL set under Vite; its image sources take no attribution.
- Prompt edit: 03 (extend `map.yaml` and `/api/map`). AGENTS.md and MASTER_PLAN §3: Node 26.

### 01 — All basin authorities and regional water agencies (2026-11-24, version 0.1.2)

- Landed: `docs/knowledge/water-authorities.md` (all 25 districts, who manages each, what it
  publishes); 9 catalogue entries (Guadiana, Duero, Ebro, Júcar, URA, ICGC, Balearics,
  IDENA soils); probes send capabilities and samples without `Origin` and check CORS apart.
- Live: `sources check` 111 ok, 0 failed, 2 not checked. Level series exist: a national
  MITECO database (hand download, human-only form) and basin spreadsheets (Guadiana, Ebro,
  Júcar); CH Júcar's firewall rejects any request carrying `Origin`; Navarra has a 1:25,000
  soil map. Not reached: CHG, Segura, Tajo, Miño-Sil, Augas de Galicia, Canary councils.
- Prompt edit: 07 (where the levels come from). Commercial-use rows added.
- VERIFY-LIVE: piezometric-levels (rewritten), basin-terms, water-authorities-unreached.

### 01 — Owner ruling: Spain-wide product, country modules (2026-11-24, version 0.1.1)

- Landed: decision 0014; catalogue `coverage`/`coverage_excludes` in ISO 3166 codes, shown
  by `sources list`; probe samples and fixtures moved to public places across Spain; test
  area removed from MASTER_PLAN, knowledge files and prompts; `countries/es/` planned for
  session 02 (prompts 02, 04, 05, 09, 11, 16 edited for it).
- Live: `sources check` 89 ok, 0 failed, 2 not checked; Catastro has no reference in Navarra
  or the Basque Country (error 16); its WFS answers EPSG:4083 requests in EPSG:4326.
- Then (0015): no sale before the owner tests the finished project on his land; organisations
  to contact afterwards in `docs/commercial-use.md`; the brief reworded without places.

### 01 — Verify data sources, terms and legal rules (2026-11-24, version 0.1.0)

- Landed: `config/defaults/sources.yaml` (32 services, 15 hosts) with its schema;
  `src/subphora/sources/` (catalogue-only async client, per-host limits, retries, probes);
  `subphora sources check|list`; 12 knowledge files incl. `legal-groundwater.md`;
  decisions 0012 (Google Map Tiles API) and 0013 (SoilGrids).
- Live: `sources check` 89 ok, 0 failed, 2 not checked (keys) from the cloud. Catastro
  forbids tiled WMS requests, rejects curl's User-Agent and resets ~1 in 3 connections;
  REDIAM lacks CORS; IGME's 1:200,000 lithostratigraphic WMS lacks EPSG:3857; MAGNA dip is
  digital (251,654 measurements); IGN WCS serves MDT05/MDT25, not MDT02; in the Andalusian
  Mediterranean plan, 54.2 wells in bodies under preventive control need authorisation.
- Prompt edits (facts only): 02 (no tile proxy; Catastro as one untiled image), 03 (proxy
  for REDIAM and the lithostratigraphic map, soil per 0013, no zona de policía service),
  06 (MDT02 fallback), 07 (piezometric levels first), 11 (no cadastral tiles in packs);
  MASTER_PLAN §3 and §4.7 likewise.
- VERIFY-LIVE: chg-ide, piezometric-levels, basin-terms, water-authorities-unreached,
  igme-water-levels, igme-geode-download,
  cnig-mdt02-coverage, egms-terms, keyed-services.

### 00 — Owner ruling after the plan (2026-11-24, version 0.0.0)

- Landed: decision 0011 (languages kept, newest versions with Node 27, any spending needs
  approval, copyright notice in every file with a test, subsurface layers); new session 08
  (interpretive cross-section), sessions 08–15 renumbered 09–16; terrain, dip and soil layers
  added to sessions 01, 03, 05 and 06; the project description sharpened.
- Live findings: Python 3.15 binary wheels exist for rasterio, pyproj, shapely, geopandas,
  numpy, scipy, pyGIMLi and WeasyPrint `(uv pip compile --only-binary, 2026-11-24)`.

### 00 — Plan the project (2026-11-24, version 0.0.0)

- Landed: the template renamed to `subphora`; the owner's brief saved as `docs/BRIEF.md`;
  `MASTER_PLAN.md` filled; six project hard rules in AGENTS.md; decisions 0003–0010; prompts
  for sessions 01–15; proprietary licence (0009).
- Owner rulings (0003): model before legal filter; all of Spain at a coarse scale plus parcel
  detail; any cheap host; no LLM; hardware deferred to session 16; deployment after the report.
- Live findings: none recorded as knowledge; Google's Map Tiles policy appears to allow
  third-party renderers and forbids offline use, and OhmPi is GPL-3.0 — both for session 01
  (or 15) to confirm.
- VERIFY-LIVE: none new.

Copyright (c) 2026 Almoon-D. All rights reserved.
