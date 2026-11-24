# Session 03ba — The regional layers still waiting for evidence

Model and effort: Opus 5.5, high.

## Goal

Every regional service that session 03b found but could not judge (verdict **E** in
`docs/knowledge/regional-layers.md`) gets a verdict under the same rule (decision 0023), and
each one that qualifies joins the map the way the first three did: catalogued, drawn inside
its area over the national layer, asked first on a tap. Nothing new is designed: the rule,
the boundaries, the clipping and the fallback exist (decision 0024).

## Read

- `docs/MASTER_PLAN.md` §§ 3, 4.1.
- `docs/decisions/` 0021, 0022, 0023, 0024.
- `docs/knowledge/regional-layers.md` in full; `water-authorities.md`, `igme.md`, `soil.md`.
- `config/defaults/regional.yaml` and its schema `src/subphora/config/regional.py`.

## Build

1. For each **E** cell (Balearic census, piezometric points, public water domain and
   geology; Cantabria geology and rivers; Catalonia water points, piezometric surfaces,
   soils 1:25,000 and rivers; the Valencian geology 1:25,000; Navarra geology, springs,
   rivers, piezometers and hydrogeological aspects; the Basque water points and rivers;
   the Andalusian springs; CH Guadiana and CH Duero): a GetFeatureInfo at a point where the
   layer draws something (find one from its GetMap), the fields to show, the scale and
   edition from its metadata. Record each in the knowledge table with its route and date.
2. The national editions the rule needs and that are not stated today (GEODE, the IGME
   water points, permeability and lithostratigraphy, the MITECO springs, piezometers and
   public water domain): find them in the publishers' metadata. While one is unknown,
   nothing qualifies over it; say so in the table.
3. Each layer that qualifies: a catalogue entry, its area (a new one needs its bbox from
   the official boundary), its `regional.yaml` entry with evidence, Spanish titles and
   field labels, fixtures and a tap test like `tests/unit/test_regional_layers.py`. A
   service without EPSG:3857 needs the export branch for regional layers (not built yet).
4. Commercial terms that differ go to `docs/commercial-use.md`.

## DO NOT BUILD

- The model; legal rules (session 09); level time series (session 07); new boundary kinds
  beyond what a qualifying layer needs.

## Done when

- `make check` is green; no **E** is left in the table (each is Q, K, S, O, L or a
  VERIFY-LIVE with its reason); in `make dev` a tap on each new regional layer names it,
  with its scale and date.

Copyright (c) 2026 Almoon-D. All rights reserved.
