# Roadmap

## What runs next

| Session | Prompt | Model and effort | Status |
|---|---|---|---|
| 00 | `docs/sessions/done/00-plan.md` | Opus 5.5 | done |
| 01 | `docs/sessions/01-verify-sources.md` | Opus 5.5, high | next |
| 02 | `docs/sessions/02-first-slice.md` | Opus 5.5, high | planned |
| 03 | `docs/sessions/03-official-layers.md` | Opus 5.5, high | planned |
| 04 | `docs/sessions/04-search.md` | Opus 5.5, medium | planned |
| 05 | `docs/sessions/05-national-map.md` | Opus 5.5, high | planned |
| 06 | `docs/sessions/06-parcel-detail.md` | Opus 5.5, high | planned |
| 07 | `docs/sessions/07-validation-depth-cost.md` | Opus 5.5, high | planned |
| 08 | `docs/sessions/08-legal-filter.md` | Opus 5.5, high | planned |
| 09 | `docs/sessions/09-field-mode.md` | Opus 5.5, high | planned |
| 10 | `docs/sessions/10-offline-packs.md` | Opus 5.5, high | planned |
| 11 | `docs/sessions/11-report.md` | Opus 5.5, medium | planned |
| 12 | `docs/sessions/12-deployment.md` | Opus 5.5, high | planned — version 1 |
| 13 | `docs/sessions/13-well-registry-learning.md` | Opus 5.5, high | planned |
| 14 | `docs/sessions/14-satellite-climate.md` | Opus 5.5, high | planned |
| 15 | `docs/sessions/15-hardware-planning.md` | Opus 5.5, high | planned |

## Live verification queue

<!-- VERIFY-LIVE(<what>) items: the check, the session that queued it, the condition that
     unblocks it. Removed when verified. -->

- VERIFY-LIVE(dependabot-merge): the first green minor or patch Dependabot PR merges by
  itself, including a github-actions one (it changes `.github/workflows/`, which the
  default token may not be allowed to merge). If that one fails, the maintenance session
  merges it by hand and this line records the outcome. Queued by the template.

## Follow-ups

<!-- Out-of-scope findings: one line each, with the session that found it. -->

- Every external endpoint, licence, price and legal rule in the plan was written from memory:
  session 01 verifies them before code depends on them. (00)

## Session log

<!-- Newest first. At most 15 lines per entry: landed, deferred, live findings, VERIFY-LIVE.
     When this section passes ~300 lines, move the oldest entries to docs/archive/. -->

### 00 — Plan the project (2026-11-24, version 0.0.0)

- Landed: the template renamed to `subphora`; the owner's brief saved as `docs/BRIEF.md`;
  `MASTER_PLAN.md` filled; six project hard rules in AGENTS.md; decisions 0003–0010; prompts
  for sessions 01–15; proprietary licence (0009).
- Owner rulings (0003): model before legal filter; all of Spain at a coarse scale plus parcel
  detail; any cheap host; no LLM; hardware deferred to session 15; deployment after the report.
- Live findings: none recorded as knowledge; Google's Map Tiles policy appears to allow
  third-party renderers and forbids offline use, and OhmPi is GPL-3.0 — both for session 01
  (or 15) to confirm.
- VERIFY-LIVE: none new.
