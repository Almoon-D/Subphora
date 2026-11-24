# Roadmap

## What runs next

| Session | Prompt | Model and effort | Status |
|---|---|---|---|
| 00 | `docs/sessions/done/00-plan.md` | Opus 5.5 | done |
| 01 | `docs/sessions/done/01-verify-sources.md` | Opus 5.5, high | done |
| 02 | `docs/sessions/02-first-slice.md` | Opus 5.5, high | next |
| 03 | `docs/sessions/03-official-layers.md` | Opus 5.5, high | planned |
| 04 | `docs/sessions/04-search.md` | Opus 5.5, medium | planned |
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
- VERIFY-LIVE(keyed-services): `aemet-opendata` and `google-map-tiles` are "not checked"
  until the owner's keys exist (sessions 15 and 03). Queued by 01.

## Follow-ups

<!-- Out-of-scope findings: one line each, with the session that found it. -->

- Every external endpoint, licence, price and legal rule in the plan was written from memory:
  session 01 verifies them before code depends on them. (00)
- Node 27 reaches end of life in mid-2027: move to Node 28 when it is released (April 2027),
  in the maintenance session or the session running then (0011). (00)
- Commercial use: no sale before the owner has tested the finished project on his land
  (decision 0015); whom to contact then is kept in `docs/commercial-use.md`. (01)
- Legal: the mining-safety rules for water boreholes and municipal licences were not read;
  session 09 reads them at the source before "drilling permits" leaves "not evaluated". (01)
- The old SIGPAC hosts (`sigpac.mapa.gob.es`, `wms.mapa.gob.es/sigpac`) did not answer
  from the cloud; the catalogue uses `sigpac-hubcloud.es`. (01)
- The owner should add the `main` ruleset of `docs/GITHUB_SETTINGS.md` → public projects:
  `main` is unprotected and a commit reached it without a pull request. (00)

## Session log

<!-- Newest first. At most 15 lines per entry: landed, deferred, live findings, VERIFY-LIVE.
     When this section passes ~300 lines, move the oldest entries to docs/archive/. -->

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
