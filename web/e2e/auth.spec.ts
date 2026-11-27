// Copyright (c) 2026 Almoon-D. All rights reserved.
// The login in a real browser, against a mocked API: the sign-in page when the server
// answers 401, its refusals, and the app once signed in; the app with no server at all.
import { readFileSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

const MAP = readFileSync(new URL("fixtures/map.json", import.meta.url), "utf-8");
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
  "base64",
);

async function mockMap(page: Page) {
  await page.route(/^https:\/\/(?!127\.0\.0\.1)/, (route) => route.fulfill({ contentType: "image/png", body: PNG }));
  await page.route("**/api/map", (route) => route.fulfill({ contentType: "application/json", body: MAP }));
  await page.route("**/api/national", (route) => route.fulfill({ status: 404, contentType: "application/json", body: "{}" }));
}

test("signs in after a wrong password and a lockout, then shows the map", async ({ page }) => {
  await mockMap(page);
  let signedIn = false;
  const bodies: unknown[] = [];
  await page.route("**/api/auth/me", (route) =>
    signedIn
      ? route.fulfill({ contentType: "application/json", body: JSON.stringify({ name: "ana" }) })
      : route.fulfill({ status: 401, contentType: "application/json", body: '{"code":"unauthenticated"}' }),
  );
  const answers = [
    { status: 401, body: '{"code":"wrong_credentials"}', headers: {} },
    { status: 429, body: '{"code":"too_many_attempts"}', headers: { "Retry-After": "600" } },
    { status: 200, body: '{"name":"ana"}', headers: {} },
  ];
  await page.route("**/api/auth/login", async (route) => {
    bodies.push(route.request().postDataJSON());
    const next = answers.shift() ?? { status: 500, body: "{}", headers: {} };
    signedIn = next.status === 200;
    await route.fulfill({ status: next.status, contentType: "application/json", body: next.body, headers: next.headers });
  });

  await page.goto("/");
  const form = page.getByRole("form", { name: "Subphora" });
  await expect(form).toBeVisible();
  const enter = page.getByRole("button", { name: "Entrar" });
  await expect(enter).toBeDisabled();

  await page.getByLabel("Nombre").fill("ana");
  await page.getByLabel("Contraseña").fill("not the password");
  await enter.click();
  await expect(page.getByRole("alert")).toHaveText("El nombre o la contraseña no son correctos.");
  await expect(page.getByLabel("Contraseña")).toHaveValue("");

  await page.getByLabel("Contraseña").fill("still not it");
  await enter.click();
  await expect(page.getByRole("alert")).toContainText("dentro de 10 min");

  await page.getByLabel("Contraseña").fill("a long password");
  await enter.click();
  await expect(page.getByRole("heading", { level: 1, name: "Subphora" })).toBeVisible();
  await expect(form).toBeHidden();
  expect(bodies).toEqual([
    { name: "ana", password: "not the password" },
    { name: "ana", password: "still not it" },
    { name: "ana", password: "a long password" },
  ]);
});

test("opens the app when the server cannot be reached, as in the field", async ({ page }) => {
  await mockMap(page);
  await page.route("**/api/auth/me", (route) => route.abort("internetdisconnected"));
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "Subphora" })).toBeVisible();
  await expect(page.getByLabel("Contraseña")).toHaveCount(0);
});
