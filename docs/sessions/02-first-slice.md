# Session 02 — First end-to-end slice: a cadastral reference on the map

Model and effort: Opus 5.5, high.

## Goal

The owner runs `make dev`, opens the app in a PC browser, types a cadastral reference and
sees that parcel outlined on the PNOA orthophoto with the cadastral layer on top. This sets
up the front end, the API and the way they talk, end to end.

## Read

- `docs/MASTER_PLAN.md` §§ 3, 4.1, 4.2, 5.
- `docs/decisions/` 0004, 0010, 0012 (the Google route) and 0014 (Spain-wide, country modules).
- `docs/knowledge/`: Catastro, IGN/CNIG (CORS and EPSG:3857 findings for both).

## Build

1. `web/`: Vite, React, TypeScript and MapLibre GL JS, each at its newest release, on Node 27
   (decision 0011), pinned in one file (`.nvmrc`); every source file carries the copyright
   notice (the copyright test covers `web/`); ESLint, `tsc --noEmit`, Vitest and Playwright
   (use the pre-installed browser). Spanish strings through a translation catalogue from the
   first string. Add the `npm` ecosystem to `.github/dependabot.yml`.
2. `make dev` runs the API and the Vite dev server; `make check` also runs the web checks.
   Extend CI to run them, with a decision that states the added monthly CI minutes.
3. API (`subphora serve`, FastAPI, in `api/`): `GET /api/parcels/{reference}` returns the
   parcel geometry (GeoJSON, EPSG:4326), area, municipality and province, using the session-01
   client and the Catastro INSPIRE WFS. Validate the reference (length, control characters)
   before calling out; a foral territory returns the "not supported yet" message (0010);
   not found, malformed and upstream failure are distinct, explicit errors. Responses cached
   in `data/cache/` with the lifetime from the catalogue. Everything specific to Spain goes
   in `countries/es/` (decision 0014): the cadastral reference format and control letters,
   the foral-territory check (ISO 3166-2 ES-NC, ES-PV), and the CRS choice by location
   (25829/25830/25831, 4083 in the Canaries; the WFS answers 4083 requests in 4326, so read
   the response's `srsName`). Create `domain/` models, `countries/`, `geo/`, `store/` (file cache),
   `services/` and `api/`, each with its import-linter contract.
4. No tile proxy: session 01 found CORS and EPSG:3857 on both PNOA (WMTS,
   GoogleMapsCompatible) and the Catastro WMS. The Catastro WMS terms forbid tiled requests,
   so the cadastral overlay is one untiled image per view (a MapLibre `image` source
   refreshed on move), never a raster tile source. Use the session-01 client for every call.
5. The page: a search box, PNOA as the base map, the Catastro WMS overlay, the parcel outline,
   zoom to the parcel, attribution for every layer, and clear Spanish error messages.
6. Tests: reference validation (every failure branch), WFS responses from fixtures (found,
   not found, malformed, timeout), CRS choice, and a Playwright test of the search flow
   against a mocked API. Use a public, non-private reference in fixtures, never the owner's.

## DO NOT BUILD

- Water, geology or Google layers; other search types; the model; field mode; offline;
  login; deployment.

## Done when

- `make check` (Python and web) is green, and `make dev` → open the URL → type a public
  cadastral reference → the parcel appears outlined on PNOA with the cadastral layer.

Copyright (c) 2026 Almoon-D. All rights reserved.
