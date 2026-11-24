# Session 03b — Regional detail over the national layers

Model and effort: Opus 5.5, high.

## Goal

For every map theme, each place in Spain shows the most detailed official data available
there: the service of its autonomous community, province or basin authority where one
qualifies (decision 0023), and the national service everywhere else and as fallback. The
panel and every tap say which source answered, at what scale and of what date. Every
autonomous community, Ceuta and Melilla are surveyed under the same rule.

## Read

- `docs/MASTER_PLAN.md` §§ 3, 4.1.
- `docs/decisions/` 0021, 0022, 0023.
- `docs/knowledge/`: water-authorities, miteco-basins, igme, soil, ign-cnig, and every
  regional file.

## Build

1. Survey, for every autonomous community, Ceuta, Melilla and every basin authority, and
   for each theme (groundwater bodies and status, rivers, springs and water points,
   piezometers and their levels, hydrogeology, geology, soils, public water domain): the
   service, its scale or resolution, date, CORS and EPSG:3857, terms, and what it adds over
   the national layer or whether it is a clip of it. One table in
   `docs/knowledge/regional-layers.md`; unreachable services go to the Live verification
   queue. Commercial terms that differ go to `docs/commercial-use.md`.
2. The qualification rule of decision 0023 as data in `config/` (official, at least as
   recent, finer or richer; never a clip; legal status from the competent authority), and a
   catalogue entry for each service that qualifies, with its evidence in the knowledge table.
3. Region boundaries from an official national service, so each regional layer is drawn
   and asked only inside its area, without gaps or overlaps at the borders.
4. One panel entry per theme. Drawing: the regional layer inside its area over the national
   baseline. Tap: the regional service first, the national one when the regional has no
   answer or fails, saying which answered, with scale and date. Services without CORS or
   EPSG:3857 go through the API's proxy (the WMS GetMap branch and the MapServer GML parser
   removed in version 0.3.1 are in git history).
5. Tests: the qualification rule, the fallback (regional empty, failing, timing out), a
   point at a regional border, and one point per autonomous community in a table test.

## DO NOT BUILD

- The model; legal rules (session 09); downloading level time series (session 07).

## Done when

- `make check` is green; in `make dev` a tap at one point in each autonomous community shows,
  per theme, which source answered with its scale and date; the survey table lists every
  autonomous community, Ceuta and Melilla, with a verdict per theme.

Copyright (c) 2026 Almoon-D. All rights reserved.
