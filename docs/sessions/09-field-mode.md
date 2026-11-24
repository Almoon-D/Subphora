# Session 09 — Field mode

Model and effort: Opus 5.5, high.

## Goal

On site, the app shows the user's live position with accuracy on a detailed map, guides them
to a chosen candidate, and records notes, photos, voice memos and the track without coverage,
syncing them later without loss.

## Read

- `docs/MASTER_PLAN.md` § 4.6 and § 3 (Interface).
- AGENTS.md hard rule 5.

## Build

1. A field-mode screen: large controls, high contrast, the position, accuracy circle and
   heading, distance and bearing to the chosen spot, "at the spot" by the §4.6 rule.
2. Observations (note, photo, voice memo) and track, written to IndexedDB before the UI
   confirms; append-only with UUIDv7 ids.
3. Sync: an outbox to an idempotent API endpoint storing records and media in `data/`
   (SQLite plus files); a visible unsynced count; export of unsynced data to a file.
4. Tests: Playwright with emulated geolocation and offline mode: record offline, reload,
   come back online, sync once; a retried sync does not duplicate; the server upsert's
   failure branches.

## DO NOT BUILD

- Offline map packs (session 10); login and deployment (session 12); instrument readings.

## Done when

- `make check` is green and on the laptop (`make dev`) the owner can walk the flow with the
  browser offline and see the records sync when it comes back. On the phone after session 12.
