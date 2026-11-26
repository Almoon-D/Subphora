// Copyright (c) 2026 Almoon-D. All rights reserved.
// The device's offline packs: each pack's record in IndexedDB (what it holds, how far its
// download got, its area and detailed map) and its files in one Cache Storage cache, which
// the service worker answers from with no coverage. Deleting a pack removes both.
import type { AreaOfInterest, ParcelAnswer } from "../api.ts";
import type { ParcelView, ParcelViews } from "../parcel/parcel.ts";
import { areaKey } from "../search/areas.ts";
import type { Box, Exclusion } from "./plan.ts";

const NAME = "subphora-packs";
const VERSION = 1;
const PACKS = "packs";
/** Every pack's cache name starts so (src/sw/strategy.ts answers from any cache). */
export const PACK_CACHE_PREFIX = "subphora-pack-";

/** Downloading now; stopped before every file was stored (resumable); or complete. */
export type PackState = "downloading" | "interrupted" | "complete";

/** Why a download stopped: paused, files that kept failing, or the device's storage full. */
export type PackStop = "paused" | "files_failed" | "storage_full";

export interface PackRecord {
  id: string;
  label: string;
  created_at: string;
  completed_at: string | null;
  state: PackState;
  stopped: PackStop | null;
  box: Box;
  min_zoom: number;
  max_zoom: number;
  /** Every file's URL, in download order. */
  files: string[];
  estimate_bytes: number;
  stored_files: number;
  stored_bytes: number;
  area: AreaOfInterest | null;
  answer: ParcelAnswer | null;
  excluded: Exclusion[];
  /** Whether the browser granted persistent storage when the pack was made. */
  persisted: boolean;
}

export function packCacheName(id: string): string {
  return `${PACK_CACHE_PREFIX}${id}`;
}

/** The page's detailed maps, with those of complete packs for areas the page has not
 * asked about: a pack brings its area's map back with no coverage. */
export function withStoredAnswers(views: ParcelViews, packs: readonly PackRecord[]): ParcelViews {
  const restored: Record<string, ParcelView> = {};
  for (const pack of packs) {
    if (pack.state === "complete" && pack.area && pack.answer) {
      restored[areaKey(pack.area)] = { state: "answered", answer: pack.answer };
    }
  }
  return { ...restored, ...views };
}

function result<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => {
      resolve(request.result);
    };
    request.onerror = () => {
      reject(request.error ?? new Error("IndexedDB request failed"));
    };
  });
}

function completed(transaction: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => {
      resolve();
    };
    transaction.onabort = () => {
      reject(transaction.error ?? new Error("IndexedDB transaction aborted"));
    };
    transaction.onerror = () => {
      reject(transaction.error ?? new Error("IndexedDB transaction failed"));
    };
  });
}

export class PackStore {
  private readonly db: IDBDatabase;
  private readonly caches: CacheStorage;

  constructor(db: IDBDatabase, cacheStorage: CacheStorage) {
    this.db = db;
    this.caches = cacheStorage;
  }

  close(): void {
    this.db.close();
  }

  /** Every pack, oldest first. */
  async list(): Promise<PackRecord[]> {
    const transaction = this.db.transaction(PACKS, "readonly");
    const records = await result(transaction.objectStore(PACKS).getAll() as IDBRequest<PackRecord[]>);
    return records.sort((a, b) => a.created_at.localeCompare(b.created_at));
  }

  async get(id: string): Promise<PackRecord | undefined> {
    const transaction = this.db.transaction(PACKS, "readonly");
    return result(transaction.objectStore(PACKS).get(id) as IDBRequest<PackRecord | undefined>);
  }

  async save(record: PackRecord): Promise<void> {
    const transaction = this.db.transaction(PACKS, "readwrite");
    const written = completed(transaction);
    transaction.objectStore(PACKS).put(record);
    await written;
  }

  cache(id: string): Promise<Cache> {
    return this.caches.open(packCacheName(id));
  }

  /** Remove a pack's files, then its record: a record without files is a pack to resume. */
  async delete(id: string): Promise<void> {
    await this.caches.delete(packCacheName(id));
    const transaction = this.db.transaction(PACKS, "readwrite");
    const written = completed(transaction);
    transaction.objectStore(PACKS).delete(id);
    await written;
  }
}

export async function openPackStore(factory: IDBFactory, cacheStorage: CacheStorage): Promise<PackStore> {
  const request = factory.open(NAME, VERSION);
  request.onupgradeneeded = () => {
    request.result.createObjectStore(PACKS, { keyPath: "id" });
  };
  return new PackStore(await result(request), cacheStorage);
}
