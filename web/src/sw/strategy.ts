// Copyright (c) 2026 Almoon-D. All rights reserved.
// How the service worker answers each request (decision 0037): the app itself (its page,
// its scripts, /api/map and /api/national) from the network, kept for the next time, and
// from what was kept when the network fails, errs or is too slow; a pack's files and the
// API's other answers the same way but never kept outside their pack; requests that change
// something (the field outbox) and searches always go to the network. With no coverage the
// page therefore opens, and a pack's map draws, from what the device holds.

/** The app's own files and settings: kept on every successful load. */
export const SHELL_CACHE = "subphora-shell";

/** shell: served and kept; stored: served from any cache when the network fails; network:
 * not touched by the service worker. */
export type Route = "shell" | "stored" | "network";

const SHELL_API = new Set(["/api/map", "/api/national"]);
// Answers that are never worth an old copy: searches and the field outbox.
const LIVE_API = ["/api/search", "/api/aoi/", "/api/field/", "/api/section"];

export function routeOf(url: URL, method: string, origin: string): Route {
  if (method !== "GET") {
    return "network";
  }
  if (url.origin !== origin) {
    return "stored";
  }
  if (SHELL_API.has(url.pathname)) {
    return "shell";
  }
  if (url.pathname.startsWith("/api/")) {
    return LIVE_API.some((prefix) => url.pathname.startsWith(prefix)) ? "network" : "stored";
  }
  return "shell";
}

export interface StrategyDeps {
  fetchFn: (request: Request) => Promise<Response>;
  /** A copy from any cache, packs included. */
  match: (request: Request) => Promise<Response | undefined>;
  /** Keep a shell response. */
  keep: (request: Request, response: Response) => Promise<void>;
  /** How long the network has before a stored copy answers instead; 0: no limit. */
  timeoutMs: number;
  wait?: (ms: number) => Promise<void>;
}

const TIMED_OUT = "timed out";

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** The network's answer if it comes in time and is good; otherwise a stored copy if there
 * is one; otherwise whatever the network answers in the end. */
export async function respond(request: Request, route: Exclude<Route, "network">, deps: StrategyDeps): Promise<Response> {
  const wait = deps.wait ?? sleep;
  const network = deps.fetchFn(request);
  // A navigation (the page itself, with or without a query) falls back to the stored page.
  const stored = deps
    .match(request)
    .then(async (copy) => copy ?? (request.mode === "navigate" ? deps.match(new Request(new URL("/", request.url).href)) : undefined))
    .catch(() => undefined);
  let first: Response | typeof TIMED_OUT;
  try {
    const timer = deps.timeoutMs > 0 ? wait(deps.timeoutMs).then((): typeof TIMED_OUT => TIMED_OUT) : new Promise<never>(() => undefined);
    first = await Promise.race([network, timer]);
  } catch (error) {
    const copy = await stored;
    if (copy) {
      return copy;
    }
    throw error;
  }
  if (first === TIMED_OUT) {
    const copy = await stored;
    return copy ?? network;
  }
  if (!first.ok) {
    return (await stored) ?? first;
  }
  if (route === "shell") {
    await deps.keep(request, first.clone()).catch(() => undefined);
  }
  return first;
}

/** The app's files among the URLs the page has loaded: kept once the worker runs, since
 * the first visit loads them before it does. */
export function shellUrls(urls: readonly string[], origin: string): string[] {
  const shell = urls.filter((url) => {
    try {
      return routeOf(new URL(url), "GET", origin) === "shell";
    } catch {
      return false;
    }
  });
  return [...new Set(shell)];
}
