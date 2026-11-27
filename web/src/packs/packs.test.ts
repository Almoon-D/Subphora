// Copyright (c) 2026 Almoon-D. All rights reserved.
// Offline packs without a browser: the plan of a pack (its tiles, its estimate, the layers
// it leaves out and why, the size limit), the storage checks (a refused persistence, no
// storage, no space), the download (complete; interrupted and resumed with nothing fetched
// twice; storage full; a file that keeps failing), the device's list of packs, and how the
// service worker answers with and without coverage.
import { readFileSync } from "node:fs";

import { IDBFactory } from "fake-indexeddb";
import { describe, expect, it } from "vitest";

import type { AreaOfInterest, MapConfig, NationalMap, ParcelAnswer } from "../api.ts";
import { areaKey } from "../search/areas.ts";
import { respond, routeOf, shellUrls } from "../sw/strategy.ts";
import { BYTES_HEADER, download, newPack, prepareStorage, type StorageLike } from "./download.ts";
import { geometryStorable, planPack, tileAt, tilesOver, zoomsOf } from "./plan.ts";
import { openPackStore, type PackRecord, packCacheName, withStoredAnswers } from "./store.ts";

const read = (name: string) => readFileSync(new URL(`../../e2e/fixtures/${name}`, import.meta.url), "utf-8");
const CONFIG = JSON.parse(read("map.json")) as MapConfig;
const NATIONAL = JSON.parse(read("national.json")) as NationalMap;
const POINT = JSON.parse(read("area-point-daimiel.json")) as AreaOfInterest;
const ANSWER = JSON.parse(read("parcel-daimiel.json")) as ParcelAnswer;
const SANTIAGO = JSON.parse(read("area-santiago.json")) as AreaOfInterest;
const ORIGIN = "http://127.0.0.1:5199";

/** A Cache Storage cache in memory, keyed by URL as the browser's is. */
class MemoryCache {
  readonly entries = new Map<string, Response>();
  /** Throw a full-storage error once this many files are kept. */
  capacity = Number.POSITIVE_INFINITY;

  match(request: RequestInfo | URL): Promise<Response | undefined> {
    const url = request instanceof Request ? request.url : String(request);
    return Promise.resolve(this.entries.get(url)?.clone());
  }

  put(request: RequestInfo | URL, response: Response): Promise<void> {
    if (this.entries.size >= this.capacity) {
      return Promise.reject(new DOMException("full", "QuotaExceededError"));
    }
    this.entries.set(request instanceof Request ? request.url : String(request), response);
    return Promise.resolve();
  }
}

class MemoryCaches {
  readonly caches = new Map<string, MemoryCache>();

  open(name: string): Promise<Cache> {
    let cache = this.caches.get(name);
    if (!cache) {
      cache = new MemoryCache();
      this.caches.set(name, cache);
    }
    return Promise.resolve(cache as unknown as Cache);
  }

  delete(name: string): Promise<boolean> {
    return Promise.resolve(this.caches.delete(name));
  }
}

function plan() {
  return planPack(CONFIG, NATIONAL, POINT, ANSWER, "Daimiel", ORIGIN);
}

function storage(overrides: Partial<{ quota: number; usage: number; persisted: boolean; persist: boolean; fails: boolean }> = {}): StorageLike {
  return {
    estimate: () => (overrides.fails ? Promise.reject(new Error("no estimate")) : Promise.resolve({ quota: overrides.quota ?? 1e10, usage: overrides.usage ?? 0 })),
    persisted: () => Promise.resolve(overrides.persisted ?? false),
    persist: () => Promise.resolve(overrides.persist ?? true),
  };
}

/** A server answering every file with `size` bytes; `failing` URLs fail every time. */
function server(size = 10, failing: ReadonlySet<string> = new Set()) {
  const asked: string[] = [];
  const fetchFn = (url: string) => {
    asked.push(url);
    if (failing.has(url)) {
      return Promise.reject(new TypeError("Failed to fetch"));
    }
    return Promise.resolve(new Response(new Uint8Array(size), { headers: { "content-type": "image/png" } }));
  };
  return { asked, fetchFn };
}

const SETTINGS = { concurrency: 3, retries: 1, progress_every: 5 };

describe("the plan of a pack", () => {
  it("finds the tile of a place as the IGN numbers it", () => {
    // Zaragoza's tile at zoom 12 (docs/knowledge/ign-cnig.md: tilerow 1525, tilecol 2037).
    expect(tileAt(-0.88, 41.65, 12)).toEqual({ x: 2037, y: 1525 });
    expect(tilesOver([-0.88, 41.65, -0.88, 41.65], 12)).toEqual([{ z: 12, x: 2037, y: 1525 }]);
  });

  it("stores each layer's zooms within the pack's, and at least its deepest", () => {
    const pack = { min_zoom: 10, max_zoom: 18 };
    expect(zoomsOf(pack, 0, 19)).toEqual([10, 11, 12, 13, 14, 15, 16, 17, 18]);
    // The national tiles stop at 9: only 9 is stored, which the map enlarges.
    expect(zoomsOf(pack, 5, 9)).toEqual([9]);
    expect(zoomsOf({ min_zoom: 6, max_zoom: 8 }, 5, 9)).toEqual([6, 7, 8]);
  });

  it("holds the base map over the buffered area, our layers, the detailed map and the answers the page reads", () => {
    const p = plan();
    const packs = CONFIG.packs;
    const base = p.files.filter((f) => f.kind === "base");
    const zooms = zoomsOf(packs, 0, 19);
    expect(base).toHaveLength(zooms.reduce((sum, z) => sum + tilesOver(p.box, z).length, 0));
    expect(base.every((f) => f.url.startsWith("https://www.ign.es/wmts/pnoa-ma?") && !f.url.includes("{"))).toBe(true);
    // The buffer widens the detailed map's box by about 500 m each way.
    const [west, south, east, north] = p.box;
    const [aWest, aSouth, aEast, aNorth] = ANSWER.job.analysis?.bbox ?? [0, 0, 0, 0];
    expect((north - south - (aNorth - aSouth)) * 111_000).toBeGreaterThan(990);
    expect((north - south - (aNorth - aSouth)) * 111_000).toBeLessThan(1010);
    expect(west).toBeLessThan(aWest);
    expect(east).toBeGreaterThan(aEast);
    const national = p.files.filter((f) => f.kind === "national");
    expect(new Set(national.map((f) => f.layer))).toEqual(new Set(packs.layers));
    expect(national.every((f) => f.url.startsWith(`${ORIGIN}/api/national/tiles/`))).toBe(true);
    const images = p.files.filter((f) => f.kind === "image").map((f) => f.url);
    expect(images).toEqual(ANSWER.layers.filter((l) => packs.layers.includes(l.id)).map((l) => `${ORIGIN}${l.image}`));
    const data = p.files.filter((f) => f.kind === "data").map((f) => f.url);
    expect(data).toContain(`${ORIGIN}/api/parcel/${ANSWER.job.id}`);
    expect(data).toContain(`${ORIGIN}/api/map`);
    expect(data.some((url) => url.startsWith(`${ORIGIN}/api/legal?`))).toBe(true);
    expect(p.estimate_bytes).toBe(
      base.length * (packs.base_maps[0]?.tile_bytes ?? 0) + national.length * packs.national_tile_bytes + images.length * packs.parcel_image_bytes,
    );
    expect(p.area).toBe(POINT);
    expect(p.answer?.job.analysis?.candidates).toHaveLength(5);
    expect(new Set(p.files.map((f) => f.url)).size).toBe(p.files.length);
    expect(p.too_large).toBe(false);
  });

  it("never holds the Catastro map, says why, and holds the parcel's geometry instead", () => {
    const p = planPack(CONFIG, NATIONAL, SANTIAGO, null, "Santiago", ORIGIN);
    expect(p.files.some((f) => f.url.includes("catastro"))).toBe(false);
    expect(p.excluded).toContainEqual({ id: "cadastre", kind: "cadastre", reason: "forbidden" });
    // Its geometry comes from the WFS (and the OVC), whose terms allow one parcel offline.
    expect(geometryStorable(SANTIAGO, CONFIG.packs)).toBe(true);
    expect(p.area).toBe(SANTIAGO);
    // Official layers whose terms were not read for this use stay out (hard rule 4).
    expect(p.excluded.filter((e) => e.kind === "overlay").every((e) => e.reason === "not_evaluated")).toBe(true);
    expect(p.excluded).toContainEqual({ id: "detailed", kind: "detailed", reason: "not_computed" });
    // Santiago is outside the synthetic national build.
    expect(p.excluded).toContainEqual({ id: "national", kind: "national", reason: "outside_built" });
  });

  it("widens a point alone by the buffer", () => {
    const p = planPack(CONFIG, NATIONAL, POINT, null, "Daimiel", ORIGIN);
    const [west, south, east, north] = p.box;
    expect((north - south) * 111_000).toBeGreaterThan(990);
    expect((north - south) * 111_000).toBeLessThan(1010);
    expect(west).toBeLessThan(POINT.bbox[0]);
    expect(east).toBeGreaterThan(POINT.bbox[2]);
  });

  it("leaves out a base map whose terms forbid storing it, and a geometry it may not store", () => {
    const config: MapConfig = {
      ...CONFIG,
      packs: {
        ...CONFIG.packs,
        base_maps: [],
        storable_services: [],
        excluded: [...CONFIG.packs.excluded, { id: "pnoa", kind: "base_map", service_id: "ign-pnoa-wmts", reason: "forbidden" }],
      },
    };
    const p = planPack(config, null, POINT, ANSWER, "Daimiel", ORIGIN);
    expect(p.files.some((f) => f.kind === "base")).toBe(false);
    expect(p.excluded).toContainEqual({ id: "pnoa", kind: "base_map", reason: "forbidden" });
    expect(p.excluded).toContainEqual({ id: "geometry", kind: "geometry", reason: "not_storable" });
    expect(p.excluded).toContainEqual({ id: "national", kind: "national", reason: "not_built" });
    expect(p.area).toBeNull();
  });

  it("is refused above the size limit, before anything is downloaded", async () => {
    const config: MapConfig = { ...CONFIG, packs: { ...CONFIG.packs, max_bytes: 1000 } };
    const p = planPack(config, NATIONAL, POINT, ANSWER, "Daimiel", ORIGIN);
    expect(p.too_large).toBe(true);
    expect(await prepareStorage(p, storage(), true)).toEqual({ ok: false, refusal: "too_large" });
  });
});

describe("the device's storage", () => {
  it("asks for persistent storage, and goes ahead (saying so) when it is refused", async () => {
    expect(await prepareStorage(plan(), storage({ persist: true }), true)).toEqual({ ok: true, persisted: true });
    expect(await prepareStorage(plan(), storage({ persist: false }), true)).toEqual({ ok: true, persisted: false });
    const throwing: StorageLike = { ...storage(), persist: () => Promise.reject(new Error("denied")) };
    expect(await prepareStorage(plan(), throwing, true)).toEqual({ ok: true, persisted: false });
  });

  it("refuses without storage, or without the space the estimate needs", async () => {
    expect(await prepareStorage(plan(), undefined, true)).toEqual({ ok: false, refusal: "no_storage" });
    expect(await prepareStorage(plan(), storage(), false)).toEqual({ ok: false, refusal: "no_storage" });
    expect(await prepareStorage(plan(), storage({ quota: 1_000_000, usage: 900_000 }), true)).toEqual({ ok: false, refusal: "no_space" });
    // Without an estimate the download itself stops if the storage fills up.
    expect((await prepareStorage(plan(), storage({ fails: true }), true)).ok).toBe(true);
  });
});

describe("the download", () => {
  const record = () => newPack(plan(), "pack-1", new Date("2026-11-26T10:00:00Z"), true);

  it("stores every file with its size and ends complete", async () => {
    const cache = new MemoryCache();
    const saved: PackRecord[] = [];
    const { asked, fetchFn } = server(10);
    const start = record();
    const end = await download(start, SETTINGS, {
      cache,
      fetchFn,
      save: (r) => {
        saved.push(r);
        return Promise.resolve();
      },
      now: () => new Date("2026-11-26T10:05:00Z"),
    });
    expect(end.state).toBe("complete");
    expect(end.completed_at).toBe("2026-11-26T10:05:00.000Z");
    expect(end.stored_files).toBe(start.files.length);
    expect(end.stored_bytes).toBe(10 * start.files.length);
    expect(new Set(asked)).toEqual(new Set(start.files));
    expect(asked).toHaveLength(start.files.length);
    expect((await cache.match(start.files[0] ?? ""))?.headers.get(BYTES_HEADER)).toBe("10");
    // The progress was written down on the way, not only at the end.
    expect(saved.filter((r) => r.state === "downloading").length).toBeGreaterThan(2);
  });

  it("resumes an interrupted download where it stopped, fetching nothing twice", async () => {
    const cache = new MemoryCache();
    const first = server(10);
    const abort = new AbortController();
    const start = record();
    let stored = 0;
    const paused = await download(start, SETTINGS, {
      cache,
      fetchFn: first.fetchFn,
      save: () => Promise.resolve(),
      onProgress: (r) => {
        stored = r.stored_files;
        if (stored >= 30) {
          abort.abort();
        }
      },
      signal: abort.signal,
    });
    expect(paused.state).toBe("interrupted");
    expect(paused.stopped).toBe("paused");
    expect(paused.stored_files).toBeGreaterThanOrEqual(30);
    expect(paused.stored_files).toBeLessThan(start.files.length);
    // Resumed from the record as last written down: what is stored is counted from the cache.
    const second = server(10);
    const resumed = await download({ ...paused, stored_files: 0, stored_bytes: 0 }, SETTINGS, {
      cache,
      fetchFn: second.fetchFn,
      save: () => Promise.resolve(),
    });
    expect(resumed.state).toBe("complete");
    expect(resumed.stored_files).toBe(start.files.length);
    expect(resumed.stored_bytes).toBe(10 * start.files.length);
    expect(second.asked).toHaveLength(start.files.length - paused.stored_files);
    expect(new Set([...first.asked.filter((url) => cache.entries.has(url)), ...second.asked])).toEqual(new Set(start.files));
  });

  it("stops when the storage is full, keeping what it stored, resumable", async () => {
    const cache = new MemoryCache();
    cache.capacity = 12;
    const end = await download(record(), SETTINGS, { cache, fetchFn: server(10).fetchFn, save: () => Promise.resolve() });
    expect(end.state).toBe("interrupted");
    expect(end.stopped).toBe("storage_full");
    expect(end.stored_files).toBe(12);
    expect(cache.entries.size).toBe(12);
  });

  it("retries a failing file, then ends interrupted without it; a refusal is not retried", async () => {
    const start = record();
    const failing = start.files[3] ?? "";
    const { asked, fetchFn } = server(10, new Set([failing]));
    const end = await download(start, SETTINGS, { cache: new MemoryCache(), fetchFn, save: () => Promise.resolve() });
    expect(end.state).toBe("interrupted");
    expect(end.stopped).toBe("files_failed");
    expect(end.stored_files).toBe(start.files.length - 1);
    expect(asked.filter((url) => url === failing)).toHaveLength(1 + SETTINGS.retries);

    const missing = start.files[4] ?? "";
    const counted: string[] = [];
    const refusing = (url: string) => {
      counted.push(url);
      return Promise.resolve(url === missing ? new Response("{}", { status: 404 }) : new Response(new Uint8Array(1)));
    };
    const refused = await download(start, SETTINGS, { cache: new MemoryCache(), fetchFn: refusing, save: () => Promise.resolve() });
    expect(refused.stopped).toBe("files_failed");
    expect(counted.filter((url) => url === missing)).toHaveLength(1);
  });
});

describe("the device's list of packs", () => {
  it("keeps records, lists them oldest first, and deletes a pack with its files", async () => {
    const memory = new MemoryCaches();
    const store = await openPackStore(new IDBFactory(), memory as unknown as CacheStorage);
    const older = { ...newPack(plan(), "a", new Date("2026-11-26T09:00:00Z"), true), state: "complete" as const };
    const newer = newPack(plan(), "b", new Date("2026-11-26T10:00:00Z"), false);
    await store.save(newer);
    await store.save(older);
    await (await store.cache("a")).put("https://example.org/tile", new Response("x"));
    expect((await store.list()).map((p) => p.id)).toEqual(["a", "b"]);
    expect(memory.caches.has(packCacheName("a"))).toBe(true);
    await store.delete("a");
    expect((await store.list()).map((p) => p.id)).toEqual(["b"]);
    expect(memory.caches.has(packCacheName("a"))).toBe(false);
    expect(await store.get("a")).toBeUndefined();
    store.close();
  });

  it("brings back a complete pack's detailed map, never over the page's own", () => {
    const complete = { ...newPack(plan(), "a", new Date(), true), state: "complete" as const };
    const key = areaKey(POINT);
    expect(withStoredAnswers({}, [complete])[key]).toEqual({ state: "answered", answer: ANSWER });
    expect(withStoredAnswers({}, [{ ...complete, state: "interrupted" }])[key]).toBeUndefined();
    expect(withStoredAnswers({ [key]: { state: "asking" } }, [complete])[key]).toEqual({ state: "asking" });
  });
});

describe("the service worker", () => {
  const origin = "https://subphora.example";
  const at = (path: string) => new URL(path, origin);

  it("keeps the app, serves the API's reads and pack files from storage, and leaves writes and searches alone", () => {
    expect(routeOf(at("/"), "GET", origin)).toBe("shell");
    expect(routeOf(at("/assets/index-abc.js"), "GET", origin)).toBe("shell");
    expect(routeOf(at("/api/map"), "GET", origin)).toBe("shell");
    expect(routeOf(at("/api/national"), "GET", origin)).toBe("shell");
    expect(routeOf(at("/api/national/tiles/potential-index/9/1/2"), "GET", origin)).toBe("stored");
    expect(routeOf(at("/api/parcel/abc/layers/potential-index"), "GET", origin)).toBe("stored");
    expect(routeOf(new URL("https://www.ign.es/wmts/pnoa-ma?x=1"), "GET", origin)).toBe("stored");
    expect(routeOf(at("/api/search?q=x"), "GET", origin)).toBe("network");
    expect(routeOf(at("/api/aoi/point?x=1"), "GET", origin)).toBe("network");
    expect(routeOf(at("/api/field/observations"), "POST", origin)).toBe("network");
    expect(routeOf(at("/api/auth/me"), "GET", origin)).toBe("network");
    expect(shellUrls([`${origin}/`, `${origin}/api/search?q=x`, "https://www.ign.es/x", `${origin}/api/map`, `${origin}/`], origin)).toEqual([
      `${origin}/`,
      `${origin}/api/map`,
    ]);
  });

  function deps(network: () => Promise<Response>, stored: Response | undefined) {
    const kept: string[] = [];
    return {
      kept,
      deps: {
        fetchFn: network,
        match: (request: Request) => Promise.resolve(request.url === `${origin}/` || request.url.endsWith("/tile") ? stored?.clone() : undefined),
        keep: (request: Request) => {
          kept.push(request.url);
          return Promise.resolve();
        },
        timeoutMs: 50,
        wait: () => new Promise<void>((resolve) => setTimeout(resolve, 5)),
      },
    };
  }

  it("answers from the network when it can, keeping the app's files only", async () => {
    const shell = deps(() => Promise.resolve(new Response("fresh")), new Response("old"));
    expect(await (await respond(new Request(`${origin}/`), "shell", shell.deps)).text()).toBe("fresh");
    expect(shell.kept).toEqual([`${origin}/`]);
    const tile = deps(() => Promise.resolve(new Response("fresh")), new Response("old"));
    expect(await (await respond(new Request(`${origin}/tile`), "stored", tile.deps)).text()).toBe("fresh");
    expect(tile.kept).toEqual([]);
  });

  it("answers from storage with no coverage, on a server error and when the network is too slow", async () => {
    const offline = deps(() => Promise.reject(new TypeError("Failed to fetch")), new Response("stored"));
    expect(await (await respond(new Request(`${origin}/tile`), "stored", offline.deps)).text()).toBe("stored");
    const failing = deps(() => Promise.resolve(new Response("bad gateway", { status: 502 })), new Response("stored"));
    expect(await (await respond(new Request(`${origin}/tile`), "stored", failing.deps)).text()).toBe("stored");
    const slow = deps(() => new Promise<Response>(() => undefined), new Response("stored"));
    expect(await (await respond(new Request(`${origin}/tile`), "stored", slow.deps)).text()).toBe("stored");
    // A page opened at another address of the app falls back to the stored page.
    const page = deps(() => Promise.reject(new TypeError("Failed to fetch")), new Response("page"));
    const navigation = { url: `${origin}/?x=1`, mode: "navigate", method: "GET" } as unknown as Request;
    expect(await (await respond(navigation, "shell", page.deps)).text()).toBe("page");
  });

  it("waits for a slow network when nothing is stored, and fails as the network does", async () => {
    let answer: (response: Response) => void = () => undefined;
    const slow = deps(() => new Promise<Response>((resolve) => (answer = resolve)), undefined);
    const pending = respond(new Request(`${origin}/other`), "stored", slow.deps);
    setTimeout(() => {
      answer(new Response("late"));
    }, 20);
    expect(await (await pending).text()).toBe("late");
    const offline = deps(() => Promise.reject(new TypeError("Failed to fetch")), undefined);
    await expect(respond(new Request(`${origin}/other`), "stored", offline.deps)).rejects.toThrow("Failed to fetch");
  });
});
