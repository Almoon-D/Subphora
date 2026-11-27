# Decisions

One file per decision: `NNNN-short-slug.md`, at most 12 lines (an owner ruling that
redirects the plan may run longer). A decision is never edited to say something else: a
later one supersedes it and both say so. This index lists every decision, newest first.

| # | Decision | Status |
|---|---|---|
| [0043](0043-owner-levels-offline-and-private.md) | The owner's water levels: typed offline, kept at rest, private beside the public | accepted |
| [0042](0042-field-instrument-path.md) | No field instrument: contracted surveys when a spot needs one | accepted |
| [0041](0041-vegetation-anomaly-and-context-layers.md) | The late-summer vegetation anomaly enters only where validation admits it | accepted |
| [0040](0040-well-registry-and-beta-update.md) | The owner's wells: a private registry and a Beta update shown as its own layer | accepted |
| [0039](0039-home-mini-pc-and-login.md) | A home mini PC behind Caddy; sessions in SQLite; backups read back every night | accepted |
| [0038](0038-report-and-export-pack.md) | The report: one shared catalogue, WeasyPrint with no fetching, GDAL for the pack | accepted |
| [0037](0037-offline-packs-and-service-worker.md) | Offline packs: planned in the browser, stored in Cache Storage, served by a service worker | accepted |
| [0036](0036-field-records-and-outbox.md) | Field records: append-only on the device, an idempotent outbox, SQLite on the server | accepted |
| [0035](0035-legal-rules-per-body-and-volume.md) | Rules narrowed to listed bodies and volume ranges; drilling needs the mining authority | accepted |
| [0034](0034-legal-rules-as-data.md) | Legal rules as data, evaluated from the official layers at each spot | accepted |
| [0033](0033-interpretive-cross-section.md) | The cross-section: a straight line, MAGNA units and dips, unknown below the evidence | accepted |
| [0032](0032-basin-piezometry-sheets.md) | Basin piezometry spreadsheets join the national database by code | accepted |
| [0031](0031-depth-and-drilling-cost.md) | Depth to water from the national piezometry database; cost as a Decimal range | accepted |
| [0030](0030-validation-against-wells.md) | Validation against public wells: presence-background AUC per body, no probability yet | accepted |
| [0029](0029-detailed-map-per-area.md) | The detailed map of an area: a cached job at 5 m, structure from MAGNA | accepted |
| [0028](0028-national-build-and-tiles.md) | The national build: per-province grids in a process pool, PMTiles served by the API | accepted |
| [0027](0027-national-model-v0.md) | The national model v0: nine criteria, seven with nationwide data, confidence that says so | accepted |
| [0026](0026-search-and-area-of-interest.md) | One area of interest from every search, checked on land by SIGPAC | accepted |
| [0025](0025-national-editions-per-part.md) | A national layer published in parts is compared by its parts over the area | accepted |
| [0024](0024-regional-layers-clipped-in-the-browser.md) | Regional layers: the rule as data, official boundaries on one grid, clipped in the browser | accepted; extended by 0025 |
| [0023](0023-regional-detail-national-baseline.md) | Regional detail first, the national service as baseline and fallback | accepted |
| [0022](0022-same-product-everywhere.md) | The same product everywhere: national layers, every basin's rules, no region in prompts | accepted; regional layers amended by 0023 |
| [0021](0021-layer-catalogue-proxy-and-taps.md) | Official layers: one catalogue, a tile proxy only where needed, taps through the API | accepted; REDIAM layers removed by 0022 |
| [0020](0020-no-google-maps.md) | No Google Maps: PNOA and the IGN maps are the base maps | accepted |
| [0019](0019-typescript-7-1-for-eslint.md) | TypeScript 7.1 for ESLint as soon as it is stable; no TypeScript 6 | accepted |
| [0018](0018-parcel-lookup-route.md) | Parcel lookup: WFS in EPSG:4326, places from the non-protected data service | accepted |
| [0017](0017-web-checks-in-ci.md) | The front end's checks run in CI (~75 min a month) | accepted |
| [0016](0016-node-26-and-typescript-7.md) | Node 26 until Node 27 is stable; TypeScript 7 checks, 6 parses for ESLint | accepted |
| [0015](0015-finish-test-then-permissions.md) | Finish the project, test on the owner's land, then seek permissions | accepted |
| [0014](0014-spain-wide-country-modules.md) | A Spain-wide product built for more countries; no test area in the repository | accepted |
| [0013](0013-soilgrids-soil-source.md) | SoilGrids 2.0 as the soil source | accepted; REDIAM layer superseded by 0022 |
| [0012](0012-google-map-tiles-api.md) | Google base maps through the Map Tiles API in MapLibre | superseded by 0020 |
| [0011](0011-owner-ruling-follow-up.md) | Owner ruling after the plan: versions, spending, copyright, subsurface | accepted |
| [0010](0010-foral-cadastres-not-supported.md) | Foral cadastres: "not supported yet" | accepted |
| [0009](0009-proprietary-licence.md) | Proprietary licence | accepted |
| [0008](0008-hardware-deferred.md) | Hardware deferred to session 16 | superseded by 0042 |
| [0007](0007-host-agnostic-deployment.md) | Host-agnostic deployment, host chosen in session 13 | accepted |
| [0006](0006-transparent-two-scale-model.md) | A transparent water-potential model at two scales, without an LLM | accepted |
| [0005](0005-google-base-map.md) | Google base maps: optional, capped, never offline | superseded by 0020 |
| [0004](0004-pwa-maplibre-fastapi.md) | One PWA (React, MapLibre) and a FastAPI backend | accepted |
| [0003](0003-owner-ruling-on-the-brief.md) | Owner ruling on the session-00 proposals | accepted |
| [0002](0002-template-review.md) | Changes from the external review of the template | accepted |
| [0001](0001-repository-from-template.md) | Repository conventions from the template | accepted |

Copyright (c) 2026 Almoon-D. All rights reserved.
