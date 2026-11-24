# Session 03 — Official water and geology layers

Model and effort: Opus 5.5, high.

## Goal

The map shows the official layers as a switchable panel with opacity and legend: water
(groundwater bodies and status, water points, piezometers, rivers, springs, public water
domain; no service draws the zona de policía, which session 09 derives), geology (MAGNA
1:50,000, permeability 1:200,000, hydrogeological map, faults, and the dip and strike of
rock layers from MAGNA's digital structural measurements), the soil maps of decision 0013
(SoilGrids; REDIAM in Andalusia), and the base maps (PNOA, IGN, and Google when a key is set).

## Read

- `docs/MASTER_PLAN.md` §§ 3, 4.1.
- `docs/decisions/` 0005, 0012 (Map Tiles API in MapLibre) and 0013 (soil).
- `docs/knowledge/`: IGME, MITECO and basin authorities, Junta de Andalucía, soil, Google,
  IGN/CNIG.

## Build

1. A layer catalogue in `config/` (service, layer, legend source, default opacity, minimum
   zoom, attribution) consumed by the API and served to the front end; the front end builds
   the panel from it. Extend session 02's `config/defaults/map.yaml` and `GET /api/map`
   (`src/subphora/api/map.py`) rather than adding a parallel one: today it holds the PNOA
   base and the cadastral overlay (one WMS image per view), and `Settings` refuses a layer
   without EPSG:3857 and CORS, which a proxied layer must be allowed to lack.
2. The layer panel: grouped (base, cadastre, water, geology), toggles, opacity sliders,
   legends (the service's own GetLegendGraphic where it exists), attribution always visible.
3. Tap on a layer feature → its attributes (WMS GetFeatureInfo or WFS), through the API where
   CORS requires it, never showing protected data.
   The REDIAM services (no CORS) and the IGME lithostratigraphic map (no EPSG:3857) are
   drawn through the API's proxy, within the catalogue's limits.
4. Google satellite and road by the route chosen in session 01, only when a key is
   configured (from the environment, served to the browser at runtime, never in the
   repository); Google logo and attribution not obscured; no caching. Without a key the
   option is simply absent.
5. Tests: catalogue validation, the feature-info proxy (success, empty, upstream failure),
   that Google is absent without a key and never cached, and the panel in Playwright.

## DO NOT BUILD

- Other search types; the model; the legal filter; satellite or climate layers (session 15).

## Done when

- `make check` is green and in `make dev` the owner can switch every water and geology layer
  on the parcel from session 02, change opacity, read the legend and tap a feature.

Copyright (c) 2026 Almoon-D. All rights reserved.
