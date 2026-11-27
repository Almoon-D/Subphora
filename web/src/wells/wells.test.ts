// Copyright (c) 2026 Almoon-D. All rights reserved.
import { describe, expect, it } from "vitest";

import {
  addReading,
  belowGround,
  deleteWell,
  EMPTY_FORM,
  EMPTY_READING,
  fetchRegistry,
  formOf,
  importWells,
  readingOf,
  saveWell,
  typedNumber,
  type Well,
  wellFromForm,
} from "./wells.ts";

const ID = "0b9f4c1e-6d2a-4f3b-9c8e-1a2b3c4d5e6f";
const WELL: Well = {
  id: ID,
  name: "Pozo sintético",
  longitude: -3.7,
  latitude: 40.42,
  depth_m: 80.5,
  flow_l_s: null,
  outcome: "productive",
  drilled_on: "2024-05-01",
  note: null,
};

function answering(status: number, body: string, seen: Request[] = []): typeof fetch {
  return (input, init) => {
    seen.push(new Request(new URL(input instanceof Request ? input.url : input.toString(), "https://test"), init));
    return Promise.resolve(new Response(body, { status, headers: { "content-type": "application/json" } }));
  };
}

describe("a well's form", () => {
  it("makes a well, reading decimal commas and leaving blanks empty", () => {
    const made = wellFromForm(
      { ...EMPTY_FORM, name: " Pozo sintético ", longitude: "-3,7", latitude: "40.42", depth_m: "80,5", outcome: "productive", drilled_on: "2024-05-01" },
      ID,
    );
    expect(made).toEqual({ ok: true, well: WELL });
  });

  it.each([
    [{ name: "" }, "name"],
    [{ name: "A", longitude: "", latitude: "40" }, "position"],
    [{ name: "A", longitude: "-300", latitude: "40" }, "position"],
    [{ name: "A", longitude: "abc", latitude: "40" }, "position"],
    [{ name: "A", longitude: "-3", latitude: "40", depth_m: "-1" }, "depth"],
    [{ name: "A", longitude: "-3", latitude: "40", flow_l_s: "x" }, "flow"],
  ])("refuses %o for its %s", (fields, problem) => {
    expect(wellFromForm({ ...EMPTY_FORM, ...fields }, ID)).toEqual({ ok: false, problem });
  });

  it("is filled back from a well to correct it", () => {
    expect(wellFromForm(formOf(WELL), ID)).toEqual({ ok: true, well: WELL });
  });

  it("reads numbers as typed", () => {
    expect([typedNumber(""), typedNumber(" 2,5 "), typedNumber("7")]).toEqual([null, 2.5, 7]);
    expect(Number.isNaN(typedNumber("dos"))).toBe(true);
  });
});

describe("a reading", () => {
  const typed = { ...EMPTY_READING, when: "2026-06-01T08:30", depth: "12,5" };

  it("is the local time as UTC, the depth below its reference, who read it and the pump", () => {
    const answer = readingOf(ID, { ...typed, reference: "casing_top", height: "0,4", measured_by: "driller", minutes: "180" }, "r");
    expect(answer).toEqual({
      ok: true,
      reading: {
        id: "r",
        well_id: ID,
        measured_at: new Date("2026-06-01T08:30").toISOString(),
        depth_to_water_m: 12.5,
        reference: "casing_top",
        reference_height_m: 0.4,
        measured_by: "driller",
        pump: "stopped",
        pump_minutes: 180,
      },
    });
    if (answer.ok) {
      expect(belowGround(answer.reading)).toBeCloseTo(12.1);
    }
  });

  it("from the ground has no height, and an unknown pump no minutes, whatever was typed", () => {
    const answer = readingOf(ID, { ...typed, height: "3", pump: "unknown", minutes: "20" }, "r");
    expect(answer.ok && [answer.reading.reference_height_m, answer.reading.pump_minutes]).toEqual([0, null]);
    const blank = readingOf(ID, typed, "r");
    expect(blank.ok && blank.reading.pump_minutes).toBeNull();
  });

  it("needs its time and level, a casing's height, and whole minutes", () => {
    expect(readingOf(ID, { ...typed, when: "" })).toEqual({ ok: false, problem: "reading" });
    expect(readingOf(ID, { ...typed, depth: "" })).toEqual({ ok: false, problem: "reading" });
    expect(readingOf(ID, { ...typed, depth: "hondo" })).toEqual({ ok: false, problem: "reading" });
    expect(readingOf(ID, { ...typed, reference: "casing_top" })).toEqual({ ok: false, problem: "height" });
    expect(readingOf(ID, { ...typed, reference: "casing_top", height: "-1" })).toEqual({ ok: false, problem: "height" });
    expect(readingOf(ID, { ...typed, minutes: "12,5" })).toEqual({ ok: false, problem: "minutes" });
    expect(readingOf(ID, { ...typed, pump: "running", minutes: "-3" })).toEqual({ ok: false, problem: "minutes" });
  });
});

describe("the registry's calls", () => {
  it("put a well under its id, as JSON", async () => {
    const seen: Request[] = [];
    const answer = await saveWell(WELL, answering(201, '{"id":"x","change":"created"}', seen));
    expect(answer).toEqual({ ok: true, body: { id: "x", change: "created" } });
    expect(seen[0]?.method).toBe("PUT");
    expect(new URL(seen[0]?.url ?? "").pathname).toBe(`/api/wells/${ID}`);
    expect(await seen[0]?.json()).toEqual(WELL);
  });

  it("report the server's failure with its detail, or the network's", async () => {
    expect(await fetchRegistry(answering(503, '{"code":"store_unavailable","detail":"the registry failed"}'))).toEqual({
      ok: false,
      failure: "store_unavailable",
      detail: "the registry failed",
    });
    const reading = {
      id: "r",
      well_id: ID,
      measured_at: "",
      depth_to_water_m: 1,
      reference: "ground" as const,
      reference_height_m: 0,
      measured_by: "owner" as const,
      pump: "stopped" as const,
      pump_minutes: null,
    };
    expect(await addReading(reading, answering(409, '{"code":"conflict"}'))).toEqual({
      ok: false,
      failure: "conflict",
      detail: null,
    });
    expect(await fetchRegistry(answering(500, "not json"))).toEqual({ ok: false, failure: "unexpected", detail: null });
    expect(await fetchRegistry(answering(418, '{"code":"teapot"}'))).toEqual({ ok: false, failure: "unexpected", detail: null });
    const offline: typeof fetch = () => Promise.reject(new TypeError("offline"));
    expect(await fetchRegistry(offline)).toEqual({ ok: false, failure: "network", detail: null });
  });

  it("delete with no body, and import a file as CSV", async () => {
    const seen: Request[] = [];
    expect(await deleteWell(ID, (input, init) => {
      seen.push(new Request(new URL(input instanceof Request ? input.url : input.toString(), "https://test"), init));
      return Promise.resolve(new Response(null, { status: 204 }));
    })).toEqual({ ok: true, body: undefined });
    expect(seen[0]?.method).toBe("DELETE");
    const report = { rows: 1, wells: { created: 1 }, readings: {}, conflict_rows: [] };
    const imported = await importWells(new Blob(["name,lon,lat\n"]), answering(200, JSON.stringify(report), seen));
    expect(imported).toEqual({ ok: true, body: report });
    expect(seen[1]?.headers.get("content-type")).toBe("text/csv");
  });
});
