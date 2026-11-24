# AEMET OpenData

Host `opendata.aemet.es`. Catalogue id: `aemet-opendata`. Access route and licence only:
used in session 15. Findings observed on 2026-11-24.

- API base `https://opendata.aemet.es/opendata/api/…`, e.g.
  `/valores/climatologicos/inventarioestaciones/todasestaciones`. It needs an API key (a
  JWT): without a valid one it answers HTTP 401 with JSON
  `{"descripcion": "JWT strings must contain exactly 2 period characters. Found: 0", "estado": 401}`.
  `(GET /valores/climatologicos/inventarioestaciones/todasestaciones, 2026-11-24)`
- The key is free, requested by e-mail at `https://opendata.aemet.es/centrodedescargas/altaUsuario`;
  the owner requests it before session 15 and stores it as the environment variable
  `AEMET_API_KEY`, never in the repository (hard rule 4).
- Responses come in two steps (a first call returns a `datos` URL to fetch the data);
  `subphora sources check` marks the service "not checked" until a key exists.
- Terms (footer of `https://opendata.aemet.es/centrodedescargas/inicio` and
  `https://www.aemet.es/es/nota_legal`): "© Aemet. Autorizado el uso de la información y su
  reproducción citando a Aemet como autora de la misma." `(GET /centrodedescargas/inicio, 2026-11-24)`

Copyright (c) 2026 Almoon-D. All rights reserved.
