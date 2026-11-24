# 0014 — A Spain-wide product, built for more countries, with no test area in the repository

- Date: 2026-11-24 · Status: accepted · Owner ruling · MASTER_PLAN §1, §3, §4.2, §5
- Ruling: Subphora is a product for all of Spain, to be sold, and later for other countries.
  It must work equally well anywhere in Spain; field tests start in Andalusia, but no
  province of the test area is named in the code, the configuration, the fixtures or the docs.
- Structure: areas are ISO 3166 codes, country (ES) > region (ES-AN) > province (ES-Z);
  water districts (ES050) and groundwater bodies are a parallel hierarchy. The source
  catalogue records each service's `coverage` and `coverage_excludes` in these codes.
  Spain-specific mechanics go in `src/subphora/countries/es/` (created in session 02);
  legal rules in `config/legal/es/`, keyed by area. Another country adds a module and data.
- Applied now: catalogue coverage (Catastro excludes ES-NC and ES-PV, checked live); probe
  samples and fixtures moved to public places across Spain (Santiago, Mérida, Lanzarote,
  Tierra de Campos, Zaragoza, Cuenca, Daimiel, Córdoba); knowledge and prompts reworded.
- Rejected: one catalogue file per country now (one country today: split when the second
  arrives); a region > province folder tree for code (most rules follow basins, not
  provinces, so the code keys data by area code instead).
- Open for the owner (selling changes terms, not decided here): the MAGNA WMS forbids a paid
  value-added service without IGME's consent; Catastro allows commercial products only on
  transformed data and not under the name "cartografía catastral"; Google's free usage is
  per project and costs grow with users; "a few users" (§4.9) becomes many customers with
  their own private data. A later decision settles each before anything is sold.

Copyright (c) 2026 Almoon-D. All rights reserved.
