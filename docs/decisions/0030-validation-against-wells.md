# 0030 — Validation against public wells: presence-background AUC per body, no probability yet

- Date: 2026-11-26 · Status: accepted · MASTER_PLAN §4.3 (validation), decisions 0006, 0027
- Decision: each national build validates per groundwater body ("none" outside): IGME wells
  with a yield against seeded random cells, AUC with a 10 km block bootstrap, on the index
  without the water-points criterion (circular). Too few wells or blocks: "not enough
  labels"; lower bound ≤ 0.5: "no better than chance". The skill joins the confidence. No
  public source records dry wells (VERIFY-LIVE(dry-wells)), so calibration is refused ("no
  dry labels") and the score stays an index.
- Rejected: background cells as absences for a probability (prevalence, not odds of water);
  random-split CV (neighbouring wells leak); one national AUC hiding bodies.

Copyright (c) 2026 Almoon-D. All rights reserved.
