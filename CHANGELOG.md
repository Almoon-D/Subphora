<!-- Copyright (c) 2026 Almoon-D. All rights reserved. -->

# Changelog

Every version that reaches `main` has a section here; the release workflow publishes it as
the release notes. At most 8 bullets per section, in plain English: what changed for a user,
not a file list.
A new project starts at 0.0.0 with no section; its first session adds `## [0.1.0] - <date>`.

## [0.3.1] - 2026-11-24

- The map is the same everywhere in Spain: every layer now covers the whole country. The two
  Andalusia-only layers are gone; the national groundwater bodies and SoilGrids already
  covered Andalusia too.
- New layer: GEODE, IGME's continuous geological map, which also covers the parts of the
  Canaries where MAGNA has no geology.
- The legal filter is now planned for every river basin and every regional water law, not
  two basins first.

## [0.3.0] - 2026-11-24

- A layer panel beside the map: groundwater bodies, their status and those declared at
  risk, public water domain, rivers, springs, piezometers and IGME water points; MAGNA
  geology, faults and the dip of the rock layers, the 1:200,000 lithostratigraphic,
  permeability and hydrogeological maps; SoilGrids clay and the Andalusian soil map.
- Each layer switches on and off, has its own opacity, its legend (or a note where the
  service has none), its source, and says from which zoom it is drawn.
- The base map switches between the PNOA orthophoto, the IGN map and the IGN map in grey.
- Tapping the map lists what the switched-on layers hold at that point (a groundwater
  body's status, a well's depth, a rock unit, a bed's dip), with source and date; only
  the fields each layer's list allows are ever shown.
- Layers whose services a browser cannot use directly are fetched and cached by
  Subphora's server, politely.

## [0.2.1] - 2026-11-24

- Google Maps is out of the plan: the base maps are the PNOA orthophoto and the IGN maps,
  free and without any card or key. Subphora no longer lists Google among its services.
- TypeScript 7.1 will replace the TypeScript 6 parser of the code checks as soon as it is
  released.

## [0.2.0] - 2026-11-24

- `make dev` starts Subphora in the browser: type a cadastral reference and the parcel
  appears outlined on the PNOA orthophoto, with Catastro's parcel map on top when zoomed in.
- The parcel card shows the municipality, province, cadastral area and the reference point
  in the parcel's own UTM zone (or REGCAN95 in the Canaries), with its source and date.
- References are checked before anything is asked of Catastro, including the two control
  letters of a 20-character reference; Navarra and the Basque Country get a clear "not
  supported yet".
- Every failure has its own message in Spanish: malformed, not found, territory not
  supported, Catastro slow or failing, server unreachable.
- Catastro's answers are kept for a week in `data/cache/`, so a parcel opens again at once.
- `make check` and CI now also check the front end, including browser tests.

## [0.1.2] - 2026-11-24

- Every water authority in Spain is now surveyed: the river-basin confederations and the
  regional water agencies, with what each publishes and where its well-level data can be had.
- `subphora sources check` now also checks the Guadiana, Duero, Ebro and Júcar basins, the
  Basque and Catalan services, the Balearic groundwater census and Navarra's detailed soil
  map.
- The checks call services the way the app's server will, and test browser access apart:
  one basin's firewall turns away any browser request.

## [0.1.1] - 2026-11-24

- Subphora is now planned as a product for all of Spain, ready for more countries later:
  places are identified by standard country, region and province codes.
- `subphora sources list` shows which part of Spain each service covers; the national
  cadastre is marked as not covering Navarra and the Basque Country.
- The live checks and test data now use public places all over Spain instead of one area.

## [0.1.0] - 2026-11-24

- `uv run subphora sources check` checks every public data service live (Catastro, SIGPAC,
  IGN, IGME, MITECO, the Junta de Andalucía, SoilGrids, Copernicus) and prints one row per
  check: ok, failed with its reason, or not checked when a key is needed.
- `uv run subphora sources list` prints the catalogue: what each service offers, its
  licence and attribution, and the limits Subphora keeps towards it.
- The app can only call the services in that catalogue, with a generic User-Agent and
  polite limits per host; any other address is refused.
- What each service really does, its terms and its quirks are written down in
  `docs/knowledge/`, one file per service, every finding dated.
- The groundwater rules that apply to a new well (the 7,000 m³/year regime, distances,
  bodies at risk) are collected with their official sources for the Guadalquivir and the
  Andalusian Mediterranean basins.
- Google base maps will come through Google's Map Tiles API inside the app's own map, never
  cached; the soil source is SoilGrids.
