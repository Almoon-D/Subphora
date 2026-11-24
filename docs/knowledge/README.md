# Knowledge

Observed behaviour of external services (APIs, data sources, brokers), one file per service.
Every finding is tagged with the route and the date it was observed, e.g.
`(GET /v1/quotes, 2026-11-18)`. Facts here are evidence, not design: the design is in
`MASTER_PLAN.md`, the reasons in `docs/decisions/`.

The source catalogue (`config/defaults/sources.yaml`) names the file for each service;
`uv run subphora sources check` re-checks the catalogued facts live.

| File | Covers |
|---|---|
| `catastro.md` | Catastro WMS, INSPIRE WFS, non-protected data, reference format |
| `sigpac.md` | SIGPAC (FEGA) queries, WMS, OGC API |
| `ign-cnig.md` | PNOA, IGN base maps, MDT (WCS and downloads), CartoCiudad |
| `igme.md` | MAGNA, GEODE, 1:200,000 maps, dip data, water points, 3D models |
| `miteco-basins.md` | Groundwater bodies, status, risk, piezometers, DPH (national services) |
| `water-authorities.md` | Every basin authority and regional water agency: services, level series, terms |
| `junta-andalucia.md` | REDIAM services and the Andalusian Mediterranean basins |
| `soil.md` | Soil options and the recommendation (decision 0013) |
| `copernicus.md` | Sentinel-2 (CDSE STAC) and EGMS |
| `aemet.md` | AEMET OpenData |
| `google-maps.md` | Map Tiles API terms, prices, caps (not used: decision 0020) |
| `nationwide-inputs.md` | What covers all of Spain, for session 05 |
| `legal-groundwater.md` | Water Law, Regulation, Andalusian law, basin-plan rules |

Copyright (c) 2026 Almoon-D. All rights reserved.
