# 0028 — The national build: per-province grids in a process pool, PMTiles served by the API

- Date: 2026-11-25 · Status: accepted · MASTER_PLAN §3 (Runtime, Coordinates), §4.3
- Decision: a region (a province or a box) is read over its box plus a 10 km buffer onto a
  100 m grid aligned to the CRS origin (EPSG:3035; 5635 in the Canaries), computed in a worker
  process, clipped to the IGN boundary and stored as a GeoTIFF with overviews and a manifest.
  The tiles of every region on disk (zoom 5-11) go into one PMTiles archive per layer, served
  by `/api/national/tiles`. Downloads use the catalogue client and file cache; a failed region
  is reported and skipped. Libraries: numpy, scipy, rasterio/GDAL (warp, rasterise), pyflwdir
  and numba (depression filling, D8), Pillow, pmtiles; vector coordinates stay with pyproj.
- Rejected: one national raster in memory (50 M cells x 10 bands); the WCS's own 100 m
  scaling (its resampling is not stated; 25 m cells are averaged here); flow accumulation
  across provinces (catchments beyond the buffer are not counted).

Copyright (c) 2026 Almoon-D. All rights reserved.
