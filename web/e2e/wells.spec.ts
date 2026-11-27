// Copyright (c) 2026 Almoon-D. All rights reserved.
// The owner's wells in a real browser against a mocked registry that stores by id, as
// ours does (decision 0040): the list, a well logged at the point tapped on the map, a
// reading, a CSV import, the validation against the owner's wells, a well deleted, and a
// registry out of reach that keeps what was typed. Every well is synthetic.
import { readFileSync } from "node:fs";

import { expect, type Page, test } from "@playwright/test";

const fixture = (name: string) => readFileSync(new URL(`fixtures/${name}`, import.meta.url), "utf-8");
const MAP = fixture("map.json");
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
  "base64",
);
const HELD_ID = "0b9f4c1e-6d2a-4f3b-9c8e-1a2b3c4d5e6f";

interface Registry {
  wells: Map<string, Record<string, unknown>>;
  readings: Record<string, unknown>[];
  puts: Record<string, unknown>[];
  imports: string[];
  reachable: boolean;
}

async function mockApi(page: Page): Promise<Registry> {
  const registry: Registry = {
    wells: new Map([
      [
        HELD_ID,
        {
          id: HELD_ID,
          name: "Pozo sintético del huerto",
          longitude: -3.6115,
          latitude: 39.0675,
          depth_m: 60,
          flow_l_s: 1.5,
          outcome: "productive",
          drilled_on: null,
          note: null,
        },
      ],
    ]),
    readings: [],
    puts: [],
    imports: [],
    reachable: true,
  };
  await page.route("**/api/map", (route) => route.fulfill({ contentType: "application/json", body: MAP }));
  await page.route("**/api/national", (route) => route.fulfill({ status: 500, contentType: "application/json", body: "{}" }));
  await page.route(/^https:\/\//, (route) => route.fulfill({ contentType: "image/png", body: PNG }));
  await page.route(/\/api\/wells(\/.*)?$/, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (!registry.reachable) {
      return route.fulfill({ status: 503, contentType: "application/json", body: '{"code":"store_unavailable","detail":"the registry failed"}' });
    }
    if (request.method() === "GET" && path === "/api/wells") {
      const wells = [...registry.wells.values()].map((well) => ({
        well,
        readings: registry.readings.filter((r) => r.well_id === well.id),
      }));
      return route.fulfill({ contentType: "application/json", body: JSON.stringify({ wells, stamp: "0123456789abcdef" }) });
    }
    if (request.method() === "GET" && path === "/api/wells/validation") {
      const validation = {
        domain: "ES030MSBT000",
        label: "Synthetic body",
        state: "not_enough_labels",
        design: "presence_absence",
        productive: 1,
        dry: 1,
        background: 0,
        blocks: 1,
        auc: null,
        calibration: null,
        no_calibration: "not_validated",
        excluded_criteria: [],
        labels_source: "Your wells",
        validated_at: "2026-11-27T00:00:00Z",
      };
      return route.fulfill({ contentType: "application/json", body: JSON.stringify({ validations: [validation], off_map: 0, unknown_outcome: 1 }) });
    }
    if (request.method() === "POST" && path === "/api/wells/import") {
      registry.imports.push(request.postData() ?? "");
      const report = { rows: 2, wells: { created: 2, updated: 0, unchanged: 0, conflict: 0 }, readings: { created: 1 }, conflict_rows: [] };
      return route.fulfill({ contentType: "application/json", body: JSON.stringify(report) });
    }
    const id = path.split("/")[3] ?? "";
    if (request.method() === "PUT") {
      const well = request.postDataJSON() as Record<string, unknown>;
      registry.puts.push(well);
      const created = !registry.wells.has(id);
      registry.wells.set(id, well);
      return route.fulfill({ status: created ? 201 : 200, contentType: "application/json", body: JSON.stringify({ id, change: created ? "created" : "updated" }) });
    }
    if (request.method() === "DELETE") {
      registry.wells.delete(id);
      return route.fulfill({ status: 204 });
    }
    if (request.method() === "POST" && path.endsWith("/readings")) {
      const reading = request.postDataJSON() as Record<string, unknown>;
      registry.readings.push(reading);
      return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ id: reading.id, change: "created" }) });
    }
    return route.fulfill({ status: 404, contentType: "application/json", body: '{"code":"unknown_well"}' });
  });
  return registry;
}

const panel = (page: Page) => page.locator("section.wells");

test("a well is logged at the tapped point, read, and its levels recorded", async ({ page }) => {
  const registry = await mockApi(page);
  await page.goto("/");
  await expect(panel(page).locator(".well")).toHaveCount(1);
  await expect(panel(page)).toContainText("Pozo sintético del huerto · Productivo · 60,0 m de hondo · 1,50 l/s");
  await expect(panel(page)).toContainText("Privados");
  // A tap on the map offers its point as the new well's position.
  const map = page.locator(".map");
  await expect(map).toBeVisible();
  const box = await map.boundingBox();
  if (!box) {
    throw new Error("the map has no box");
  }
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  const form = panel(page).locator("form.well-form");
  await form.getByLabel("Nombre").fill("Sondeo sintético seco");
  await form.getByRole("button", { name: "Usar el último punto tocado en el mapa" }).click();
  await expect(form.getByLabel("Longitud (grados)")).not.toHaveValue("");
  await form.getByLabel("Resultado").selectOption("dry");
  await form.getByLabel("Profundidad del pozo (m)").fill("120,5");
  await form.getByRole("button", { name: "Guardar pozo" }).click();
  await expect(panel(page)).toContainText("Pozo guardado.");
  await expect(panel(page).locator(".well")).toHaveCount(2);
  const put = registry.puts[0];
  expect(put).toMatchObject({ name: "Sondeo sintético seco", outcome: "dry", depth_m: 120.5, flow_l_s: null });
  expect(typeof put?.longitude).toBe("number");
  // A water level for the held well.
  const held = panel(page).locator(`[data-well="${HELD_ID}"]`);
  await held.getByLabel("Fecha y hora de la lectura").fill("2026-06-01T08:30");
  await held.getByLabel("Agua a (m bajo el suelo)").fill("12,5");
  await held.getByRole("button", { name: "Guardar lectura" }).click();
  await expect(held).toContainText("1 lectura(s); la última, agua a 12,50 m");
  expect(registry.readings[0]).toMatchObject({ well_id: HELD_ID, depth_to_water_m: 12.5 });
  // Deleting asks once more first.
  await held.getByRole("button", { name: "Borrar" }).click();
  await held.getByRole("button", { name: /Seguro/ }).click();
  await expect(panel(page).locator(".well")).toHaveCount(1);
});

test("a CSV is imported and the map is graded against the owner's wells", async ({ page }) => {
  const registry = await mockApi(page);
  await page.goto("/");
  await panel(page)
    .getByLabel("Archivo CSV")
    .setInputFiles({ name: "pozos.csv", mimeType: "text/csv", buffer: Buffer.from("nombre;longitud;latitud\nA;-3,6;39,0\n") });
  await expect(panel(page)).toContainText("2 filas leídas: 2 pozos nuevos, 0 ya estaban, 1 lecturas nuevas.");
  expect(registry.imports[0]).toContain("nombre;longitud;latitud");
  await panel(page).getByRole("button", { name: "Comparar el mapa con mis pozos" }).click();
  const graded = panel(page).locator('[data-validation="not_enough_labels"]');
  await expect(graded).toContainText("Synthetic body: aún no hay pozos suficientes para medirlo (1 productivos y 1 secos).");
  await expect(panel(page)).toContainText("1 sin resultado conocido");
});

test("a registry out of reach says so and keeps what was typed", async ({ page }) => {
  const registry = await mockApi(page);
  registry.reachable = false;
  await page.goto("/");
  await expect(panel(page).getByRole("alert").first()).toContainText("El registro de pozos del servidor falla ahora");
  const form = panel(page).locator("form.well-form");
  await form.getByLabel("Nombre").fill("Pozo sintético");
  await form.getByRole("button", { name: "Guardar pozo" }).click();
  await expect(panel(page)).toContainText("La posición no es válida");
  await form.getByLabel("Longitud (grados)").fill("-3,61");
  await form.getByLabel("Latitud (grados)").fill("39,06");
  await form.getByRole("button", { name: "Guardar pozo" }).click();
  await expect(panel(page)).toContainText("falla ahora (the registry failed)");
  await expect(form.getByLabel("Nombre")).toHaveValue("Pozo sintético");
});
