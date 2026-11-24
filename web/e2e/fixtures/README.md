<!-- Copyright (c) 2026 Almoon-D. All rights reserved. -->

# Browser-test fixtures

What the API answers, produced on 2026-11-24 by `create_app` over the recorded Catastro
answers in `tests/fixtures/parcels/` (no network):

| File | Request |
|---|---|
| `parcel-santiago.json` | `GET /api/parcels/7279701NH3477G`: the public parcel of the Praza do Obradoiro, Santiago de Compostela |
| `map.json` | `GET /api/map` with the default configuration |

`tests/unit/test_parcels_api.py` checks that both still match the API; regenerate them
when it fails.
