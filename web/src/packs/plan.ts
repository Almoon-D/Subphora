// Copyright (c) 2026 Almoon-D. All rights reserved.
// What an offline pack holds (MASTER_PLAN §4.7, decision 0037): for one area, the base-map
// tiles over its box and a buffer at the zooms of packs.yaml, our index and confidence
// layers (the national tiles and the detailed map's images), the API answers the page
// reads there, the area's geometry and its candidate spots; and every map layer it does
// not hold, with the reason. Only layers whose terms allow storing them are planned (hard
// rule 4): the Catastro map never, the parcel's geometry from the WFS instead.
import {
  type AreaOfInterest,
  type MapConfig,
  type NationalMap,
  type ExcludedLayer,
  legalPath,
  type PacksConfig,
  type ParcelAnswer,
  parcelPath,
} from "../api.ts";
import { widen } from "../field/geodesy.ts";
import { overlayTiles } from "../map/layers.ts";

export type Box = readonly [number, number, number, number];

/** The web-mercator tile scheme stops at this latitude. */
const MERCATOR_MAX_LATITUDE = 85.0511287798066;

export type FileKind = "base" | "national" | "image" | "data";

export interface PackFile {
  url: string;
  kind: FileKind;
  /** The layer it belongs to (a base map, a national layer), or the API answer it is. */
  layer: string;
}

/** Something a pack leaves out, and why. A map layer: its terms (forbidden, or not read
 * for this use) or packs.yaml; the area's own data: not storable, not computed or built. */
export interface Exclusion {
  id: string;
  kind: ExcludedLayer["kind"] | "geometry" | "detailed" | "national";
  reason: ExcludedLayer["reason"] | "not_storable" | "not_computed" | "not_built" | "outside_built";
}

export interface PackPlan {
  label: string;
  /** West, south, east, north: the area's box (and its detailed map's) and the buffer. */
  box: Box;
  min_zoom: number;
  max_zoom: number;
  files: PackFile[];
  /** Files per layer, for the summary. */
  counts: Record<string, number>;
  estimate_bytes: number;
  /** Null when the area's geometry cannot be stored. */
  area: AreaOfInterest | null;
  /** The finished detailed map, with its candidates; null when there is none. */
  answer: ParcelAnswer | null;
  excluded: Exclusion[];
  /** Above packs.yaml's max_bytes: refused before anything is downloaded. */
  too_large: boolean;
}

/** The tile column and row holding a point at a zoom, in the XYZ web-mercator scheme. */
export function tileAt(lon: number, lat: number, zoom: number): { x: number; y: number } {
  const n = 2 ** zoom;
  const clamped = Math.max(-MERCATOR_MAX_LATITUDE, Math.min(MERCATOR_MAX_LATITUDE, lat));
  const radians = (clamped * Math.PI) / 180;
  const x = Math.floor(((lon + 180) / 360) * n);
  const y = Math.floor(((1 - Math.asinh(Math.tan(radians)) / Math.PI) / 2) * n);
  return { x: Math.min(n - 1, Math.max(0, x)), y: Math.min(n - 1, Math.max(0, y)) };
}

/** Every tile over a box at a zoom. */
export function tilesOver(box: Box, zoom: number): { z: number; x: number; y: number }[] {
  const [west, south, east, north] = box;
  const topLeft = tileAt(west, north, zoom);
  const bottomRight = tileAt(east, south, zoom);
  const tiles: { z: number; x: number; y: number }[] = [];
  for (let x = topLeft.x; x <= bottomRight.x; x += 1) {
    for (let y = topLeft.y; y <= bottomRight.y; y += 1) {
      tiles.push({ z: zoom, x, y });
    }
  }
  return tiles;
}

/** The zooms stored of a layer drawn from `layerMin` to `layerMax`: the pack's range within
 * the layer's, and at least the layer's deepest level, which the map enlarges beyond it. */
export function zoomsOf(pack: Pick<PacksConfig, "min_zoom" | "max_zoom">, layerMin: number, layerMax: number): number[] {
  const from = Math.min(Math.max(pack.min_zoom, layerMin), layerMax);
  const to = Math.min(pack.max_zoom, layerMax);
  const zooms: number[] = [];
  for (let zoom = from; zoom <= to; zoom += 1) {
    zooms.push(zoom);
  }
  return zooms;
}

/** A tile's URL exactly as the map asks for it, so that the stored copy answers it. */
export function tileUrl(template: string, tile: { z: number; x: number; y: number }): string {
  return template.replaceAll("{z}", String(tile.z)).replaceAll("{x}", String(tile.x)).replaceAll("{y}", String(tile.y));
}

function intersection(a: Box, b: Box): Box | null {
  const box: Box = [Math.max(a[0], b[0]), Math.max(a[1], b[1]), Math.min(a[2], b[2]), Math.min(a[3], b[3])];
  return box[0] <= box[2] && box[1] <= box[3] ? box : null;
}

/** Whether every source of the area's geometry lets it be stored. */
export function geometryStorable(area: AreaOfInterest, packs: Pick<PacksConfig, "storable_services">): boolean {
  return area.sources.every((source) => packs.storable_services.includes(source.service_id));
}

/** The pack of an area: what it holds, what it leaves out, and its estimated size. */
export function planPack(
  config: MapConfig,
  national: NationalMap | null,
  area: AreaOfInterest,
  answer: ParcelAnswer | null,
  label: string,
  origin: string,
): PackPlan {
  const packs = config.packs;
  const done = answer?.job.analysis ? answer : null;
  // The area, and the detailed map's box around it, with the buffer.
  const analysed = done?.job.analysis?.bbox;
  const covered: Box = analysed
    ? [Math.min(area.bbox[0], analysed[0]), Math.min(area.bbox[1], analysed[1]), Math.max(area.bbox[2], analysed[2]), Math.max(area.bbox[3], analysed[3])]
    : area.bbox;
  const box = widen(covered, packs.buffer_m);
  const files: PackFile[] = [];
  const counts: Record<string, number> = {};
  let estimate = 0;
  const add = (file: PackFile, bytes: number) => {
    files.push(file);
    counts[file.layer] = (counts[file.layer] ?? 0) + 1;
    estimate += bytes;
  };
  const excluded: Exclusion[] = packs.excluded.map((layer) => ({ id: layer.id, kind: layer.kind, reason: layer.reason }));

  for (const chosen of packs.base_maps) {
    const base = config.base_maps.find((b) => b.id === chosen.id);
    // Only listed base maps, whose terms the server checked, are stored.
    for (const template of base ? base.tiles.slice(0, 1) : []) {
      for (const zoom of zoomsOf(packs, 0, base?.max_zoom ?? 0)) {
        for (const tile of tilesOver(box, zoom)) {
          add({ url: tileUrl(template, tile), kind: "base", layer: chosen.id }, chosen.tile_bytes);
        }
      }
    }
  }

  const built = national?.built ? national : null;
  const nationalBox = built?.bounds ? intersection(box, built.bounds) : null;
  if (!built) {
    excluded.push({ id: "national", kind: "national", reason: "not_built" });
  } else if (!nationalBox) {
    excluded.push({ id: "national", kind: "national", reason: "outside_built" });
  } else {
    for (const layer of built.layers.filter((l) => packs.layers.includes(l.id))) {
      for (const template of overlayTiles(layer, origin).slice(0, 1)) {
        for (const zoom of zoomsOf(packs, layer.min_zoom, layer.max_zoom)) {
          for (const tile of tilesOver(nationalBox, zoom)) {
            add({ url: tileUrl(template, tile), kind: "national", layer: layer.id }, packs.national_tile_bytes);
          }
        }
      }
    }
  }

  if (done) {
    for (const layer of done.layers.filter((l) => packs.layers.includes(l.id))) {
      add({ url: `${origin}${layer.image}`, kind: "image", layer: layer.id }, packs.parcel_image_bytes);
    }
    add({ url: `${origin}${parcelPath(done.job.id)}`, kind: "data", layer: "parcel" }, 0);
  } else {
    excluded.push({ id: "detailed", kind: "detailed", reason: "not_computed" });
  }

  // What the page asks for when it opens and when the area is selected: small answers,
  // left out of the estimate and counted once stored.
  add({ url: `${origin}/api/map`, kind: "data", layer: "map" }, 0);
  add({ url: `${origin}/api/national`, kind: "data", layer: "map" }, 0);
  add({ url: `${origin}${legalPath(area.centre[0], area.centre[1], area.region_code)}`, kind: "data", layer: "legal" }, 0);

  const storable = geometryStorable(area, packs);
  if (!storable) {
    excluded.push({ id: "geometry", kind: "geometry", reason: "not_storable" });
  }
  return {
    label,
    box,
    min_zoom: packs.min_zoom,
    max_zoom: packs.max_zoom,
    files,
    counts,
    estimate_bytes: estimate,
    area: storable ? area : null,
    answer: done,
    excluded,
    too_large: estimate > packs.max_bytes,
  };
}
