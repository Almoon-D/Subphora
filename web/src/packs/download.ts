// Copyright (c) 2026 Almoon-D. All rights reserved.
// Making a pack: the storage checks before anything is downloaded (a pack too large, a
// browser that cannot store one, too little space left), persistent storage asked for,
// and the download itself: a few files at a time, each retried, its progress written down
// as it goes. What is already stored is counted from the cache, so an interrupted
// download (a pause, a lost signal, a closed page) resumes where it stopped.
import type { PacksConfig } from "../api.ts";
import type { PackPlan } from "./plan.ts";
import type { PackRecord } from "./store.ts";

/** Each stored file carries its size, so that a resumed download counts it unread. */
export const BYTES_HEADER = "x-subphora-bytes";

/** Why a pack cannot be made: larger than packs.yaml allows, a browser without storage for
 * it (an insecure page, an old browser), or too little space left on the device. */
export type Refusal = "too_large" | "no_storage" | "no_space";

/** The parts of the browser's StorageManager a pack needs. */
export interface StorageLike {
  estimate(): Promise<{ quota?: number; usage?: number }>;
  persisted(): Promise<boolean>;
  persist(): Promise<boolean>;
}

export type Prepared = { ok: true; persisted: boolean } | { ok: false; refusal: Refusal };

/** Check that the pack fits, and ask for persistent storage: without it the browser may
 * clear the pack under storage pressure, which the pack's card then says. */
export async function prepareStorage(plan: Pick<PackPlan, "estimate_bytes" | "too_large">, storage: StorageLike | undefined, canCache: boolean): Promise<Prepared> {
  if (plan.too_large) {
    return { ok: false, refusal: "too_large" };
  }
  if (!storage || !canCache) {
    return { ok: false, refusal: "no_storage" };
  }
  try {
    const { quota, usage } = await storage.estimate();
    if (quota !== undefined && quota - (usage ?? 0) < plan.estimate_bytes) {
      return { ok: false, refusal: "no_space" };
    }
  } catch {
    // No estimate: the download itself stops if the storage fills up.
  }
  let persisted: boolean;
  try {
    persisted = (await storage.persisted()) || (await storage.persist());
  } catch {
    persisted = false;
  }
  return { ok: true, persisted };
}

/** A new pack's record, before its first file. */
export function newPack(plan: PackPlan, id: string, now: Date, persisted: boolean): PackRecord {
  return {
    id,
    label: plan.label,
    created_at: now.toISOString(),
    completed_at: null,
    state: "downloading",
    stopped: null,
    box: plan.box,
    min_zoom: plan.min_zoom,
    max_zoom: plan.max_zoom,
    files: plan.files.map((file) => file.url),
    estimate_bytes: plan.estimate_bytes,
    stored_files: 0,
    stored_bytes: 0,
    area: plan.area,
    answer: plan.answer,
    excluded: plan.excluded,
    persisted,
  };
}

export interface DownloadDeps {
  cache: Pick<Cache, "match" | "put">;
  fetchFn: (url: string, init: RequestInit) => Promise<Response>;
  /** Write the record down (IndexedDB). */
  save: (record: PackRecord) => Promise<void>;
  onProgress?: (record: PackRecord) => void;
  /** Aborted: the download pauses, resumable. */
  signal?: AbortSignal;
  now?: () => Date;
}

function isQuotaError(error: unknown): boolean {
  return error instanceof Error && error.name === "QuotaExceededError";
}

/** A file's body and type, after up to `retries` more tries; null when it kept failing,
 * the server refused it, or the download was paused. */
async function fetchFile(url: string, retries: number, deps: DownloadDeps): Promise<Blob | null> {
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    if (deps.signal?.aborted) {
      return null;
    }
    try {
      const init: RequestInit = { mode: "cors", credentials: "same-origin", ...(deps.signal ? { signal: deps.signal } : {}) };
      const response = await deps.fetchFn(url, init);
      if (response.ok) {
        return await response.blob();
      }
      // A refusal (no such tile, no such job) does not change on a retry.
      if (response.status < 500) {
        return null;
      }
    } catch {
      // A lost connection or a pause: tried again, or given up below.
    }
  }
  return null;
}

/** Download every file not yet stored; resolves with the record as it ends: complete, or
 * interrupted with the reason (paused, files that kept failing, storage full). */
export async function download(record: PackRecord, settings: Pick<PacksConfig, "concurrency" | "retries" | "progress_every">, deps: DownloadDeps): Promise<PackRecord> {
  const now = deps.now ?? (() => new Date());
  const paused = () => deps.signal?.aborted === true;
  const pending: string[] = [];
  let storedFiles = 0;
  let storedBytes = 0;
  for (const url of record.files) {
    const hit = await deps.cache.match(url);
    if (hit) {
      storedFiles += 1;
      storedBytes += Number(hit.headers.get(BYTES_HEADER) ?? 0);
    } else {
      pending.push(url);
    }
  }
  let current: PackRecord = { ...record, state: "downloading", stopped: null, stored_files: storedFiles, stored_bytes: storedBytes };
  await deps.save(current);
  deps.onProgress?.(current);

  let next = 0;
  let failed = 0;
  // Set by a worker when the storage is full: every worker then stops.
  const storage = { full: false };
  let unsaved = 0;
  const worker = async (): Promise<void> => {
    while (!storage.full && !paused()) {
      const url = pending[next];
      if (url === undefined) {
        return;
      }
      next += 1;
      const body = await fetchFile(url, settings.retries, deps);
      if (!body) {
        failed += paused() ? 0 : 1;
        continue;
      }
      const headers = { "content-type": body.type || "application/octet-stream", [BYTES_HEADER]: String(body.size) };
      try {
        await deps.cache.put(url, new Response(body, { headers }));
      } catch (error) {
        if (isQuotaError(error)) {
          storage.full = true;
          return;
        }
        throw error;
      }
      current = { ...current, stored_files: current.stored_files + 1, stored_bytes: current.stored_bytes + body.size };
      deps.onProgress?.(current);
      unsaved += 1;
      if (unsaved >= settings.progress_every) {
        unsaved = 0;
        await deps.save(current);
      }
    }
  };
  await Promise.all(Array.from({ length: settings.concurrency }, worker));

  if (storage.full) {
    current = { ...current, state: "interrupted", stopped: "storage_full" };
  } else if (paused()) {
    current = { ...current, state: "interrupted", stopped: "paused" };
  } else if (failed > 0) {
    current = { ...current, state: "interrupted", stopped: "files_failed" };
  } else {
    current = { ...current, state: "complete", stopped: null, completed_at: now().toISOString() };
  }
  await deps.save(current);
  deps.onProgress?.(current);
  return current;
}
