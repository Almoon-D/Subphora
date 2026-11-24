<!-- Copyright (c) 2026 Almoon-D. All rights reserved. -->

## Plan

<!-- 5–15 bullets, written before the code. -->

## Changes

## Tests

<!-- What runs, which failure branches are covered; `make check` result. -->

## Live findings

<!-- Observations against an external service, tagged with route and date, or "none". -->

## Risks

## Safety checklist

<!-- Keep the generic boxes; replace the last ones with the project's own hard rules
     (AGENTS.md → Hard rules). -->

- [ ] Fails closed: every ambiguity on a critical path refuses or alerts
- [ ] Failure-branch tests for every critical path touched
- [ ] No secrets, account ids, tokens or personal data in code, fixtures, logs or this PR
- [ ] No hardcoded values: thresholds, schedules and budgets live in `config/`
- [ ] Every new config key has a consumer
- [ ] Every score ships with confidence, inputs and missing inputs; an uncalibrated score says "index" (hard rule 1)
- [ ] Every recommendation carries its legal status, source, date and disclaimer (hard rule 2)
- [ ] No measurement starts or is imported without a passed safety checklist (hard rule 3)
- [ ] Only catalogued hosts, within their terms; nothing cached against its terms; no keys in the repository (hard rule 4)
- [ ] Field data written locally before confirmation; sync idempotent and append-only (hard rule 5)
- [ ] No titular data; no private parcels, wells or notes in the repository or fixtures (hard rule 6)

## Follow-ups

## VERIFY-LIVE

<!-- Checks that need live credentials, also queued in docs/ROADMAP.md, or "none". -->
