# Brief — Subphora: find groundwater with evidence instead of guesswork

## 0. How I want you to work

* I am the owner, a finance professional and the "IT person" of a family farming company (about 2,000 ha of dry farmland, olive groves and almond orchards on four estates — three in Antequera (Málaga), one in Sevilla). I am not a hydrogeologist, a geophysicist or an electronics engineer. Talk to me in plain Spanish.
* Challenge me. Everything below is a starting point, not a specification to obey. Where an idea of mine is weak, wrong, illegal, too expensive or not worth building, say so with the evidence and propose something better. Where you see a feature, data source or method I have not thought of that would clearly help, propose it. Put your proposals in a "Proposals for the owner" list in the session-00 report, each with a recommendation; I approve or reject them, and only approved ones enter `MASTER_PLAN.md`.
* Science, not magic. No software or device "sees" water. The product estimates the probability of finding exploitable groundwater from public data and field measurements, shows its uncertainty honestly, and tells me what would reduce it. Never present a guess as a certainty, never mention dowsing as a method, and reject any "water detector" idea that has no physical basis (for example the phone's magnetometer).
* Verify, don't recall. Every external endpoint, licence, price or legal rule named below was written from memory and may be outdated. Plan an early research session that checks each one live and records the findings in `docs/knowledge/` (tagged with route and date) before code depends on it.

## 1. The goal

A tool that, for any Spanish cadastral reference (and, if you agree, any SIGPAC reference or a point/polygon drawn on the map), tells me where on that land I have the best chance of finding groundwater, how deep it probably is, how sure we are, and whether I am even allowed to drill there — and then helps me go to the field, measure, and improve the estimate with real data.

It has two sides:

1. Software: an app that works on a PC and on a mobile phone.
2. Hardware: a low-cost field instrument (to be chosen — see §5) whose measurements the software plans, records, processes and adds to the map.

"Done" for version 1: I type a cadastral reference, see the parcel on the map with all the layers below and our water-potential map, open a per-parcel report, walk to the best candidate spot with my phone, and log a field observation there. The hardware integration comes in later sessions, but the design must leave room for it from day one.

## 2. Software — the maps

The map viewer must show, as switchable layers with opacity and a legend:

1. Google Maps (satellite and road). Use only official Google APIs with my own API key and a hard billing cap; never scrape Google tiles. Check Google's terms on overlaying third-party layers on Google imagery and on using Google tiles in non-Google map libraries (Maps JavaScript API vs Map Tiles API), and record the choice in a decision. Also offer the PNOA orthophoto (IGN/CNIG, free, often sharper in Spain) as an alternative base map, and make the app fully usable without a Google key.
2. Cadastral map: parcel boundaries and references (Sede Electrónica del Catastro WMS, and its INSPIRE WFS to fetch a parcel's geometry by reference). Never fetch or show owner (titular) data — it is protected. Note: País Vasco and Navarra have their own foral cadastres outside the national one; handle them explicitly (supported via their own services, or a clear "not supported yet" message — your call).
3. Water map: groundwater bodies (masas de agua subterránea) and their status (good/poor, at risk, declared overexploited), known water points (IGME's water-point database and the river-basin authority's registers where public), the piezometric network and its levels, rivers and streams, springs, and the protected zones (dominio público hidráulico, zona de policía, protection perimeters).
4. Geological map: IGME's MAGNA 1:50,000 geology, the 1:200,000 lithostratigraphic and permeability map, the hydrogeological map, and faults where available.
5. Our water-potential map (the core of the product): a map we compute that combines all the data and shows where the probability of finding water is higher. See §3.

Other layers worth evaluating (propose which earn their place): LiDAR terrain models from CNIG (MDT02/MDT05) and the derived slope, drainage network and topographic wetness index; Sentinel-2 vegetation indices, especially late-summer NDVI anomalies (plants that stay green in August may tap shallow water); the European Ground Motion Service (subsidence over heavily pumped aquifers); climate and recharge data (AEMET, rainfall). Explain why GRACE and other coarse satellite products are or are not useful at parcel scale.

## 3. Software — the water-potential model

* Start with a transparent, explainable multi-criteria model (weighted overlay of lithology and permeability, structure and lineament density, terrain, drainage, vegetation anomaly, distance to and data from known productive wells, groundwater body status, piezometric levels). Weights live in `config/`, with the source of each weight recorded.
* Every pixel is explainable: tapping a point shows its score, the contribution of each input, the data date and resolution of each input, and which inputs are missing.
* Uncertainty is a first-class output: show a confidence layer next to the score. Low data coverage must lower the confidence, never be silently interpolated.
* Estimated depth to water: where piezometric data exists, ground elevation (LiDAR) minus the water-table elevation, with its uncertainty. Use it in a drilling-cost estimate (cost per metre in `config/`).
* Validation: test the model against known wells (productive vs dry where the data says so) and report how well it actually discriminates. If it does no better than chance in an area, the app must say so.
* Learning from the field: field measurements (§5) and drilled-well results I log (depth, flow, dry/productive) update the map locally. Propose the method (for example Bayesian updating, or a later machine-learning model once there is enough data).
* Legal filter, shown before anything else: for the selected parcel, determine the competent authority from the location (a Confederación Hidrográfica, or a regional water agency — for example, parts of Antequera drain to the Guadalhorce, in the Andalusian Mediterranean basins managed by the Junta de Andalucía, not to the Guadalquivir), the groundwater body and its legal status, and the main rules that apply (the 7,000 m³/year regime of article 54.2 of the Water Law and when it needs authorization, distances to existing wells and to the public water domain, the basin plan's limits). The app gives plain-language guidance with links to the official source, says clearly that it is not legal advice, and flags "you probably cannot drill here" before I spend money looking.

## 4. Software — modes

At least two modes; propose more if they earn their place.

1. Research mode (PC or phone, from home): search by cadastral reference, SIGPAC reference, address, municipality or coordinates; see all the layers of §2; compare parcels; see the ranked candidate spots on each parcel with score, confidence, estimated depth and legal status; export a per-parcel report (PDF) that a hydrogeologist or the water authority can read.
2. Field mode (phone or laptop, on site): "see me" as a live GPS position on a very detailed map (PNOA or Google satellite, parcel boundaries, our map), with my accuracy circle; guide me to a chosen candidate spot (distance and direction); let me drop points with photos, notes and voice memos; record my track. Fincas often have no mobile coverage: field mode must work offline with layers downloaded beforehand for the selected parcels, and sync when back online. It is also the front end of the hardware: plan a survey line on the map, guide me to place each electrode or sensor at its exact position, receive the readings from the instrument, and show a first result on site.

Ideas for further modes or features (accept, reject or improve): a survey planner; a well registry (my existing wells, their depths, flows and water levels over time); a monitoring dashboard for water-level sensors in existing wells; an "ask a professional" export pack.

Users: me and a few non-technical people of the family company. Interface in Spanish (keep it translatable). Simple, large controls in field mode — it is used outdoors, in sunlight, sometimes with gloves.

## 5. Hardware — I am lost here, so research and recommend

I want a low-cost field instrument that adds real underground measurements at the candidate spots. Evaluate the options, compare them (cost, depth reached, what it can and cannot detect, suitability for the local geology — limestone/karst around Antequera, sediments and marls in the Guadalquivir valley —, build difficulty, safety, open-source maturity) and recommend a path, probably starting simple and growing. Candidates I know of:

* Vertical electrical sounding (VES) with a simple 4-electrode resistivity meter (Schlumberger or Wenner). Cheapest; shows layers under one point; depth reached depends on electrode spread (deep targets need long cables).
* Electrical resistivity tomography (ERT) with an open-source multi-electrode meter such as OhmPi (Raspberry Pi based; published as costing under about $500 for 32 electrodes and about €3,000 for the 64-electrode 2024 version — verify). Gives a 2D cross-section along a line. Processing with open-source inversion software such as pyGIMLi or ResIPy.
* Passive seismic (HVSR) with a 3-component geophone or a ready-made seismometer: estimates the thickness of sediments over bedrock; does not see water directly.
* VLF electromagnetics: finds conductive fractures in hard rock; harder to build.
* Methods we should hire, not build (for example magnetic resonance sounding, the only method directly sensitive to water, or TEM): say when paying a contractor for one survey beats building our own.
* Precise positioning: is phone GPS (a few metres) enough, or do we need a low-cost RTK GNSS receiver using the free public correction networks in Spain (IGN, Junta de Andalucía)?
* Afterwards: a cheap water-level logger (pressure sensor + ESP32, LoRa or similar) for existing and new wells.

For the chosen instrument the plan must cover: bill of materials with current prices and suppliers in Spain/EU, build guide, calibration and testing against known ground (an existing well of ours), how it talks to the app (USB, Bluetooth, Wi-Fi, file import — your recommendation), the processing pipeline from raw readings to an inverted model, and how the result feeds the water-potential map. Electrical safety is a hard rule: resistivity instruments inject current into the ground; the design, the app and the build guide must include protections and a safety checklist the app enforces before a measurement starts. Check the licences of any open hardware we reuse.

## 6. Constraints

* Budget: open public data first; free tiers; Google Maps only with a hard spending cap; no paid API without my approval. Hardware: tell me the total for each option; the first instrument should cost hundreds of euros, not thousands, unless you show it is worth it.
* Hosting: propose it (static app plus a small backend for heavy raster processing, a free-tier VM such as Oracle Cloud Always Free, or something else). Heavy processing can be precomputed per parcel on demand and cached.
* Platforms: PC browser and mobile (Android first; iPhone too if cheap). A progressive web app may cover both with GPS and offline support — or not; decide and record why.
* Stack: the template is Python (keep it for data processing and the backend: for example GDAL/rasterio, geopandas, pyproj, OWSLib). Add a JavaScript/TypeScript front end if needed, pinned and covered by Dependabot as AGENTS.md requires. Coordinates: ETRS89 / UTM (EPSG:25830 for mainland Spain, 25829/25831 at the edges), REGCAN95 in the Canaries; handle any Spanish parcel.
* Data licences: attribution for Catastro, IGME, IGN/CNIG, Copernicus, as each licence requires; respect the terms and rate limits of every service; cache politely.
* Privacy: no owner (titular) data; my parcels, wells and field notes are private data — never committed, never sent to an LLM with identifiers.

## 7. Hard rules (derive them into AGENTS.md, each enforced in code or tests)

1. Never present an estimate as a certainty: every score ships with its confidence and its inputs; missing data lowers confidence, it is never invented.
2. Legal status is shown with every recommendation, with its source and date, and labelled as guidance, not legal advice.
3. No measurement starts without the safety checklist passing.
4. Official APIs and terms only; no scraping against a service's terms; API keys and secrets never in the repository.
5. Field mode never loses data when offline.

## 8. What I need from session 00

1. Run the template's steps (rename to `subphora`, interview only for gaps, fill `MASTER_PLAN.md`, decisions, hard rules).
2. Propose the architecture (components, data flow, where each part runs) and the technology choices, each with the alternative you rejected and why.
3. The hardware recommendation as a decision record: options compared, recommended path, rough budget.
4. The build plan as sessions, each small and ending in something I can see or run. Suggested order (change it if you have a better one): research/verification of every data source and legal rule → parcel lookup and map viewer with official layers → water-potential model v1 with explainability and validation → legal filter → field mode with GPS and offline → per-parcel report → hardware build and integration → learning from field data. Put a working end-to-end slice early rather than perfecting one layer.
5. The "Proposals for the owner" list (§0), and the list of things only I can do (create a Google Cloud project and key with a cap, pick parcels for testing, find data from our existing wells, buy hardware).
6. The prompt for session 01 with model and effort, as AGENTS.md says.

Copyright (c) 2026 Almoon-D. All rights reserved.
