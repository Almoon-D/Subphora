# Session 10 — Offline map packs

Model and effort: Opus 5.5, high.

## Goal

Before going to an estate, the owner downloads a pack for the selected parcels (PNOA and
cadastral tiles, our index and confidence layers, the parcel geometry, the candidates) and
the map works there with no coverage.

## Read

- `docs/MASTER_PLAN.md` § 4.6.
- `docs/knowledge/` IGN/CNIG and Catastro (caching terms), and decision 0005.

## Build

1. Pack definition: area plus buffer, zoom range and size limit from `config/`, a size
   estimate before download, progress, resume after interruption.
2. Storage via the service worker with persistent storage requested; the list of packs, their
   size and date; delete.
3. Google layers never included (hard rule 4); layers whose terms forbid caching excluded,
   per the knowledge files.
4. Tests: pack size estimate, interrupted download resumed, the map served offline from the
   pack, Google excluded, storage refusal handled.

## DO NOT BUILD

- Background sync beyond session 09's outbox; deployment.

## Done when

- `make check` is green and in `make dev` a downloaded pack shows the parcel with the browser
  offline.
