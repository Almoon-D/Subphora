# 0034 — Legal rules as data, evaluated from the official layers at each spot

- Date: 2026-11-26 · Status: accepted · MASTER_PLAN §4.5, decisions 0014, 0022, 0023
- Decision: rules live in `config/legal/es/`, one file per area key (ES, ES-AN, ES050…), each
  with source, article, publication and reading dates; `areas.yaml` lists all 25 districts
  and 19 regions with whether their plan or water law is loaded and, if not, why. Eight rule
  kinds (notice, concession, authorisation, body status, no new concessions, well distance,
  official zone, zona de policía) are mechanics in `subphora.legal`, which imports only
  domain and config. Facts come from the map layers' feature info (body, status, at-risk
  declaration, public water domain, regional zones) and the candidate's measured distances.
- A rule that blocks decides; else any area not loaded gives "rules not loaded"; else an
  authorisation or an unchecked rule gives "conditions apply". Unknown input is never a pass.
- Rejected: one verdict per district without rules (hides the national ones); guessing
  regional laws not read; urban land or Red Natura without a layer (stricter value, flagged).

Copyright (c) 2026 Almoon-D. All rights reserved.
