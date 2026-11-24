# Google Maps Platform

Host `tile.googleapis.com`. Catalogue id: `google-map-tiles` (needs the owner's key; never
probed without it). The route chosen is decision 0012. Findings read from Google's public
documentation on 2026-11-24; nothing was called with a key.

## Map Tiles API (2D tiles)

- Requires a session token: `POST https://tile.googleapis.com/v1/createSession?key=…` with
  a JSON body (`mapType`: `roadmap`, `satellite`, `terrain` (with a roadmap layer) or
  `streetview`; `language`; `region`). The token is valid about two weeks (`expiry` in the
  response); tiles are then requested per z/x/y with the session. The key travels in the
  URL query, so no URL with a key may be logged. `(developers.google.com/maps/documentation/tile/session_tokens, 2026-11-24)`
- **Third-party renderers are allowed**: "When you use the Map Tiles API to display Google
  Maps using a third-party renderer, you must not overlap or obscure the Google logo with
  any other logo, such as the renderer's logo", keeping a buffer between the logos; no logo
  may obscure the data attribution returned by the API. `(…/tile/policies, 2026-11-24)`
- **Overlays are allowed**: with Google as base map and third-party data on top, the
  third-party attribution must not overlap the Google attribution and must be clearly
  separate, and users must be able to tell which part is Google's. `(…/tile/policies, 2026-11-24)`
- Attribution: the Google Maps logo (16–19 dp high, unmodified, outlined version on busy
  backgrounds) or the text "Google Maps" where space is short, plus the data attribution
  returned by the API (viewport information). `(…/tile/policies, 2026-11-24)`
- **No caching, no offline use**: "you must not pre-fetch, index, store, or cache any
  Content except under the limited conditions stated in the terms"; offline uses are
  listed as prohibited; the client must honour the responses' `Cache-Control` (`max-age`,
  `private`…), which is HTTP caching in the browser, not storage. Google tiles never enter
  an offline pack, a server cache or the model (decision 0005). `(…/tile/policies, 2026-11-24)`
- Quota: every 2D tile request counts against the project's daily quota (default 15,000
  2D Tile requests per project per day); session-token and viewport requests do not.
  `(…/tile/usage-and-billing, 2026-11-24)`

## Prices and caps

- 2D Map Tiles: **100,000 free requests per month**, then USD 0.60 per 1,000 (falling
  with volume). Maps JavaScript API ("Dynamic Maps"): 10,000 free map loads per month,
  then USD 7.00 per 1,000. `(developers.google.com/maps/billing-and-pricing/pricing, 2026-11-24)`
- Hard cap: Google states that "a quota sets the most your project can use an API, so it
  also sets the most you can be charged for that API"; lowering a quota lowers that
  ceiling. Quotas per day are set in the Google Cloud console (APIs & Services → the
  API → Quotas); a budget alert alone does not stop charges. `(…/billing-and-pricing/manage-costs, 2026-11-24)`
- With a cap of, for example, 3,000 2D tile requests per day the month stays under
  100,000 requests, inside the free usage. The owner sets the figure when creating the key
  (session 03).

## Maps JavaScript API

- Google's own renderer: it cannot be used inside MapLibre, so choosing it would mean a
  second map library for one base layer. Not chosen (decision 0012).

Copyright (c) 2026 Almoon-D. All rights reserved.
