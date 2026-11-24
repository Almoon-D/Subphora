# 0002 — Changes from the external review of the template

- Date: 2026-11-24 · Status: accepted · Inherited from the repository template
- Decision: session 00 plans a new project and every session leaves the next prompt ready;
  one session at a time per repository; a cloud session prepares itself (SessionStart hook
  → `make setup`); Dependabot auto-merge only for updates read as minor or patch (fails
  closed); no dependencies or config keys without a consumer; no pre-commit (it repeats
  `make check`); LF line endings for every text file.
- Rejected: dropping pytest-xdist (≈1 s slower on a tiny suite, a third faster on a grown
  one); trimming AGENTS.md to ~600 words (≈2k tokens a session, small next to the work);
  title-only squash messages (owner's choice: title and description).

Copyright (c) 2026 Almoon-D. All rights reserved.
