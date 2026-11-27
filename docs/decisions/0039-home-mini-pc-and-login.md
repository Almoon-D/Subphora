# 0039 — A home mini PC behind Caddy; sessions in SQLite; backups read back every night

- Date: 2026-11-27 · Status: accepted · MASTER_PLAN §3 (Hosting), §4.9; decision 0007
- Choice (owner, 2026-11-27): a mini PC at home (about €150 once, €1–3 a month of power),
  over Oracle Cloud Always Free (halved to 2 OCPU / 12 GB in June 2026, idle reclaim) and
  Hetzner CAX11 (about €7 a month with VAT). A free DuckDNS name follows the home address.
- Decision: `deploy/compose.yaml` runs the API, Caddy (automatic HTTPS, the PWA, `/sw.js`
  and the page `no-cache`) and a nightly backup, as the owner's own user. Login: users added
  by `subphora users`, scrypt hashes, a random session token kept only as its SHA-256,
  cookie HttpOnly + Secure + SameSite=Lax, a per-name lockout; every route but the login and
  `/api/health` refuses without a session. Backups: a `.tar.gz` of `data/` minus the cache,
  SQLite copied by its backup API, a SHA-256 manifest, read back in full before old ones go.
- Rejected: a VPN or tunnel (another account and app on every phone); passlib or argon2
  (stdlib scrypt is enough for a few users); building images in CI (≈10 min a run).
- Cost: zero recurring; DuckDNS is free. CI unchanged.

Copyright (c) 2026 Almoon-D. All rights reserved.
