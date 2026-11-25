<!-- Copyright (c) 2026 Almoon-D. All rights reserved. -->

# Browser-test fixtures

What the API answers, produced on 2026-11-25 by `create_app` over the recorded answers in
`tests/fixtures/parcels/` and `tests/fixtures/search/`, or over the synthetic services of
`tests/national_support.py` (no network). Every place is public.

| File | Request |
|---|---|
| `area-santiago.json` | `GET /api/aoi/cadastral/7279701NH3477G`: the parcel of the Praza do Obradoiro, Santiago de Compostela |
| `area-sigpac-campos.json` | `GET /api/aoi/sigpac/34:48:0:0:13:12:1`: an enclosure in Tierra de Campos |
| `search-daimiel.json` | `GET /api/search?q=Daimiel`: CartoCiudad's towns, municipality and streets |
| `area-daimiel.json` | `GET /api/aoi/place?type=Municipio&id=13039`: the municipality of Daimiel |
| `area-point-daimiel.json` | `GET /api/aoi/point?crs=OGC:CRS84&x=-3.6115&y=39.0675&origin=coordinates` |
| `map.json` | `GET /api/map` with the default configuration |
| `national.json` | `GET /api/national` after a national build of a synthetic box in Madrid (`tests/national_support.py`) |
| `explain-madrid.json` | `GET /api/national/explain?lon=-3.70&lat=40.42` over that build |

`tests/unit/test_map_catalogue.py` checks that they still match the API's models (and
`map.json` its answer); regenerate them when it fails.
