// Copyright (c) 2026 Almoon-D. All rights reserved.
// Registering the service worker (src/sw/sw.ts; built as /sw.js) once the map settings
// are read, with their network timeout, and asking it to keep the app's files that this
// first visit loaded before it ran. A browser without service workers (or a page that is
// not secure) simply has none: the app works online as before, and packs say why not.

/** The worker's script: Vite serves the source while developing, the build emits /sw.js. */
function scriptUrl(timeoutMs: number): string {
  const path = import.meta.env.DEV ? "/src/sw/sw.ts" : "/sw.js";
  return `${path}?${new URLSearchParams({ timeout: String(timeoutMs) }).toString()}`;
}

/** Register the worker; resolves false when the browser has none or refuses it. `extra`
 * names files the page loads that its resource list may miss (the map's worker). */
export async function registerServiceWorker(timeoutMs: number, extra: readonly string[] = []): Promise<boolean> {
  if (!("serviceWorker" in navigator)) {
    return false;
  }
  const container = navigator.serviceWorker;
  try {
    // Vite's source has imports; the built /sw.js is one classic script, which every
    // browser with service workers runs.
    await container.register(scriptUrl(timeoutMs), { type: import.meta.env.DEV ? "module" : "classic", scope: "/" });
  } catch {
    return false;
  }
  // Never awaited by the page: a blocked worker never becomes ready.
  void container.ready.then((registration) => {
    const loaded = performance.getEntriesByType("resource").map((entry) => entry.name);
    const urls = [new URL("/", window.location.href).href, ...loaded, ...extra.map((url) => new URL(url, window.location.href).href)];
    registration.active?.postMessage({ type: "warm", urls });
  });
  return true;
}
