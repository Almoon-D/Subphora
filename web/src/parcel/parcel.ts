// Copyright (c) 2026 Almoon-D. All rights reserved.
// The detailed map of each area in the browser: where its job stands, when to ask again,
// whether a tap falls on it, and which areas can be compared.
import type { AreaAnalysis, AreaOfInterest, ParcelAnswer, ParcelFailure, ParcelLayer, ParcelResult } from "../api.ts";
import { areaKey } from "../search/areas.ts";

/** An area's detailed map: being asked for, answered (a job in any state), or refused. */
export type ParcelView =
  | { state: "asking" }
  | { state: "answered"; answer: ParcelAnswer }
  | { state: "failed"; failure: ParcelFailure };

/** The detailed maps of this page's areas, by area key. */
export type ParcelViews = Readonly<Record<string, ParcelView>>;

const MS_PER_S = 1000;

/** Milliseconds until the job should be asked again, or null when it is settled. */
export function pollDelay(view: ParcelView | undefined): number | null {
  if (view?.state !== "answered") {
    return null;
  }
  const { job } = view.answer;
  return job.state === "queued" || job.state === "running" ? job.poll_after_s * MS_PER_S : null;
}

/** The views with one area's answer in place. */
export function withParcelResult(views: ParcelViews, key: string, result: ParcelResult): Record<string, ParcelView> {
  const view: ParcelView = result.ok
    ? { state: "answered", answer: result.answer }
    : { state: "failed", failure: result.failure };
  return { ...views, [key]: view };
}

/** The finished analysis of a view, if it has one. */
export function analysisOf(view: ParcelView | undefined): AreaAnalysis | null {
  return view?.state === "answered" ? view.answer.job.analysis : null;
}

/** Whether a point lies in the box of a finished detailed map (the API decides exactly). */
export function onAnalysis(analysis: AreaAnalysis | null, lon: number, lat: number): boolean {
  if (!analysis) {
    return false;
  }
  const [west, south, east, north] = analysis.bbox;
  return west <= lon && lon <= east && south <= lat && lat <= north;
}

/** The layer drawn when a detailed map first shows: the first one configured visible. */
export function initialParcelLayer(layers: readonly ParcelLayer[]): string | null {
  return (layers.find((l) => l.visible) ?? layers[0])?.id ?? null;
}

/** The areas of the session whose detailed map is done, in the session's order. */
export function comparable(
  areas: readonly AreaOfInterest[],
  views: ParcelViews,
): { area: AreaOfInterest; analysis: AreaAnalysis }[] {
  return areas.flatMap((area) => {
    const analysis = analysisOf(views[areaKey(area)]);
    return analysis ? [{ area, analysis }] : [];
  });
}

/** What the map draws of a detailed map, for the page and its tests: id, layer, candidates. */
export function describeParcel(analysis: AreaAnalysis | null, layer: string | null): string {
  return analysis ? `${analysis.id}:${layer ?? ""}:${String(analysis.candidates.length)}` : "";
}
