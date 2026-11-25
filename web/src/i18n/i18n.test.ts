// Copyright (c) 2026 Almoon-D. All rights reserved.
import { describe, expect, it } from "vitest";

import { readFileSync } from "node:fs";

import { type AoiOrigin, INFO_FAILURES, type MapConfig, SEARCH_FAILURES } from "../api.ts";
import { es } from "./es.ts";
import { formatArea, formatNumber, lookup, t } from "./index.ts";

// The API's GET /api/map (the Python tests keep this fixture equal to it).
const MAP = JSON.parse(readFileSync(new URL("../../e2e/fixtures/map.json", import.meta.url), "utf-8")) as MapConfig;

describe("t", () => {
  it("fills every placeholder", () => {
    expect(t("parcel.place", { municipality: "MERIDA", province: "BADAJOZ" })).toBe("MERIDA (BADAJOZ)");
  });

  it("formats numbers the Spanish way", () => {
    expect(t("parcel.heading", { reference: 7 })).toBe("Parcela 7");
    expect(formatNumber(13352)).toBe("13.352");
    expect(formatNumber(2.5, 2)).toBe("2,50");
  });

  it("refuses a missing parameter", () => {
    expect(() => t("parcel.place", { municipality: "MERIDA" })).toThrow("missing parameter province");
  });

  it("has a message for every failure the server can send", () => {
    for (const failure of SEARCH_FAILURES) {
      expect(Object.keys(es)).toContain(`error.${failure}`);
    }
    for (const failure of INFO_FAILURES) {
      expect(Object.keys(es)).toContain(`info.error.${failure}`);
    }
  });

  it("names every kind of area, every CRS a reading is in and every service that can fail", () => {
    const origins: AoiOrigin[] = [
      "cadastral",
      "sigpac_enclosure",
      "sigpac_parcel",
      "municipality",
      "place",
      "street",
      "address",
      "coordinates",
      "drawn_point",
      "drawn_polygon",
    ];
    const keys = [
      ...origins.map((o) => `origin.${o}`),
      ...["OGC:CRS84", "EPSG:4083", "EPSG:25829", "EPSG:25830", "EPSG:25831"].map((c) => `crs.${c}`),
      ...["catastro-wfs-parcels", "sigpac-queries", "cartociudad"].map((s) => `service.${s}`),
    ];
    expect(keys.filter((key) => !(key in es))).toEqual([]);
  });

  it("names every base map, group and layer the map serves", () => {
    const keys = [
      ...MAP.base_maps.map((b) => `base.${b.id}`),
      ...MAP.overlay_groups.map((g) => `group.${g}`),
      ...MAP.overlays.map((o) => `layer.${o.id}`),
      ...MAP.overlays.flatMap((o) => o.regional.map((r) => `layer.${r.id}`)),
      ...MAP.overlays.flatMap((o) => o.regional.flatMap((r) => r.area_ids.map((id) => `area.${id}`))),
    ];
    expect(keys.filter((key) => !(key in es))).toEqual([]);
  });
});

describe("lookup", () => {
  it("falls back to the given text for a key with no message", () => {
    expect(lookup("field.nº de hoja", "nº de hoja")).toBe("Hoja MAGNA");
    expect(lookup("field.Nombre", "Nombre")).toBe("Nombre");
  });
});

describe("formatArea", () => {
  it("gives square metres below a hectare", () => {
    expect(formatArea(9999)).toBe("9.999 m²");
  });

  it("adds hectares from one hectare", () => {
    expect(formatArea(23614448)).toBe("23.614.448 m² (2.361,44 ha)");
  });
});
