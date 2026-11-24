# 0004 — One PWA (React, MapLibre) and a FastAPI backend

- Date: 2026-11-24 · Status: accepted · MASTER_PLAN §4.1–4.2
- Context: PC and phone (Android first), GPS, offline use, heavy raster work in Python, few users.
- Decision: a progressive web app in TypeScript (Vite, React, MapLibre GL JS) with IndexedDB and a
  service worker for offline use; a Python FastAPI server for data, model and reports; SQLite
  and a file cache for storage.
- Rejected: native Android and iOS apps (two code bases and store publishing for what a PWA
  has); Leaflet (raster-only, no rotation, weaker with many overlays); OpenLayers (heavier on
  the phone); Svelte or plain TypeScript (less tooling for the field UI); PostGIS (one more
  server to run and back up for a handful of users).
- Risk: iOS may evict storage of an unused PWA: field data is synced and exportable.
