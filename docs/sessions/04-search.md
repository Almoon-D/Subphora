# Session 04 — More ways to search

Model and effort: Opus 5.5, medium.

## Goal

Besides a cadastral reference, the owner finds a place by SIGPAC reference, address,
municipality, coordinates (decimal degrees, degrees-minutes-seconds, or UTM with zone), or
by drawing a point or polygon on the map, and that place becomes the area the rest of the
app analyses.

## Read

- `docs/MASTER_PLAN.md` §§ 1, 3, 4.1.
- `docs/knowledge/`: SIGPAC, CartoCiudad, Catastro.

## Build

1. One search box that recognises the input type, with explicit choice when ambiguous.
2. API (Spanish formats in `countries/es/`, decision 0014): SIGPAC enclosure or parcel → geometry; address and municipality → location via
   CartoCiudad; coordinate parsing and conversion with `pyproj`; a drawn polygon accepted as
   an area of interest. One domain type, "area of interest", whatever its origin.
3. A short list of the areas selected in this browser session, to switch between them.
   A click on the map already asks the switched-on layers what lies there (session 03,
   `web/src/App.tsx` `onTap`): while drawing, the click belongs to the drawing.
4. Tests: every parser's failure branches (bad formats, out-of-Spain coordinates, wrong UTM
   zone), mocked SIGPAC and CartoCiudad responses, and the drawing flow in Playwright.

## DO NOT BUILD

- Saving areas on the server; the model; parcel comparison (session 06).

## Done when

- `make check` is green and in `make dev` each search type and a drawn polygon land on the map
  as the selected area.

Copyright (c) 2026 Almoon-D. All rights reserved.
