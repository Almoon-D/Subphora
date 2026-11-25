// Copyright (c) 2026 Almoon-D. All rights reserved.
// The search flow in a real browser, against a mocked API. Every request that would leave
// the machine (the API, PNOA tiles, Catastro's WMS) is answered here.
import { readFileSync } from "node:fs";

import { expect, test, type Page, type Request } from "@playwright/test";

const fixture = (name: string) => readFileSync(new URL(`fixtures/${name}`, import.meta.url), "utf-8");
const MAP = fixture("map.json");
const SANTIAGO = fixture("area-santiago.json");
const CAMPOS = fixture("area-sigpac-campos.json");
const DAIMIEL = fixture("area-daimiel.json");
const POINT = fixture("area-point-daimiel.json");
const DAIMIEL_SEARCH = fixture("search-daimiel.json");
const REFERENCE = "7279701NH3477G";
// A 1×1 transparent PNG: the stand-in for every tile and cadastral image.
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
  "base64",
);

interface Answer {
  status: number;
  body: string;
}

const ok = (body: string): Answer => ({ status: 200, body });
const reading = (kind: string, origin: string, label: string, resolve: string) =>
  JSON.stringify({ interpretations: [{ kind, origin, label, detail: null, position: null, resolve }] });

/** What the API answers: /api/search by its text, /api/aoi/… by path and query. */
const SEARCHES: Record<string, Answer> = {
  [REFERENCE]: ok(reading("cadastral", "cadastral", REFERENCE, `/api/aoi/cadastral/${REFERENCE}`)),
  "34:48:0:0:13:12:1": ok(reading("sigpac", "sigpac_enclosure", "34:48:0:0:13:12:1", "/api/aoi/sigpac/34:48:0:0:13:12:1")),
  Daimiel: ok(DAIMIEL_SEARCH),
  "39.0675, -3.6115": ok(
    reading(
      "coordinates",
      "coordinates",
      "39.067500, -3.611500",
      "/api/aoi/point?crs=OGC%3ACRS84&x=-3.6115&y=39.0675&origin=coordinates",
    ),
  ),
};
const AREAS: Record<string, Answer> = {
  [`/api/aoi/cadastral/${REFERENCE}`]: ok(SANTIAGO),
  "/api/aoi/sigpac/34:48:0:0:13:12:1": ok(CAMPOS),
  "/api/aoi/place?type=Municipio&id=13039": ok(DAIMIEL),
  "/api/aoi/point?crs=OGC%3ACRS84&x=-3.6115&y=39.0675&origin=coordinates": ok(POINT),
};

interface Mocks {
  searches: string[];
  areaRequests: string[];
  cadastreRequests: URL[];
}

async function mockEverything(
  page: Page,
  searches: Record<string, Answer> = SEARCHES,
  areas: Record<string, Answer> = AREAS,
): Promise<Mocks> {
  const mocks: Mocks = { searches: [], areaRequests: [], cadastreRequests: [] };
  await page.route("**/api/map", (route) => route.fulfill({ contentType: "application/json", body: MAP }));
  await page.route("**/api/search?*", (route) => {
    const text = new URL(route.request().url()).searchParams.get("q") ?? "";
    mocks.searches.push(text);
    const answer = searches[text] ?? { status: 404, body: '{"code":"no_match","source":"cartociudad"}' };
    return route.fulfill({ status: answer.status, contentType: "application/json", body: answer.body });
  });
  await page.route("**/api/aoi/**", (route) => {
    const url = new URL(route.request().url());
    const key = decodeURIComponent(url.pathname) + url.search;
    mocks.areaRequests.push(key);
    const answer = areas[key] ?? { status: 404, body: '{"code":"not_found"}' };
    return route.fulfill({ status: answer.status, contentType: "application/json", body: answer.body });
  });
  await page.route("https://www.ign.es/**", (route) => route.fulfill({ contentType: "image/png", body: PNG }));
  await page.route("https://ovc.catastro.meh.es/**", (route) => {
    mocks.cadastreRequests.push(new URL(route.request().url()));
    return route.fulfill({ contentType: "image/png", body: PNG });
  });
  return mocks;
}

async function search(page: Page, text: string): Promise<void> {
  await page.getByLabel("Buscar un lugar").fill(text);
  await page.getByRole("button", { name: "Buscar", exact: true }).click();
}

test("a cadastral reference outlines its parcel on PNOA with the cadastral layer", async ({ page }) => {
  const mocks = await mockEverything(page);
  const tiles: Request[] = [];
  page.on("request", (request) => {
    if (request.url().startsWith("https://www.ign.es/wmts/pnoa-ma?")) {
      tiles.push(request);
    }
  });
  await page.goto("/");
  await expect(page.getByText("Acerca el mapa para ver las parcelas catastrales.")).toBeVisible();

  await search(page, ` ${REFERENCE} `);

  await expect(page.getByRole("heading", { name: `Parcela ${REFERENCE}` })).toBeVisible();
  await expect(page.getByText("SANTIAGO DE COMPOSTELA (A CORUÑA)")).toBeVisible();
  await expect(page.getByText("Superficie catastral: 13.352 m² (1,34 ha)")).toBeVisible();
  await expect(page.getByText(/Punto de referencia \(EPSG:25829\)/)).toBeVisible();
  // The map holds the parcel's outline.
  await expect(page.getByRole("region", { name: `Parcela ${REFERENCE}` })).toHaveAttribute(
    "data-area",
    `cadastral:${REFERENCE}`,
  );
  expect(mocks.searches).toEqual([REFERENCE]);
  expect(mocks.areaRequests).toEqual([`/api/aoi/cadastral/${REFERENCE}`]);

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
  const mocks = await mockEverything(page);
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

test("a SIGPAC reference outlines its enclosure", async ({ page }) => {
  await mockEverything(page);
  await page.goto("/");
  await search(page, "34:48:0:0:13:12:1");
  await expect(page.getByRole("heading", { name: "Recinto SIGPAC: 34:48:0:0:13:12:1" })).toBeVisible();
  await expect(page.getByText("Provincia de Palencia")).toBeVisible();
  await expect(page.getByText("Superficie SIGPAC: 62.744 m² (6,27 ha)")).toBeVisible();
  await expect(page.getByText(/Fuente: SIGPAC, FEGA, CC BY 4.0/)).toBeVisible();
  await expect(page.locator(".map")).toHaveAttribute("data-area", "sigpac_enclosure:34:48:0:0:13:12:1");
  // The outline is SIGPAC's: the map's attribution names it while it is shown.
  await expect(page.locator(".maplibregl-ctrl-attrib")).toContainText("SIGPAC, FEGA, CC BY 4.0");
  await search(page, "nowhere at all");
  await expect(page.locator(".maplibregl-ctrl-attrib")).not.toContainText("SIGPAC");
});

test("coordinates become a point on the map", async ({ page }) => {
  await mockEverything(page);
  await page.goto("/");
  await search(page, "39.0675, -3.6115");
  await expect(page.getByRole("heading", { name: "Coordenadas: 39.067500, -3.611500" })).toBeVisible();
  await expect(page.getByText("Provincia de Ciudad Real")).toBeVisible();
  await expect(page.getByText(/Punto \(EPSG:25830\): X 447\.099, Y 4\.324\.445/)).toBeVisible();
  await expect(page.locator(".map")).toHaveAttribute("data-area", "coordinates:39.067500, -3.611500");
});

test("a text that reads several ways asks which one is meant", async ({ page }) => {
  const mocks = await mockEverything(page);
  await page.goto("/");
  await search(page, "Daimiel");
  await expect(page.getByRole("heading", { name: "¿Qué buscabas?" })).toBeVisible();
  const choices = page.getByRole("region", { name: "¿Qué buscabas?" }).getByRole("listitem");
  await expect(choices).toHaveCount(8);
  // Nothing is selected until a choice is made.
  expect(mocks.areaRequests).toEqual([]);
  await expect(page.locator(".map")).toHaveAttribute("data-area", "");

  await page.getByRole("button", { name: "Municipio: Daimiel, Ciudad Real (Ciudad Real)" }).click();
  await expect(page.getByRole("heading", { name: "Municipio: Daimiel (Ciudad Real)" })).toBeVisible();
  await expect(page.getByText("Daimiel (Ciudad Real)", { exact: true })).toBeVisible();
  await expect(page.getByText(/Fuente: CartoCiudad CC-BY 4.0 scne.es/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "¿Qué buscabas?" })).toBeHidden();
  expect(mocks.areaRequests).toEqual(["/api/aoi/place?type=Municipio&id=13039"]);
});

test("a choice can be declined", async ({ page }) => {
  await mockEverything(page);
  await page.goto("/");
  await search(page, "Daimiel");
  await page.getByRole("button", { name: "Ninguna" }).click();
  await expect(page.getByRole("heading", { name: "¿Qué buscabas?" })).toBeHidden();
});

test("the session's areas can be switched, and survive a reload of the tab", async ({ page }) => {
  await mockEverything(page);
  await page.goto("/");
  await search(page, REFERENCE);
  await expect(page.locator(".map")).toHaveAttribute("data-area", `cadastral:${REFERENCE}`);
  // One area: no list yet.
  await expect(page.getByRole("heading", { name: "Áreas de esta sesión" })).toBeHidden();
  await search(page, "34:48:0:0:13:12:1");
  await expect(page.locator(".map")).toHaveAttribute("data-area", "sigpac_enclosure:34:48:0:0:13:12:1");

  const list = page.locator(".session");
  await expect(list.getByRole("button")).toHaveText([`Parcela ${REFERENCE}`, "Recinto SIGPAC: 34:48:0:0:13:12:1"]);
  await expect(list.getByRole("button", { name: "Recinto SIGPAC: 34:48:0:0:13:12:1" })).toHaveAttribute(
    "aria-current",
    "true",
  );
  await list.getByRole("button", { name: `Parcela ${REFERENCE}` }).click();
  await expect(page.locator(".map")).toHaveAttribute("data-area", `cadastral:${REFERENCE}`);
  await expect(page.getByRole("heading", { name: `Parcela ${REFERENCE}` })).toBeVisible();

  // Searching for an area already listed selects it instead of adding it again.
  await search(page, "34:48:0:0:13:12:1");
  await expect(page.locator(".map")).toHaveAttribute("data-area", "sigpac_enclosure:34:48:0:0:13:12:1");
  await expect(list.getByRole("button")).toHaveCount(2);

  await page.reload();
  await expect(page.locator(".session").getByRole("button")).toHaveCount(2);
  await expect(page.locator(".map")).toHaveAttribute("data-area", "sigpac_enclosure:34:48:0:0:13:12:1");
});

const failures = [
  { status: 400, code: "malformed_reference", source: null, message: "La referencia catastral no es válida" },
  { status: 400, code: "malformed_sigpac", source: null, message: "La referencia SIGPAC no es válida" },
  { status: 400, code: "malformed_coordinates", source: null, message: "Las coordenadas no se entienden" },
  { status: 422, code: "wrong_utm_zone", source: null, message: "Con ese huso UTM el punto no cae en España" },
  { status: 422, code: "outside_country", source: "sigpac-queries", message: "Ese lugar no está en España" },
  { status: 404, code: "no_match", source: "cartociudad", message: "CartoCiudad no encuentra ningún lugar" },
  { status: 404, code: "not_found", source: "sigpac-queries", message: "SIGPAC no tiene ningún lugar con esa referencia." },
  { status: 422, code: "territory_not_supported", source: null, message: "Navarra o en el País Vasco" },
  { status: 502, code: "upstream_error", source: "catastro-wfs-parcels", message: "Catastro ha respondido con un error." },
  { status: 504, code: "upstream_timeout", source: "cartociudad", message: "CartoCiudad no ha respondido a tiempo." },
  { status: 502, code: "upstream_error", source: null, message: "El servicio ha respondido con un error." },
];

for (const { status, code, source, message } of failures) {
  test(`an answer ${String(status)} ${code} from ${String(source)} explains itself in Spanish`, async ({ page }) => {
    const body = JSON.stringify({ code, detail: "English detail", source });
    await mockEverything(page, { anything: { status, body } });
    await page.goto("/");
    await search(page, "anything");
    await expect(page.getByRole("alert")).toContainText(message);
    await expect(page.getByText("English detail")).toHaveCount(0);
    await expect(page.locator(".area")).toHaveCount(0);
  });
}

test("a failure while resolving a reading names its service", async ({ page }) => {
  await mockEverything(page, SEARCHES, {
    [`/api/aoi/cadastral/${REFERENCE}`]: { status: 504, body: '{"code":"upstream_timeout","source":"catastro-wfs-parcels"}' },
  });
  await page.goto("/");
  await search(page, REFERENCE);
  await expect(page.getByRole("alert")).toHaveText(
    "Catastro no ha respondido a tiempo. Vuelve a intentarlo en unos minutos.",
  );
});

test("an empty search asks for something without calling the API", async ({ page }) => {
  const mocks = await mockEverything(page);
  await page.goto("/");
  await search(page, "   ");
  await expect(page.getByRole("alert")).toHaveText(
    "Escribe una referencia catastral o SIGPAC, una dirección, un municipio o unas coordenadas.",
  );
  expect(mocks.searches).toEqual([]);
});

test("an unreachable API is reported", async ({ page }) => {
  await mockEverything(page);
  await page.route("**/api/search?*", (route) => route.abort("connectionrefused"));
  await page.goto("/");
  await search(page, REFERENCE);
  await expect(page.getByRole("alert")).toHaveText("No se puede conectar con el servidor de Subphora.");
});

test("a map that cannot be configured is reported", async ({ page }) => {
  await page.route("**/api/map", (route) => route.fulfill({ status: 500, body: "{}" }));
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("No se ha podido cargar la configuración del mapa");
});

test("a failed search after a found one leaves no area on the map", async ({ page }) => {
  await mockEverything(page);
  await page.goto("/");
  await search(page, REFERENCE);
  await expect(page.getByRole("region", { name: `Parcela ${REFERENCE}` })).toBeVisible();

  await search(page, "nowhere at all");
  await expect(page.getByRole("alert")).toContainText("CartoCiudad no encuentra ningún lugar");
  await expect(page.locator(".area")).toHaveCount(0);
  await expect(page.locator(".map")).toHaveAttribute("data-area", "");
});
