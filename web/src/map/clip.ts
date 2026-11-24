// Copyright (c) 2026 Almoon-D. All rights reserved.
// A regional layer is drawn only inside its areas (decision 0023): its tiles come through
// a MapLibre protocol that fetches the layer's own tile and keeps only the pixels inside
// the areas' official boundaries. Every area is rounded to one shared grid by the server,
// so neighbouring areas meet without gaps or overlaps, and the national layer beneath
// shows everywhere else.
import type { AreaBoundary } from "../api.ts";

export const CLIP_PROTOCOL = "subphora-clip";

type Box = readonly [number, number, number, number];
type PixelRing = [number, number][];

export interface ClipRequest {
  areaIds: string[];
  size: number;
  z: number;
  x: number;
  y: number;
  /** The layer's own tile URL, its placeholders already filled in by MapLibre. */
  source: string;
}

/** The tile template MapLibre fills in: our prefix keeps {z}/{x}/{y} for the clip. */
export function clipTemplate(areaIds: readonly string[], size: number, template: string): string {
  return `${CLIP_PROTOCOL}://${areaIds.map(encodeURIComponent).join(",")}/${String(size)}/{z}/{x}/{y}/${template}`;
}

const CLIP_URL = new RegExp(`^${CLIP_PROTOCOL}://([^/]+)/(\\d+)/(\\d+)/(\\d+)/(\\d+)/(.+)$`);

export function parseClipUrl(url: string): ClipRequest | null {
  const match = CLIP_URL.exec(url);
  if (!match) {
    return null;
  }
  const [, areas = "", size = "", z = "", x = "", y = "", source = ""] = match;
  return {
    areaIds: areas.split(",").map(decodeURIComponent),
    size: Number(size),
    z: Number(z),
    x: Number(x),
    y: Number(y),
    source,
  };
}

/** Web Mercator: (lon, lat) in the pixels of tile (z, x, y) of `size` pixels. */
export function toTilePixel(lon: number, lat: number, z: number, x: number, y: number, size: number): [number, number] {
  const scale = 2 ** z * size;
  const sin = Math.sin((lat * Math.PI) / 180);
  const worldX = ((lon + 180) / 360) * scale;
  const worldY = (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * scale;
  return [worldX - x * size, worldY - y * size];
}

/** West, south, east, north of tile (z, x, y) in degrees. */
export function tileBox(z: number, x: number, y: number): Box {
  const n = 2 ** z;
  const lon = (col: number) => (col / n) * 360 - 180;
  const lat = (row: number) => (Math.atan(Math.sinh(Math.PI * (1 - (2 * row) / n))) * 180) / Math.PI;
  return [lon(x), lat(y + 1), lon(x + 1), lat(y)];
}

export function boxesMeet(a: Box, b: Box): boolean {
  return a[0] <= b[2] && b[0] <= a[2] && a[1] <= b[3] && b[1] <= a[3];
}

function ringBox(ring: readonly (readonly [number, number])[]): Box {
  let [west, south, east, north] = [Infinity, Infinity, -Infinity, -Infinity];
  for (const [lon, lat] of ring) {
    west = Math.min(west, lon);
    east = Math.max(east, lon);
    south = Math.min(south, lat);
    north = Math.max(north, lat);
  }
  return [west, south, east, north];
}

/** The rings of every polygon of the areas that reaches the tile, in its pixels. */
export function ringsInTile(areas: readonly AreaBoundary[], z: number, x: number, y: number, size: number): PixelRing[] {
  const tile = tileBox(z, x, y);
  const rings: PixelRing[] = [];
  for (const area of areas) {
    if (!boxesMeet(area.bbox, tile)) {
      continue;
    }
    for (const polygon of area.geometry.coordinates) {
      const [outer] = polygon;
      if (!outer || !boxesMeet(ringBox(outer), tile)) {
        continue;
      }
      for (const ring of polygon) {
        rings.push(ring.map(([lon, lat]) => toTilePixel(lon, lat, z, x, y, size)));
      }
    }
  }
  return rings;
}

type LoadArea = (areaId: string) => Promise<AreaBoundary>;

async function png(canvas: OffscreenCanvas): Promise<ArrayBuffer> {
  return (await canvas.convertToBlob({ type: "image/png" })).arrayBuffer();
}

/** The protocol's handler: the layer's tile, cleared outside the areas. A tile outside
 * every area, or in an area whose boundary could not be read, is a transparent one (the
 * national layer shows beneath; `loadArea` reports the failure), and the layer's service is
 * not asked for it. */
export function clipHandler(loadArea: LoadArea, fetchFn: typeof fetch = fetch) {
  return async (params: { url: string }, abort: AbortController): Promise<{ data: ArrayBuffer }> => {
    const request = parseClipUrl(params.url);
    if (!request) {
      throw new Error(`not a clipped tile: ${params.url}`);
    }
    const { size, z, x, y } = request;
    const settled = await Promise.allSettled(request.areaIds.map(loadArea));
    const areas = settled.flatMap((result) => (result.status === "fulfilled" ? [result.value] : []));
    const rings = ringsInTile(areas, z, x, y, size);
    const canvas = new OffscreenCanvas(size, size);
    // A canvas encodes only once it has a context, even a blank one.
    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("no 2D canvas");
    }
    if (rings.length === 0) {
      return { data: await png(canvas) };
    }
    const response = await fetchFn(request.source, { signal: abort.signal });
    if (!response.ok) {
      throw new Error(`the tile answered ${String(response.status)}`);
    }
    const image = await createImageBitmap(await response.blob());
    const path = new Path2D();
    for (const ring of rings) {
      ring.forEach(([px, py], index) => {
        if (index === 0) {
          path.moveTo(px, py);
        } else {
          path.lineTo(px, py);
        }
      });
      path.closePath();
    }
    context.clip(path, "evenodd");
    context.drawImage(image, 0, 0, size, size);
    image.close();
    return { data: await png(canvas) };
  };
}
