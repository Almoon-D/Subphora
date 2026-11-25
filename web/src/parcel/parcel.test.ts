// Copyright (c) 2026 Almoon-D. All rights reserved.
import { describe, expect, it } from "vitest";

import { readFileSync } from "node:fs";

import {
  type AreaOfInterest,
  fetchParcel,
  fetchParcelExplanation,
  PARCEL_FAILURES,
  type ParcelAnswer,
  startParcel,
} from "../api.ts";
import { es } from "../i18n/es.ts";
import { areaKey } from "../search/areas.ts";
import {
  analysisOf,
  comparable,
  describeParcel,
  initialParcelLayer,
  onAnalysis,
  type ParcelView,
  pollDelay,
  withParcelResult,
} from "./parcel.ts";

const read = (name: string) => readFileSync(new URL(`../../e2e/fixtures/${name}`, import.meta.url), "utf-8");
const DONE = JSON.parse(read("parcel-daimiel.json")) as ParcelAnswer;
const QUEUED = JSON.parse(read("parcel-queued.json")) as ParcelAnswer;
const POINT = JSON.parse(read("area-point-daimiel.json")) as AreaOfInterest;
const CAMPOS = JSON.parse(read("area-sigpac-campos.json")) as AreaOfInterest;

const answered = (answer: ParcelAnswer): ParcelView => ({ state: "answered", answer });

function answering(status: number, body: string): typeof fetch {
  return () => Promise.resolve(new Response(body, { status, headers: { "content-type": "application/json" } }));
}

describe("the job", () => {
  it("is asked again while queued or running, when its answer says", () => {
    expect(pollDelay(answered(QUEUED))).toBe(QUEUED.job.poll_after_s * 1000);
    const running = { ...QUEUED, job: { ...QUEUED.job, state: "running" as const } };
    expect(pollDelay(answered(running))).toBe(QUEUED.job.poll_after_s * 1000);
    expect(pollDelay(answered(DONE))).toBeNull();
    expect(pollDelay({ state: "asking" })).toBeNull();
    expect(pollDelay({ state: "failed", failure: "too_large" })).toBeNull();
    expect(pollDelay(undefined)).toBeNull();
  });

  it("keeps each area's answer under its key", () => {
    const views = withParcelResult({}, "a", { ok: true, answer: DONE });
    const both = withParcelResult(views, "b", { ok: false, failure: "network" });
    expect(analysisOf(both.a)).toEqual(DONE.job.analysis);
    expect(both.b).toEqual({ state: "failed", failure: "network" });
    expect(analysisOf(both.b)).toBeNull();
  });
});

describe("the finished map", () => {
  const analysis = DONE.job.analysis;

  it("answers a tap inside its box only", () => {
    expect(analysis).not.toBeNull();
    const [west, south, east, north] = analysis?.bbox ?? [0, 0, 0, 0];
    expect(onAnalysis(analysis, (west + east) / 2, (south + north) / 2)).toBe(true);
    expect(onAnalysis(analysis, east + 0.01, north)).toBe(false);
    expect(onAnalysis(null, west, south)).toBe(false);
  });

  it("draws the first layer configured visible, or the first", () => {
    expect(initialParcelLayer(DONE.layers)).toBe("potential-index");
    const hidden = DONE.layers.map((l) => ({ ...l, visible: false }));
    expect(initialParcelLayer(hidden)).toBe(hidden[0]?.id);
    expect(initialParcelLayer([])).toBeNull();
  });

  it("names what the map draws", () => {
    expect(describeParcel(analysis, "terrain-slope")).toBe(`${DONE.job.id}:terrain-slope:5`);
    expect(describeParcel(analysis, null)).toBe(`${DONE.job.id}::5`);
    expect(describeParcel(null, "terrain-slope")).toBe("");
  });

  it("compares the session's areas whose map is done, in the session's order", () => {
    const views = { [areaKey(CAMPOS)]: answered(DONE), [areaKey(POINT)]: answered(QUEUED) };
    expect(comparable([POINT, CAMPOS], views).map((row) => row.area)).toEqual([CAMPOS]);
    const both = { ...views, [areaKey(POINT)]: answered(DONE) };
    expect(comparable([POINT, CAMPOS], both).map((row) => row.area)).toEqual([POINT, CAMPOS]);
  });
});

describe("the API's detailed map", () => {
  it("starts a job by posting the area", async () => {
    let posted: RequestInit | undefined;
    const spy: typeof fetch = (_input, init) => {
      posted = init;
      return Promise.resolve(new Response(JSON.stringify(QUEUED), { status: 202 }));
    };
    expect(await startParcel(POINT, spy)).toEqual({ ok: true, answer: QUEUED });
    expect(posted?.method).toBe("POST");
    expect(typeof posted?.body).toBe("string");
    expect(JSON.parse(posted?.body as string)).toEqual(POINT);
  });

  it("passes on the server's reason, and calls anything else unexpected", async () => {
    expect(await fetchParcel("x", answering(422, '{"code":"too_large"}'))).toEqual({ ok: false, failure: "too_large" });
    expect(await fetchParcel("x", answering(500, '{"code":"boom"}'))).toEqual({ ok: false, failure: "unexpected" });
    expect(await fetchParcel("x", answering(500, "not json"))).toEqual({ ok: false, failure: "unexpected" });
    const offline: typeof fetch = () => Promise.reject(new TypeError("offline"));
    expect(await fetchParcel("x", offline)).toEqual({ ok: false, failure: "network" });
  });

  it("asks for a cell's explanation by the job's id and the point", async () => {
    let asked = "";
    const spy: typeof fetch = (input) => {
      asked = input instanceof Request ? input.url : input.toString();
      return Promise.resolve(new Response(read("explain-parcel-daimiel.json"), { status: 200 }));
    };
    const result = await fetchParcelExplanation("45f6a846b1f3eac7", -3.6115, 39.0675, spy);
    expect(result.ok).toBe(true);
    expect(asked).toBe("/api/parcel/45f6a846b1f3eac7/explain?lon=-3.6115000&lat=39.0675000");
    const outside = await fetchParcelExplanation("x", 0, 0, answering(404, '{"code":"outside_grid"}'));
    expect(outside).toEqual({ ok: false, failure: "outside_grid" });
  });

  it("has a message for every failure", () => {
    for (const failure of PARCEL_FAILURES) {
      expect(Object.keys(es)).toContain(`detailed.error.${failure}`);
    }
  });
});
