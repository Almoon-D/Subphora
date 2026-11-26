// Copyright (c) 2026 Almoon-D. All rights reserved.
// The cross-section's drawing arithmetic, kept out of the component so it is tested: the
// vertical range and exaggeration, the projected contacts' lines (stopped at the faults
// on either side), the water table's estimated stretches, and what a tap on the section
// picks (a borehole, a fault, a contact, the water table, else the cell under it).
import type { Borehole, Contact, CrossSection, FaultCrossing, SectionCell, SectionColumn, WaterTablePoint } from "../api.ts";

/** One colour per surface unit, cycled; never the water table's blue or a fault's red. */
export const UNIT_COLOURS = ["#c9a66b", "#8fb573", "#d98f5c", "#a58cc4", "#e3c84f", "#7fa6a1", "#c97f9a", "#9c9c6b"];

export function unitColour(index: number): string {
  return UNIT_COLOURS[index % UNIT_COLOURS.length] ?? "#999999";
}

/** The elevations drawn: from the deepest cell bottom to a little above the highest ground. */
export function verticalRange(section: CrossSection): { bottom: number; top: number } {
  const grounds = section.profile.map((p) => p.ground_m).filter((g): g is number => g !== null);
  if (grounds.length === 0) {
    return { bottom: -section.depth_m, top: 0 };
  }
  const high = Math.max(...grounds);
  const low = Math.min(...grounds);
  const margin = Math.max(5, (high - low + section.depth_m) * 0.05);
  return { bottom: low - section.depth_m, top: high + margin };
}

/** How many times the drawing stretches heights over lengths (1: true scale). */
export function exaggeration(widthPx: number, heightPx: number, lengthM: number, verticalM: number): number {
  if (widthPx <= 0 || heightPx <= 0 || lengthM <= 0 || verticalM <= 0) {
    return 1;
  }
  return heightPx / verticalM / (widthPx / lengthM);
}

/** The block between the faults either side of a distance along the line. */
export function faultBlock(faults: readonly FaultCrossing[], distance: number, length: number): [number, number] {
  let low = 0;
  let high = length;
  for (const fault of faults) {
    if (fault.distance_m <= distance) {
      low = Math.max(low, fault.distance_m);
    } else {
      high = Math.min(high, fault.distance_m);
    }
  }
  return [low, high];
}

/** A contact drawn from the ground down to `bottom`: along its apparent dip when
 * projected, stopped at its fault block's edges; vertical otherwise. */
export function contactLine(
  contact: Contact,
  faults: readonly FaultCrossing[],
  length: number,
  bottom: number,
): [[number, number], [number, number]] {
  const ground = contact.ground_m ?? bottom;
  const start: [number, number] = [contact.distance_m, ground];
  if (contact.state !== "projected" || contact.apparent_dip_deg === null) {
    return [start, [contact.distance_m, bottom]];
  }
  const tangent = Math.tan((contact.apparent_dip_deg * Math.PI) / 180);
  const [low, high] = faultBlock(faults, contact.distance_m, length);
  if (Math.abs(tangent) < 1e-9) {
    return [start, [tangent >= 0 ? high : low, ground]];
  }
  let end: [number, number] = [contact.distance_m + (ground - bottom) / tangent, bottom];
  if (end[0] > high || end[0] < low) {
    const edge = end[0] > high ? high : low;
    end = [edge, ground - (edge - contact.distance_m) * tangent];
  }
  return [start, end];
}

/** A contact's line cut where it passes below the evidence's reach of the column under
 * it: the "unknown" zone is drawn as such, never crossed by an extrapolated line. */
export function withinReach(section: CrossSection, line: [[number, number], [number, number]]): [[number, number], [number, number]] | null {
  const [[x0, y0], [x1, y1]] = line;
  const steps = 200;
  let last: [number, number] | null = null;
  for (let k = 0; k <= steps; k++) {
    const share = k / steps;
    const point: [number, number] = [x0 + share * (x1 - x0), y0 + share * (y1 - y0)];
    const column = section.columns.reduce((best, c) =>
      Math.abs(c.distance_m - point[0]) < Math.abs(best.distance_m - point[0]) ? c : best,
    );
    if (column.ground_m === null || column.ground_m - point[1] > column.reach_m) {
      break;
    }
    last = point;
  }
  return last === null ? null : [line[0], last];
}

/** The runs of consecutive estimated water-table points (a gap where it is unknown). */
export function waterTableStretches(points: readonly WaterTablePoint[]): WaterTablePoint[][] {
  const stretches: WaterTablePoint[][] = [];
  let current: WaterTablePoint[] = [];
  for (const point of points) {
    if (point.state === "estimated") {
      current.push(point);
    } else if (current.length > 0) {
      stretches.push(current);
      current = [];
    }
  }
  if (current.length > 0) {
    stretches.push(current);
  }
  return stretches;
}

export type Picked =
  | { kind: "borehole"; borehole: Borehole }
  | { kind: "fault"; fault: FaultCrossing }
  | { kind: "contact"; contact: Contact }
  | { kind: "water"; point: WaterTablePoint }
  | { kind: "cell"; column: SectionColumn; cell: SectionCell }
  | { kind: "above" };

function nearest<T>(items: readonly T[], distanceOf: (item: T) => number): { item: T; gap: number } | null {
  let best: { item: T; gap: number } | null = null;
  for (const item of items) {
    const gap = distanceOf(item);
    if (best === null || gap < best.gap) {
      best = { item, gap };
    }
  }
  return best;
}

/** What a tap at (distance, elevation) points at; `along` and `up` are how near (in
 * metres along the line and in height) a mark must be to be picked before the cell. */
export function pick(section: CrossSection, distance: number, elevation: number, along: number, up: number): Picked | null {
  const borehole = nearest(section.boreholes, (b) => Math.abs(b.distance_m - distance));
  if (borehole && borehole.gap <= along) {
    const ground = borehole.item.ground_m;
    if (ground === null || (elevation <= ground + up && elevation >= ground - borehole.item.depth_m - up)) {
      return { kind: "borehole", borehole: borehole.item };
    }
  }
  const water = nearest(
    section.water_table.filter((p) => p.water_table !== null),
    (p) => Math.abs(p.distance_m - distance),
  );
  if (water?.item.water_table && water.gap <= along && Math.abs(water.item.water_table.elevation_m - elevation) <= up) {
    return { kind: "water", point: water.item };
  }
  const fault = nearest(section.faults, (f) => Math.abs(f.distance_m - distance));
  if (fault && fault.gap <= along) {
    return { kind: "fault", fault: fault.item };
  }
  const { bottom } = verticalRange(section);
  const contact = nearest(section.contacts, (c) => {
    const [[x0, y0], [x1, y1]] = contactLine(c, section.faults, section.length_m, bottom);
    if (elevation > Math.max(y0, y1) + up || elevation < Math.min(y0, y1) - up) {
      return Infinity;
    }
    const x = y0 === y1 ? x0 : x0 + ((elevation - y0) * (x1 - x0)) / (y1 - y0);
    return Math.abs(x - distance);
  });
  if (contact && contact.gap <= along) {
    return { kind: "contact", contact: contact.item };
  }
  const column = nearest(section.columns, (c) => Math.abs(c.distance_m - distance));
  if (!column) {
    return null;
  }
  const ground = column.item.ground_m;
  if (ground !== null && elevation > ground) {
    return { kind: "above" };
  }
  const depth = ground === null ? 0 : ground - elevation;
  const cell = nearest(column.item.cells, (c) => (depth >= c.top_m && depth < c.top_m + section.row_m ? 0 : Infinity));
  if (!cell || cell.gap === Infinity) {
    return null;
  }
  return { kind: "cell", column: column.item, cell: cell.item };
}
