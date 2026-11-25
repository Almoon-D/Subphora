// Copyright (c) 2026 Almoon-D. All rights reserved.
// The national water-potential map in a real browser against a mocked API: its layers and
// legends, and a tap that explains the index with its confidence.
import { readFileSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

const fixture = (name: string) => readFileSync(new URL(`fixtures/${name}`, import.meta.url), "utf-8");
const MAP = JSON.parse(fixture("map.json")) as Record<string, unknown>;
const NATIONAL = fixture("national.json");
const EXPLAIN = fixture("explain-madrid.json");
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
  "base64",
);
// The synthetic region of national.json: a small box in Madrid.
const MADRID = { longitude: -3.7, latitude: 40.42, zoom: 13 };

interface Mocks {
  tiles: string[];
  explained: URL[];
}

async function mockApi(page: Page, national: string | null, explain = { status: 200, body: EXPLAIN }): Promise<Mocks> {
  const mocks: Mocks = { tiles: [], explained: [] };
  await page.route("**/api/map", (route) =>
    route.fulfill({ contentType: "application/json", body: JSON.stringify({ ...MAP, initial_view: MADRID }) }),
  );
  await page.route("**/api/national", (route) =>
    national === null
      ? route.fulfill({ status: 500, contentType: "application/json", body: "{}" })
      : route.fulfill({ contentType: "application/json", body: national }),
  );
  await page.route("**/api/national/tiles/**", (route) => {
    mocks.tiles.push(route.request().url());
    return route.fulfill({ contentType: "image/png", body: PNG });
  });
  await page.route("**/api/national/explain?**", (route) => {
    mocks.explained.push(new URL(route.request().url()));
    return route.fulfill({ status: explain.status, contentType: "application/json", body: explain.body });
  });
  // Every map service the page might ask (base map, cadastre) answers a blank tile.
  await page.route(/^https:\/\//, (route) => route.fulfill({ contentType: "image/png", body: PNG }));
  return mocks;
}

const map = (page: Page) => page.locator(".map");
const panel = (page: Page) => page.locator("fieldset.national");

async function tapCentre(page: Page): Promise<void> {
  const box = await map(page).boundingBox();
  if (!box) {
    throw new Error("the map has no box");
  }
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
}

test("the index is drawn when the map opens, with a legend that says index", async ({ page }) => {
  const mocks = await mockApi(page, NATIONAL);
  await page.goto("/");
  await expect(map(page)).toHaveAttribute("data-national", "potential-index");
  await expect.poll(() => mocks.tiles.length).toBeGreaterThan(0);
  expect(mocks.tiles.every((url) => new URL(url).pathname.startsWith("/api/national/tiles/potential-index/"))).toBe(true);
  const index = panel(page).locator('[data-layer="potential-index"]');
  await expect(index.locator('[data-legend="potential-index"]')).toContainText("Índice relativo (no es una probabilidad)");
  await expect(index.locator('[data-legend="potential-index"]')).toContainText("0,20 – 0,40");
  await expect(panel(page)).toContainText("No es una probabilidad de encontrar agua");
  await expect(panel(page)).not.toContainText("probabilidad de agua");
  await expect(page.locator(".maplibregl-ctrl-attrib")).toContainText("Origen de los datos: © CN Instituto Geológico y Minero de España (IGME)");
});

test("the confidence, slope, drainage and wetness layers switch on with their legends", async ({ page }) => {
  const mocks = await mockApi(page, NATIONAL);
  await page.goto("/");
  for (const id of ["potential-confidence", "terrain-slope", "terrain-drainage", "terrain-wetness"]) {
    const item = panel(page).locator(`[data-layer="${id}"]`);
    await item.getByRole("checkbox").check();
    await expect(item.locator(`[data-legend="${id}"] li`).first()).toBeVisible();
  }
  await expect(map(page)).toHaveAttribute(
    "data-national",
    "potential-index potential-confidence terrain-slope terrain-drainage terrain-wetness",
  );
  await expect(panel(page).locator('[data-legend="potential-confidence"]')).toContainText("Confianza");
  await expect(panel(page).locator('[data-legend="terrain-slope"]')).toContainText("≥ 30°");
  await expect(panel(page).locator('[data-legend="terrain-drainage"]')).toContainText("2,0 km");
  await expect.poll(() => mocks.tiles.some((url) => url.includes("/terrain-wetness/"))).toBe(true);
});

test("a tap explains the index with its confidence, inputs and missing data", async ({ page }) => {
  const mocks = await mockApi(page, NATIONAL);
  await page.goto("/");
  await expect(map(page)).toHaveAttribute("data-national", "potential-index");
  await tapCentre(page);
  const explanation = page.locator(".national-explanation");
  await expect(explanation.locator(".score")).toContainText("Índice 0,76");
  await expect(explanation.locator(".score")).toContainText("Confianza media (0,67)");
  await expect(explanation.locator('[data-criterion="permeability"]')).toContainText("ALTA (CARBONATADAS-ALTA)");
  await expect(explanation.locator('[data-criterion="groundwater_body"]')).toContainText("Malo");
  await expect(explanation.locator('[data-missing="no_dataset"]')).toHaveCount(3);
  await expect(explanation.locator('[data-component="skill"]')).toContainText("sin medir todavía");
  await expect(explanation).toContainText("No es una probabilidad");
  const [asked] = mocks.explained;
  expect(Number(asked?.searchParams.get("lon"))).toBeCloseTo(MADRID.longitude, 2);
  expect(Number(asked?.searchParams.get("lat"))).toBeCloseTo(MADRID.latitude, 2);
});

test("a tap outside the regions built says so", async ({ page }) => {
  await mockApi(page, NATIONAL, { status: 404, body: '{"code":"outside_built_area"}' });
  await page.goto("/");
  await expect(map(page)).toHaveAttribute("data-national", "potential-index");
  await tapCentre(page);
  await expect(page.locator(".national-explanation .error")).toContainText("fuera de las zonas calculadas");
});

test("before any build the panel says how to build it and the map draws nothing of it", async ({ page }) => {
  const unbuilt = { ...(JSON.parse(NATIONAL) as object), built: false, regions: [], bounds: null, rendered_at: null };
  const mocks = await mockApi(page, JSON.stringify(unbuilt));
  await page.goto("/");
  await expect(panel(page)).toHaveAttribute("data-built", "false");
  await expect(panel(page)).toContainText("subphora national build");
  await expect(map(page)).toHaveAttribute("data-national", "");
  await tapCentre(page);
  await expect(page.locator(".info")).toContainText("Activa una capa con consulta");
  expect(mocks.tiles).toEqual([]);
  expect(mocks.explained).toEqual([]);
});

test("when the national map cannot be read the rest of the page still works", async ({ page }) => {
  await mockApi(page, null);
  await page.goto("/");
  await expect(page.getByText("No se ha podido leer el mapa nacional")).toBeVisible();
  await expect(page.locator('[data-layer="groundwater-status"]')).toBeVisible();
});
