<!-- Copyright (c) 2026 Almoon-D. All rights reserved. -->

# Changelog

Every version that reaches `main` has a section here; the release workflow publishes it as
the release notes. At most 8 bullets per section, in plain English: what changed for a user,
not a file list.
A new project starts at 0.0.0 with no section; its first session adds `## [0.1.0] - <date>`.

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
