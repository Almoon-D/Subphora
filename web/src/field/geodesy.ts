// Copyright (c) 2026 Almoon-D. All rights reserved.
// Distances and directions on the WGS84 ellipsoid, from GeographicLib (the geodesic
// algorithms PROJ uses on the server): no hand-written coordinate maths.
import { Geodesic } from "geographiclib-geodesic";

import type { Position } from "../api.ts";

const WGS84 = Geodesic.WGS84;
// Inverse and Direct: ask for the distance and the azimuths, and for the end point.
const DISTANCE_AND_AZIMUTH = Geodesic.DISTANCE | Geodesic.AZIMUTH;
const END_POINT = Geodesic.LATITUDE | Geodesic.LONGITUDE;

export interface Leg {
  /** Metres along the ellipsoid. */
  distance_m: number;
  /** Degrees clockwise from true north, 0 to 360. */
  bearing_deg: number;
}

/** The distance and the initial bearing from one point to another. */
export function leg(from: Position, to: Position): Leg {
  const answer = WGS84.Inverse(from[1], from[0], to[1], to[0], DISTANCE_AND_AZIMUTH);
  const azimuth = answer.azi1 ?? 0;
  return { distance_m: answer.s12 ?? 0, bearing_deg: (azimuth + 360) % 360 };
}

/** A ring of `vertices` points at `radius_m` around a point, closed, for an accuracy circle. */
export function circle(centre: Position, radius_m: number, vertices: number): Position[] {
  const ring: Position[] = [];
  for (let index = 0; index < vertices; index += 1) {
    const azimuth = (360 * index) / vertices;
    const end = WGS84.Direct(centre[1], centre[0], azimuth, radius_m, END_POINT);
    ring.push([end.lon2 ?? centre[0], end.lat2 ?? centre[1]]);
  }
  const first = ring[0];
  if (first) {
    ring.push(first);
  }
  return ring;
}

/** MASTER_PLAN §4.7: at the spot within `at_spot_m` of it, and never while the reported
 * accuracy is worse than that distance. */
export function atSpot(distance_m: number, accuracy_m: number, at_spot_m: number): boolean {
  return accuracy_m <= at_spot_m && distance_m <= at_spot_m;
}

/** The name of the compass point nearest a bearing, of eight: n, ne, e, se, s, sw, w, nw. */
export function compassPoint(bearing_deg: number): "n" | "ne" | "e" | "se" | "s" | "sw" | "w" | "nw" {
  const points = ["n", "ne", "e", "se", "s", "sw", "w", "nw"] as const;
  return points[Math.round((((bearing_deg % 360) + 360) % 360) / 45) % 8] ?? "n";
}

/** A west, south, east, north box widened by `distance_m` on every side: its north and south
 * edges moved along the meridian, its east and west edges at the latitude where a degree of
 * longitude is shortest, so that the whole box keeps at least that margin. */
export function widen(box: readonly [number, number, number, number], distance_m: number): [number, number, number, number] {
  const [west, south, east, north] = box;
  const north2 = WGS84.Direct(north, west, 0, distance_m, END_POINT).lat2 ?? north;
  const south2 = WGS84.Direct(south, west, 180, distance_m, END_POINT).lat2 ?? south;
  const widest = Math.abs(north2) > Math.abs(south2) ? north2 : south2;
  const east2 = WGS84.Direct(widest, east, 90, distance_m, END_POINT).lon2 ?? east;
  const west2 = WGS84.Direct(widest, west, 270, distance_m, END_POINT).lon2 ?? west;
  return [west2, south2, east2, north2];
}
