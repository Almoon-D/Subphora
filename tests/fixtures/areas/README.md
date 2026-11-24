<!-- Copyright (c) 2026 Almoon-D. All rights reserved. -->

# Area-boundary fixtures

Official boundaries fetched on 2026-11-24 as GeoJSON in EPSG:4326 (`docs/knowledge/regional-layers.md`),
then **coarsened to a 0.01° grid** (about 1 km) with `subphora.geo.areas.round_to_grid` so that
they stay small; the live answers carry full detail (Catalonia: 15 MB). Only the code property
is kept. Third-party data: exempt from the copyright notice.

| File | Request |
|---|---|
| `ign_es_nc.json` | IGN `au:AdministrativeUnit`, `au:nationalCode` 34150000000 (Navarra) |
| `ign_es_ct.json` | IGN `au:AdministrativeUnit`, `au:nationalCode` 34090000000 (Catalonia) |
| `ign_es_vc.json` | IGN `au:AdministrativeUnit`, `au:nationalCode` 34100000000 (Valencian Community) |
| `miteco_es020.json` | MITECO `agua:demarhidro_2027`, `cod_ddhh` ES020 (Duero) |
| `miteco_es040.json` | the same, ES040 (Guadiana) |
| `miteco_es060.json` | MITECO `agua:demarhidro_2027`, `cod_ddhh` ES060 (Cuencas Mediterráneas Andaluzas) |
| `miteco_es063.json` | the same, ES063 (Guadalete y Barbate) |
| `miteco_es064.json` | the same, ES064 (Tinto, Odiel y Piedras) |

Test points are kept more than 2 km from every border, where the coarse and the full
boundaries agree.
