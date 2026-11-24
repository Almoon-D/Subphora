// Copyright (c) 2026 Almoon-D. All rights reserved.
import { describe, expect, it } from "vitest";

import { readFileSync } from "node:fs";

import { INFO_FAILURES, LOOKUP_FAILURES, type MapConfig } from "../api.ts";
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
    for (const failure of LOOKUP_FAILURES) {
      expect(Object.keys(es)).toContain(`error.${failure}`);
    }
    for (const failure of INFO_FAILURES) {
      expect(Object.keys(es)).toContain(`info.error.${failure}`);
    }
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
