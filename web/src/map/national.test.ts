// Copyright (c) 2026 Almoon-D. All rights reserved.
import { describe, expect, it } from "vitest";

import type { InputValue, NationalMap } from "../api.ts";
import type { MapLayers } from "./layers.ts";
import { describeNational, formatQuantity, legendText, nationalAnswersTap, percent, valueText } from "./national.ts";

const NATIONAL: NationalMap = {
  kind: "index",
  built: true,
  rendered_at: "2026-11-25T10:00:00Z",
  bounds: [-1, 41, 0, 42],
  regions: [{ id: "ES-Z", name: "Zaragoza", bbox: [-1, 41, 0, 42], built_at: "2026-11-25T10:00:00Z" }],
  layers: [
    {
      id: "potential-index",
      variable: "index",
      tiles: ["/api/national/tiles/potential-index/{z}/{x}/{y}"],
      min_zoom: 5,
      max_zoom: 11,
      tile_size: 256,
      opacity: 0.65,
      visible: true,
      unit: "index",
      legend: [],
    },
    {
      id: "terrain-slope",
      variable: "slope_deg",
      tiles: ["/api/national/tiles/terrain-slope/{z}/{x}/{y}"],
      min_zoom: 5,
      max_zoom: 11,
      tile_size: 256,
      opacity: 0.7,
      visible: false,
      unit: "deg",
      legend: [],
    },
  ],
  attributions: ["IGME"],
};

function layers(visible: Record<string, boolean>): MapLayers {
  return {
    base: "pnoa",
    cadastre: { visible: false, opacity: 1 },
    overlays: {},
    national: Object.fromEntries(Object.entries(visible).map(([id, on]) => [id, { visible: on, opacity: 1 }])),
  };
}

const value = (change: Partial<InputValue>): InputValue => ({
  number: null,
  unit: null,
  at_least: false,
  category: null,
  label: null,
  absent: false,
  ...change,
});

describe("the national map in the browser", () => {
  it("names the layers drawn, and none before a build", () => {
    const on = layers({ "potential-index": true, "terrain-slope": true });
    expect(describeNational(NATIONAL, on)).toBe("potential-index terrain-slope");
    expect(describeNational({ ...NATIONAL, built: false }, on)).toBe("");
    expect(describeNational(null, on)).toBe("");
  });

  it("asks for an explanation only with a layer on and inside a region built", () => {
    const on = layers({ "potential-index": true });
    expect(nationalAnswersTap(NATIONAL, on, -0.5, 41.5)).toBe(true);
    expect(nationalAnswersTap(NATIONAL, on, -3.7, 40.4)).toBe(false);
    expect(nationalAnswersTap(NATIONAL, layers({ "potential-index": false }), -0.5, 41.5)).toBe(false);
    expect(nationalAnswersTap({ ...NATIONAL, built: false }, on, -0.5, 41.5)).toBe(false);
    expect(nationalAnswersTap(null, on, -0.5, 41.5)).toBe(false);
  });

  it("writes quantities in their units", () => {
    expect(formatQuantity(0.6234, "index")).toBe("0,62");
    expect(formatQuantity(12.4, "deg")).toBe("12°");
    expect(formatQuantity(250, "m")).toBe("250 m");
    expect(formatQuantity(2000, "m")).toBe("2,0 km");
    expect(formatQuantity(31.6, "pct")).toBe("32 %");
    expect(formatQuantity(9.2, "twi")).toBe("9");
    expect(percent(0.25)).toBe("25 %");
  });

  it("writes legend classes as ranges", () => {
    expect(legendText({ min: null, max: 0.2, colour: "#000000" }, "index")).toBe("< 0,20");
    expect(legendText({ min: 0.2, max: 0.4, colour: "#000000" }, "index")).toBe("0,20 – 0,40");
    expect(legendText({ min: 30, max: null, colour: "#000000" }, "deg")).toBe("≥ 30°");
    expect(legendText({ min: null, max: null, colour: "#000000" }, "deg")).toBe("");
  });

  it("writes an input's value, absent and at least", () => {
    expect(valueText(value({ category: "ALTA", label: "CARBONATADAS-ALTA" }))).toBe("ALTA (CARBONATADAS-ALTA)");
    expect(valueText(value({ category: "Bueno", label: "Bueno" }))).toBe("Bueno");
    expect(valueText(value({ absent: true }))).toBe("fuera de toda masa de agua subterránea");
    expect(valueText(value({ number: 10_000, unit: "m", at_least: true }))).toBe("al menos 10,0 km");
    expect(valueText(value({ number: 3, unit: "deg" }))).toBe("3°");
    expect(valueText(value({}))).toBe("");
  });
});
