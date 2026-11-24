# Session 01 — Verify data sources, terms and legal rules

Model and effort: Opus 5.5, high.

## Goal

Every external service and legal rule the plan names has been checked live, its observed
behaviour is recorded in `docs/knowledge/`, and the owner can run one command that reports
the status of every service. No later session builds on an endpoint, licence or rule
written from memory.

## Read

- `docs/MASTER_PLAN.md` §§ 1–4 (§3 Data sources, §4.2 the `sources/` layer, §4.4 legal).
- `docs/decisions/` 0003–0006 and 0010.
- `docs/BRIEF.md` §§ 2, 3 (legal filter) and 6, for the services and rules the owner named.

## Build

1. **Source catalogue** `config/defaults/sources.yaml` with a schema in `config/`: for each
   service, an id, the publishing body, kind (WMS, WMTS, WFS, WCS, OGC API, REST, download),
   base URL, the layers or datasets of interest, supported CRS, licence and the exact
   attribution text, terms URL, politeness (concurrent requests, minimum interval, cache
   lifetime), and whether it needs a key. Its consumer is the command in step 3.
2. **`src/subphora/sources/`**: an async `httpx` client that refuses any host outside the
   catalogue (hard rule 4), sends a generic `subphora/<version>` User-Agent, applies the
   per-host limits, and has timeouts from `config/`. Probes per kind: capabilities parsed
   (are the layers there; is EPSG:3857 offered), a CORS check (does a request with an
   `Origin` header get `Access-Control-Allow-Origin`), and one small sample request (a
   tile, a feature of a public parcel). Add `respx` and import-linter contracts for the
   new layer. Tests use trimmed real responses in `tests/fixtures/` with sidecar notes of
   source and date, and cover timeouts, HTTP errors, malformed capabilities and a refused
   host.
3. **`uv run subphora sources check [--only <id>]`** prints one row per service and check:
   ok, failed (with reason) or not checked (needs a key). Exit code non-zero on any failure.
4. **Knowledge files**, one per service, findings tagged `(route, date)`:
   - Catastro: the WMS; the INSPIRE WFS for cadastral parcels (query by reference, output
     CRS, geometry quality); the non-protected-data services; the reference format and its
     control characters; which endpoints return protected owner data, so they are never
     called.
   - SIGPAC (FEGA and the Junta de Andalucía viewer services): lookup by
     province:municipality:aggregate:zone:polygon:parcel:enclosure.
   - IGN/CNIG: PNOA WMTS and WMS, the IGN base maps, MDT02/MDT05/MDT25 access (WCS or
     download) and coverage, the CartoCiudad geocoder, and the licence (expected CC BY 4.0:
     confirm that caching for offline use is allowed).
   - IGME: MAGNA 1:50,000 WMS and the vector downloads (GEODE), the 1:200,000
     lithostratigraphic and permeability map, the hydrogeological map, faults, the
     water-point database (what fields: depth, yield, water level, dry), and the licence.
   - MITECO and the basin authorities: groundwater bodies and their status (quantitative,
     chemical, at risk, declared overexploited) in the current basin-plan cycle, the
     piezometric network and its levels, rivers, public water domain and zona de policía
     (SNCZI), river-basin districts. Guadalquivir (CHG) and the Andalusian Mediterranean
     basins (Junta de Andalucía) in detail; note which other basins publish the same.
   - Copernicus (Sentinel-2 access, EGMS) and AEMET OpenData (key needed): access route
     and licence only; they are used in session 14.
   - Google Maps Platform: Map Tiles API and Maps JavaScript API terms on third-party
     renderers, overlays, attribution, caching and offline use, and how to set hard daily
     quota caps. Record the route as a new decision that follows 0005.
   - Nationwide inputs for session 05: which datasets cover all of Spain, at what scale,
     in which format and download size (permeability 1:200,000, lithology, MDT, groundwater
     bodies, water points), and their date.
5. **Legal knowledge** `docs/knowledge/legal-groundwater.md`: article 54.2 of the
   consolidated Water Law (the 7,000 m³/year regime) and the articles of the Public Water
   Domain Regulation that govern it (authorisation or notice, distances to other wells and
   to the public water domain); the Andalusian water law where it adds rules; the normative
   part of the current Guadalquivir and Andalusian Mediterranean basin plans on new
   abstractions in groundwater bodies at risk or in poor status; drilling permits. Each rule
   with its BOE/BOJA or plan link, article, and date checked. Mark anything unclear as
   uncertain rather than guessing: session 08 turns it into rules as data.
6. If the cloud environment's network blocks a host, record it, queue
   `VERIFY-LIVE(<service>)` in ROADMAP, and tell the owner to run
   `uv run subphora sources check` on their PC.
7. Correct facts in later prompts (02–15) that this session's findings change, and log each
   edit.

## DO NOT BUILD

- The front end, the API server, the map viewer, the model or the legal engine.
- Bulk downloads of any dataset (probes fetch samples only).
- Anything using a Google key or any paid service.

## Done when

- `make check` is green and `uv run subphora sources check` prints the status table (live
  where the network allows, otherwise queued as VERIFY-LIVE).
- One knowledge file per service and the legal knowledge file exist, every finding tagged
  with route and date, and the Google-route decision is recorded.
