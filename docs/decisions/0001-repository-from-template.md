# 0001 — Repository conventions from the template

- Date: 2026-11-24 · Status: accepted · Inherited from the repository template
- Context: a repository on GitHub Free (private ones get a small Actions allowance and no
  branch protection), built by agent sessions that open, review and merge their own PRs.
- Decision: `ci` on pull requests only, always reporting (prose-only changes pass in
  seconds); Dependabot monthly, grouped, with a week of cooldown, its non-major updates
  merged by CI once green; releases published from `CHANGELOG.md` when the version changes,
  starting at 0.1.0 (0.0.0 publishes nothing); one file per decision and per session prompt.
- Rejected: CI on every push to `main` (it repeats the PR's run); weekly Dependabot left
  open for a monthly session (each rebase re-runs CI); GitHub auto-merge (needs branch
  protection, unavailable to private repositories on Free).
- Cost: one CI run per pull request plus about two short runs per Dependabot batch.

Copyright (c) 2026 Almoon-D. All rights reserved.
