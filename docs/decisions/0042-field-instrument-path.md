# 0042 — Field instruments: a water-level meter, then a 4-electrode resistivity meter

- Date: 2026-11-27 · Status: proposed, awaiting the owner's ruling · Supersedes 0008; BRIEF §5
- Decision: buy a 100 m water-level meter (dipper, about €560-960) for the owner's wells;
  then build a 4-electrode OhmPi v2024 meter for vertical soundings (VES, about €1,100,
  board BOM €461 + VAT), DPH5005 capped at 50 V and 48 mA, readings imported as OhmPi files
  behind the checklist of hard rule 3, inverted with pyGIMLi (Apache-2.0). Phone GPS and a
  tape place the electrodes. Grow to 16-32 electrodes (ERT) only if soundings prove useful.
  Evidence: `docs/knowledge/field-instruments.md`.
- Rejected for now: HVSR (≈$955-1,405, sees bedrock depth, not water); VLF (no open design,
  depends on military transmitters); RTK (≈€211, needless for a 1D sounding); loggers until
  the owner reads levels by hand; GPL code (OhmPi, ResIPy, hvsrpy) linked into Subphora.
- Cost: about €1,700-2,000, against a dry 100 m hole (€3,500-12,000). It sees tens of
  metres; deep karst and aquifers below about 60 m stay a contracted survey.

Copyright (c) 2026 Almoon-D. All rights reserved.
