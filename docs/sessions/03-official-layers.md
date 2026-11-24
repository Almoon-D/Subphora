# Session 03 — Official water and geology layers

Model and effort: Opus 5.5, high.

## Goal

The map shows the official layers as a switchable panel with opacity and legend: water
(groundwater bodies and status, water points, piezometers, rivers, springs, public water
domain; no service draws the zona de policía, which session 09 derives), geology (MAGNA
1:50,000, permeability 1:200,000, hydrogeological map, faults, and the dip and strike of
rock layers from MAGNA's digital structural measurements), the soil maps of decision 0013
(SoilGrids; REDIAM in Andalusia), and the base maps (PNOA and the IGN maps; no Google, decision 0020).

## Read

- `docs/MASTER_PLAN.md` §§ 3, 4.1.
- `docs/decisions/` 0013 (soil) and 0020 (no Google).
- `docs/knowledge/`: IGME, MITECO and basin authorities, Junta de Andalucía, soil,
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
4. A base-map switch between the PNOA orthophoto and the IGN maps (`ign-base-wmts`:
   `IGNBaseTodo`, `IGNBase-gris`), each with its attribution.
5. Tests: catalogue validation, the feature-info proxy (success, empty, upstream failure),
   and the panel and the base-map switch in Playwright.

## DO NOT BUILD

- Other search types; the model; the legal filter; satellite or climate layers (session 15).

## Done when

- `make check` is green and in `make dev` the owner can switch every water and geology layer
  on the parcel from session 02, change opacity, read the legend and tap a feature.

Copyright (c) 2026 Almoon-D. All rights reserved.
