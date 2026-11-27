// Copyright (c) 2026 Almoon-D. All rights reserved.
// The owner's wells in a real browser against a mocked registry that stores by id, as
// ours does (decision 0040): the list, a well logged at the point tapped on the map, a
// reading, a CSV import, the validation against the owner's wells, a well deleted, a
// registry out of reach that keeps what was typed, and a water level typed with no
// coverage (session 17): kept on the device, through a reload and a sync cut by another,
// and in the registry once. Every well is synthetic.
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
  /** False: every registry request fails as if there were no coverage. */
  online: boolean;
  /** How many times each reading was sent in a batch. */
  sent: Map<string, number>;
  /** Store the next batch, then never answer it (the page reloads meanwhile). */
  hangNext: boolean;
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
    online: true,
    sent: new Map(),
    hangNext: false,
  };
  await page.route("**/api/map", (route) => route.fulfill({ contentType: "application/json", body: MAP }));
  await page.route("**/api/national", (route) => route.fulfill({ status: 500, contentType: "application/json", body: "{}" }));
  await page.route(/^https:\/\//, (route) => route.fulfill({ contentType: "image/png", body: PNG }));
  await page.route(/\/api\/wells(\/.*)?$/, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (!registry.online) {
      return route.abort("internetdisconnected");
    }
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
    if (request.method() === "POST" && path === "/api/wells/readings") {
      const { readings } = request.postDataJSON() as { readings: Record<string, unknown>[] };
      const results = readings.map((reading) => {
        const id = String(reading.id);
        registry.sent.set(id, (registry.sent.get(id) ?? 0) + 1);
        if (!registry.wells.has(String(reading.well_id))) {
          return { id, outcome: "unknown_well" };
        }
        const held = registry.readings.find((r) => r.id === id);
        if (!held) {
          registry.readings.push(reading);
          return { id, outcome: "created" };
        }
        return { id, outcome: JSON.stringify(held) === JSON.stringify(reading) ? "duplicate" : "conflict" };
      });
      if (registry.hangNext) {
        registry.hangNext = false;
        // Never answered: the reload cancels it.
        return new Promise<void>(() => undefined);
      }
      return route.fulfill({ contentType: "application/json", body: JSON.stringify({ results }) });
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
  await held.getByLabel("Agua a (m bajo la referencia)").fill("12,5");
  await held.getByRole("button", { name: "Guardar lectura" }).click();
  await expect(panel(page)).toContainText("Lectura guardada en este dispositivo");
  await expect(held).toContainText("1 lectura(s); la última, agua a 12,50 m bajo el suelo");
  expect(registry.readings[0]).toMatchObject({
    well_id: HELD_ID,
    depth_to_water_m: 12.5,
    reference: "ground",
    reference_height_m: 0,
    measured_by: "owner",
    pump: "stopped",
    pump_minutes: null,
  });
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
  await expect(panel(page).locator("[data-wells-failure]")).toContainText("El registro de pozos del servidor falla ahora");
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

test("a water level typed with no coverage is kept, survives reloads and a cut sync, and reaches the registry once", async ({ page, context }) => {
  const registry = await mockApi(page);
  await page.goto("/");
  const held = panel(page).locator(`[data-well="${HELD_ID}"]`);
  await expect(held).toContainText("Sin lecturas de nivel.");
  // No coverage at the well head: the browser offline, and the registry with it.
  await context.setOffline(true);
  registry.online = false;
  await held.getByLabel("Fecha y hora de la lectura").fill("2026-11-20T08:00");
  await held.getByLabel("Agua a (m bajo la referencia)").fill("13");
  await held.getByLabel("Medido desde").selectOption("casing_top");
  await held.getByLabel("Altura del brocal sobre el suelo (m)").fill("0,5");
  await held.getByLabel("Quién lo midió").selectOption("driller");
  await held.getByLabel("La bomba").selectOption("stopped");
  await held.getByLabel(/^Parada desde hace/).fill("600");
  await held.getByRole("button", { name: "Guardar lectura" }).click();
  await expect(panel(page).getByRole("status")).toContainText("Lectura guardada en este dispositivo");
  await expect(held.locator("[data-pending-readings]")).toContainText("1 lectura(s) guardada(s) en este dispositivo, por enviar: agua a 12,50 m bajo el suelo");
  // One more, while pumping: kept and sent like the other, flagged in the list.
  await held.getByLabel("Fecha y hora de la lectura").fill("2026-11-20T12:00");
  await held.getByLabel("Agua a (m bajo la referencia)").fill("19");
  await held.getByLabel("La bomba").selectOption("running");
  await held.getByRole("button", { name: "Guardar lectura" }).click();
  await expect(held.locator("[data-pending-readings]")).toHaveAttribute("data-pending-readings", "2");
  await expect(held).toContainText("(con la bomba en marcha)");
  expect(registry.readings).toEqual([]);

  // The browser back online, the server still out of reach; the page reloads and the list
  // is the device's copy, with both readings still waiting.
  await context.setOffline(false);
  await page.reload();
  await expect(panel(page).locator("[data-wells-copy]")).toContainText("Sin conexión con el servidor");
  await expect(held.locator("[data-pending-readings]")).toHaveAttribute("data-pending-readings", "2");

  // Coverage returns, but the first answer is lost: the page reloads mid-sync.
  registry.online = true;
  registry.hangNext = true;
  await page.evaluate(() => window.dispatchEvent(new Event("online")));
  await expect.poll(() => registry.readings.length).toBe(2);
  await page.reload();
  // The reload's round sends them again; the registry takes them as duplicates.
  await expect.poll(() => [...registry.sent.values()]).toEqual([2, 2]);
  await expect(page.getByRole("button", { name: "Modo campo", exact: true })).toBeVisible();
  await expect(held).toContainText("2 lectura(s); la última, agua a 19,00 m bajo el suelo");
  await expect(held.locator("[data-pending-readings]")).toHaveCount(0);
  expect(registry.readings).toHaveLength(2);
  expect(registry.readings[0]).toMatchObject({
    well_id: HELD_ID,
    measured_at: new Date("2026-11-20T08:00").toISOString(),
    depth_to_water_m: 13,
    reference: "casing_top",
    reference_height_m: 0.5,
    measured_by: "driller",
    pump: "stopped",
    pump_minutes: 600,
  });
  expect(registry.readings[1]).toMatchObject({ pump: "running", pump_minutes: null });
  expect(String(registry.readings[0]?.id)).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-7/);
});
