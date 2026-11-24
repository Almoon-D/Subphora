# Session 09 — Legal filter

Model and effort: Opus 5.5, high.

## Goal

For any selected area and candidate the app shows the competent water authority, the
groundwater body and its legal status, the rules that apply, and a verdict ("probably not
allowed", "conditions apply", "no blocking rule found", "rules not loaded for this basin"),
with sources, dates and the "guidance, not legal advice" disclaimer.

## Read

- `docs/MASTER_PLAN.md` § 4.5.
- `docs/knowledge/legal-groundwater.md` and the MITECO and basin files.

## Build

1. Re-check the legal knowledge file's sources live (dates move; basin plans are revised) and
   update it.
2. `legal/`: rules as data in `config/legal/es/`, keyed by area code (ES for national rules,
   ES-AN for Andalusian ones, the district code such as ES050 for a basin plan; decision 0014), each with its source, article, date and date checked; an engine that
   evaluates them for a location (authority, body status, distances to wells and the public
   water domain); its import-linter contract.
3. The legal panel shown first for an area, and the legal status on every candidate,
   replacing "not evaluated" (hard rule 2). Candidates inside a blocking zone are marked.
4. Tests: each rule's branches, a location in a basin without rules, boundary cases at
   distance limits, and the disclaimer's presence on every output.

## DO NOT BUILD

- Rules for basins other than the Guadalquivir and the Andalusian Mediterranean basins (the
  first two loaded) beyond what the national rules cover; any form-filling or filing with an authority.

## Done when

- `make check` is green and in `make dev` the owner's test area shows the authority, body
  status, applicable rules and verdict with sources and dates.

Copyright (c) 2026 Almoon-D. All rights reserved.
