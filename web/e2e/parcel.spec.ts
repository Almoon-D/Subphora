// Copyright (c) 2026 Almoon-D. All rights reserved.
// The detailed map of an area in a real browser against a mocked API: the job while it
// runs, the area's mean, its layers drawn as one image, its candidates with their legal
// status, a tap that explains a cell, the failures, and two areas compared.
import { readFileSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

const fixture = (name: string) => readFileSync(new URL(`fixtures/${name}`, import.meta.url), "utf-8");
const MAP = fixture("map.json");
const POINT = JSON.parse(fixture("area-point-daimiel.json")) as Record<string, unknown>;
const CAMPOS = JSON.parse(fixture("area-sigpac-campos.json")) as Record<string, unknown>;
const QUEUED = JSON.parse(fixture("parcel-queued.json")) as { job: Record<string, unknown> };
const DAIMIEL = fixture("parcel-daimiel.json");
const CAMPOS_DONE = fixture("parcel-campos.json");
const EXPLAIN = fixture("explain-parcel-daimiel.json");
const LEGAL = fixture("legal-daimiel.json");
const DAIMIEL_ID = (JSON.parse(DAIMIEL) as { job: { id: string } }).job.id;
const CAMPOS_ID = (JSON.parse(CAMPOS_DONE) as { job: { id: string } }).job.id;
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
  "base64",
);
// Ask again at once: the test need not wait the configured seconds.
const QUEUED_NOW = JSON.stringify({ ...QUEUED, job: { ...QUEUED.job, poll_after_s: 0.05 } });

interface Answer {
  status: number;
  body: string;
}

interface Mocks {
  posted: unknown[];
  polled: string[];
  images: string[];
  explained: URL[];
}

/** The API: /api/parcel answers ``start`` to a POST (by the area's label), then ``done``. */
async function mockApi(page: Page, start: (label: string) => Answer, done: Record<string, string>): Promise<Mocks> {
  const mocks: Mocks = { posted: [], polled: [], images: [], explained: [] };
  await page.route("**/api/map", (route) => route.fulfill({ contentType: "application/json", body: MAP }));
  await page.route("**/api/national", (route) => route.fulfill({ status: 500, contentType: "application/json", body: "{}" }));
  await page.route("**/api/legal?*", (route) => route.fulfill({ contentType: "application/json", body: LEGAL }));
  await page.route("**/api/parcel", (route) => {
    const area = route.request().postDataJSON() as { label: string };
    mocks.posted.push(area);
    const answer = start(area.label);
    return route.fulfill({ status: answer.status, contentType: "application/json", body: answer.body });
  });
  await page.route(/\/api\/parcel\/[0-9a-f]{16}$/, (route) => {
    const id = new URL(route.request().url()).pathname.split("/").pop() ?? "";
    mocks.polled.push(id);
    return route.fulfill({ contentType: "application/json", body: done[id] ?? '{"code":"unknown_job"}' });
  });
  await page.route("**/api/parcel/*/layers/*", (route) => {
    mocks.images.push(new URL(route.request().url()).pathname);
    return route.fulfill({ contentType: "image/png", body: PNG });
  });
  await page.route("**/api/parcel/*/explain?*", (route) => {
    mocks.explained.push(new URL(route.request().url()));
    return route.fulfill({ contentType: "application/json", body: EXPLAIN });
  });
  await page.route(/^https:\/\//, (route) => route.fulfill({ contentType: "image/png", body: PNG }));
  return mocks;
}

/** Open the page with the session's areas already selected (this tab's storage). */
async function openWith(page: Page, areas: Record<string, unknown>[]): Promise<void> {
  await page.addInitScript((session) => {
    window.sessionStorage.setItem("subphora.session-areas", session);
  }, JSON.stringify({ areas, selected: 0 }));
  await page.goto("/");
}

const panel = (page: Page) => page.locator("section.parcel");
const map = (page: Page) => page.locator(".map");

test("an area's detailed map runs, then shows its mean, layer and candidates", async ({ page }) => {
  const mocks = await mockApi(page, () => ({ status: 202, body: QUEUED_NOW }), { [DAIMIEL_ID]: DAIMIEL });
  await openWith(page, [POINT]);
  // The area's legal panel comes first, before anything is computed.
  const legalPanel = page.locator("section.legal-panel");
  await expect(legalPanel.locator(".legal-status")).toHaveAttribute("data-legal", "rules_not_loaded");
  await expect(legalPanel).toContainText("Masa de agua subterránea: Synthetic body (ES030MSBT000)");
  await expect(legalPanel).toContainText("Ley autonómica ES-CM");
  await expect(legalPanel).toContainText("Licencia municipal de obras");
  await expect(panel(page)).toHaveAttribute("data-state", "idle");
  await panel(page).getByRole("button", { name: "Calcular el mapa detallado" }).click();
  await expect(panel(page)).toHaveAttribute("data-state", "done");
  expect(mocks.posted).toHaveLength(1);
  expect(mocks.polled).toContain(DAIMIEL_ID);
  // The mean, always with its confidence, and named an index.
  await expect(panel(page).locator(".score").first()).toContainText("Índice 0,70");
  await expect(panel(page).locator(".score").first()).toContainText("Confianza");
  await expect(panel(page)).toContainText("No es una probabilidad");
  await expect(panel(page)).toContainText("MDT05");
  // Candidates: ranked, each with its legal status and the disclaimer.
  const candidates = panel(page).locator(".candidate");
  await expect(candidates).toHaveCount(5);
  const legal = candidates.first().locator(".legal-status");
  await expect(legal).toHaveAttribute("data-legal", "rules_not_loaded");
  await expect(legal).toContainText("Normas no cargadas");
  await expect(legal).toContainText("Organismo competente: Confederación Hidrográfica del Tajo");
  await expect(legal.locator('[data-scope="basin_plan"]')).toContainText("No se leyó la parte normativa");
  await legal.getByText(/Normas evaluadas/).click();
  await expect(legal.locator('[data-rule="rdph-87-2-distance"]')).toContainText("inventario del IGME");
  await expect(legal.locator('[data-rule="rdph-87-2-distance"] a')).toContainText("art. 87.2");
  await expect(candidates.first()).toContainText("Orientación, no asesoramiento legal");
  // Each candidate has its depth to water and its drilling cost, and the area its validation.
  await expect(candidates.first().locator(".depth")).toHaveAttribute("data-depth", "estimated");
  await expect(candidates.first()).toContainText("Profundidad del agua: unos");
  await expect(candidates.first()).toContainText("posible karst");
  await expect(candidates.first().locator('[data-levels-source="miteco-piezometry-db"]')).toContainText("Niveles del");
  await expect(candidates.first()).toContainText("Coste de perforación: entre");
  await expect(panel(page).locator('[data-validation="validated"]').first()).toContainText("AUC");
  await expect(page.locator(".candidate-marker")).toHaveCount(5);
  // The report and the pack are downloads; the pack takes the photos only when ticked.
  const downloads = panel(page).locator(`[data-downloads="${DAIMIEL_ID}"]`);
  await expect(downloads.locator('[data-download="report"]')).toHaveAttribute("href", `/api/parcel/${DAIMIEL_ID}/report.pdf`);
  const pack = downloads.locator('[data-download="pack"]');
  await expect(pack).toHaveAttribute("href", `/api/parcel/${DAIMIEL_ID}/pack.zip?media=false&wells=false`);
  await downloads.getByLabel("Incluir en el paquete las fotos y notas de voz de campo").check();
  await expect(pack).toHaveAttribute("href", `/api/parcel/${DAIMIEL_ID}/pack.zip?media=true&wells=false`);
  // The index is drawn first; another layer replaces it.
  await expect(map(page)).toHaveAttribute("data-parcel", `${DAIMIEL_ID}:potential-index:5`);
  await expect.poll(() => mocks.images).toContain(`/api/parcel/${DAIMIEL_ID}/layers/potential-index`);
  await panel(page).locator('[data-parcel-layer="terrain-slope"] input').check();
  await expect(map(page)).toHaveAttribute("data-parcel", `${DAIMIEL_ID}:terrain-slope:5`);
  await expect.poll(() => mocks.images).toContain(`/api/parcel/${DAIMIEL_ID}/layers/terrain-slope`);
  await expect(panel(page).locator('[data-legend="parcel-terrain-slope"]')).toContainText("≥ 30°");
});

test("a tap on the detailed map explains its cell", async ({ page }) => {
  const mocks = await mockApi(page, () => ({ status: 200, body: DAIMIEL }), {});
  await openWith(page, [POINT]);
  await panel(page).getByRole("button", { name: "Calcular el mapa detallado" }).click();
  await expect(map(page)).toHaveAttribute("data-parcel", `${DAIMIEL_ID}:potential-index:5`);
  const box = await map(page).boundingBox();
  if (!box) {
    throw new Error("the map has no box");
  }
  // The map is centred on the area's point, inside the detailed map.
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  const explanation = page.locator(".parcel-explanation");
  await expect(explanation.locator(".score")).toContainText("Índice");
  await expect(explanation.locator('[data-criterion="slope"]')).toBeVisible();
  await expect(explanation).toContainText("Celda de 5 m del mapa detallado");
  // Beside the map's own index, the value updated with the owner's wells and the well that moved it.
  const updated = explanation.locator(".updated-with-wells");
  await expect(updated).toContainText("Actualizado con tus pozos: índice 0,83");
  await expect(updated).toContainText("antes 0,76");
  await expect(updated).toContainText("Confianza");
  await expect(updated).toContainText("Productivo a 40 m");
  await expect(updated).toContainText("sigue siendo un índice");
  expect(mocks.explained[0]?.pathname).toBe(`/api/parcel/${DAIMIEL_ID}/explain`);
});

test("a refused area and a failed job say why and can be asked again", async ({ page }) => {
  const failed = JSON.stringify({
    job: { ...QUEUED.job, state: "failed", failure: "upstream_timeout", detail: "IGN: timed out" },
    layers: [],
  });
  let posts = 0;
  await mockApi(
    page,
    () => (++posts === 1 ? { status: 422, body: '{"code":"too_large"}' } : { status: 200, body: failed }),
    {},
  );
  await openWith(page, [POINT]);
  await panel(page).getByRole("button", { name: "Calcular el mapa detallado" }).click();
  await expect(panel(page).locator('[data-failure="too_large"]')).toContainText("demasiado grande");
  await panel(page).getByRole("button", { name: "Calcular el mapa detallado" }).click();
  await expect(panel(page).locator('[data-failure="upstream_timeout"]')).toContainText("no ha respondido a tiempo");
  await expect(panel(page).getByRole("button", { name: "Calcular el mapa detallado" })).toBeVisible();
});

test("two areas with their detailed maps are compared side by side", async ({ page }) => {
  const byLabel: Record<string, string> = { [String(POINT.label)]: DAIMIEL, [String(CAMPOS.label)]: CAMPOS_DONE };
  await mockApi(page, (label) => ({ status: 200, body: byLabel[label] ?? "{}" }), {});
  await openWith(page, [POINT, CAMPOS]);
  await panel(page).getByRole("button", { name: "Calcular el mapa detallado" }).click();
  await expect(panel(page)).toHaveAttribute("data-state", "done");
  await expect(page.locator("section.comparison")).toHaveCount(0);
  await page.locator(".session").getByRole("button").nth(1).click();
  await panel(page).getByRole("button", { name: "Calcular el mapa detallado" }).click();
  await expect(map(page)).toHaveAttribute("data-parcel", `${CAMPOS_ID}:potential-index:5`);
  const rows = page.locator("section.comparison tbody tr");
  await expect(rows).toHaveCount(2);
  await expect(rows.first()).toHaveAttribute("data-compare", DAIMIEL_ID);
  await expect(rows.nth(1)).toHaveAttribute("data-compare", CAMPOS_ID);
  await expect(rows.first().locator(".score").first()).toContainText("Confianza");
  await expect(rows.first().locator("td").nth(1).locator(".score")).toHaveCount(3);
});
