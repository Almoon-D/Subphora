// Copyright (c) 2026 Almoon-D. All rights reserved.
import { describe, expect, it } from "vitest";

import { fetchMapConfig, fetchParcel } from "./api.ts";

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
