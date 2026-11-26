# 0032 — Basin piezometry spreadsheets join the national database by code

- Date: 2026-11-26 · Status: accepted · MASTER_PLAN §4.3 (depth), decision 0031, owner ruling
- Decision: `subphora piezometry import` also reads CH Júcar's F71 zip (static levels) and
  CH Guadiana's monthly sheet (depth below ground, turned into a level with its MDT05
  ground) when present in `data/piezometry/basins/`. Their levels join the national
  piezometer of the same code (a date in both keeps the national value); a piezometer only
  they hold is added with its own place and body (Júcar's code; Guadiana's body name matched
  to a national one, else left out). Each piezometer and each depth names its sources.
- Rejected: CH Ebro's sheets (series end in 2021, 297 of 327 already national); a separate
  dataset per basin (two water tables for one spot); guessing a body for an unnamed one.

Copyright (c) 2026 Almoon-D. All rights reserved.
