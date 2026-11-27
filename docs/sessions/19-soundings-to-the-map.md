# Session 19 — From soundings to a layered model and the map

Model and effort: Opus 5.5, high.

## Goal

A resistivity sounding imported in session 18 becomes a layered model of the ground under
its point, with its uncertainty, shown beside the index and in the cross-section, and it
feeds the map only as a decision recorded in this session allows.

## Read

- `docs/MASTER_PLAN.md` § 4.3, § 4.4, § 4.8; decisions 0006, 0033, 0040, 0042.
- `docs/knowledge/field-instruments.md` (Resistivity, Fit by setting).
- pyGIMLi's 1D VES modelling and inversion documentation (Apache-2.0).
- `src/subphora/model/section.py`, `src/subphora/model/learning.py`.

## Build

1. A 1D inversion of a sounding with pyGIMLi (added at its newest release): a few-layer
   model with resistivity and thickness per layer, the misfit, and a range per layer from
   the inversion's uncertainty; settings (layers, regularisation, error model) in config.
2. The interpretation as a labelled interpretation, never a finding: each layer's likely
   materials from its resistivity and the local geology, with the ambiguity said (clay,
   marl and salty water all read low), and the depth to a likely saturated permeable layer
   when the well level or geology supports it.
3. The sounding at its point on the detailed map and in the cross-section of session 08,
   marked as measured, with its date, misfit and confidence.
4. Feeding the map: a decision record for how a sounding moves the index at its point
   (like a well in decision 0040, with its own weight and range, or only shown); hard rule 1
   holds: the input, its source, date and confidence cross the API.
5. Tests: the inversion recovers a synthetic three-layer model within its ranges; a poor
   fit lowers confidence; a sounding never fills a missing input elsewhere.

## DO NOT BUILD

- ERT (2D) processing, which waits for a ruling after the first soundings; HVSR, VLF.

## Done when

- `make check` is green and the synthetic sounding shows its layered model, ranges and
  interpretation at its point and in a cross-section through it.

Copyright (c) 2026 Almoon-D. All rights reserved.
