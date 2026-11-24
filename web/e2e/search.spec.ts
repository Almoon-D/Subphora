// Copyright (c) 2026 Almoon-D. All rights reserved.
// The search flow in a real browser, against a mocked API. Every request that would leave
// the machine (the API, PNOA tiles, Catastro's WMS) is answered here.
import { readFileSync } from "node:fs";

import { expect, test, type Page, type Request } from "@playwright/test";

const fixture = (name: string) => readFileSync(new URL(`fixtures/${name}`, import.meta.url), "utf-8");
const MAP = fixture("map.json");
const PARCEL = fixture("parcel-santiago.json");
const REFERENCE = "7279701NH3477G";
// A 1×1 transparent PNG: the stand-in for every tile and cadastral image.
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
  "base64",
);

interface Mocks {
  parcelRequests: string[];
  cadastreRequests: URL[];
}

async function mockEverything(page: Page, parcel: { status: number; body: string }): Promise<Mocks> {
  const mocks: Mocks = { parcelRequests: [], cadastreRequests: [] };
  await page.route("**/api/map", (route) => route.fulfill({ contentType: "application/json", body: MAP }));
  await page.route("**/api/parcels/**", (route) => {
    mocks.parcelRequests.push(new URL(route.request().url()).pathname);
    return route.fulfill({ status: parcel.status, contentType: "application/json", body: parcel.body });
  });
  await page.route("https://www.ign.es/**", (route) => route.fulfill({ contentType: "image/png", body: PNG }));
  await page.route("https://ovc.catastro.meh.es/**", (route) => {
    mocks.cadastreRequests.push(new URL(route.request().url()));
    return route.fulfill({ contentType: "image/png", body: PNG });
  });
  return mocks;
}

async function search(page: Page, reference: string): Promise<void> {
  await page.getByLabel("Referencia catastral").fill(reference);
  await page.getByRole("button", { name: "Buscar" }).click();
}

test("a reference outlines its parcel on PNOA with the cadastral layer", async ({ page }) => {
  const mocks = await mockEverything(page, { status: 200, body: PARCEL });
  const tiles: Request[] = [];
  page.on("request", (request) => {
    if (request.url().startsWith("https://www.ign.es/wmts/pnoa-ma?")) {
      tiles.push(request);
    }
  });
  await page.goto("/");
  await expect(page.getByText("Acerca el mapa para ver las parcelas catastrales.")).toBeVisible();

  await search(page, ` ${REFERENCE.toLowerCase()} `);

  await expect(page.getByRole("heading", { name: `Parcela ${REFERENCE}` })).toBeVisible();
  await expect(page.getByText("SANTIAGO DE COMPOSTELA (A CORUÑA)")).toBeVisible();
  await expect(page.getByText("Superficie catastral: 13.352 m² (1,34 ha)")).toBeVisible();
  await expect(page.getByText(/Punto de referencia \(EPSG:25829\)/)).toBeVisible();
  // The map holds the parcel's outline.
  await expect(page.getByRole("region", { name: `Parcela ${REFERENCE}` })).toHaveAttribute("data-parcel", REFERENCE);
  expect(mocks.parcelRequests).toEqual([`/api/parcels/${REFERENCE.toLowerCase()}`]);

  // Zoomed to the parcel, the cadastral layer is one untiled image of the whole view.
  await expect.poll(() => mocks.cadastreRequests.length).toBeGreaterThan(0);
  await expect(page.getByText("Acerca el mapa para ver las parcelas catastrales.")).toBeHidden();
  const image = mocks.cadastreRequests.at(-1);
  expect(image?.searchParams.get("REQUEST")).toBe("GetMap");
  expect(image?.searchParams.get("CRS")).toBe("EPSG:3857");
  expect(image?.searchParams.get("LAYERS")).toBe("CP.CadastralParcel");
  const [west, south, east, north] = (image?.searchParams.get("BBOX") ?? "").split(",").map(Number);
  // The parcel's reference point, in EPSG:3857 metres, lies inside the requested view.
  const x = -951201;
  const y = 5293821;
  expect(west).toBeLessThan(x);
  expect(east).toBeGreaterThan(x);
  expect(south).toBeLessThan(y);
  expect(north).toBeGreaterThan(y);
  const viewport = page.viewportSize();
  expect(Number(image?.searchParams.get("WIDTH"))).toBeGreaterThan((viewport?.width ?? 0) / 2);

  expect(tiles.length).toBeGreaterThan(0);
  await expect(page.locator(".maplibregl-ctrl-attrib")).toContainText("PNOA CC-BY 4.0 scne.es");
  await expect(page.locator(".maplibregl-ctrl-attrib")).toContainText("Dirección General del Catastro");
  await expect(page.getByText(/Fuente: Dirección General del Catastro, consultado el/)).toBeVisible();
});

test("moving the map asks for one new image, not tiles", async ({ page }) => {
  const mocks = await mockEverything(page, { status: 200, body: PARCEL });
  await page.goto("/");
  await search(page, REFERENCE);
  await expect.poll(() => mocks.cadastreRequests.length).toBeGreaterThan(0);
  const before = mocks.cadastreRequests.length;

  const map = page.locator(".maplibregl-canvas");
  const box = await map.boundingBox();
  if (!box) {
    throw new Error("the map has no size");
  }
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 120, box.y + box.height / 2 + 60, { steps: 5 });
  await page.mouse.up();

  await expect.poll(() => mocks.cadastreRequests.length).toBe(before + 1);
  const moved = mocks.cadastreRequests.at(-1)?.searchParams.get("BBOX");
  expect(moved).not.toBe(mocks.cadastreRequests[before - 1]?.searchParams.get("BBOX"));
});

const failures = [
  { status: 400, code: "malformed_reference", message: "La referencia catastral no es válida" },
  { status: 404, code: "parcel_not_found", message: "Catastro no tiene ninguna parcela con esa referencia." },
  { status: 422, code: "territory_not_supported", message: "Navarra o en el País Vasco" },
  { status: 502, code: "upstream_error", message: "Catastro ha respondido con un error." },
  { status: 504, code: "upstream_timeout", message: "Catastro no ha respondido a tiempo." },
];

for (const { status, code, message } of failures) {
  test(`an answer ${String(status)} ${code} explains itself in Spanish`, async ({ page }) => {
    await mockEverything(page, { status, body: JSON.stringify({ code, detail: "English detail" }) });
    await page.goto("/");
    await search(page, "29015A16799999");
    await expect(page.getByRole("alert")).toContainText(message);
    await expect(page.getByText("English detail")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: /Parcela/ })).toHaveCount(0);
  });
}

test("an empty search asks for a reference without calling the API", async ({ page }) => {
  const mocks = await mockEverything(page, { status: 200, body: PARCEL });
  await page.goto("/");
  await search(page, "   ");
  await expect(page.getByRole("alert")).toHaveText("Escribe una referencia catastral.");
  expect(mocks.parcelRequests).toEqual([]);
});

test("an unreachable API is reported", async ({ page }) => {
  await mockEverything(page, { status: 200, body: PARCEL });
  await page.route("**/api/parcels/**", (route) => route.abort("connectionrefused"));
  await page.goto("/");
  await search(page, REFERENCE);
  await expect(page.getByRole("alert")).toHaveText("No se puede conectar con el servidor de Subphora.");
});

test("a map that cannot be configured is reported", async ({ page }) => {
  await page.route("**/api/map", (route) => route.fulfill({ status: 500, body: "{}" }));
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("No se ha podido cargar la configuración del mapa");
});
