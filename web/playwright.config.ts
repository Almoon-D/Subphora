// Copyright (c) 2026 Almoon-D. All rights reserved.
// Browser tests of the page against a mocked API: every /api call and every map service
// is answered by the test, so no request leaves the machine.
import { defineConfig, devices } from "@playwright/test";

// A Chromium installed apart from Playwright's own (the cloud sessions have one).
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
const port = 5199;

export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  reporter: "list",
  use: {
    baseURL: `http://127.0.0.1:${String(port)}`,
    trace: "off",
    locale: "es-ES",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        launchOptions: {
          ...(executablePath ? { executablePath } : {}),
          // WebGL without a GPU, for MapLibre; a synthetic microphone for voice memos.
          args: [
            "--enable-unsafe-swiftshader",
            "--use-angle=swiftshader",
            "--use-fake-device-for-media-stream",
            "--use-fake-ui-for-media-stream",
          ],
        },
      },
    },
  ],
  webServer: {
    command: `npx vite --host 127.0.0.1 --port ${String(port)} --strictPort`,
    url: `http://127.0.0.1:${String(port)}`,
    reuseExistingServer: false,
    env: { SUBPHORA_API_URL: "" },
  },
});
