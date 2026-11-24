# Roadmap

## What runs next

| Session | Prompt | Model | Status |
|---|---|---|---|
| 00 | `docs/sessions/00-plan.md` | Opus 5.5 | next |
| 01 | written by session 00 | — | — |

## Live verification queue

<!-- VERIFY-LIVE(<what>) items: the check, the session that queued it, the condition that
     unblocks it. Removed when verified. -->

- VERIFY-LIVE(dependabot-merge): the first green minor or patch Dependabot PR merges by
  itself, including a github-actions one (it changes `.github/workflows/`, which the
  default token may not be allowed to merge). If that one fails, the maintenance session
  merges it by hand and this line records the outcome. Queued by the template.

## Follow-ups

<!-- Out-of-scope findings: one line each, with the session that found it. -->

## Session log

<!-- Newest first. At most 15 lines per entry: landed, deferred, live findings, VERIFY-LIVE.
     When this section passes ~300 lines, move the oldest entries to docs/archive/. -->
