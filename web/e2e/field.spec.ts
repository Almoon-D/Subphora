// Copyright (c) 2026 Almoon-D. All rights reserved.
// Field mode in a real browser with emulated geolocation and network (hard rule 5): the
// position and the guidance to a spot, "at the spot" by the rule; notes, a photo, a voice
// memo and the track recorded offline, kept through a reload, and synced once when the
// server is reachable again; a sync cut by a reload and a sync retried after a server error
// that duplicate nothing; the export; and a refused permission. The API is mocked by a
// server that upserts by id, as ours does.
import { readFileSync } from "node:fs";

import { type BrowserContext, expect, type Page, test } from "@playwright/test";

const fixture = (name: string) => readFileSync(new URL(`fixtures/${name}`, import.meta.url), "utf-8");
const MAP = fixture("map.json");
const POINT = JSON.parse(fixture("area-point-daimiel.json")) as Record<string, unknown>;
const DAIMIEL = fixture("parcel-daimiel.json");
const LEGAL = fixture("legal-daimiel.json");
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
  "base64",
);
const JPEG = Buffer.from([0xff, 0xd8, 0xff, 0xe0, ...Buffer.from("synthetic photo")]);

// The Daimiel point (public place) and a spot about 111 m north of it.
const HERE = { longitude: -3.6115, latitude: 39.0675 };
const SPOT = { area_id: "0123456789abcdef", rank: 1, longitude: -3.6115, latitude: 39.0685 };

interface Server {
  /** Body of every record stored, by id. */
  records: Map<string, string>;
  /** How many times each id was created (must stay 1) and sent at all. */
  created: Map<string, number>;
  sent: Map<string, number>;
  files: Map<string, number>;
  /** False: every field request fails as if there were no coverage. */
  reachable: boolean;
  /** Store the next batch, then never answer it (the page reloads meanwhile). */
  hangNext: boolean;
  /** Store the next batch, then answer 503 as if the answer failed. */
  failNext: boolean;
}

async function mockApi(page: Page): Promise<Server> {
  const server: Server = {
    records: new Map(),
    created: new Map(),
    sent: new Map(),
    files: new Map(),
    reachable: true,
    hangNext: false,
    failNext: false,
  };
  const map = { ...(JSON.parse(MAP) as object), initial_view: { ...HERE, zoom: 15 } };
  await page.route("**/api/map", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify(map) }));
  await page.route("**/api/national", (route) => route.fulfill({ status: 500, contentType: "application/json", body: "{}" }));
  await page.route("**/api/legal?*", (route) => route.fulfill({ contentType: "application/json", body: LEGAL }));
  await page.route(/^https:\/\//, (route) => route.fulfill({ contentType: "image/png", body: PNG }));
  await page.route("**/api/field/observations", async (route) => {
    if (!server.reachable) {
      return route.abort("internetdisconnected");
    }
    const { observations } = route.request().postDataJSON() as { observations: { id: string }[] };
    const results = observations.map((o) => {
      const body = JSON.stringify(o);
      server.sent.set(o.id, (server.sent.get(o.id) ?? 0) + 1);
      const stored = server.records.get(o.id);
      if (stored === undefined) {
        server.records.set(o.id, body);
        server.created.set(o.id, (server.created.get(o.id) ?? 0) + 1);
        return { id: o.id, outcome: "created" };
      }
      return { id: o.id, outcome: stored === body ? "duplicate" : "conflict" };
    });
    if (server.hangNext) {
      server.hangNext = false;
      // Never answered: the reload cancels it.
      return new Promise<void>(() => undefined);
    }
    if (server.failNext) {
      server.failNext = false;
      return route.fulfill({ status: 503, contentType: "application/json", body: '{"code":"store_unavailable"}' });
    }
    return route.fulfill({ contentType: "application/json", body: JSON.stringify({ results }) });
  });
  await page.route("**/api/field/observations/*/media", (route) => {
    if (!server.reachable) {
      return route.abort("internetdisconnected");
    }
    const id = new URL(route.request().url()).pathname.split("/").at(-2) ?? "";
    if (!server.records.has(id)) {
      return route.fulfill({ status: 404, contentType: "application/json", body: '{"code":"unknown_observation"}' });
    }
    const created = !server.files.has(id);
    server.files.set(id, route.request().postDataBuffer()?.length ?? 0);
    return route.fulfill({
      status: created ? 201 : 200,
      contentType: "application/json",
      body: JSON.stringify({ id, outcome: created ? "created" : "duplicate" }),
    });
  });
  return server;
}

/** Open the page in field mode, walking to `target` (none: no target). */
async function openField(page: Page, target: typeof SPOT | null = SPOT): Promise<void> {
  await page.addInitScript((session) => {
    if (!window.sessionStorage.getItem("subphora.field")) {
      window.sessionStorage.setItem("subphora.field", session);
    }
  }, JSON.stringify({ on: true, target }));
  await page.goto("/");
  await expect(page.locator(".map")).toHaveAttribute("data-base", "pnoa");
}

const outbox = (page: Page) => page.locator("section.outbox");

async function writeNote(page: Page, text: string): Promise<void> {
  await page.getByRole("button", { name: "Nota", exact: true }).click();
  await page.getByLabel("Escribe la nota").fill(text);
  await page.getByRole("button", { name: "Guardar la nota" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Nota guardada en el dispositivo." })).toBeVisible();
}

async function moveTo(context: BrowserContext, longitude: number, latitude: number, accuracy = 5): Promise<void> {
  await context.setGeolocation({ longitude, latitude, accuracy });
}

test.use({ geolocation: { ...HERE, accuracy: 5 }, permissions: ["geolocation", "microphone"] });

test("shows the position, its accuracy and the way to the spot, and 'at the spot' by the rule", async ({ page, context }) => {
  await mockApi(page);
  await openField(page);
  await expect(page.getByText("Precisión: ±5 m")).toBeVisible();
  // Standing still: the device gives no heading, and the page says so.
  await expect(page.getByText("Rumbo: sin datos")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Destino: punto 1" })).toBeVisible();
  const guidance = page.locator(".guidance");
  await expect(guidance).toHaveAttribute("data-at-spot", "false");
  await expect(guidance).toHaveAttribute("data-distance", "111");
  await expect(guidance).toContainText("111 m");
  await expect(guidance).toContainText("Dirección: 0° (N)");
  await expect(page.locator(".map")).toHaveAttribute("data-field", "fix:-3.61150,39.06750,5|target:1");
  await expect(page.locator(".target-marker")).toHaveCount(1);
  // At the spot, with a good fix.
  await moveTo(context, SPOT.longitude, SPOT.latitude + 0.00003, 4);
  await expect(guidance).toHaveAttribute("data-at-spot", "true");
  await expect(page.getByText("Estás en el punto")).toBeVisible();
  // At the same place with a poor fix: it cannot be confirmed.
  await moveTo(context, SPOT.longitude, SPOT.latitude, 25);
  await expect(guidance).toHaveAttribute("data-at-spot", "false");
  await expect(guidance).toContainText("Con una precisión de ±25 m no se puede confirmar que estás en el punto: hace falta ±10 m o mejor.");
  // East of the spot, the way points west.
  await moveTo(context, SPOT.longitude + 0.002, SPOT.latitude, 5);
  await expect(guidance).toContainText("Dirección: 270° (O)");
  await page.getByRole("button", { name: "Quitar el destino" }).click();
  await expect(page.getByRole("heading", { name: "Sin destino" })).toBeVisible();
  await expect(page.locator(".target-marker")).toHaveCount(0);
});

test("records offline, keeps everything through a reload, and syncs each record once", async ({ page, context }) => {
  const server = await mockApi(page);
  await openField(page);
  await expect(outbox(page)).toHaveAttribute("data-unsynced", "0");
  // The browser offline; the mocked routes would still answer, so they refuse too.
  await context.setOffline(true);
  server.reachable = false;

  await writeNote(page, "Afloramiento de calizas junto al camino");
  await expect(outbox(page)).toHaveAttribute("data-unsynced", "1");

  await page.getByLabel("Texto para la próxima foto").fill("Brocal de piedra");
  await page.locator('input[type="file"][accept^="image/"]').setInputFiles({ name: "pozo.jpg", mimeType: "image/jpeg", buffer: JPEG });
  await expect(page.getByText("Foto guardada en el dispositivo.")).toBeVisible();
  await expect(outbox(page)).toHaveAttribute("data-unsynced", "2");

  await page.getByRole("button", { name: "Nota de voz" }).click();
  await expect(page.getByRole("button", { name: "Detener y guardar" })).toBeVisible();
  await page.waitForTimeout(400);
  await page.getByRole("button", { name: "Detener y guardar" }).click();
  await expect(page.getByText("Nota de voz guardada en el dispositivo.")).toBeVisible();
  await expect(outbox(page)).toHaveAttribute("data-unsynced", "3");

  await page.getByRole("button", { name: "Grabar la ruta" }).click();
  await expect(page.getByRole("button", { name: "Detener la ruta (1 puntos)" })).toBeVisible();
  await moveTo(context, HERE.longitude, HERE.latitude + 0.0003);
  await expect(page.getByRole("button", { name: "Detener la ruta (2 puntos)" })).toBeVisible();
  await page.getByRole("button", { name: "Detener la ruta (2 puntos)" }).click();
  await expect(outbox(page)).toHaveAttribute("data-unsynced", "5");
  await expect(outbox(page)).toContainText("Sin conexión: se enviará cuando vuelva la cobertura.");
  expect(server.records.size).toBe(0);

  // The browser is back online but the server is still out of reach; the page reloads.
  await context.setOffline(false);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Modo campo" })).toBeVisible();
  await expect(outbox(page)).toHaveAttribute("data-unsynced", "5");

  await expect(outbox(page)).toContainText("Sin conexión");
  // Coverage comes back: the browser says so, and the outbox sends.
  server.reachable = true;
  await page.evaluate(() => window.dispatchEvent(new Event("online")));
  await expect(outbox(page)).toHaveAttribute("data-unsynced", "0");
  await expect(outbox(page)).toContainText("Todo está en el servidor.");
  expect(server.records.size).toBe(5);
  expect([...server.created.values()].every((n) => n === 1)).toBe(true);
  expect(server.files.size).toBe(2);
  const kinds = [...server.records.values()].map((body) => (JSON.parse(body) as { kind: string }).kind).sort();
  expect(kinds).toEqual(["note", "photo", "track_point", "track_point", "voice"]);
  const photo = [...server.records.values()].map((b) => JSON.parse(b) as Record<string, unknown>).find((r) => r.kind === "photo");
  expect(photo).toMatchObject({ text: "Brocal de piedra", media: { content_type: "image/jpeg", size_bytes: JPEG.length } });
  expect(photo?.position).toMatchObject({ accuracy_m: 5 });
  expect(photo?.target).toEqual(SPOT);
  expect([...server.files.values()]).toContain(JPEG.length);

  // Each record went once; a later round, after a reload, sends nothing again.
  expect([...server.sent.values()].every((n) => n === 1)).toBe(true);
  await page.reload();
  await expect(outbox(page)).toHaveAttribute("data-unsynced", "0");
  await page.evaluate(() => window.dispatchEvent(new Event("online")));
  await expect(outbox(page)).toContainText("Todo está en el servidor.");
  expect([...server.sent.values()].every((n) => n === 1)).toBe(true);
});

test("a sync cut by a reload is finished after it, without duplicates", async ({ page }) => {
  const server = await mockApi(page);
  await openField(page, null);
  server.hangNext = true;
  await writeNote(page, "Primera");
  await writeNote(page, "Segunda");
  await writeNote(page, "Tercera");
  await expect.poll(() => server.records.size).toBeGreaterThan(0);
  await expect(outbox(page)).toHaveAttribute("data-unsynced", /[1-9]/);
  await page.reload();
  await expect(outbox(page)).toHaveAttribute("data-unsynced", "0");
  expect(server.records.size).toBe(3);
  expect([...server.created.values()]).toEqual([1, 1, 1]);
  // The record whose answer was lost was sent again and taken as a duplicate.
  expect(Math.max(...server.sent.values())).toBe(2);
});

test("a sync retried after a server error duplicates nothing", async ({ page }) => {
  const server = await mockApi(page);
  await openField(page, null);
  server.failNext = true;
  await writeNote(page, "Pozo seco");
  await expect(outbox(page)).toContainText("El servidor no responde bien; se volverá a intentar.");
  await expect(outbox(page)).toHaveAttribute("data-unsynced", "1");
  expect(server.records.size).toBe(1);
  await page.getByRole("button", { name: "Enviar ahora" }).click();
  await expect(outbox(page)).toHaveAttribute("data-unsynced", "0");
  expect([...server.created.values()]).toEqual([1]);
  expect([...server.sent.values()]).toEqual([2]);
});

test("exports what has not been sent", async ({ page }) => {
  const server = await mockApi(page);
  server.reachable = false;
  await openField(page, null);
  await writeNote(page, "Sin cobertura en el barranco");
  await page.locator('input[type="file"][accept^="image/"]').setInputFiles({ name: "pozo.jpg", mimeType: "image/jpeg", buffer: JPEG });
  await expect(outbox(page)).toHaveAttribute("data-unsynced", "2");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exportar lo no enviado" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/^subphora-campo-\d{8}-\d{4}\.json$/);
  const path = await file.path();
  const exported = JSON.parse(readFileSync(path, "utf-8")) as {
    format: string;
    records: { observation: { kind: string; text: string | null }; media: { type: string; base64: string } | null }[];
  };
  expect(exported.format).toBe("subphora-field-export");
  expect(exported.records.map((r) => r.observation.kind).sort()).toEqual(["note", "photo"]);
  const photo = exported.records.find((r) => r.observation.kind === "photo");
  expect(Buffer.from(photo?.media?.base64 ?? "", "base64")).toEqual(JPEG);
});

test("a file the server would refuse is not kept", async ({ page }) => {
  await mockApi(page);
  await openField(page, null);
  await page.locator('input[type="file"][accept^="image/"]').setInputFiles({ name: "x.gif", mimeType: "image/gif", buffer: Buffer.from("GIF89a") });
  await expect(page.getByRole("alert").filter({ hasText: "Este tipo de archivo no se admite." })).toBeVisible();
  await expect(outbox(page)).toHaveAttribute("data-unsynced", "0");
});

test("a candidate of the detailed map becomes the spot to walk to", async ({ page }) => {
  await mockApi(page);
  await page.route("**/api/parcel", (route) => route.fulfill({ contentType: "application/json", body: DAIMIEL }));
  await page.route("**/api/parcel/*/layers/*", (route) => route.fulfill({ contentType: "image/png", body: PNG }));
  await page.addInitScript((session) => {
    window.sessionStorage.setItem("subphora.session-areas", session);
  }, JSON.stringify({ areas: [POINT], selected: 0 }));
  await page.goto("/");
  await page.locator("section.parcel").getByRole("button", { name: "Calcular el mapa detallado" }).click();
  await expect(page.locator("section.parcel")).toHaveAttribute("data-state", "done");
  await page.getByRole("button", { name: "Modo campo" }).click();
  await expect(page.getByRole("heading", { name: "Sin destino" })).toBeVisible();
  await page.getByRole("button", { name: "Ir al punto 2" }).click();
  await expect(page.getByRole("heading", { name: "Destino: punto 2" })).toBeVisible();
  await expect(page.locator(".map")).toHaveAttribute("data-field", /\|target:2$/);
  await expect(page.locator(".guidance")).toHaveAttribute("data-distance", /^\d+$/);
  // The spot is kept for a reload of the tab, and leaving field mode returns to the area.
  await page.reload();
  await expect(page.getByRole("heading", { name: "Destino: punto 2" })).toBeVisible();
  await page.getByRole("button", { name: "Salir" }).click();
  await expect(page.locator("section.parcel")).toBeVisible();
});

test.describe("without permission to locate", () => {
  test.use({ permissions: [] });

  test("says so, and still records without a position", async ({ page }) => {
    const server = await mockApi(page);
    await openField(page, null);
    await expect(page.getByRole("alert").filter({ hasText: "No hay permiso para usar tu posición" })).toBeVisible();
    await expect(page.locator(".map")).toHaveAttribute("data-field", "nofix");
    await writeNote(page, "Sin posición");
    await expect(outbox(page)).toHaveAttribute("data-unsynced", "0");
    const [stored] = [...server.records.values()].map((b) => JSON.parse(b) as Record<string, unknown>);
    expect(stored).toMatchObject({ kind: "note", text: "Sin posición", position: null });
  });
});
