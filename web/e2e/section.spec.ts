// Copyright (c) 2026 Almoon-D. All rights reserved.
// Drawing a cross-section's line and reading its section, in a real browser against a
// mocked API: the "interpretation" label, the vertical exaggeration, the legend, what a tap
// on the section explains, and a line the server refuses.
import { readFileSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

import type { CrossSection } from "../src/api.ts";
import { verticalRange } from "../src/section/section.ts";

const fixture = (name: string) => readFileSync(new URL(`fixtures/${name}`, import.meta.url), "utf-8");
const MAP = fixture("map.json");
const SECTION = fixture("section-daimiel.json");
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
  "base64",
);
const VIEW = { longitude: -3.61, latitude: 39.07, zoom: 13 };

interface Asked {
  lines: { start: number[]; end: number[] }[];
  taps: number;
}

async function mockEverything(page: Page, answer: { status: number; body: string } = { status: 200, body: SECTION }) {
  const asked: Asked = { lines: [], taps: 0 };
  const map = { ...(JSON.parse(MAP) as object), initial_view: VIEW };
  await page.route("**/api/map", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify(map) }));
  await page.route("**/api/layers/*/info?*", (route) => {
    asked.taps += 1;
    return route.fulfill({ status: 404, contentType: "application/json", body: '{"code":"no_feature_info"}' });
  });
  await page.route("**/api/section", (route) => {
    asked.lines.push(route.request().postDataJSON() as { start: number[]; end: number[] });
    return route.fulfill({ status: answer.status, contentType: "application/json", body: answer.body });
  });
  for (const host of ["https://www.ign.es/**", "https://ovc.catastro.meh.es/**"]) {
    await page.route(host, (route) => route.fulfill({ contentType: "image/png", body: PNG }));
  }
  return asked;
}

async function clickMap(page: Page, dx: number, dy: number): Promise<void> {
  const box = await page.locator(".maplibregl-canvas").boundingBox();
  if (!box) {
    throw new Error("the map has no size");
  }
  await page.mouse.click(box.x + box.width / 2 + dx, box.y + box.height / 2 + dy);
}

async function drawLine(page: Page): Promise<void> {
  await expect(page.locator(".map")).toHaveAttribute("data-base", "pnoa");
  await page.getByRole("button", { name: "Dibujar un corte" }).click();
  await expect(page.getByText("Toca el mapa en el inicio y en el final del corte: una línea recta de 100 m a 5.000 m.")).toBeVisible();
  await clickMap(page, -150, 0);
  await expect(page.locator(".map")).toHaveAttribute("data-draft", "line:1");
  await clickMap(page, 150, 0);
}

// The drawing's frame (SectionPanel.tsx): a 1000 x 380 view box, the plot inside margins.
const FRAME = { width: 1000, height: 380, left: 60, right: 12, top: 28, bottom: 30 };

/** Click the section's drawing at a distance along the line and a depth below the ground
 * of the column there. */
async function clickSection(page: Page, distance: number, depth: number): Promise<void> {
  const section = JSON.parse(SECTION) as CrossSection;
  const column = section.columns.reduce((best, c) =>
    Math.abs(c.distance_m - distance) < Math.abs(best.distance_m - distance) ? c : best,
  );
  const { bottom, top } = verticalRange(section);
  const elevation = (column.ground_m ?? 0) - depth;
  const plotW = FRAME.width - FRAME.left - FRAME.right;
  const plotH = FRAME.height - FRAME.top - FRAME.bottom;
  const x = FRAME.left + (column.distance_m / section.length_m) * plotW;
  const y = FRAME.top + ((top - elevation) / (top - bottom)) * plotH;
  const svg = page.locator(".section-svg");
  await svg.scrollIntoViewIfNeeded();
  const box = await svg.boundingBox();
  if (!box) {
    throw new Error("the section has no size");
  }
  await page.mouse.click(box.x + (x / FRAME.width) * box.width, box.y + (y / FRAME.height) * box.height);
}

test("a drawn line shows its interpretive section, explained on a tap", async ({ page }) => {
  const asked = await mockEverything(page);
  await page.goto("/");
  await drawLine(page);

  const sheet = page.locator(".section-sheet");
  await expect(sheet.getByRole("heading", { name: /Corte geológico/ })).toBeVisible();
  await expect(sheet.locator(".section-badge")).toHaveText("INTERPRETACIÓN");
  await expect(sheet.locator(".section-stamp")).toHaveText("INTERPRETACIÓN");
  await expect(sheet.getByText(/^Exageración vertical ×/)).toBeVisible();
  for (const unit of ["Calizas", "Margas", "Areniscas"]) {
    await expect(sheet.locator(".section-legend").getByText(unit)).toBeVisible();
  }
  await expect(sheet.getByText("Los sondeos públicos no traen su columna litológica.")).toBeVisible();
  await expect(sheet.locator('rect[data-state="unknown"]').first()).toBeAttached();
  await expect(sheet.locator('[data-contact="projected"]')).toHaveCount(1);
  await expect(sheet.locator("[data-fault]")).toHaveCount(1);
  await expect(sheet.locator("[data-borehole]")).toHaveCount(1);

  // The line went west to east, through the view's centre; drawing it was not a tap.
  expect(asked.lines).toHaveLength(1);
  const [line] = asked.lines;
  expect(line?.start[0]).toBeLessThan(VIEW.longitude);
  expect(line?.end[0]).toBeGreaterThan(VIEW.longitude);
  expect(asked.taps).toBe(0);
  await expect(page.locator(".map")).toHaveAttribute("data-draft", "");

  // A tap 15 m under the ground near the start: Calizas, with its confidence explained.
  await clickSection(page, 40, 15);
  const explained = sheet.locator(".section-explain");
  await expect(explained).toContainText("Calizas");
  await expect(explained).toContainText(/Confianza \d+ %/);
  await expect(explained).toContainText("Profundidad: factor");

  // A tap at the bottom of the section: unknown, not extrapolated.
  await clickSection(page, 300, 290);
  await expect(explained).toContainText("Desconocido");

  if (process.env.SECTION_SCREENSHOT) {
    await page.screenshot({ path: process.env.SECTION_SCREENSHOT, fullPage: true });
  }
  await sheet.getByRole("button", { name: "Cerrar" }).click();
  await expect(sheet).toHaveCount(0);
});

test("a line the server refuses explains itself", async ({ page }) => {
  await mockEverything(page, { status: 422, body: '{"code":"too_long","detail":"the line is 9000 m"}' });
  await page.goto("/");
  await drawLine(page);
  await expect(page.locator(".section-sheet").getByRole("alert")).toHaveText(
    "La línea es demasiado larga: el corte admite hasta 5.000 m.",
  );
});
