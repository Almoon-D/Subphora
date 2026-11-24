// Copyright (c) 2026 Almoon-D. All rights reserved.
import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import type { MapConfig } from "../api.ts";
import {
  answersTap,
  describeOverlays,
  describeRegional,
  initialLayers,
  overlaysByGroup,
  overlayTiles,
  queryableOverlays,
  reachesZoom,
  scaleOf,
  withOverlay,
} from "./layers.ts";

const MAP = JSON.parse(readFileSync(new URL("../../e2e/fixtures/map.json", import.meta.url), "utf-8")) as MapConfig;

function overlay(id: string) {
  const found = MAP.overlays.find((o) => o.id === id);
  if (!found) {
    throw new Error(`no overlay ${id}`);
  }
  return found;
}

describe("initialLayers", () => {
  it("starts on the first base map with the configured states", () => {
    const layers = initialLayers(MAP);
    expect(layers.base).toBe("pnoa");
    expect(layers.cadastre).toEqual({ visible: true, opacity: 1 });
    expect(layers.overlays["groundwater-bodies"]).toEqual({ visible: false, opacity: 0.5 });
  });

  it("refuses a configuration without a base map", () => {
    expect(() => initialLayers({ ...MAP, base_maps: [] })).toThrow("no base map");
  });
});

describe("withOverlay", () => {
  it("changes one overlay and leaves the rest", () => {
    const layers = initialLayers(MAP);
    const changed = withOverlay(layers, "rivers", { visible: true });
    expect(changed.overlays.rivers).toEqual({ visible: true, opacity: 0.9 });
    expect(changed.overlays.springs).toEqual(layers.overlays.springs);
    expect(layers.overlays.rivers?.visible).toBe(false);
  });

  it("ignores an unknown overlay", () => {
    const layers = initialLayers(MAP);
    expect(withOverlay(layers, "nope", { visible: true })).toBe(layers);
  });
});

describe("overlayTiles", () => {
  it("makes the proxy's route absolute and leaves a service's URL alone", () => {
    expect(overlayTiles(overlay("lithostratigraphy"), "http://localhost:5173")).toEqual([
      "http://localhost:5173/api/layers/lithostratigraphy/tiles/{z}/{x}/{y}",
    ]);
    const [rivers] = overlayTiles(overlay("rivers"), "http://localhost:5173");
    expect(rivers).toMatch(/^https:\/\/gis\.miteco\.gob\.es\/.*BBOX=\{bbox-epsg-3857\}$/);
  });
});

// Santiago de Compostela, and Tafalla (Navarra), where the regional soil map answers taps.
const SANTIAGO = [-8.545, 42.881] as const;
const TAFALLA = [-1.7, 42.55] as const;

describe("queryableOverlays", () => {
  it("asks only the layers switched on, drawn at the zoom, with feature info", () => {
    let layers = initialLayers(MAP);
    expect(queryableOverlays(MAP, layers, ...SANTIAGO, 16)).toEqual([]);
    for (const id of ["rivers", "water-points", "soil-clay"]) {
      layers = withOverlay(layers, id, { visible: true });
    }
    expect(queryableOverlays(MAP, layers, ...SANTIAGO, 16).map((o) => o.id)).toEqual(["rivers", "water-points"]);
    // Water points are drawn from zoom 15; SoilGrids answers no value.
    expect(queryableOverlays(MAP, layers, ...SANTIAGO, 12).map((o) => o.id)).toEqual(["rivers"]);
    // In Navarra the regional soil map answers a tap from its own zoom.
    expect(queryableOverlays(MAP, layers, ...TAFALLA, 16).map((o) => o.id)).toEqual([
      "rivers",
      "water-points",
      "soil-clay",
    ]);
  });
});

describe("answersTap", () => {
  it("lets a regional layer answer only inside its bounds and from its zoom", () => {
    const soils = overlay("soil-clay");
    expect(answersTap(soils, ...TAFALLA, 12)).toBe(true);
    expect(answersTap(soils, ...TAFALLA, 11)).toBe(false);
    expect(answersTap(soils, ...SANTIAGO, 16)).toBe(false);
  });
});

describe("scaleOf", () => {
  it("names the scale, the grid cell or nothing", () => {
    expect(scaleOf(overlay("hydrogeology").detail)).toEqual({ kind: "scale", value: 200000 });
    expect(scaleOf(overlay("soil-clay").detail)).toEqual({ kind: "cell", value: 250 });
    expect(scaleOf(overlay("springs").detail)).toBeNull();
  });
});

describe("describeRegional", () => {
  it("lists the regional layers of the themes switched on", () => {
    const layers = withOverlay(initialLayers(MAP), "soil-clay", { visible: true });
    expect(describeRegional(MAP, initialLayers(MAP))).toBe("");
    expect(describeRegional(MAP, layers)).toBe("navarra-soils catalonia-soils");
  });
});

describe("reachesZoom", () => {
  it("starts at the layer's minimum zoom", () => {
    expect(reachesZoom(overlay("magna-dip"), 12.9)).toBe(false);
    expect(reachesZoom(overlay("magna-dip"), 13)).toBe(true);
  });
});

describe("overlaysByGroup", () => {
  it("keeps the groups' and the layers' order", () => {
    const groups = overlaysByGroup(MAP);
    expect(groups.map(([group]) => group)).toEqual(["water", "geology", "soil"]);
    expect(groups[2]?.[1].map((o) => o.id)).toEqual(["soil-clay"]);
  });
});

describe("describeOverlays", () => {
  it("lists the drawn overlays with their opacity", () => {
    let layers = initialLayers(MAP);
    expect(describeOverlays(MAP, layers)).toBe("");
    layers = withOverlay(withOverlay(layers, "rivers", { visible: true, opacity: 0.3 }), "groundwater-bodies", {
      visible: true,
    });
    expect(describeOverlays(MAP, layers)).toBe("groundwater-bodies:0.5 rivers:0.3");
  });
});
