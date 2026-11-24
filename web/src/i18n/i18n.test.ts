// Copyright (c) 2026 Almoon-D. All rights reserved.
import { describe, expect, it } from "vitest";

import { LOOKUP_FAILURES } from "../api.ts";
import { es } from "./es.ts";
import { formatArea, formatNumber, t } from "./index.ts";

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
