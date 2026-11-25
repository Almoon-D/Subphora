# 0026 — One area of interest from every search, checked on land by SIGPAC

- Date: 2026-11-25 · Status: accepted · MASTER_PLAN §1, §3 (Coordinates), §4.1
- Context: six ways to name a place must end as one thing the later sessions analyse, and
  typed or drawn coordinates must be in Spain, in the right UTM zone, with a province.
- Decision: `GET /api/search` answers every valid reading of the text, each with the
  `/api/aoi/…` path that resolves it; one reading resolves at once, several are a choice
  (six numbers are a SIGPAC parcel and degrees alike). Every path returns one
  `AreaOfInterest`. A point is in Spain when it lies in a territory box of `search.yaml`
  and SIGPAC has an enclosure under it, which names the province; Ceuta and Melilla, which
  SIGPAC lacks, are placed by their boxes and say so (`land_checked`). Zone-less UTM and
  unlabelled degrees offer only the readings on land. The session's list lives in the
  browser's sessionStorage, never on the server.
- Rejected: CartoCiudad's reverse geocoder (finds only nearby addresses: none at a rural
  point in Granada); the IGN's administrative-units WFS per click (answers a whole region);
  boxes alone (accept Portugal, Andorra and the sea); one endpoint per format in the
  browser (the formats are Spain's, so the country module reads them).

Copyright (c) 2026 Almoon-D. All rights reserved.
