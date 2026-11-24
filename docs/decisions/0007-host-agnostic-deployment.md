# 0007 — Host-agnostic deployment, host chosen in session 13

- Date: 2026-11-24 · Status: accepted · MASTER_PLAN §3, §4.9
- Context: the owner accepts any cheap host: a free tier, a cheap paid server, or a machine
  they buy.
- Decision: package the app as Docker Compose (API, Caddy for HTTPS and the static PWA) for any
  Linux host, x86-64 or ARM64. Until session 13 it runs locally (`make dev`). Session 13 puts
  the options (such as Oracle Cloud Always Free, a server of about €5 a month, or a home mini
  PC) and their costs to the owner, who chooses.
- Rejected: choosing Oracle Cloud now (free capacity and idle-instance reclaim are uncertain);
  a serverless platform (heavy raster work and a long-lived cache fit poorly).
- Cost: zero until session 13; then the owner's choice.

Copyright (c) 2026 Almoon-D. All rights reserved.
