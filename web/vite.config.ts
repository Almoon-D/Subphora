// Copyright (c) 2026 Almoon-D. All rights reserved.
// Vite builds and serves the front end; Vitest runs its unit tests.
// `make dev` sets SUBPHORA_API_URL so that /api reaches `subphora serve`. Without it (the
// Playwright tests, which answer /api themselves) there is no proxy.
// The service worker (src/sw/sw.ts) is its own entry, emitted as /sw.js so that it controls
// the whole site; while developing, Vite serves its source with the header that lets it.
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const apiUrl = process.env.SUBPHORA_API_URL;

export default defineConfig({
  plugins: [react()],
  server: {
    headers: { "Service-Worker-Allowed": "/" },
    ...(apiUrl ? { proxy: { "/api": { target: apiUrl } } } : {}),
  },
  build: {
    // MapLibre GL JS alone is about 1.3 MB minified; anything else stays well under it.
    chunkSizeWarningLimit: 1500,
    rolldownOptions: {
      input: { index: "index.html", sw: "src/sw/sw.ts" },
      output: {
        entryFileNames: (chunk) => (chunk.name === "sw" ? "sw.js" : "assets/[name]-[hash].js"),
      },
    },
  },
  test: {
    include: ["src/**/*.test.ts"],
    environment: "node",
  },
});
