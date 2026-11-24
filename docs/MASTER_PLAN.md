# Master plan

The design. Sessions build it; they do not relitigate it. A change of design is an owner
decision, recorded in `docs/decisions/` and then reflected here. The owner's original request
is `docs/BRIEF.md`; where this plan differs from it, an owner ruling in `docs/decisions/`
says why (0003).

## 1. Goal

Subphora estimates where groundwater is most likely to be found, anywhere in Spain, from
public data and field evidence, and says how sure it is. It is a product for landowners,
farmers and the people who advise them, anywhere in Spain, and is built so that other
countries can be added later (decision 0014). Its first users are the owner and a few
non-technical people of a family farming company (dry farmland, olive groves and almond
orchards); their land is the test area, which lives in private configuration and never in
the repository. Nothing in the code or the design favours one area of Spain. Nothing is
sold before the owner has tested the finished project on his land; the permissions a sale
would need are tracked in `docs/commercial-use.md` (decision 0015).

For a location (a cadastral reference, a SIGPAC reference, an address, a municipality,
coordinates, or a point or polygon drawn on the map) the app shows:

1. **Where:** a water-potential map of all of Spain at a coarse scale, refined to a detailed
   map around a selected parcel, with ranked candidate spots.
2. **How deep:** the estimated depth to water where piezometric data allows it, with its
   uncertainty and a drilling-cost range.
3. **How sure:** a confidence layer next to every score, the contribution of every input,
   the inputs that are missing, and how well the model performs against known wells in that
   area, including an explicit "no better than chance here" when that is the case.
4. **Whether drilling is allowed:** the competent water authority, the groundwater body and
   its legal status, and the main rules that apply, as plain-language guidance with the
   official source and its date. It is never legal advice.
5. **What lies below:** terrain layers (slope, drainage, wetness), the dip of the rock
   layers where the geological map records it, the soil map, and an interpretive geological
   cross-section along a line the user draws, always marked as interpretation.
6. **In the field:** the user's live GPS position on a detailed map, guidance to a candidate
   spot, and observations (notes, photos, voice memos, track) recorded without coverage and
   synced later.

"Done" for version 1 (after session 13): the owner types a cadastral reference, sees the
parcel with the official layers and our water-potential map, opens the per-parcel report,
walks to the best candidate spot with a phone, and logs a field observation there.
After version 1: a well registry whose results update the map (14), satellite and climate
layers (15), and the hardware plan (16).

The product never claims to see water. It estimates a likelihood and shows what would
reduce the uncertainty.

## 2. Non-goals

- No dowsing, no "water detector" claims, and no method without a physical basis (phone
  magnetometer apps, commercial "natural electric field" water detectors). The app never
  presents an estimate as a certainty.
- No cadastral owner (titular) data: only the non-protected cadastral data is fetched or shown.
- No legal advice: legal output is guidance with its source, date and a disclaimer.
- No LLM or other generative AI in the product. The model is a transparent weighted overlay,
  later calibrated statistically (decision 0006). Field data is never sent to an LLM.
- No native mobile apps: one progressive web app for PC, Android and iPhone (0004).
- No scraping and no use of a service against its terms. No Google Maps (decision 0020).
  Data whose terms forbid storing it is never cached or used offline.
- No paid service, paid API or recurring cost without the owner's approval in a decision.
- No unprompted recommendations to hire a hydrogeologist or other professional. The
  professional export pack (session 12) exists for when the owner chooses to use one.
- No hardware design or purchase before session 16. Until then, the data model only stays
  open to a future instrument (§4.8).

## 3. Constraints

**Budget.** Public open data first, free tiers, zero recurring spend by default. Any paid service or API, however cheap, needs the owner's approval in a decision first
(0011).

**Data sources** (each verified live in session 01, recorded in `docs/knowledge/`):
Catastro (WMS; INSPIRE WFS for parcel geometry), SIGPAC (FEGA), IGN/CNIG (PNOA orthophoto,
MDT02/MDT05/MDT25, CartoCiudad geocoder), IGME (MAGNA 1:50,000 and the continuous GEODE, 1:200,000 lithostratigraphic
and permeability map, hydrogeological map, water-point database), MITECO and the basin
authorities (groundwater bodies and status, piezometric network, rivers, public water domain,
zona de policía, basin plans), the regional water agencies of the intra-community basins,
Copernicus (Sentinel-2, EGMS), AEMET; the structural data of the geological maps
(bedding dip and strike), public borehole logs with lithology, and a soil map (SoilGrids 2.0,
decision 0013). The catalogue of every host, its terms and limits is
`config/defaults/sources.yaml`. Foral cadastres (País Vasco, Navarra) are not
supported yet (decision 0010), they will be implemented once subphora is finished.

**Jurisdiction.** All of Spain for maps, search, the model and the legal filter, with the
same code and the same quality everywhere (decision 0022): every map layer covers all of
Spain, and the legal rules are loaded for every river-basin district and every regional
water law. Where field tests happen does not shape the product; no session prompt names a
region. A district whose rules could not be read says "rules not loaded", with the reason.

**Areas and countries** (decision 0014). An area is an ISO 3166 code: country (ES) > region,
the autonomous community (ES-CT) > province (ES-B). Water management is a parallel
hierarchy, because basins cross regions: river-basin district (ES050) > groundwater body.
Every catalogued service records its coverage in these codes. Everything specific to Spain
(reference formats, cadastre and SIGPAC rules, CRS choice, territories not supported, legal
rules) lives in a country module, so another country is a new module and new data, not a
change to the model, the API or the front end.

**Coordinates.** ETRS89 / UTM zones 29, 30 and 31 (EPSG:25829, 25830, 25831) on the mainland
and Balearics, chosen by the parcel's location; REGCAN95 / UTM 28N (EPSG:4083) in the
Canaries; Web Mercator (EPSG:3857) only for display tiles; the national grid in ETRS89-LAEA
(EPSG:3035), with a separate Canaries grid. `pyproj` does every transformation; no
hand-written coordinate maths.

**Licences and politeness.** Every layer and report carries the attribution its licence
requires (Catastro, IGN/CNIG, IGME, MITECO, Copernicus). Every external host has a
rate limit and cache lifetime in `config/`; the HTTP client sends a generic `subphora/<version>`
User-Agent and no personal contact data.

**Privacy.** The owner's test area, parcels, wells, field notes, photos, voice memos and
tracks are private: stored only on the owner's devices and server, never committed (`data/`
is git-ignored), never in fixtures (tests use public or synthetic parcels spread across
Spain), never sent to an LLM.

**Runtime.** Each part in the language best suited to it: Python for the backend and data
processing (its geospatial and geophysics libraries have no equal), TypeScript for the front
end. Every toolchain and dependency at its newest release, even before the ecosystem has
fully caught up (0011): Python 3.15 and the newest stable Node (26 until Node 27's stable
release in April 2027, decision 0016), each pinned in one file (`.python-version`, `.nvmrc`)
and covered by Dependabot. Network I/O is
asyncio (`httpx`); CPU-bound raster work runs in a process pool, never in the event loop.
Money is `Decimal`; datetimes are timezone-aware UTC, shown in `Europe/Madrid` (or
`Atlantic/Canary`) through `zoneinfo`.

**Copyright.** Every file that can hold a comment carries the notice
`Copyright (c) 2026 Almoon-D. All rights reserved.` as its first or last line; files that
cannot (JSON, lock files, `.python-version`, binaries, empty markers) and third-party data
(fixtures) are exempt by an explicit list. A test enforces it (0011).

**Interface.** Spanish, every string translatable from day one. Field mode has large controls,
high contrast for sunlight, and works with gloves.

**Hosting.** Any cheap Linux machine: a free tier (such as Oracle Cloud Always Free), a cheap
paid server, or a computer the owner buys. The app is packaged to run on any of them; the
owner picks in session 13 (decision 0007). Until then it runs locally (`make dev`).

## 4. Architecture

```
 browser / phone (PWA)                       server (owner's host)                 public services
 ┌──────────────────────────┐   HTTPS   ┌──────────────────────────────┐  HTTPS  ┌───────────────┐
 │ web/  React + TypeScript │ ────────► │ api/  FastAPI                │ ──────► │ Catastro, IGN │
 │ MapLibre GL JS map       │ ◄──────── │ services/ orchestration      │ ◄────── │ IGME, MITECO  │
 │ IndexedDB: field data,   │           │ model/  legal/  geo/         │         │ basins, FEGA  │
 │   offline packs, outbox  │           │ sources/ polite cached client│         │ Copernicus    │
 │ service worker (offline) │           │ store/  SQLite + file cache  │         │ AEMET         │
 └──────────────────────────┘           └──────────────────────────────┘         └───────────────┘
 batch: `subphora national build` → national potential grid → raster tiles (PMTiles) served by api
```

### 4.1 Front end (`web/`)

A progressive web app (Vite, React, TypeScript, MapLibre GL JS), installable on Android and
iPhone (decision 0004). Two modes:

- **Research mode:** search (cadastral, SIGPAC, address, municipality, coordinates, drawn
  point or polygon); switchable layers with opacity and legend; the national and parcel
  potential maps; terrain, dip and soil layers; tap-to-explain; ranked candidate spots;
  parcel comparison; the geological cross-section; report export.
- **Field mode:** live position with accuracy circle and heading; distance and direction to
  a chosen spot; observations (note, photo, voice memo) and track; downloaded offline packs.
  IndexedDB is the device's source of truth: every observation is written there before the
  UI confirms it, and an outbox syncs it later with an idempotency key (§4.7).

Base maps: PNOA orthophoto (default) and IGN maps; no Google maps (decision 0020). Official layers come from their WMS/WMTS services directly,
or through the server's caching proxy where a service lacks CORS or EPSG:3857 (session 01
records which); a tap on the map asks the server what the switched-on layers hold there,
and it shows only the fields the layer catalogue allows (decision 0021).

### 4.2 Server (`src/subphora/`)

A FastAPI application (`subphora serve`) and a CLI (`subphora …`), in layers:

| Package | Role | May import |
|---|---|---|
| `domain/` | frozen models: references, estimates, explanations, legal status, observations | nothing of ours |
| `config/` | settings schema and loader | `domain` |
| `sources/` | one async client per external service; catalogue, rate limits, cache, attribution | `domain`, `config` |
| `countries/` | one module per country (`es/` first): area codes, reference formats, CRS rules, territories not supported | `domain`, `config` |
| `geo/` | CRS choice, reprojection, clipping, raster and vector operations, terrain derivatives | `domain`, `config` |
| `model/` | criteria, scoring, confidence, explanation, candidates, validation, calibration, depth, cost | `domain`, `config`, `geo` |
| `legal/` | authority lookup and rule evaluation from rules held as data | `domain`, `config` |
| `store/` | SQLite for private data and job state; file cache for rasters and tiles | `domain`, `config` |
| `services/` | use cases: fetch inputs, run the model, assemble a parcel analysis | all of the above |
| `report/` | per-parcel PDF and professional export pack | `domain`, `config`, `services` |
| `api/`, `__main__` | HTTP and CLI boundaries | everything |

Each boundary is an import-linter contract added by the session that creates the package.
`model/` and `legal/` never import `sources/`: they receive data, so they are testable
without network.

### 4.3 The water-potential model (decision 0006)

**Two scales.**
1. **National:** a grid of all of Spain (default 100 m, in `config/`) from nationwide inputs.
   It is precomputed by `subphora national build [--region …]`, published as raster tiles,
   and is what the user sees when the app opens.
2. **Parcel:** computed on demand around a selected parcel (parcel plus buffer, default 5 m,
   with MDT02 where available), from detailed inputs, and cached per parcel.

**Criteria.** Each input becomes a 0–1 suitability through a lookup table or function in
`config/`, with the source of every weight and class recorded:
lithology and permeability, structure (faults, lineament density, and the dip of permeable
layers where it is recorded), terrain (slope, topographic wetness index, drainage proximity),
soil infiltration capacity, groundwater-body status, distance to and yield of known
water points, piezometric depth, and later the late-summer vegetation anomaly (15).

**Score.** A weighted linear combination over the inputs available at that cell, with the
weights renormalised over what is present. Until it is calibrated (session 07) the score is a
**relative potential index**, labelled as such, never a probability.

**Confidence (0–1, with labels low/medium/high at thresholds in `config/`).** Combines the
share of total weight whose inputs are present, how well each input's resolution fits the
cell, the age of each input, the distance to the nearest validation evidence, and the
model's measured skill in that hydrogeological domain. Missing data lowers confidence; it is
never interpolated silently.

**Explanation.** For any cell: the score, each input's value and contribution, each input's
source, date and resolution, the missing inputs, and the confidence breakdown.

**Candidates.** The top cells of a parcel by score among those above a minimum confidence,
separated by a minimum distance (both in `config/`), each with score, confidence, estimated
depth and legal status ("not evaluated" until session 09).

**Validation and calibration (07).** Against public water points (productive where yield is
recorded; dry where a source says so) with spatial block cross-validation: AUC with a
bootstrap interval per hydrogeological domain. Where the interval's lower bound is not above
0.5 the app says "no better than chance here". Where enough labelled wells exist (threshold
in `config/`), a calibration turns the index into a probability with an interval; elsewhere it
stays an index.

**Depth and cost (07).** Water-table elevation is interpolated only within one groundwater
body from piezometric levels, with uncertainty growing with distance and "unknown" beyond a
maximum distance (in `config/`). Depth = ground elevation (LiDAR) − water-table elevation,
with propagated uncertainty, flagged as unreliable in karst. Drilling cost = depth range ×
cost per metre plus fixed costs (`Decimal`, in `config/` with source and date).

**Learning (14).** The owner's well results (depth, flow, dry or productive) and field
observations update the probabilities locally: a Bayesian update of the calibrated prior with
a spatially decaying likelihood whose range is in `config/`. A machine-learning model is
considered only once the labelled wells pass a threshold in `config/`, and only if it beats the
transparent model under the same validation.

### 4.4 Geological cross-section (session 08)

Along a line the user draws, the app draws an interpretive section of the ground: surface
elevation from LiDAR, the geological units cut by the line, their dips projected downward,
public borehole logs near the line, and the water-table estimate of §4.3 where it exists.
It is labelled "interpretation" throughout, with confidence falling with depth and with the
distance to the nearest borehole; below the deepest evidence the section is drawn as
unknown, never extrapolated without a mark. No national 3D model of the subsurface exists,
so this view never pretends to be one.

### 4.5 Legal filter (session 09)

From the location: the river-basin district and competent authority (a Confederación
Hidrográfica, or the regional water agency of an intra-community basin), the groundwater
body and its legal status, and the rules that apply: the article 54.2 regime of the Water
Law (up to 7,000 m³/year) and when it needs authorisation, regional water laws, distances to
existing wells and to the public water domain, the basin plan's limits on new abstractions,
and the drilling permits. Rules are data in `config/legal/`, each with the official source
(BOE, the regional official gazette, the basin plan), its date and the date it was checked;
the engine evaluates them and returns "probably not allowed", "conditions apply", "no blocking
rule found" or "rules not loaded for this basin". Every output carries the disclaimer.

### 4.6 Reports (session 12)

`report/` renders a per-parcel PDF (WeasyPrint) that a hydrogeologist or water authority can
read: maps, candidates, scores with confidence, explanations, validation skill, depth and
cost ranges, legal guidance, every source with its date and attribution, and the
limitations. The professional export pack adds a ZIP with the layers (GeoPackage, COG) and
tables (CSV).

### 4.7 Field mode and offline

- **Positioning:** the browser Geolocation API with its reported accuracy circle. A position
  only counts as "at the spot" within a distance in `config/`, and never if the accuracy is
  worse than that distance.
- **Observations:** append-only records (UUIDv7 ids, UTC time, position with accuracy,
  kind, payload and media as IndexedDB blobs). An edit is a new version, never an overwrite.
  The server accepts the same id twice as one record, so a retried sync never duplicates or
  loses data.
- **Offline packs (11):** for the selected parcels and a buffer, the PNOA tiles, our
  potential and confidence layers, and the parcel geometry (Catastro's terms forbid tiled
  requests and massive downloads, so no cadastral tiles), at zooms in `config/`,
   stored by the service worker with persistent storage requested.
- **Data safety:** a manual export of all unsynced data to a file, and a visible count of
  unsynced records.

### 4.8 Room for hardware

Hardware is not designed before session 16 (decision 0008). The design keeps two things open
for it: observations have a `kind`, so a future instrument reading or survey line is a new
kind rather than a new store; and a measurement that injects current is gated by the safety
checklist of hard rule 3, which the session that first controls or imports instrument data
enforces in code.

### 4.9 Deployment (session 13)

Docker Compose with the API and a Caddy reverse proxy (HTTPS, static PWA), on any Linux host
(x86-64 or ARM64). A login for the few users (hashed passwords, secure cookies), nightly
backups of `data/` to a place the owner chooses, and secrets only from the environment
(decision 0007).

## 5. Layout

```
src/subphora/
  domain/     frozen models, imports nothing else of ours
  config/     settings schema and loader
  sources/    external-service clients and the source catalogue          (01)
  countries/  country modules: es/ (references, areas, CRS rules)        (02)
  geo/        CRS, reprojection, clipping, terrain derivatives           (02, 05)
  model/      water-potential model, validation, depth, cost, section    (05, 07, 08)
  legal/      legal filter                                               (09)
  store/      SQLite for private data, file cache                        (02)
  services/   use cases                                                  (02)
  report/     PDF and export pack                                        (12)
  api/        FastAPI app                                                (02)
web/          the PWA: Vite, React, TypeScript, MapLibre GL JS           (02)
config/       defaults/, owner.yaml, legal/ (rules as data)              (09)
data/         private data and caches, git-ignored                       (02)
deploy/       Docker Compose and Caddy                                   (13)
```

The number is the session that creates each package.

## 6. Build path

Each session ends in something the owner can see or run. The table with status is in
`docs/ROADMAP.md`; each prompt is in `docs/sessions/`.

| # | Session | The owner sees |
|---|---|---|
| 01 | Verify data sources, terms and legal rules | `subphora sources check` prints the status of every service; a knowledge file per source |
| 02 | First end-to-end slice | `make dev`: type a cadastral reference, see the parcel on PNOA with the cadastral layer |
| 03 | Official layers | Water, geology (with dip symbols) and soil layers, IGN base maps, opacity and legend |
| 04 | More ways to search | SIGPAC, coordinates, municipality, address, drawn point or polygon |
| 05 | National potential map v0 | All of Spain coloured by potential index, with its confidence layer and the slope, drainage and wetness layers |
| 06 | Parcel detail | High-resolution parcel map, tap-to-explain, ranked candidates, parcel comparison |
| 07 | Validation, depth and cost | Model skill against known wells per area; estimated depth and drilling-cost range |
| 08 | Geological cross-section | Draw a line, see an interpretive section of the ground below it, marked as interpretation |
| 09 | Legal filter | Authority, groundwater-body status, key rules and the "probably cannot drill" flag |
| 10 | Field mode | GPS position, guidance to a spot, observations and track without coverage, then sync |
| 11 | Offline map packs | Parcels downloaded for use with no coverage |
| 12 | Report and professional pack | The per-parcel PDF and the ZIP |
| 13 | Deployment | The app on the owner's chosen host with login, installed on a phone: version 1 |
| 14 | Well registry and learning | Logged wells and outcomes update the map |
| 15 | Satellite and climate layers | Late-summer vegetation anomaly (irrigation masked), ground motion, rainfall |
| 16 | Hardware planning | Options compared with prices; the owner decides |

Copyright (c) 2026 Almoon-D. All rights reserved.
