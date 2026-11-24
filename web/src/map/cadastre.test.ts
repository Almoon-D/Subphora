// Copyright (c) 2026 Almoon-D. All rights reserved.
import { describe, expect, it } from "vitest";

import type { MapConfig } from "../api.ts";
import { cadastreImageUrl, cadastreVisible, imageSize } from "./cadastre.ts";

const cadastre: MapConfig["cadastre"] = {
  service_id: "catastro-wms",
  url: "https://ovc.catastro.meh.es/cartografia/INSPIRE/spadgcwms.aspx",
  params: {
    SERVICE: "WMS",
    VERSION: "1.3.0",
    REQUEST: "GetMap",
    LAYERS: "CP.CadastralParcel",
    STYLES: "",
    CRS: "EPSG:3857",
    FORMAT: "image/png",
    TRANSPARENT: "true",
  },
  min_zoom: 15,
  refresh_delay_ms: 400,
  max_image_px: 2048,
  attribution: "Dirección General del Catastro",
  visible: true,
  opacity: 1,
};

describe("imageSize", () => {
  it("keeps a small view as it is", () => {
    expect(imageSize(800, 600, 1, 2048)).toEqual({ width: 800, height: 600 });
  });

  it("follows the pixel ratio", () => {
    expect(imageSize(800, 600, 2, 2048)).toEqual({ width: 1600, height: 1200 });
  });

  it("scales a large view down, keeping its shape", () => {
    expect(imageSize(1600, 900, 2, 2048)).toEqual({ width: 2048, height: 1152 });
  });

  it("never asks for an empty image", () => {
    expect(imageSize(0, 0, 1, 2048)).toEqual({ width: 1, height: 1 });
  });
});

describe("cadastreImageUrl", () => {
  it("asks for one image of the whole view in EPSG:3857", () => {
    const url = new URL(cadastreImageUrl(cadastre, [-951500, 5293500, -950900, 5294100], { width: 600, height: 600 }));
    expect(url.origin + url.pathname).toBe(cadastre.url);
    expect(url.searchParams.get("REQUEST")).toBe("GetMap");
    expect(url.searchParams.get("CRS")).toBe("EPSG:3857");
    expect(url.searchParams.get("BBOX")).toBe("-951500.00,5293500.00,-950900.00,5294100.00");
    expect(url.searchParams.get("WIDTH")).toBe("600");
    expect(url.searchParams.get("HEIGHT")).toBe("600");
    expect(url.searchParams.get("STYLES")).toBe("");
    expect(url.searchParams.has("TILED")).toBe(false);
  });
});

describe("cadastreVisible", () => {
  it("shows the parcels only from the minimum zoom", () => {
    expect(cadastreVisible(cadastre, 14.9)).toBe(false);
    expect(cadastreVisible(cadastre, 15)).toBe(true);
  });
});
