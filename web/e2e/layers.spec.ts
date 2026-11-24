// Copyright (c) 2026 Almoon-D. All rights reserved.
// The layer panel, the base-map switch and a tap on the map, in a real browser against a
// mocked API and mocked map services: no request leaves the machine.
import { readFileSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

const fixture = (name: string) => readFileSync(new URL(`fixtures/${name}`, import.meta.url), "utf-8");
const MAP = fixture("map.json");
const PARCEL = fixture("parcel-santiago.json");
const REFERENCE = "7279701NH3477G";
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
  "base64",
);

interface Overlay {
  id: string;
  group: string;
  tiles: string[];
  proxied: boolean;
  min_zoom: number;
}
const OVERLAYS = (JSON.parse(MAP) as { overlays: Overlay[] }).overlays;
const SERVICE_HOSTS = [
  "https://www.ign.es/**",
  "https://ovc.catastro.meh.es/**",
  "https://gis.miteco.gob.es/**",
  "https://mapas.igme.es/**",
  "https://maps.isric.org/**",
  "https://idena.navarra.es/**",
  "https://geoserveis.icgc.cat/**",
  "https://terramapas.icv.gva.es/**",
  "https://geoguadiana.chguadiana.es/**",
  "https://mirame.chduero.es/**",
];

interface Mocks {
  /** Every request to a map service or to the API's layer routes. */
  urls: string[];
  infoRequests: URL[];
  areaRequests: string[];
}

// Tafalla, in Navarra, where the regional soil map is drawn over SoilGrids.
const TAFALLA = { longitude: -1.7, latitude: 42.55 };

/** A square "Navarra" around Tafalla, as GET /api/areas/ES-NC would answer it. */
function navarra(half: number) {
  const [x, y] = [TAFALLA.longitude, TAFALLA.latitude];
  const ring = [
    [x - half, y - half],
    [x + half, y - half],
    [x + half, y + half],
    [x - half, y + half],
    [x - half, y - half],
  ];
  return {
    id: "ES-NC",
    kind: "region",
    bbox: [x - half, y - half, x + half, y + half],
    geometry: { type: "MultiPolygon", coordinates: [[ring]] },
    source: source("Unidades administrativas CC-BY 4.0 ign.es"),
    grid_deg: 0.0001,
  };
}

async function mockEverything(
  page: Page,
  info: Record<string, { status: number; body: string }> = {},
  view: { longitude: number; latitude: number; zoom: number } | null = null,
): Promise<Mocks> {
  const mocks: Mocks = { urls: [], infoRequests: [], areaRequests: [] };
  const body = view ? JSON.stringify({ ...(JSON.parse(MAP) as object), initial_view: view }) : MAP;
  await page.route("**/api/map", (route) => route.fulfill({ contentType: "application/json", body }));
  await page.route("**/api/areas/*", (route) => {
    const area = new URL(route.request().url()).pathname.split("/")[3] ?? "";
    mocks.areaRequests.push(area);
    return area === "ES-NC"
      ? route.fulfill({ contentType: "application/json", body: JSON.stringify(navarra(0.05)) })
      : route.fulfill({ status: 502, contentType: "application/json", body: '{"code":"upstream_error"}' });
  });
  await page.route("**/api/parcels/**", (route) =>
    route.fulfill({ contentType: "application/json", body: PARCEL }),
  );
  await page.route("**/api/layers/*/tiles/**", (route) => {
    mocks.urls.push(route.request().url());
    return route.fulfill({ contentType: "image/png", body: PNG });
  });
  await page.route("**/api/layers/*/info?**", (route) => {
    const url = new URL(route.request().url());
    mocks.infoRequests.push(url);
    const layer = url.pathname.split("/")[3] ?? "";
    const answer = info[layer] ?? { status: 200, body: JSON.stringify(emptyInfo(layer)) };
    return route.fulfill({ status: answer.status, contentType: "application/json", body: answer.body });
  });
  for (const host of SERVICE_HOSTS) {
    await page.route(host, (route) => {
      mocks.urls.push(route.request().url());
      return route.fulfill({ contentType: "image/png", body: PNG });
    });
  }
  return mocks;
}

function source(attribution: string) {
  return { service_id: "x", publisher: "x", attribution, retrieved_at: "2026-11-24T10:00:00Z" };
}

const NATIONAL = { level: "national", publisher: "x", detail: { scale_denominator: null, cell_m: null, edition: null }, area_id: null };

function emptyInfo(layer: string) {
  return { layer_id: layer, features: [], source: source("x"), answered_by: { ...NATIONAL, layer_id: layer }, fallbacks: [] };
}

async function showParcel(page: Page): Promise<void> {
  await page.goto("/");
  await page.getByLabel("Referencia catastral").fill(REFERENCE);
  await page.getByRole("button", { name: "Buscar" }).click();
  await expect(page.locator(".map")).toHaveAttribute("data-parcel", REFERENCE);
}

/** The requests that drew `overlay`: to its service, or to the API's proxy. */
function tileRequests(mocks: Mocks, overlay: Overlay): string[] {
  const [template = ""] = overlay.tiles;
  const prefix = overlay.proxied ? template.split("{z}")[0] ?? "" : template.split("BBOX=")[0] ?? "";
  return mocks.urls.filter((url) => (overlay.proxied ? new URL(url).pathname.startsWith(prefix) : url.startsWith(prefix)));
}

const map = (page: Page) => page.locator(".map");

/** Errors the page logs: a regional tile the clip cannot make shows up here. */
function consoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => errors.push(error.message));
  return errors;
}
const cadastreImages = (mocks: Mocks) => mocks.urls.filter((url) => url.startsWith("https://ovc.catastro.meh.es/")).length;
const attribution = (page: Page) => page.locator(".maplibregl-ctrl-attrib");

test("every water and geology layer switches on over the parcel", async ({ page }) => {
  // Sixteen layers' tiles through software WebGL: slow on a small runner.
  test.setTimeout(90_000);
  const mocks = await mockEverything(page);
  await showParcel(page);
  const layers = OVERLAYS.filter((o) => o.group === "water" || o.group === "geology");
  expect(layers.length).toBeGreaterThan(10);
  for (const overlay of layers) {
    await page.locator(`[data-layer="${overlay.id}"]`).getByRole("checkbox").check();
  }
  await expect(map(page)).toHaveAttribute("data-overlays", new RegExp(layers.map((o) => `${o.id}:`).join(".*")));
  for (const overlay of layers) {
    await expect.poll(() => tileRequests(mocks, overlay).length, { message: overlay.id }).toBeGreaterThan(0);
  }
  // Each direct WMS tile is one GetMap in EPSG:3857, its box filled in by the map.
  const rivers = OVERLAYS.find((o) => o.id === "rivers");
  const tile = new URL(rivers ? (tileRequests(mocks, rivers)[0] ?? "") : "");
  expect(tile.searchParams.get("CRS")).toBe("EPSG:3857");
  expect(tile.searchParams.get("BBOX")?.split(",")).toHaveLength(4);
  // The service without EPSG:3857 is reached through the API only.
  expect(mocks.urls.some((url) => url.includes("/api/layers/lithostratigraphy/tiles/"))).toBe(true);
  expect(mocks.urls.some((url) => url.includes("IGME_Litoestratigrafico_200"))).toBe(false);
  // Every source drawn is credited on the map.
  await expect(attribution(page)).toContainText("© Ministerio para la Transición Ecológica y el Reto Demográfico");
  await expect(attribution(page)).toContainText("Origen de los datos: © CN Instituto Geológico y Minero de España (IGME)");
  await expect(attribution(page)).toContainText("Dirección General del Catastro");
});

test("a layer's opacity and legend", async ({ page }) => {
  const mocks = await mockEverything(page);
  await showParcel(page);
  const item = page.locator('[data-layer="groundwater-status"]');
  await item.getByRole("checkbox").check();
  await expect.poll(() => cadastreImages(mocks)).toBeGreaterThan(0);
  const images = cadastreImages(mocks);
  await item.getByRole("slider", { name: /Opacidad/ }).fill("30");
  await expect(map(page)).toHaveAttribute("data-overlays", "groundwater-status:0.3");
  await expect(item.getByText("30 %")).toBeVisible();
  // Changing a layer asks Catastro for nothing: only moving the map does.
  await page.getByRole("slider", { name: "Opacidad: Parcelas catastrales" }).fill("50");
  await page.waitForTimeout(600);
  expect(cadastreImages(mocks)).toBe(images);

  await item.getByText("Leyenda", { exact: true }).click();
  const legend = item.getByRole("img", { name: /Leyenda de Estado cuantitativo/ });
  await expect(legend).toBeVisible();
  expect(await legend.getAttribute("src")).toContain("REQUEST=GetLegendGraphic");
  await expect.poll(() => mocks.urls.some((url) => url.includes("GetLegendGraphic"))).toBe(true);
  await expect(item.getByText("Fuente: © Ministerio para la Transición Ecológica y el Reto Demográfico")).toBeVisible();

  // MAGNA publishes no readable legend: the panel says so instead of a blank.
  const magna = page.locator('[data-layer="magna-lithology"]');
  await magna.getByRole("checkbox").check();
  await expect(magna.getByText("El servicio no publica una leyenda legible")).toBeVisible();

  await item.getByRole("checkbox").uncheck();
  await expect(map(page)).toHaveAttribute("data-overlays", "magna-lithology:0.6");
});

test("a layer below its zoom says so and is not requested", async ({ page }) => {
  const mocks = await mockEverything(page);
  await page.goto("/");
  const magna = page.locator('[data-layer="magna-lithology"]');
  await magna.getByRole("checkbox").check();
  await expect(magna.getByText("Visible desde el zoom 11: acerca el mapa.")).toBeVisible();
  await page.waitForTimeout(500);
  expect(mocks.urls.filter((url) => url.startsWith("https://mapas.igme.es/"))).toEqual([]);
});

test("the base map switches between PNOA and the IGN maps", async ({ page }) => {
  const mocks = await mockEverything(page);
  await page.goto("/");
  await expect(page.getByRole("radio", { name: "Ortofoto PNOA" })).toBeChecked();
  await expect(map(page)).toHaveAttribute("data-base", "pnoa");
  await expect(attribution(page)).toContainText("PNOA CC-BY 4.0 scne.es");

  await page.getByRole("radio", { name: "Mapa IGN", exact: true }).check();
  await expect(map(page)).toHaveAttribute("data-base", "ign-base");
  await expect.poll(() => mocks.urls.filter((url) => url.includes("/wmts/ign-base?") && url.includes("layer=IGNBaseTodo")).length).toBeGreaterThan(0);
  await expect(attribution(page)).toContainText("IGN Base CC-BY 4.0 scne.es");
  await expect(attribution(page)).not.toContainText("PNOA CC-BY 4.0 scne.es");

  await page.getByRole("radio", { name: "Mapa IGN en gris" }).check();
  await expect(map(page)).toHaveAttribute("data-base", "ign-base-grey");
  await expect.poll(() => mocks.urls.filter((url) => url.includes("layer=IGNBase-gris")).length).toBeGreaterThan(0);
});

test("the cadastral layer can be switched off", async ({ page }) => {
  await mockEverything(page);
  await page.goto("/");
  await expect(page.getByText("Acerca el mapa para ver las parcelas catastrales.")).toBeVisible();
  await page.getByRole("checkbox", { name: "Parcelas catastrales" }).uncheck();
  await expect(page.getByText("Acerca el mapa para ver las parcelas catastrales.")).toBeHidden();
});

const PERMEABILITY = {
  layer_id: "permeability",
  features: [{ fields: [{ name: "Permeabilidad", value: "MEDIA" }, { name: "Descripción", value: "DETRÍTICAS-MEDIA" }] }],
  source: source("Origen de los datos: © CN Instituto Geológico y Minero de España (IGME)"),
  answered_by: {
    level: "national",
    layer_id: "permeability",
    publisher: "Instituto Geológico y Minero de España (IGME)",
    detail: { scale_denominator: 200000, cell_m: null, edition: null },
    area_id: null,
  },
  fallbacks: [],
};

test("a tap shows what the switched-on layers hold there", async ({ page }) => {
  const mocks = await mockEverything(page, {
    permeability: { status: 200, body: JSON.stringify(PERMEABILITY) },
    piezometers: { status: 502, body: '{"code":"upstream_error","detail":"English detail"}' },
  });
  await showParcel(page);
  for (const id of ["permeability", "piezometers", "soil-clay"]) {
    await page.locator(`[data-layer="${id}"]`).getByRole("checkbox").check();
  }
  await map(page).click();

  const info = page.getByRole("region", { name: "En el punto tocado" });
  await expect(info.getByRole("heading", { name: "Permeabilidad 1:200.000" })).toBeVisible();
  await expect(info.getByText("DETRÍTICAS-MEDIA")).toBeVisible();
  await expect(info.getByText(/Fuente: Origen de los datos: © CN Instituto Geológico y Minero de España \(IGME\), consultado el/)).toBeVisible();
  await expect(
    info.getByText("Responde la capa nacional: Instituto Geológico y Minero de España (IGME) (escala 1:200.000 · fecha no indicada)."),
  ).toBeVisible();
  await expect(info.getByRole("heading", { name: "Piezómetros (red oficial)" })).toBeVisible();
  await expect(info.getByText("El servicio ha respondido con un error.")).toBeVisible();
  await expect(info.getByText("English detail")).toHaveCount(0);
  await expect(page.locator(".maplibregl-marker")).toHaveCount(1);
  // SoilGrids answers no value to a tap, and Santiago is outside every regional soil map:
  // it is not asked.
  expect(mocks.infoRequests.map((url) => url.pathname).sort()).toEqual([
    "/api/layers/permeability/info",
    "/api/layers/piezometers/info",
  ]);
  const asked = mocks.infoRequests[0];
  expect(Number(asked?.searchParams.get("lon"))).toBeCloseTo(-8.545, 2);
  expect(Number(asked?.searchParams.get("lat"))).toBeCloseTo(42.881, 2);
  expect(Number(asked?.searchParams.get("zoom"))).toBeGreaterThan(11);
});

test("a tap with no layer switched on asks nothing", async ({ page }) => {
  const mocks = await mockEverything(page);
  await showParcel(page);
  // Before any tap the panel is not shown.
  await expect(page.getByRole("region", { name: "En el punto tocado" })).toHaveCount(0);
  await map(page).click();
  await expect(page.getByText("Activa una capa con consulta")).toBeVisible();
  expect(mocks.infoRequests).toEqual([]);
});

test("a tap on nothing says so", async ({ page }) => {
  await mockEverything(page);
  await showParcel(page);
  await page.locator('[data-layer="rivers"]').getByRole("checkbox").check();
  await map(page).click();
  await expect(page.getByText("Nada de esta capa en este punto.")).toBeVisible();
});

const NAVARRA_SOIL = {
  layer_id: "soil-clay",
  features: [{ fields: [{ name: "SOILTAXON1", value: "Lithic Xeric Torriorthent" }] }],
  source: source("Gobierno de Navarra (IDENA), CC BY 4.0"),
  answered_by: {
    level: "regional",
    layer_id: "navarra-soils",
    publisher: "Gobierno de Navarra (IDENA)",
    detail: { scale_denominator: 25000, cell_m: null, edition: 2023 },
    area_id: "ES-NC",
  },
  fallbacks: [],
};

test("a regional layer is drawn inside its area over the national one, and answers there", async ({ page }) => {
  const mocks = await mockEverything(
    page,
    { "soil-clay": { status: 200, body: JSON.stringify(NAVARRA_SOIL) } },
    { ...TAFALLA, zoom: 13 },
  );
  const errors = consoleErrors(page);
  await page.goto("/");
  const soil = page.locator('[data-layer="soil-clay"]');
  await soil.getByRole("checkbox").check();
  await expect(map(page)).toHaveAttribute("data-regional", "navarra-soils catalonia-soils");
  // The theme's sources: the national baseline and the regional layer, each with its scale and date.
  await expect(soil.locator('[data-source="soil-clay"]')).toHaveText(
    "Nacional, toda España: ISRIC World Soil Information (celdas de 250 m · edición 2021).",
  );
  await expect(soil.locator('[data-source="navarra-soils"]')).toHaveText(
    "Regional, dibujada encima dentro de Navarra: Mapa de suelos de Navarra 1:25.000 (escala 1:25.000 · edición 2023).",
  );
  await expect(
    soil.getByText("Consulta al tocar solo dentro de Navarra y Cataluña: la capa nacional no devuelve valores."),
  ).toBeVisible();
  // The boundary is read once, and the regional service is asked for its tiles.
  await expect.poll(() => mocks.areaRequests).toEqual(["ES-NC"]);
  await expect.poll(() => mocks.urls.filter((url) => url.startsWith("https://idena.navarra.es/")).length).toBeGreaterThan(0);
  await expect.poll(() => mocks.urls.filter((url) => url.startsWith("https://maps.isric.org/")).length).toBeGreaterThan(0);
  await expect(attribution(page)).toContainText("Gobierno de Navarra (IDENA), CC BY 4.0");
  // The area covers part of the view: tiles inside it and outside it were both made.
  expect(errors).toEqual([]);

  await map(page).click();
  const info = page.getByRole("region", { name: "En el punto tocado" });
  await expect(info.getByText("Lithic Xeric Torriorthent")).toBeVisible();
  await expect(info.getByText("Suelo dominante (Soil Taxonomy)")).toBeVisible();
  await expect(
    info.getByText("Responde la capa regional de Navarra: Gobierno de Navarra (IDENA) (escala 1:25.000 · edición 2023)."),
  ).toBeVisible();
  expect(mocks.infoRequests.map((url) => url.pathname)).toEqual(["/api/layers/soil-clay/info"]);
});

test("a tap where the regional layer has nothing says the national one answered", async ({ page }) => {
  const fallback = {
    ...emptyInfo("hydrogeology"),
    answered_by: {
      level: "national",
      layer_id: "hydrogeology",
      publisher: "Instituto Geológico y Minero de España (IGME)",
      detail: { scale_denominator: 200000, cell_m: null, edition: 2010 },
      area_id: null,
    },
    fallbacks: [{ layer_id: "catalonia-hydrogeology", reason: "upstream_timeout" }],
  };
  await mockEverything(page, { hydrogeology: { status: 200, body: JSON.stringify(fallback) } });
  await showParcel(page);
  await page.locator('[data-layer="hydrogeology"]').getByRole("checkbox").check();
  await map(page).click();
  const info = page.getByRole("region", { name: "En el punto tocado" });
  await expect(
    info.getByText("Unidades hidrogeológicas de Cataluña 1:25.000 no ha respondido a tiempo: responde la capa nacional."),
  ).toBeVisible();
  await expect(
    info.getByText("Responde la capa nacional: Instituto Geológico y Minero de España (IGME) (escala 1:200.000 · edición 2010)."),
  ).toBeVisible();
});

test("an area whose boundary cannot be read leaves the national layer and says so", async ({ page }) => {
  const config = JSON.parse(MAP) as { overlays: { id: string; regional: { area_ids: string[] }[] }[] };
  const soil = config.overlays.find((o) => o.id === "soil-clay")?.regional[0];
  expect(soil?.area_ids).toEqual(["ES-NC"]);
  const mocks = await mockEverything(page, {}, { ...TAFALLA, zoom: 13 });
  await page.unroute("**/api/areas/*");
  let asked = 0;
  await page.route("**/api/areas/*", (route) => {
    asked += 1;
    return route.fulfill({ status: 504, contentType: "application/json", body: '{"code":"upstream_timeout"}' });
  });
  const errors = consoleErrors(page);
  await page.goto("/");
  await page.locator('[data-layer="soil-clay"]').getByRole("checkbox").check();
  await expect(page.getByText("No se ha podido leer el límite oficial de Navarra")).toBeVisible();
  // Asked once, not again for every tile; its tiles are blank, not errors.
  expect(asked).toBe(1);
  // The browser logs the failed request itself; nothing else may fail.
  expect(errors.filter((text) => !text.includes("status of 504"))).toEqual([]);
  // Without its boundary the regional service is not asked; SoilGrids still draws.
  await expect.poll(() => mocks.urls.filter((url) => url.startsWith("https://maps.isric.org/")).length).toBeGreaterThan(0);
  expect(mocks.urls.filter((url) => url.startsWith("https://idena.navarra.es/"))).toEqual([]);
});
