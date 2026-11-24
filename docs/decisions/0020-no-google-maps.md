# 0020 — No Google Maps: PNOA and the IGN maps are the base maps

- Date: 2026-11-24 · Status: accepted · Owner ruling · Supersedes 0005 and 0012 · MASTER_PLAN §2, §3, §4.1
- Context: a Map Tiles API key needs a Google Cloud billing account with a card, even for the
  free tier; the owner will not give one. Google would add a second satellite view and a
  street map, both covered in Spain by free, keyless IGN services (PNOA, `ign-base-wmts`).
- Ruling: Google Maps is dropped from the product: no key, no layer, no catalogue entry
  (`google-map-tiles` removed). Session 03 offers PNOA and the IGN maps as base maps.
- Kept: `docs/knowledge/google-maps.md` as the record of what was read; the cache's
  "lifetime 0 = never stored" rule, for any service whose terms forbid storage.
- Rejected: building the Google option "in case" (code nobody will run).

Copyright (c) 2026 Almoon-D. All rights reserved.
