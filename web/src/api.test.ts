// Copyright (c) 2026 Almoon-D. All rights reserved.
import { describe, expect, it } from "vitest";

import { fetchFeatureInfo, fetchMapConfig, fetchParcel } from "./api.ts";

function answering(status: number, body: string): typeof fetch {
  return () => Promise.resolve(new Response(body, { status, headers: { "content-type": "application/json" } }));
}

describe("fetchParcel", () => {
  it("returns the parcel", async () => {
    const result = await fetchParcel("7279701NH3477G", answering(200, '{"reference":"7279701NH3477G"}'));
    expect(result).toEqual({ ok: true, parcel: { reference: "7279701NH3477G" } });
  });

  it("asks for the trimmed, escaped reference", async () => {
    let asked = "";
    const spy: typeof fetch = (input) => {
      asked = input instanceof Request ? input.url : input.toString();
      return Promise.resolve(new Response("{}", { status: 200 }));
    };
    await fetchParcel("  7279701 NH3477G/x ", spy);
    expect(asked).toBe("/api/parcels/7279701%20NH3477G%2Fx");
  });

  it.each([
    [400, "malformed_reference"],
    [404, "parcel_not_found"],
    [422, "territory_not_supported"],
    [502, "upstream_error"],
    [504, "upstream_timeout"],
  ])("passes on the server's reason (%i)", async (status, code) => {
    const result = await fetchParcel("x", answering(status, JSON.stringify({ code, detail: "…" })));
    expect(result).toEqual({ ok: false, failure: code });
  });

  it("calls an unknown code unexpected", async () => {
    expect(await fetchParcel("x", answering(500, '{"code":"boom"}'))).toEqual({ ok: false, failure: "unexpected" });
    expect(await fetchParcel("x", answering(500, '"text"'))).toEqual({ ok: false, failure: "unexpected" });
  });

  it("calls a body that is not JSON unexpected", async () => {
    expect(await fetchParcel("x", answering(502, "<html>Bad gateway</html>"))).toEqual({
      ok: false,
      failure: "unexpected",
    });
  });

  it("reports an unreachable server", async () => {
    const offline: typeof fetch = () => Promise.reject(new TypeError("Failed to fetch"));
    expect(await fetchParcel("x", offline)).toEqual({ ok: false, failure: "network" });
  });
});

describe("fetchMapConfig", () => {
  it("returns the configuration", async () => {
    expect(await fetchMapConfig(answering(200, '{"parcel_padding_px":60}'))).toEqual({ parcel_padding_px: 60 });
  });

  it("throws when the server fails", async () => {
    await expect(fetchMapConfig(answering(500, "{}"))).rejects.toThrow("answered 500");
  });
});

describe("fetchFeatureInfo", () => {
  it("asks the API for the layer at the point and zoom", async () => {
    let asked = "";
    const spy: typeof fetch = (input) => {
      asked = input instanceof Request ? input.url : input.toString();
      return Promise.resolve(new Response('{"layer_id":"rivers","features":[]}', { status: 200 }));
    };
    const result = await fetchFeatureInfo("rivers", -3.7, 40.4, 14.256, spy);
    expect(asked).toBe("/api/layers/rivers/info?lon=-3.700000&lat=40.400000&zoom=14.26");
    expect(result).toEqual({ ok: true, layerId: "rivers", info: { layer_id: "rivers", features: [] } });
  });

  it.each([
    [502, "upstream_error"],
    [504, "upstream_timeout"],
  ])("passes on the server's reason (%i)", async (status, code) => {
    const result = await fetchFeatureInfo("rivers", 0, 0, 10, answering(status, JSON.stringify({ code })));
    expect(result).toEqual({ ok: false, layerId: "rivers", failure: code });
  });

  it("calls anything else unexpected", async () => {
    expect(await fetchFeatureInfo("x", 0, 0, 10, answering(404, '{"code":"unknown_layer"}'))).toEqual({
      ok: false,
      layerId: "x",
      failure: "unexpected",
    });
    expect(await fetchFeatureInfo("x", 0, 0, 10, answering(502, "<html/>"))).toEqual({
      ok: false,
      layerId: "x",
      failure: "unexpected",
    });
    expect(await fetchFeatureInfo("x", 0, 0, 10, answering(500, '"text"'))).toEqual({
      ok: false,
      layerId: "x",
      failure: "unexpected",
    });
  });

  it("reports an unreachable server", async () => {
    const offline: typeof fetch = () => Promise.reject(new TypeError("Failed to fetch"));
    expect(await fetchFeatureInfo("x", 0, 0, 10, offline)).toEqual({ ok: false, layerId: "x", failure: "network" });
  });
});
