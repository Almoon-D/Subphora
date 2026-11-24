# 0006 — A transparent water-potential model at two scales, without an LLM

- Date: 2026-11-24 · Status: accepted · MASTER_PLAN §4.3
- Context: a map of all of Spain that zooms to a parcel, explainable at every point, honest.
- Decision: a weighted multi-criteria overlay, weights and classes in `config/` with sources. A
  national 100 m grid precomputed by a batch command and served as tiles; a 5 m grid per
  parcel on demand. The score is a relative index until session 07 calibrates it against
  wells; a confidence layer goes with it everywhere. Learning is Bayesian updating; machine
  learning only past a threshold of labelled wells and only if it validates better.
- Rejected: an LLM to produce or explain the map (unneeded, not reproducible, a privacy risk);
  a black-box model first (too few labelled wells); per-parcel only (owner wants Spain).

Copyright (c) 2026 Almoon-D. All rights reserved.
