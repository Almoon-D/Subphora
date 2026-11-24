// Copyright (c) 2026 Almoon-D. All rights reserved.
import { describe, expect, it } from "vitest";

import type { AreaBoundary } from "../api.ts";
import { boxesMeet, clipTemplate, parseClipUrl, ringsInTile, tileBox, toTilePixel } from "./clip.ts";

function square(id: string, west: number, south: number, east: number, north: number): AreaBoundary {
  return {
    id,
    kind: "region",
    bbox: [west, south, east, north],
    geometry: {
      type: "MultiPolygon",
      coordinates: [
        [
          [
            [west, south],
            [east, south],
            [east, north],
            [west, north],
            [west, south],
          ],
        ],
      ],
    },
    source: { service_id: "ign-admin-units", publisher: "IGN", attribution: "IGN", retrieved_at: "2026-11-24T10:00:00Z" },
    grid_deg: 0.0001,
  };
}

describe("clip URLs", () => {
  it("keep the tile's place for MapLibre to fill in, and the layer's own URL", () => {
    const template = clipTemplate(["ES060", "ES063"], 256, "https://example.org/wms?BBOX={bbox-epsg-3857}");
    expect(template).toBe("subphora-clip://ES060,ES063/256/{z}/{x}/{y}/https://example.org/wms?BBOX={bbox-epsg-3857}");
    const filled = template.replace("{z}", "12").replace("{x}", "2025").replace("{y}", "1547").replace("{bbox-epsg-3857}", "1,2,3,4");
    expect(parseClipUrl(filled)).toEqual({
      areaIds: ["ES060", "ES063"],
      size: 256,
      z: 12,
      x: 2025,
      y: 1547,
      source: "https://example.org/wms?BBOX=1,2,3,4",
    });
  });

  it("refuse anything else", () => {
    expect(parseClipUrl("https://example.org/tile.png")).toBeNull();
    expect(parseClipUrl("subphora-clip://ES-NC/256/z/1/2/https://x")).toBeNull();
  });
});

describe("tile geometry", () => {
  it("places the corners of a tile on its pixel edges", () => {
    const [west, south, east, north] = tileBox(12, 2025, 1547);
    const [x0, y0] = toTilePixel(west, north, 12, 2025, 1547, 256);
    const [x1, y1] = toTilePixel(east, south, 12, 2025, 1547, 256);
    expect(x0).toBeCloseTo(0, 6);
    expect(y0).toBeCloseTo(0, 6);
    expect(x1).toBeCloseTo(256, 6);
    expect(y1).toBeCloseTo(256, 6);
  });

  it("tells boxes that meet from boxes apart", () => {
    expect(boxesMeet([0, 0, 1, 1], [1, 1, 2, 2])).toBe(true);
    expect(boxesMeet([0, 0, 1, 1], [1.1, 0, 2, 1])).toBe(false);
  });
});

describe("ringsInTile", () => {
  const tile = { z: 10, x: 506, y: 378 };

  it("keeps only the areas that reach the tile, in its pixels", () => {
    const [west, south, east, north] = tileBox(tile.z, tile.x, tile.y);
    const middle = (west + east) / 2;
    const inside = square("A", west - 1, south - 1, middle, north + 1);
    const away = square("B", east + 1, south, east + 2, north);
    const rings = ringsInTile([inside, away], tile.z, tile.x, tile.y, 256);
    expect(rings).toHaveLength(1);
    const xs = rings[0]?.map(([px]) => px) ?? [];
    // The area covers the tile's western half: its eastern edge is at pixel 128.
    expect(Math.max(...xs)).toBeCloseTo(128, 6);
  });

  it("gives nothing for a tile outside every area: the layer is not asked", () => {
    const [, , east, north] = tileBox(tile.z, tile.x, tile.y);
    expect(ringsInTile([square("B", east + 1, north + 1, east + 2, north + 2)], tile.z, tile.x, tile.y, 256)).toEqual([]);
  });

  it("puts a border shared by two areas on the same pixels in both", () => {
    const [west, south, east, north] = tileBox(tile.z, tile.x, tile.y);
    const middle = (west + east) / 2;
    const left = ringsInTile([square("A", west - 1, south - 1, middle, north + 1)], tile.z, tile.x, tile.y, 256);
    const right = ringsInTile([square("B", middle, south - 1, east + 1, north + 1)], tile.z, tile.x, tile.y, 256);
    const edge = (rings: [number, number][][], pick: (xs: number[]) => number) => pick(rings[0]?.map(([px]) => px) ?? []);
    expect(edge(left, (xs) => Math.max(...xs))).toBe(edge(right, (xs) => Math.min(...xs)));
  });
});
