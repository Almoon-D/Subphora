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
| 04 | `docs/sessions/04-search.md` | Opus 5.5, medium | next |
| 05 | `docs/sessions/05-national-map.md` | Opus 5.5, high | planned |
| 06 | `docs/sessions/06-parcel-detail.md` | Opus 5.5, high | planned |
| 07 | `docs/sessions/07-validation-depth-cost.md` | Opus 5.5, high | planned |
| 08 | `docs/sessions/08-cross-section.md` | Opus 5.5, high | planned |
| 09 | `docs/sessions/09-legal-filter.md` | Opus 5.5, high | planned |
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

- VERIFY-LIVE(dependabot-merge): the first green minor or patch Dependabot PR merges by
  itself, including a github-actions one (it changes `.github/workflows/`, which the
  default token may not be allowed to merge). If that one fails, the maintenance session
  merges it by hand and this line records the outcome. Queued by the template.
- VERIFY-LIVE(chg-ide): every path on `idechg.chguadalquivir.es` redirected to an error page
  from the cloud session; find the CHG's OGC endpoints (MITECO's national services cover
  the bodies meanwhile). Queued by 01; unblocked by a browser look at the CHG geoportal.
- VERIFY-LIVE(piezometric-levels): open the national piezometry database (a hand download,
  behind a human-only form) and the basin spreadsheets (Guadiana, Ebro, Júcar) and record
  their columns and dates (`docs/knowledge/water-authorities.md`). Queued by 01; the owner
  downloads the national file before session 07, which needs it.
- VERIFY-LIVE(basin-terms): the licence of the basin spreadsheets and downloads (Guadiana,
  Ebro, Júcar) and of the Balearic service, not stated on their pages. Queued by 01; session 07.
- VERIFY-LIVE(water-authorities-unreached): CH Guadalquivir, Segura, Tajo, Miño-Sil, Augas de
  Galicia and the Canary island councils published no reachable data service from the cloud;
  find their endpoints from a browser. Queued by 01; session 07 (levels) and 09 (rules).
- VERIFY-LIVE(igme-water-levels): levels per IGME water point exist only in the BDAguas web
  app, with no documented API; ask IGME or find a download. Queued by 01; session 07.
- VERIFY-LIVE(igme-geode-download): the GEODE vector download route and size. Queued by 01;
  session 05.
- VERIFY-LIVE(cnig-mdt02-coverage): MDT02 coverage and download route (the CNIG download
  centre is a JavaScript app). Queued by 01; session 06.
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
- VERIFY-LIVE(keyed-services): `aemet-opendata` is "not checked"
  until the owner's key exists (session 15). Queued by 01.

## Follow-ups

<!-- Out-of-scope findings: one line each, with the session that found it. -->

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
  with a link to full size; a better legend (by unit, from the tap) can come with the
  parcel view (session 06). (03)
- The file cache never deletes an expired entry; with the tile proxy it grows with every
  view. Session 13 (deployment) adds a size cap or a sweep. (03)
- `/api/layers/*` answers anyone who reaches the server: fine on `localhost`; session 13
  puts the whole API behind the owner's access control before it is exposed. (03)
- SoilGrids gives no value on a tap; the parcel view (session 06) reads clay and sand from
  its WCS at the parcel, everywhere in Spain alike. (03)
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
- The owner should add the `main` ruleset of `docs/GITHUB_SETTINGS.md` → public projects:
  `main` is unprotected and a commit reached it without a pull request. (00)

## Session log

<!-- Newest first. At most 15 lines per entry: landed, deferred, live findings, VERIFY-LIVE.
     When this section passes ~300 lines, move the oldest entries to docs/archive/. -->

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
