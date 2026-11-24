# 0009 — Proprietary licence

- Date: 2026-11-24 · Status: accepted · Owner ruling
- Context: a private tool for a family company in a private repository; the template defaulted
  to AGPL-3.0 without a LICENSE file.
- Decision: all rights reserved: `license = "LicenseRef-Proprietary"` and the
  `Private :: Do Not Upload` classifier in `pyproject.toml`; no LICENSE file.
- Rejected: AGPL-3.0 (only useful if the code were shared).
- Note: reusing GPL software (such as OhmPi or pyGIMLi tools) privately, without
  distributing it, stays compatible; any future distribution needs a new decision.

Copyright (c) 2026 Almoon-D. All rights reserved.
