# Session 09 — Legal filter

Model and effort: Opus 5.5, high.

## Goal

For any selected area and candidate, anywhere in Spain, the app shows the competent water
authority, the groundwater body and its legal status, the rules that apply, and a verdict
("probably not allowed", "conditions apply", "no blocking rule found", "rules not loaded for
this basin"), with sources, dates and the "guidance, not legal advice" disclaimer. Every
river-basin district gets the same treatment (decision 0022).

## Read

- `docs/MASTER_PLAN.md` §§ 3 (Jurisdiction), 4.5.
- `docs/decisions/` 0014 and 0022.
- `docs/knowledge/legal-groundwater.md`, `water-authorities.md` and the MITECO file.

## Build

1. Re-check the legal knowledge file's sources live (dates move; basin plans are revised) and
   complete it for every river-basin district (the normative part of each 2022-2027 basin
   plan: limits on new abstractions, bodies at risk, distances) and for every regional water
   law that adds conditions to a well. Record what could not be read, and why.
2. `legal/`: rules as data in `config/legal/es/`, keyed by area code (ES for national rules,
   a region code such as ES-CT for a regional water law, the district code such as ES091 for
   a basin plan; decision 0014), each with its source, article, date and date checked; an
   engine that evaluates them for a location (authority, body status, distances to wells
   and the public water domain); its import-linter contract.
3. The legal panel shown first for an area, and the legal status on every candidate,
   replacing "not evaluated" (hard rule 2). Candidates inside a blocking zone are marked.
4. Tests: each rule's branches, a location in every district (a table test), a district
   whose plan could not be read, boundary cases at distance limits, and the disclaimer's
   presence on every output.

## DO NOT BUILD

- Any form-filling or filing with an authority; municipal licences beyond saying that one
  is needed.

## Done when

- `make check` is green and in `make dev` a location in each river-basin district shows the
  authority, body status, applicable rules and verdict with sources and dates; a district
  whose rules could not be read says so, with the reason. If every district cannot be done
  with quality in one session, merge a coherent subset and write `09a` for the rest
  (AGENTS.md → Session workflow 7).

Copyright (c) 2026 Almoon-D. All rights reserved.
