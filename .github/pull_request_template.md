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
- [ ] <project-specific rule>

## Follow-ups

## VERIFY-LIVE

<!-- Checks that need live credentials, also queued in docs/ROADMAP.md, or "none". -->
