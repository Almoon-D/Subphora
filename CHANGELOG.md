<!-- Copyright (c) 2026 Almoon-D. All rights reserved. -->

# Changelog

Every version that reaches `main` has a section here; the release workflow publishes it as
the release notes. At most 8 bullets per section, in plain English: what changed for a user,
not a file list.
A new project starts at 0.0.0 with no section; its first session adds `## [0.1.0] - <date>`.

## [0.16.0] - 2026-11-26

- Report: once an area's detailed map is done, "Descargar el informe (PDF)" gives a report a
  hydrogeologist or the basin authority can read: maps, every candidate with its index and
  confidence, explanation, depth, drilling cost and legal status, the model's measured
  skill, field notes, every source with its date and licence, the limitations and the
  legal disclaimer.
- Professional pack: "Descargar el paquete (ZIP)" adds the layers for a GIS (a GeoPackage
  with the area, candidates and field records, and COG rasters of the index, confidence
  and depth to water) and CSV tables; field photos and voice memos only when ticked.
- Anything missing (no depth without imported levels, no field records) is said, with why.

## [0.15.0] - 2026-11-26

- Offline packs: before going to a site, download a pack of the selected area and the map
  works there with no coverage: PNOA orthophoto around it (zooms 10 to 18), the potential
  index and its confidence, the detailed map's images, the parcel's outline and candidates.
- Before downloading, the panel lists what the pack holds and what it leaves out with the
  reason (the Catastro map never: its terms forbid it), and its estimated size; packs above
  250 MB, or larger than the space left on the device, are refused.
- A download shows its progress, can be paused, and resumes where it stopped after a lost
  signal or a closed page, without downloading anything twice.
- The app now opens and reloads with no coverage at all (a service worker keeps it), so
  field mode and a pack's area keep working on site.
- The packs on the device are listed with their size and date, to open again or delete.

## [0.14.0] - 2026-11-26

- Field mode: a "Modo campo" button turns the panel into large, high-contrast controls with
  your live position, its accuracy circle and heading on the map.
- Pick a candidate spot of the detailed map and the panel shows the distance and direction
  to it; it says "at the spot" only within 10 m and with an accuracy of ±10 m or better.
- Notes, photos, voice memos and the walked track are saved on the device first, with or
  without coverage, and only then confirmed.
- They sync to the server when there is a connection, in batches that can be retried or cut
  by a reload without duplicating or losing anything; the panel counts what is unsent.
- Everything unsent can be exported to a file; `subphora field summary` counts what arrived.

## [0.13.0] - 2026-11-26

- The legal filter now knows the basin plans of 17 of Spain's 25 river-basin districts
  (Miño-Sil, both Cantábricos, Duero, Tajo, Guadiana, Guadalquivir, the three Andalusian
  ones, Segura, Júcar, Ebro, Catalonia, Balearics, Ceuta and Melilla) and part of four
  Canary island plans, all read at their official sources on 2026-11-26.
- Every region's water law has been read: the Canary Water Law adds an island council's
  authorisation; the others add nothing to drilling a well, and the filter says so.
- New conditions shown with their article: distances that grow with the volume (Tajo) or
  the pump's flow (Balearics, Miño-Sil), bodies closed to new concessions (Guadiana, Ebro,
  Segura), authorisations in listed bodies (Catalonia, Tajo) and the Júcar's for any well.
- Every status now lists the regional mining authority's approval of the drilling project.
- Where a plan could not be read (Galicia-Costa, Fuerteventura, La Palma, La Gomera) the
  status still says "rules not loaded", and why.

## [0.12.0] - 2026-11-26

- A legal panel opens first for every selected area: the water authority, the groundwater
  body with its quantitative status and any at-risk declaration, every rule that applies
  with its official source, article and dates, and a verdict with the disclaimer.
- Every candidate spot now carries its own legal verdict ("probably not allowed",
  "conditions apply", "no blocking rule found" or "rules not loaded"), with the distance to
  the nearest inventoried water point and channel checked against each rule's limit.
- Spots inside a zone that forbids the well (an exclusion circle, a Guadiana closed
  perimeter, a Duero "zona no autorizada") are marked on the list and struck on the map.
- Loaded: the national Water Law and its Regulation, the Andalusian Water Law, the
  Guadalquivir and Andalusian Mediterranean plans, and the closed zones of the Guadiana and
  Duero; every other district and region says its rules are not loaded, and why.

## [0.11.0] - 2026-11-26

- "Dibujar un corte": tap the start and end of a line on the map and a geological
  cross-section of the ground under it opens below the map, always labelled
  "interpretation", with its vertical exaggeration and a legend.
- The section shows the ground profile (5 m terrain), the MAGNA 1:50,000 units the line
  crosses with their contacts carried down along the nearest measured dip, the faults, the
  public boreholes nearby with their depth, and the water table where it can be estimated.
- Every cell has a confidence that falls with depth and with distance to a measured dip or
  a borehole; below what the evidence reaches it is drawn hatched as "unknown".
- Tapping any part of the section explains it: the unit and why, the contact and its dip,
  the fault, the borehole or the water table and where each comes from.

## [0.10.0] - 2026-11-26

- `subphora piezometry import` also reads the Júcar and Guadiana basin authorities' level
  spreadsheets when they are in `data/piezometry/basins/`, bringing the levels in those
  basins up to 2026 and adding 140 piezometers only the Júcar file holds.
- Each depth on a candidate spot lists the sources of the levels it used, with their dates.

## [0.9.0] - 2026-11-26

- The model is checked against public wells: every national build measures, per
  groundwater body, how well the index separates productive wells from random places (AUC
  with its interval), and says "validated", "no better than chance" or "not enough wells".
- That measured skill now counts in the confidence, and a new layer maps it.
- The index stays an index: no public record of dry wells exists yet, so it is not turned
  into a probability anywhere, and the app says why.
- `subphora piezometry import` reads the national piezometry database downloaded by hand
  (needs mdbtools).
- Each candidate spot shows the estimated depth to water with its range, from the
  piezometers of its own groundwater body, or "unknown" and why; karst rock is flagged.
- Each candidate with a depth shows a drilling cost range in euros, with the sources and
  date of the prices (overridable in `config/owner.yaml`).
- The detailed map's summary lists the validation of each groundwater body it touches.

## [0.8.0] - 2026-11-25

- A detailed map of any selected area: "Calcular el mapa detallado" computes the potential
  index at 5 m over the parcel, enclosure, drawn polygon or a 250 m disc around a point,
  shows the job while it runs, and keeps the result for the next time.
- The detailed map adds the faults and the dip of the layers mapped on MAGNA 1:50,000, and
  reads slope, drainage and wetness from the 5 m terrain model; it says which inputs are
  missing there and what the area's mean index and confidence rest on.
- Its index, confidence, slope, drainage and wetness layers are drawn over the area, with
  their legends; a tap inside the area explains that cell.
- Ranked candidate spots: the best cells with at least medium confidence, kept apart,
  numbered on the map, each with its explanation, "legal status: not evaluated" and the
  "guidance, not legal advice" note.
- Two or more analysed areas are compared side by side: size, mean index and confidence,
  and their best candidates.

## [0.7.0] - 2026-11-25

- A national map of groundwater potential: when the app opens, every province built is
  coloured by a relative potential index (0 to 1), labelled an index and never a
  probability, with a confidence layer beside it.
- `subphora national build --region ES-Z` (a province), `--region ES-AR` (every province of
  a region), a box in degrees, or `--all`, downloads the nationwide public inputs politely
  and computes the 100 m grids; the Canaries have their own grid.
- The index weighs permeability and lithology (IGME), slope, wetness and drainage (IGN
  terrain), topsoil clay (SoilGrids), the groundwater body's status (MITECO) and nearby
  water points (IGME); criteria without nationwide data yet are listed as missing.
- A tap on the map explains the index there: each input's value, suitability, weight,
  contribution, source and date, the inputs missing, and what the confidence depends on.
- Slope, distance to the drainage network and the topographic wetness index are map layers
  too, each with its legend.

## [0.6.0] - 2026-11-25

- One search box for every way to name a place: a cadastral or SIGPAC reference (parcel or
  enclosure), an address, a town or municipality, or coordinates in decimal degrees,
  degrees-minutes-seconds or UTM, with a decimal point or comma.
- When a text reads several ways (UTM without its zone, six bare numbers, a name shared by
  many places) the app asks which one was meant, and offers only readings that fall on
  land in Spain.
- A point or a polygon drawn on the map becomes the selected area; while drawing, a click
  on the map adds to the drawing instead of asking the layers.
- Every found or drawn place becomes the same "area of interest": its outline or point,
  province, area, centre in the local CRS, and the official source and date that named it,
  which the map's attribution also credits.
- Coordinates outside Spain, at sea, or in the wrong UTM zone or band are refused with a
  plain message; Ceuta and Melilla, which SIGPAC does not cover, say so on the card.
- The areas selected in a browser tab are listed to switch between them; they stay in that
  tab only, never on the server.

## [0.5.0] - 2026-11-24

- Five more regional layers on the map, each inside its official boundary: Catalonia's
  1:25,000 soil map, the 1:25,000 geological maps of Navarra and of the Valencian
  Community, the Guadiana basin's perimeters where no new groundwater abstraction is
  allowed, and the Duero basin's zoning of where groundwater may be abstracted.
- A tap on them names the source, its scale and its date; where they map nothing, the
  national layer answers and says so.
- Every regional service the survey had left open now has a verdict; the ones that wait on
  a fact only a publisher or a browser can give say which, in
  `docs/knowledge/regional-layers.md`.
- The permeability and lithostratigraphic maps now show their edition (2009).
- A tap no longer lists the same unit twice where two of its polygons meet.

## [0.4.0] - 2026-11-24

- Regional detail on the map: inside Navarra its 1:25,000 soil map, inside Catalonia the
  ICGC's 1:25,000 hydrogeological units, and in the three Andalusian intra-community basins
  the groundwater bodies the Junta keeps under preventive control, each drawn over the
  national layer and only inside its official boundary.
- A tap asks the regional service first and the national one when the regional has
  nothing, fails or is too slow, and says which answered, with its scale and its date.
- Every layer in the panel names its national source and any regional ones, each with its
  scale and edition, or says when the publisher states neither.
- Every autonomous community, Ceuta, Melilla and every basin authority surveyed under the
  same rule; the verdicts per theme are in `docs/knowledge/regional-layers.md`.

## [0.3.2] - 2026-11-24

- Planned: the map will use each region's own, more detailed official services where they
  qualify, with the national services as the baseline everywhere and the fallback when a
  regional one has nothing or fails. Every region is surveyed first, under the same rule.

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
