// Copyright (c) 2026 Almoon-D. All rights reserved.
// Offline packs in a real browser with its service worker: a pack of an area downloaded
// with its detailed map, then the page reloaded with no network at all, showing the area,
// its detailed map, its candidates and its base-map tiles from the device; the Catastro
// map never stored; a download cut by a reload resumed with nothing stored twice; and a
// browser that refuses persistent storage, or has no space left. Every request is routed
// by the test (the service worker's own included), so nothing leaves the machine.
import { readFileSync } from "node:fs";

import { type BrowserContext, expect, type Page, test } from "@playwright/test";

const fixture = (name: string) => readFileSync(new URL(`fixtures/${name}`, import.meta.url), "utf-8");
const POINT = JSON.parse(fixture("area-point-daimiel.json")) as Record<string, unknown>;
const NATIONAL = fixture("national.json");
const DAIMIEL = fixture("parcel-daimiel.json");
const LEGAL = fixture("legal-daimiel.json");
const DAIMIEL_ID = (JSON.parse(DAIMIEL) as { job: { id: string } }).job.id;
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
  "base64",
);
const MAP = JSON.stringify({
  ...(JSON.parse(fixture("map.json")) as object),
  initial_view: { longitude: -3.6115, latitude: 39.0675, zoom: 15 },
});

test.use({ serviceWorkers: "allow" });

interface Network {
  /** False: every request fails as if there were no coverage. */
  reachable: boolean;
  /** PNOA tile URLs answered, each time one was. */
  tiles: string[];
  /** Hold every PNOA tile request from this many answered on, until released. */
  holdAfter: number | null;
  /** Every URL asked of a Catastro host. */
  catastro: string[];
}

async function mockNetwork(context: BrowserContext): Promise<Network> {
  const network: Network = { reachable: true, tiles: [], holdAfter: null, catastro: [] };
  const answer = (body: string) => ({ contentType: "application/json", body });
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (!network.reachable) {
      return route.abort("internetdisconnected");
    }
    if (url.hostname.includes("catastro")) {
      network.catastro.push(url.href);
      return route.fulfill({ contentType: "image/png", body: PNG });
    }
    if (url.protocol === "https:" && !url.pathname.startsWith("/wmts/pnoa-ma")) {
      return route.fulfill({ contentType: "image/png", body: PNG });
    }
    if (url.protocol === "https:") {
      if (network.holdAfter !== null && network.tiles.length >= network.holdAfter) {
        // Never answered: the reload cuts the download here.
        return new Promise<void>(() => undefined);
      }
      network.tiles.push(url.href);
      return route.fulfill({ contentType: "image/jpeg", body: PNG });
    }
    const path = url.pathname;
    if (path === "/api/map") return route.fulfill(answer(MAP));
    if (path === "/api/national") return route.fulfill(answer(NATIONAL));
    if (path === "/api/legal") return route.fulfill(answer(LEGAL));
    if (path === "/api/parcel") return route.fulfill(answer(DAIMIEL));
    if (path === `/api/parcel/${DAIMIEL_ID}`) return route.fulfill(answer(DAIMIEL));
    if (path.startsWith("/api/parcel/") || path.startsWith("/api/national/tiles/")) {
      return route.fulfill({ contentType: "image/png", body: PNG });
    }
    if (path.startsWith("/api/")) return route.fulfill({ status: 404, ...answer('{"code":"not_found"}') });
    return route.continue();
  });
  return network;
}

/** Open the page with the Daimiel point selected (kept by this tab through reloads), once
 * the service worker controls it. */
async function open(page: Page): Promise<void> {
  await page.addInitScript((session) => {
    if (!window.sessionStorage.getItem("subphora.session-areas")) {
      window.sessionStorage.setItem("subphora.session-areas", session);
    }
  }, JSON.stringify({ areas: [POINT], selected: 0 }));
  await page.goto("/");
  await page.waitForFunction(() => navigator.serviceWorker.controller !== null);
  await expect(page.locator(".map")).toHaveAttribute("data-base", "pnoa");
}

const packs = (page: Page) => page.locator("section.packs");
// Every file of a pack goes through the test's routing: a few hundred take some seconds.
const DOWNLOADED = { timeout: 60_000 };
const detailed = (page: Page) => page.locator("section.parcel");

async function computeDetailedMap(page: Page): Promise<void> {
  await detailed(page).getByRole("button", { name: "Calcular el mapa detallado" }).click();
  await expect(detailed(page)).toHaveAttribute("data-state", "done");
}

/** Show the IGN map, so that every PNOA tile asked for is the download's. */
async function showIgnMap(page: Page): Promise<void> {
  await page.getByRole("radio", { name: "Mapa IGN", exact: true }).check();
  await expect(page.locator(".map")).toHaveAttribute("data-base", "ign-base");
}

/** The URLs every pack cache holds. */
function stored(page: Page): Promise<string[]> {
  return page.evaluate(async () => {
    const names = (await caches.keys()).filter((name) => name.startsWith("subphora-pack-"));
    const urls = await Promise.all(names.map(async (name) => (await (await caches.open(name)).keys()).map((r) => r.url)));
    return urls.flat();
  });
}

test("a downloaded pack shows the area, its detailed map and its tiles with no network", async ({ context, page }) => {
  // A full download then an offline reload of the dev server's modules: about 19 s on a
  // fast machine, past the 30 s default on a loaded CI runner. Three times the budget.
  test.slow();
  const network = await mockNetwork(context);
  await open(page);
  await computeDetailedMap(page);
  const plan = packs(page).locator(".pack-plan");
  await expect(plan).toContainText("Ortofoto PNOA:");
  await expect(plan).toContainText("5 puntos candidatos");
  await expect(plan).toContainText("Tamaño estimado:");
  // The Catastro map is left out, with the reason; the parcel's outline is kept instead.
  await plan.getByText("No se guarda:").click();
  await expect(plan.locator('[data-reason="forbidden"]')).toContainText("Mapa catastral");
  await expect(plan.locator('[data-reason="forbidden"]')).toContainText("sus condiciones prohíben guardarlo");
  const files = Number(await plan.getAttribute("data-files"));
  const catastroBefore = network.catastro.length;

  await packs(page).getByRole("button", { name: /Descargar el paquete/ }).click();
  const item = packs(page).locator("li.pack");
  await expect(item).toHaveAttribute("data-state", "complete", DOWNLOADED);
  await expect(item).toHaveAttribute("data-files", `${String(files)}/${String(files)}`);
  const kept = await stored(page);
  expect(kept).toHaveLength(files);
  expect(kept.some((url) => url.includes("catastro"))).toBe(false);
  expect(network.catastro.length).toBe(catastroBefore);
  const tile = kept.find((url) => url.startsWith("https://www.ign.es/wmts/pnoa-ma?")) ?? "";

  // No coverage at all: the page, its settings, the area and its detailed map come back.
  network.reachable = false;
  await context.setOffline(true);
  await page.reload();
  await expect(page.locator(".map")).toHaveAttribute("data-base", "pnoa");
  await expect(page.locator(".map")).toHaveAttribute("data-area", "coordinates:39.067500, -3.611500");
  await expect(page.locator(".map")).toHaveAttribute("data-parcel", `${DAIMIEL_ID}:potential-index:5`);
  await expect(packs(page).getByRole("status")).toContainText("Sin conexión");
  await expect(detailed(page).locator(".candidate")).toHaveCount(5);
  // A stored tile answers from the device; one outside the pack fails as the network does.
  const answers = await page.evaluate(async (url) => {
    const inPack = await fetch(url).then((r) => r.status, () => 0);
    const outside = await fetch(url.replace("tilecol=", "tilecol=9")).then((r) => r.status, () => 0);
    return { inPack, outside };
  }, tile);
  expect(answers).toEqual({ inPack: 200, outside: 0 });

  // Opening the pack selects its area again, as a new session would need.
  await packs(page).getByRole("button", { name: "Abrir" }).click();
  await expect(page.locator(".map")).toHaveAttribute("data-parcel", `${DAIMIEL_ID}:potential-index:5`);

  await packs(page).getByRole("button", { name: "Borrar" }).click();
  await expect(packs(page)).toContainText("Aún no hay paquetes guardados.");
  expect(await stored(page)).toHaveLength(0);
});

test("a download cut by a reload resumes, storing nothing twice", async ({ context, page }) => {
  const network = await mockNetwork(context);
  await open(page);
  await showIgnMap(page);
  await computeDetailedMap(page);
  const files = Number(await packs(page).locator(".pack-plan").getAttribute("data-files"));
  network.holdAfter = network.tiles.length + 40;
  await packs(page).getByRole("button", { name: /Descargar el paquete/ }).click();
  await expect(packs(page).locator(".pack-progress")).toContainText("Descargando");
  // The download runs at the runner's pace, so these waits take the download's timeout.
  await expect.poll(() => network.tiles.length, DOWNLOADED).toBeGreaterThanOrEqual(network.holdAfter);
  // Give the stored files time to be written down, then close the page mid-download.
  await expect.poll(async () => (await stored(page)).length, DOWNLOADED).toBeGreaterThanOrEqual(30);
  // The held requests stay unanswered; the reloaded page's map is answered again.
  network.holdAfter = null;
  await page.reload();
  await showIgnMap(page);
  const item = packs(page).locator("li.pack");
  await expect(item).toHaveAttribute("data-state", "interrupted");
  await expect(item).toContainText("puedes reanudarla");
  const before = new Set(await stored(page));
  expect(before.size).toBeLessThan(files);

  const answeredBefore = network.tiles.length;
  await item.getByRole("button", { name: "Reanudar" }).click();
  await expect(item).toHaveAttribute("data-state", "complete", DOWNLOADED);
  await expect(item).toHaveAttribute("data-files", `${String(files)}/${String(files)}`);
  const resumed = network.tiles.slice(answeredBefore);
  // Only what was missing was asked for again.
  expect(resumed.filter((url) => before.has(url))).toEqual([]);
  expect(await stored(page)).toHaveLength(files);
});

test.describe("a browser that refuses storage", () => {
  test("goes ahead without persistent storage, and says the pack may be cleared", async ({ context, page }) => {
    await mockNetwork(context);
    await page.addInitScript(() => {
      Object.defineProperty(navigator.storage, "persist", { value: () => Promise.resolve(false) });
      Object.defineProperty(navigator.storage, "persisted", { value: () => Promise.resolve(false) });
    });
    await open(page);
    await packs(page).getByRole("button", { name: /Descargar el paquete/ }).click();
    const item = packs(page).locator("li.pack");
    await expect(item).toHaveAttribute("data-state", "complete", DOWNLOADED);
    await expect(item).toContainText("podría borrar el paquete");
  });

  test("refuses a pack the device has no space for, storing nothing", async ({ context, page }) => {
    await mockNetwork(context);
    await page.addInitScript(() => {
      Object.defineProperty(navigator.storage, "estimate", { value: () => Promise.resolve({ quota: 1000, usage: 900 }) });
    });
    await open(page);
    await packs(page).getByRole("button", { name: /Descargar el paquete/ }).click();
    await expect(packs(page).getByRole("alert")).toContainText("No queda espacio suficiente");
    await expect(packs(page)).toContainText("Aún no hay paquetes guardados.");
    expect(await stored(page)).toHaveLength(0);
  });
});
