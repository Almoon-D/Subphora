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
];

interface Mocks {
  /** Every request to a map service or to the API's layer routes. */
  urls: string[];
  infoRequests: URL[];
}

async function mockEverything(page: Page, info: Record<string, { status: number; body: string }> = {}): Promise<Mocks> {
  const mocks: Mocks = { urls: [], infoRequests: [] };
  await page.route("**/api/map", (route) => route.fulfill({ contentType: "application/json", body: MAP }));
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

function emptyInfo(layer: string) {
  return { layer_id: layer, features: [], source: source("x") };
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
  await expect(info.getByRole("heading", { name: "Piezómetros (red oficial)" })).toBeVisible();
  await expect(info.getByText("El servicio ha respondido con un error.")).toBeVisible();
  await expect(info.getByText("English detail")).toHaveCount(0);
  await expect(page.locator(".maplibregl-marker")).toHaveCount(1);
  // SoilGrids answers no value to a tap: it is not asked.
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
