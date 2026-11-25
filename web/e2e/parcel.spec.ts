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
  await expect(panel(page)).toHaveAttribute("data-state", "idle");
  await panel(page).getByRole("button", { name: "Calcular el mapa detallado" }).click();
  await expect(panel(page)).toHaveAttribute("data-state", "done");
  expect(mocks.posted).toHaveLength(1);
  expect(mocks.polled).toContain(DAIMIEL_ID);
  // The mean, always with its confidence, and named an index.
  await expect(panel(page).locator(".score").first()).toContainText("Índice 0,68");
  await expect(panel(page).locator(".score").first()).toContainText("Confianza");
  await expect(panel(page)).toContainText("No es una probabilidad");
  await expect(panel(page)).toContainText("MDT05");
  // Candidates: ranked, each with its legal status and the disclaimer.
  const candidates = panel(page).locator(".candidate");
  await expect(candidates).toHaveCount(5);
  await expect(candidates.first().locator(".legal")).toHaveAttribute("data-legal", "not_evaluated");
  await expect(candidates.first()).toContainText("Situación legal: sin evaluar");
  await expect(candidates.first()).toContainText("Orientación, no asesoramiento legal");
  await expect(candidates.first()).toContainText("Profundidad del agua: sin estimar");
  await expect(page.locator(".candidate-marker")).toHaveCount(5);
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
