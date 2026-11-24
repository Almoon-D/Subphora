// Copyright (c) 2026 Almoon-D. All rights reserved.
// Vite builds and serves the front end; Vitest runs its unit tests.
// `make dev` sets SUBPHORA_API_URL so that /api reaches `subphora serve`. Without it (the
// Playwright tests, which answer /api themselves) there is no proxy.
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const apiUrl = process.env.SUBPHORA_API_URL;

export default defineConfig({
  plugins: [react()],
  server: apiUrl ? { proxy: { "/api": { target: apiUrl } } } : {},
  // MapLibre GL JS alone is about 1.3 MB minified; anything else stays well under it.
  build: { chunkSizeWarningLimit: 1500 },
  test: {
    include: ["src/**/*.test.ts"],
    environment: "node",
  },
});
