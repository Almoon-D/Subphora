# Session 09a — Legal rules for every district and region

Model and effort: Opus 5.5, high.

## Goal

The legal filter of session 09 knows the rules of every river-basin district and every
regional water law of Spain, read at their official sources, so that "rules not loaded"
remains only where a text truly cannot be read (decision 0022). The engine, the API and the
panels exist; this session adds data, and a rule kind only where a text needs one.

## Read

- `docs/MASTER_PLAN.md` §§ 3 (Jurisdiction), 4.5.
- `docs/decisions/` 0014, 0022 and 0034.
- `docs/knowledge/legal-groundwater.md` (its "Not read yet" section names what is missing),
  `water-authorities.md`.
- `config/legal/es/areas.yaml` and the rule files; `src/subphora/legal/engine.py` (the rule
  kinds) and `tests/unit/test_legal.py`.

## Build

1. Check first that the official hosts answer (BOE, the regional gazettes, the basin
   authorities). If the cloud network refuses them, use the owner's computer (device folder
   or Remote Control) or stop and report: never write a rule from memory.
2. Re-read the sources already loaded (dates move; plans are revised) and update their
   `published` and `checked` dates.
3. For each district whose plan is `not_read` or `partial`: read the normative part of its
   2022-2027 plan (limits on new abstractions, bodies at risk, distances between wells,
   closed zones) and add its file `config/legal/es/es<code>.yaml`; set `plan` to `loaded`,
   or keep it `partial` with the reason. The Canary island plans and the Balearic plan are
   their own districts.
4. For each region whose `water_law` is `not_read`: find whether a regional water law adds
   conditions to a well (Catalonia, the Basque Country, Galicia, Aragón, the Canaries, the
   Balearics and others); add its rules, or mark it `loaded` with no rules when it adds
   none, saying so in the knowledge file.
5. The mining-safety rules for water boreholes (the regional mining authority's
   authorisation): read them at the source; turn the "not evaluated" permit into a rule or
   keep it with the reason.
6. VERIFY-LIVE(legal-taps): one tap on `groundwater-status` and `groundwater-at-risk` at a
   real point confirms the fields `legal.yaml` reads.
7. Tests: a table row per newly loaded district and region (`test_a_place_in_every_district`
   changes its expectation), each new rule's branches, and the boundary of each new distance.

## DO NOT BUILD

- Form-filling or filing with an authority; municipal licences beyond saying one is needed.
- New map layers; a new rule kind that no text read needs.

## Done when

- `make check` is green and `GET /api/legal` at a point of each district gives its rules
  with sources and dates; every district or region still not loaded says why in
  `areas.yaml`, and the knowledge file records what could not be read.

Copyright (c) 2026 Almoon-D. All rights reserved.
