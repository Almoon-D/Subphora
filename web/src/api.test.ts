// Copyright (c) 2026 Almoon-D. All rights reserved.
import { describe, expect, it } from "vitest";

import {
  drawnPoint,
  drawnPolygon,
  fetchFeatureInfo,
  fetchMapConfig,
  packPath,
  reportPath,
  resolveArea,
  searchText,
} from "./api.ts";

function answering(status: number, body: string): typeof fetch {
  return () => Promise.resolve(new Response(body, { status, headers: { "content-type": "application/json" } }));
}

describe("searchText", () => {
  it("returns the readings", async () => {
    const result = await searchText("Daimiel", answering(200, '{"interpretations":[{"label":"Daimiel"}]}'));
    expect(result).toEqual({ ok: true, interpretations: [{ label: "Daimiel" }] });
  });

  it("asks for the trimmed, escaped text", async () => {
    let asked = "";
    const spy: typeof fetch = (input) => {
      asked = input instanceof Request ? input.url : input.toString();
      return Promise.resolve(new Response('{"interpretations":[]}', { status: 200 }));
    };
    await searchText("  40°25'N 3°42'O / x ", spy);
    expect(asked).toBe("/api/search?q=40%C2%B025%27N+3%C2%B042%27O+%2F+x");
  });

  it.each([
    [400, "malformed_coordinates", null],
    [404, "no_match", "cartociudad"],
    [422, "wrong_utm_zone", null],
    [502, "upstream_error", "sigpac-queries"],
    [504, "upstream_timeout", "catastro-wfs-parcels"],
  ])("passes on the server's reason (%i %s)", async (status, code, source) => {
    const result = await searchText("x", answering(status, JSON.stringify({ code, detail: "…", source })));
    expect(result).toEqual({ ok: false, failure: code, source });
  });

  it("calls an unknown code or a body that is not JSON unexpected", async () => {
    const unexpected = { ok: false, failure: "unexpected", source: null };
    expect(await searchText("x", answering(500, '{"code":"boom"}'))).toEqual(unexpected);
    expect(await searchText("x", answering(500, '"text"'))).toEqual(unexpected);
    expect(await searchText("x", answering(502, "<html>Bad gateway</html>"))).toEqual(unexpected);
  });

  it("reports an unreachable server", async () => {
    const offline: typeof fetch = () => Promise.reject(new TypeError("Failed to fetch"));
    expect(await searchText("x", offline)).toEqual({ ok: false, failure: "network", source: null });
  });
});

describe("resolveArea", () => {
  it("returns the area", async () => {
    expect(await resolveArea("/api/aoi/sigpac/1:1:0:0:1:1", answering(200, '{"origin":"sigpac_parcel"}'))).toEqual({
      ok: true,
      area: { origin: "sigpac_parcel" },
    });
  });

  it("asks only the API's own area paths", async () => {
    let called = false;
    const spy: typeof fetch = () => {
      called = true;
      return Promise.resolve(new Response("{}"));
    };
    expect(await resolveArea("https://elsewhere.example/api/aoi/x", spy)).toEqual({
      ok: false,
      failure: "unexpected",
      source: null,
    });
    expect(called).toBe(false);
  });
});

describe("drawing", () => {
  it("asks for a drawn point in WGS 84", async () => {
    let asked = "";
    const spy: typeof fetch = (input) => {
      asked = input instanceof Request ? input.url : input.toString();
      return Promise.resolve(new Response('{"origin":"drawn_point"}'));
    };
    await drawnPoint(-3.6, 39.1, spy);
    expect(asked).toBe("/api/aoi/point?crs=OGC%3ACRS84&x=-3.6&y=39.1&origin=drawn_point");
  });

  it("posts a drawn polygon as a closed GeoJSON ring", async () => {
    let sent: RequestInit | undefined;
    const spy: typeof fetch = (_input, init) => {
      sent = init;
      return Promise.resolve(new Response('{"origin":"drawn_polygon"}'));
    };
    const result = await drawnPolygon(
      [
        [0, 0],
        [1, 0],
        [1, 1],
      ],
      spy,
    );
    expect(result.ok).toBe(true);
    expect(sent?.method).toBe("POST");
    expect(JSON.parse(sent?.body as string)).toEqual({
      type: "Polygon",
      coordinates: [
        [
          [0, 0],
          [1, 0],
          [1, 1],
          [0, 0],
        ],
      ],
    });
  });

  it("sends an empty ring for no vertices, for the server to refuse", async () => {
    let sent: RequestInit | undefined;
    const spy: typeof fetch = (_input, init) => {
      sent = init;
      return Promise.resolve(new Response('{"code":"invalid_polygon"}', { status: 400 }));
    };
    expect(await drawnPolygon([], spy)).toEqual({ ok: false, failure: "invalid_polygon", source: null });
    expect(JSON.parse(sent?.body as string)).toEqual({ type: "Polygon", coordinates: [[]] });
  });
});

describe("fetchMapConfig", () => {
  it("returns the configuration", async () => {
    expect(await fetchMapConfig(answering(200, '{"area_padding_px":60}'))).toEqual({ area_padding_px: 60 });
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

describe("report downloads", () => {
  it("names the area's report and pack, with photos only when asked", () => {
    expect(reportPath("0123456789abcdef")).toBe("/api/parcel/0123456789abcdef/report.pdf");
    expect(packPath("0123456789abcdef", false)).toBe("/api/parcel/0123456789abcdef/pack.zip?media=false&wells=false");
    expect(packPath("0123456789abcdef", true)).toBe("/api/parcel/0123456789abcdef/pack.zip?media=true&wells=false");
    expect(packPath("0123456789abcdef", false, true)).toBe("/api/parcel/0123456789abcdef/pack.zip?media=false&wells=true");
  });
});
