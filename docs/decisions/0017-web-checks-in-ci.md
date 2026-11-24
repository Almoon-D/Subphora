# 0017 — The front end's checks run in CI

- Date: 2026-11-24 · Status: accepted · MASTER_PLAN §4.1
- Decision: the `ci` job sets up Node from `.nvmrc` (npm cache) and Playwright's Chromium
  with its system libraries, then `make check` runs ESLint, tsc, Vitest, the build and
  Playwright. No new job, matrix or schedule; prose-only pull requests still skip it all.
- Cost: ~2.5 more minutes per code run; at ~30 runs a month, ~75 minutes of the 2,000 free
  ones of a private repository on GitHub Free (none on a public one).
- Rejected: a separate web job (a second runner start per run); caching the browser (its
  system libraries are installed anyway).

Copyright (c) 2026 Almoon-D. All rights reserved.
