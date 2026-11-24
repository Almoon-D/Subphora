# 0011 — Owner ruling after the plan: versions, spending, copyright, subsurface

- Date: 2026-11-24 · Status: accepted · Owner ruling · MASTER_PLAN §1, §3, §4.3, §4.4
- Languages: the best language for each part, not Python by default. Python stays for the
  backend and data (rasterio, geopandas, pyproj, pyGIMLi have no equal; Python 3.15 wheels
  checked for all of them) and TypeScript for the front end. Rejected: Rust or Go (faster,
  but the geospatial and geophysics libraries would have to be rebuilt).
- Versions: the newest release of every toolchain and dependency, even before the ecosystem
  fully catches up. Node 27 by owner choice over Node 26 LTS, knowing 27 never gets long-term
  support and ends mid-2027: the project moves to Node 28 when it is released.
- Spending: any paid service, however cheap, needs the owner's approval first. Rejected: a
  pre-approved monthly cap.
- Copyright: `Copyright (c) 2026 Almoon-D. All rights reserved.` as the first or last line of
  every file that can hold a comment, enforced by a test with an explicit exemption list
  (JSON, lock files, `.python-version`, binaries, empty markers, third-party fixtures). The
  year was 2027 in the template: corrected to the year of first publication.
- Subsurface: terrain layers (slope, drainage, wetness) shown as layers; bedding dip as a
  layer and model input where digital; a soil map; an interpretive cross-section, as a new
  session 08. Sessions 08–15 became 09–16; references in 0003, 0007 and 0008 were renumbered
  only.

Copyright (c) 2026 Almoon-D. All rights reserved.
