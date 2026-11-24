# 0013 — SoilGrids 2.0 as the soil source

- Date: 2026-11-24 · Status: accepted · MASTER_PLAN §3 ("session 01 chooses the source")
- Context: the soil map feeds the model (infiltration) and a map layer, for all of Spain.
  Options compared in `docs/knowledge/soil.md`.
- Decision: SoilGrids 2.0 (ISRIC, 250 m, CC BY 4.0, WCS): numeric clay and sand fractions
  with 5–95 % quantiles that feed the confidence layer, nationwide, no registration. The
  REDIAM 1:400,000 soil map is shown in Andalusia as a qualitative context layer.
- Rejected: the European Soil Database (1:1,000,000, registration, nothing SoilGrids lacks);
  REDIAM alone (Andalusia only, associations without texture values).
- Limit: 250 m cells are regional at parcel scale; the parcel view says so.

Copyright (c) 2026 Almoon-D. All rights reserved.
