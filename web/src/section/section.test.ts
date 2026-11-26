// Copyright (c) 2026 Almoon-D. All rights reserved.
import { describe, expect, it } from "vitest";

import { readFileSync } from "node:fs";

import type { Contact, CrossSection, FaultCrossing, WaterTablePoint } from "../api.ts";
import {
  contactLine,
  exaggeration,
  faultBlock,
  pick,
  unitColour,
  verticalRange,
  waterTableStretches,
  withinReach,
} from "./section.ts";

// POST /api/section on the synthetic Spain (e2e/fixtures/README.md).
const SECTION = JSON.parse(
  readFileSync(new URL("../../e2e/fixtures/section-daimiel.json", import.meta.url), "utf-8"),
) as CrossSection;

function contact(state: Contact["state"], apparent: number | null, at = 100, ground = 500): Contact {
  return {
    distance_m: at,
    ground_m: ground,
    before: 0,
    after: 1,
    state,
    apparent_dip_deg: apparent,
    measurement: null,
    measurement_m: null,
  };
}

describe("exaggeration", () => {
  it("compares the drawing's scale for heights with its scale for lengths", () => {
    // 1000 px for 1000 m, 100 px for 10 m: heights ten times larger.
    expect(exaggeration(1000, 100, 1000, 10)).toBeCloseTo(10);
    expect(exaggeration(1000, 1000, 1000, 1000)).toBeCloseTo(1);
    expect(exaggeration(0, 100, 1000, 10)).toBe(1);
  });
});

describe("verticalRange", () => {
  it("runs from the section's depth under the lowest ground to above the highest", () => {
    const { bottom, top } = verticalRange(SECTION);
    const grounds = SECTION.profile.map((p) => p.ground_m ?? 0);
    expect(bottom).toBeCloseTo(Math.min(...grounds) - SECTION.depth_m);
    expect(top).toBeGreaterThan(Math.max(...grounds));
  });
});

describe("contactLine", () => {
  const faults: FaultCrossing[] = [{ distance_m: 300, kind: "Falla conocida" }];

  it("follows the apparent dip down to the bottom", () => {
    const [start, end] = contactLine(contact("projected", 45), [], 1000, 400);
    expect(start).toEqual([100, 500]);
    expect(end[0]).toBeCloseTo(200);
    expect(end[1]).toBe(400);
  });

  it("stops at the fault of its block", () => {
    const [, end] = contactLine(contact("projected", 10), faults, 1000, 0);
    expect(end[0]).toBe(300);
    expect(end[1]).toBeCloseTo(500 - 200 * Math.tan(Math.PI / 18));
    const [, before] = contactLine(contact("projected", -10), faults, 1000, 0);
    expect(before[0]).toBe(0);
  });

  it("draws an unprojected contact vertical", () => {
    expect(contactLine(contact("not_projected", null), faults, 1000, 0)).toEqual([
      [100, 500],
      [100, 0],
    ]);
  });

  it("finds the fault block of a distance", () => {
    expect(faultBlock(faults, 100, 1000)).toEqual([0, 300]);
    expect(faultBlock(faults, 400, 1000)).toEqual([300, 1000]);
  });
});

describe("waterTableStretches", () => {
  it("breaks the line where the water table is unknown", () => {
    const table = { elevation_m: 1, low_m: 0, high_m: 2, body: "B", body_label: "B", piezometers: 1, nearest_m: 1 };
    const known = (d: number): WaterTablePoint => ({ distance_m: d, state: "estimated", reason: null, water_table: table });
    const unknown = (d: number): WaterTablePoint => ({
      distance_m: d,
      state: "unknown",
      reason: "outside_bodies",
      water_table: null,
    });
    const stretches = waterTableStretches([known(0), known(1), unknown(2), known(3)]);
    expect(stretches.map((s) => s.map((p) => p.distance_m))).toEqual([[0, 1], [3]]);
  });
});

describe("pick", () => {
  it("picks the fault, the borehole and the cell under a tap", () => {
    const [fault] = SECTION.faults;
    const [borehole] = SECTION.boreholes;
    const column = SECTION.columns[2];
    expect(fault && borehole && column && column.ground_m !== null).toBe(true);
    if (!fault || !borehole || !column || column.ground_m === null || borehole.ground_m === null) {
      return;
    }
    expect(pick(SECTION, fault.distance_m, column.ground_m - 50, 5, 1)?.kind).toBe("fault");
    expect(pick(SECTION, borehole.distance_m, borehole.ground_m - 10, 5, 1)?.kind).toBe("borehole");
    const cell = pick(SECTION, column.distance_m, column.ground_m - 5, 1, 0.1);
    expect(cell?.kind).toBe("cell");
    expect(cell?.kind === "cell" && cell.cell.state).toBe("interpreted");
    const deep = pick(SECTION, column.distance_m, column.ground_m - SECTION.depth_m + 5, 1, 0.1);
    expect(deep?.kind === "cell" && deep.cell.state).toBe("unknown");
    expect(pick(SECTION, column.distance_m, column.ground_m + 3, 1, 0.1)?.kind).toBe("above");
  });
});

describe("unitColour", () => {
  it("cycles its colours", () => {
    expect(unitColour(0)).toBe(unitColour(8));
    expect(unitColour(0)).not.toBe(unitColour(1));
  });
});

describe("withinReach", () => {
  it("stops a contact's line where it passes below the evidence's reach", () => {
    const column = SECTION.columns[0];
    if (!column || column.ground_m === null) {
      throw new Error("the fixture has a first column with ground");
    }
    const ground = column.ground_m;
    const line: [[number, number], [number, number]] = [
      [column.distance_m, ground],
      [column.distance_m, ground - 1000],
    ];
    const kept = withinReach(SECTION, line);
    expect(kept?.[1][1]).toBeGreaterThanOrEqual(ground - column.reach_m - 1e-6);
    expect(kept?.[1][1]).toBeLessThan(ground - column.reach_m + 10);
    expect(withinReach(SECTION, [[column.distance_m, ground - 999], [column.distance_m, ground - 1000]])).toBeNull();
  });
});
