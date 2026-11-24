// Copyright (c) 2026 Almoon-D. All rights reserved.
// The cadastral overlay is one WMS image per view: Catastro forbids tiled requests
// (docs/knowledge/catastro.md). These helpers build that one request.
import type { MapConfig } from "../api.ts";

/** West, south, east, north in EPSG:3857 metres. */
export type MercatorBox = readonly [number, number, number, number];

export interface ImageSize {
  width: number;
  height: number;
}

/** The view's size in image pixels, scaled down so neither side exceeds `maxPx`. */
export function imageSize(cssWidth: number, cssHeight: number, pixelRatio: number, maxPx: number): ImageSize {
  const width = cssWidth * pixelRatio;
  const height = cssHeight * pixelRatio;
  const scale = Math.min(1, maxPx / Math.max(width, height, 1));
  return {
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
  };
}

/** The GetMap URL of one image covering `box` at `size`. */
export function cadastreImageUrl(
  cadastre: MapConfig["cadastre"],
  box: MercatorBox,
  size: ImageSize,
): string {
  const url = new URL(cadastre.url);
  for (const [key, value] of Object.entries(cadastre.params)) {
    url.searchParams.set(key, value);
  }
  // WMS 1.3.0 in EPSG:3857: easting, northing order.
  url.searchParams.set("BBOX", box.map((value) => value.toFixed(2)).join(","));
  url.searchParams.set("WIDTH", String(size.width));
  url.searchParams.set("HEIGHT", String(size.height));
  return url.toString();
}

export function cadastreVisible(cadastre: MapConfig["cadastre"], zoom: number): boolean {
  return zoom >= cadastre.min_zoom;
}
