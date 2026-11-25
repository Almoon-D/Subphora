// Copyright (c) 2026 Almoon-D. All rights reserved.
// Drawing a point or a polygon on the map, in a real browser against a mocked API: while
// drawing, a click on the map belongs to the drawing, not to the tap.
import { readFileSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

const fixture = (name: string) => readFileSync(new URL(`fixtures/${name}`, import.meta.url), "utf-8");
const MAP = fixture("map.json");
const POINT = JSON.parse(fixture("area-point-daimiel.json")) as Record<string, unknown>;
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
  "base64",
);
// Over Daimiel, close enough for clicks a few hundred pixels apart to stay in Spain.
const VIEW = { longitude: -3.61, latitude: 39.07, zoom: 12 };

type Ring = [number, number][];

interface Mocks {
  polygons: Ring[];
  points: URL[];
  taps: number;
  searches: number;
}

/** The answer the API gives a drawn polygon, built around the ring it was sent. */
function drawnArea(ring: Ring) {
  const lons = ring.map(([lon]) => lon);
  const lats = ring.map(([, lat]) => lat);
  return {
    ...POINT,
    origin: "drawn_polygon",
    label: null,
    geometry: { type: "MultiPolygon", coordinates: [[ring]] },
    bbox: [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)],
    area_m2: 1234567,
  };
}

async function mockEverything(page: Page, polygon: { status: number; body: string } | null = null): Promise<Mocks> {
  const mocks: Mocks = { polygons: [], points: [], taps: 0, searches: 0 };
  const map = { ...(JSON.parse(MAP) as object), initial_view: VIEW };
  await page.route("**/api/map", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify(map) }));
  await page.route("**/api/layers/*/info?*", (route) => {
    mocks.taps += 1;
    return route.fulfill({ status: 404, contentType: "application/json", body: '{"code":"no_feature_info"}' });
  });
  await page.route("**/api/search?*", (route) => {
    mocks.searches += 1;
    return route.fulfill({ status: 404, contentType: "application/json", body: '{"code":"no_match"}' });
  });
  await page.route("**/api/aoi/polygon", (route) => {
    const body = route.request().postDataJSON() as { type: string; coordinates: Ring[] };
    const ring = body.coordinates[0] ?? [];
    mocks.polygons.push(ring);
    const answer = polygon ?? { status: 200, body: JSON.stringify(drawnArea(ring)) };
    return route.fulfill({ status: answer.status, contentType: "application/json", body: answer.body });
  });
  await page.route("**/api/aoi/point?*", (route) => {
    const url = new URL(route.request().url());
    mocks.points.push(url);
    const centre = [Number(url.searchParams.get("x")), Number(url.searchParams.get("y"))];
    const area = { ...POINT, origin: "drawn_point", label: "39.07, -3.61", geometry: { type: "Point", coordinates: centre } };
    return route.fulfill({ contentType: "application/json", body: JSON.stringify(area) });
  });
  for (const host of ["https://www.ign.es/**", "https://ovc.catastro.meh.es/**"]) {
    await page.route(host, (route) => route.fulfill({ contentType: "image/png", body: PNG }));
  }
  return mocks;
}

/** Click the map at an offset from its centre, in pixels. */
async function clickMap(page: Page, dx: number, dy: number): Promise<void> {
  const box = await page.locator(".maplibregl-canvas").boundingBox();
  if (!box) {
    throw new Error("the map has no size");
  }
  await page.mouse.click(box.x + box.width / 2 + dx, box.y + box.height / 2 + dy);
}

async function mapReady(page: Page): Promise<void> {
  await expect(page.locator(".map")).toHaveAttribute("data-base", "pnoa");
}

test("a drawn polygon becomes the selected area", async ({ page }) => {
  const mocks = await mockEverything(page);
  await page.goto("/");
  await mapReady(page);

  await page.getByRole("button", { name: "Dibujar un polígono" }).click();
  await expect(page.getByText("Toca el mapa para añadir vértices (0 de 200 como máximo).")).toBeVisible();
  const finish = page.getByRole("button", { name: "Terminar" });
  await expect(finish).toBeDisabled();

  await clickMap(page, -100, -80);
  await clickMap(page, 120, -60);
  await expect(page.locator(".map")).toHaveAttribute("data-draft", "polygon:2");
  await expect(finish).toBeDisabled();
  await clickMap(page, 40, 110);
  await expect(page.locator(".map")).toHaveAttribute("data-draft", "polygon:3");
  // The clicks drew; none of them was a tap.
  await expect(page.getByRole("heading", { name: "En el punto tocado" })).toBeHidden();
  expect(mocks.taps).toBe(0);

  // Undo the last vertex, and put another one instead.
  await page.getByRole("button", { name: "Deshacer" }).click();
  await expect(page.locator(".map")).toHaveAttribute("data-draft", "polygon:2");
  await clickMap(page, 20, 120);
  await finish.click();

  await expect(page.getByRole("heading", { name: "Polígono dibujado" })).toBeVisible();
  await expect(page.getByText("Superficie: 1.234.567 m² (123,46 ha)")).toBeVisible();
  await expect(page.locator(".map")).toHaveAttribute("data-area", "drawn_polygon:");
  await expect(page.locator(".map")).toHaveAttribute("data-draft", "");
  // One closed ring of three vertices, west to east, around the view's centre.
  const [ring] = mocks.polygons;
  expect(ring).toHaveLength(4);
  expect(ring?.[0]).toEqual(ring?.[3]);
  const [first, second] = ring ?? [];
  expect(first?.[0]).toBeLessThan(VIEW.longitude);
  expect(second?.[0]).toBeGreaterThan(VIEW.longitude);
  expect(first?.[1]).toBeGreaterThan(VIEW.latitude);

  // Drawing is over: a click is a tap again.
  await clickMap(page, 0, 0);
  await expect(page.getByRole("heading", { name: "En el punto tocado" })).toBeVisible();
});

test("a drawn point becomes the selected area", async ({ page }) => {
  const mocks = await mockEverything(page);
  await page.goto("/");
  await mapReady(page);
  await page.getByRole("button", { name: "Dibujar un punto" }).click();
  await expect(page.getByText("Toca el mapa donde quieras el punto.")).toBeVisible();
  await clickMap(page, 0, 0);

  await expect(page.getByRole("heading", { name: "Punto dibujado: 39.07, -3.61" })).toBeVisible();
  expect(mocks.points).toHaveLength(1);
  const asked = mocks.points[0];
  expect(asked?.searchParams.get("origin")).toBe("drawn_point");
  expect(asked?.searchParams.get("crs")).toBe("OGC:CRS84");
  expect(Number(asked?.searchParams.get("x"))).toBeCloseTo(VIEW.longitude, 2);
  expect(Number(asked?.searchParams.get("y"))).toBeCloseTo(VIEW.latitude, 2);
  await expect(page.locator(".map")).toHaveAttribute("data-area", "drawn_point:39.07, -3.61");
  expect(mocks.taps).toBe(0);
});

test("a cancelled drawing leaves nothing, and clicks are taps again", async ({ page }) => {
  const mocks = await mockEverything(page);
  await page.goto("/");
  await mapReady(page);
  await page.getByRole("button", { name: "Dibujar un polígono" }).click();
  await clickMap(page, -50, -50);
  await page.getByRole("button", { name: "Cancelar" }).click();
  await expect(page.locator(".map")).toHaveAttribute("data-draft", "");
  await clickMap(page, 0, 0);
  await expect(page.getByRole("heading", { name: "En el punto tocado" })).toBeVisible();
  expect(mocks.polygons).toEqual([]);
});

test("a polygon the server refuses explains itself", async ({ page }) => {
  await mockEverything(page, { status: 400, body: '{"code":"invalid_polygon","detail":"sides cross"}' });
  await page.goto("/");
  await mapReady(page);
  await page.getByRole("button", { name: "Dibujar un polígono" }).click();
  await clickMap(page, -100, -100);
  await clickMap(page, 100, 100);
  await clickMap(page, 100, -100);
  await page.getByRole("button", { name: "Terminar" }).click();
  await expect(page.getByRole("alert")).toHaveText(
    "El polígono no es válido: necesita al menos tres vértices distintos y sus lados no pueden cruzarse.",
  );
  await expect(page.locator(".area")).toHaveCount(0);
});

test("a search while drawing ends the drawing", async ({ page }) => {
  const mocks = await mockEverything(page);
  await page.goto("/");
  await mapReady(page);
  await page.getByRole("button", { name: "Dibujar un polígono" }).click();
  await clickMap(page, -50, -50);
  await page.getByLabel("Buscar un lugar").fill("Daimiel");
  await page.getByRole("button", { name: "Buscar", exact: true }).click();
  await expect(page.locator(".map")).toHaveAttribute("data-draft", "");
  expect(mocks.searches).toBe(1);
});
