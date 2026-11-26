# 0036 — Field records: append-only on the device, an idempotent outbox, SQLite on the server

- Date: 2026-11-26 · Status: accepted · MASTER_PLAN §4.7, hard rule 5
- Decision: a record (note, photo, voice memo, track point) gets a UUIDv7 on the device and
  is written with its file and outbox entry in one IndexedDB transaction (`add`, durability
  "strict") before the page confirms it. Files are kept as bytes with their type (Blob
  support in IndexedDB differs between browsers). The outbox sends batches, then each file
  after its record; the server keeps a record's canonical JSON under its id in SQLite
  (`data/field/`): same id and content is a duplicate, other content a conflict that
  overwrites nothing. A file must match the declared type, size and SHA-256.
- Distances, bearings and the accuracy circle come from GeographicLib, as PROJ's do.
- Rejected: one growing track record (it would be rewritten); Blobs in IndexedDB; deleting
  device records once synced (the device stays a source of truth).

Copyright (c) 2026 Almoon-D. All rights reserved.
