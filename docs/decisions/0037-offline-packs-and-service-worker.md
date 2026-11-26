# 0037 — Offline packs: planned in the browser, stored in Cache Storage, served by a service worker

- Date: 2026-11-26 · Status: accepted · MASTER_PLAN §4.7, hard rule 4
- Decision: each catalogued service says whether its terms allow storing its data offline
  (`offline: allowed | forbidden | not_evaluated`, the default counting as forbidden); the
  settings refuse a pack listing anything else. The browser plans a pack of one area (tiles
  of the configured base maps and our index and confidence over its box plus `buffer_m`, the
  detailed map's images, the API answers it reads), estimates it from `packs.yaml`, refuses it
  above `max_bytes` or the free quota, asks for persistent storage, downloads into one cache
  per pack and keeps the record (area, candidates, progress) in IndexedDB. A hand-written
  service worker serves the app and every stored file network-first with a timeout.
- Rejected: Workbox or vite-plugin-pwa (a build plugin for three routes); downloading in the
  worker (no progress or pause without messaging); Catastro tiles (its terms).

Copyright (c) 2026 Almoon-D. All rights reserved.
