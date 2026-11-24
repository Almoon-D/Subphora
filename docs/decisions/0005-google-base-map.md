# 0005 — Google base maps: optional, capped, never offline

- Date: 2026-11-24 · Status: accepted · MASTER_PLAN §3, §4.1
- Context: the owner wants Google satellite and road; Google's terms limit rendering,
  attribution and storage of its tiles.
- Decision: PNOA is the default base map and the app works fully without a Google key. With the
  owner's key (referrer-restricted, daily quota caps per API), Google satellite and road are
  optional. Google tiles are never cached, put in offline packs or analysed. Session 01 reads
  the current terms and picks Map Tiles API in MapLibre (its policy covers third-party
  renderers) or the Maps JavaScript API, in a new decision.
- Rejected: scraping Google tiles (against the terms); Google as the only base map.
