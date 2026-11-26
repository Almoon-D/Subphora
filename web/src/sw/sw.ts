// Copyright (c) 2026 Almoon-D. All rights reserved.
// The service worker (decision 0037): it takes over the page at once, keeps the app's own
// files when the page asks, and answers every request as src/sw/strategy.ts says. Its
// script URL carries the network timeout from packs.yaml (?timeout=ms).
import { respond, routeOf, SHELL_CACHE, shellUrls } from "./strategy.ts";

// The few service-worker types used here, typed locally: the WebWorker library conflicts
// with the DOM library that the rest of the app is checked against.
interface ExtendableEvent extends Event {
  waitUntil(promise: Promise<unknown>): void;
}
interface FetchEvent extends ExtendableEvent {
  readonly request: Request;
  respondWith(response: Promise<Response>): void;
}
interface MessageEvent extends ExtendableEvent {
  readonly data: unknown;
}
interface WorkerScope {
  readonly location: { readonly href: string; readonly origin: string };
  skipWaiting(): Promise<void>;
  readonly clients: { claim(): Promise<void> };
  addEventListener(type: "install" | "activate", listener: (event: ExtendableEvent) => void): void;
  addEventListener(type: "fetch", listener: (event: FetchEvent) => void): void;
  addEventListener(type: "message", listener: (event: MessageEvent) => void): void;
}

const scope = globalThis as unknown as WorkerScope;
const timeoutMs = Number(new URL(scope.location.href).searchParams.get("timeout"));

/** Keep the app's files the page names (the first visit loads them before the worker runs). */
async function warm(urls: readonly string[]): Promise<void> {
  const cache = await caches.open(SHELL_CACHE);
  await Promise.all(
    shellUrls(urls, scope.location.origin).map(async (url) => {
      try {
        const response = await fetch(url, { credentials: "same-origin" });
        if (response.ok) {
          await cache.put(url, response);
        }
      } catch {
        // Kept on a later visit.
      }
    }),
  );
}

scope.addEventListener("install", (event) => {
  event.waitUntil(scope.skipWaiting());
});

scope.addEventListener("activate", (event) => {
  event.waitUntil(scope.clients.claim());
});

scope.addEventListener("message", (event) => {
  const data = event.data as { type?: unknown; urls?: unknown } | null;
  if (data?.type === "warm" && Array.isArray(data.urls)) {
    event.waitUntil(warm(data.urls.filter((url): url is string => typeof url === "string")));
  }
});

scope.addEventListener("fetch", (event) => {
  const request = event.request;
  const route = routeOf(new URL(request.url), request.method, scope.location.origin);
  if (route === "network") {
    return;
  }
  event.respondWith(
    respond(request, route, {
      fetchFn: (r) => fetch(r),
      // Vite and some services answer "Vary: Origin"; a copy serves whoever asks.
      match: (r) => caches.match(r, { ignoreVary: true }),
      keep: async (r, response) => {
        const cache = await caches.open(SHELL_CACHE);
        await cache.put(r, response);
      },
      timeoutMs: Number.isFinite(timeoutMs) && timeoutMs > 0 ? timeoutMs : 0,
    }),
  );
});
