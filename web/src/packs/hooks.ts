// Copyright (c) 2026 Almoon-D. All rights reserved.
// The page's offline packs: the store opened once, the list kept current, a download run
// (one at a time) that can be paused and resumed, and deletion.
import { useCallback, useEffect, useRef, useState } from "react";

import type { PacksConfig } from "../api.ts";
import { uuidv7 } from "../field/records.ts";
import { download, newPack, prepareStorage, type Refusal } from "./download.ts";
import type { PackPlan } from "./plan.ts";
import { openPackStore, type PackRecord, type PackStore } from "./store.ts";

export interface Packs {
  /** Null while opening, or when this browser cannot store packs. */
  store: PackStore | null;
  available: boolean;
  packs: PackRecord[];
  /** The pack downloading now, as it progresses. */
  active: PackRecord | null;
  refusal: Refusal | null;
  start: (plan: PackPlan) => Promise<void>;
  resume: (id: string) => Promise<void>;
  pause: () => void;
  remove: (id: string) => Promise<void>;
}

const canCache = () => typeof caches !== "undefined" && typeof indexedDB !== "undefined";

export function usePacks(settings: PacksConfig | null): Packs {
  const [store, setStore] = useState<PackStore | null>(null);
  const [available, setAvailable] = useState(canCache);
  const [packs, setPacks] = useState<PackRecord[]>([]);
  const [active, setActive] = useState<PackRecord | null>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!canCache()) {
      return;
    }
    let opened: PackStore | null = null;
    let current = true;
    openPackStore(indexedDB, caches).then(
      async (packStore) => {
        opened = packStore;
        if (!current) {
          packStore.close();
          return;
        }
        // A download cut by a closed page is resumable, not running.
        const listed = (await packStore.list()).map((p) => (p.state === "downloading" ? { ...p, state: "interrupted" as const, stopped: "paused" as const } : p));
        setStore(packStore);
        setPacks(listed);
      },
      () => {
        setAvailable(false);
      },
    );
    return () => {
      current = false;
      controller.current?.abort();
      opened?.close();
    };
  }, []);

  const refresh = useCallback(async (packStore: PackStore) => {
    setPacks(await packStore.list());
  }, []);

  const run = useCallback(
    async (record: PackRecord) => {
      if (!store || !settings) {
        return;
      }
      const abort = new AbortController();
      controller.current = abort;
      setActive(record);
      try {
        const cache = await store.cache(record.id);
        await download(record, settings, {
          cache,
          fetchFn: (url, init) => fetch(url, init),
          save: (r) => store.save(r),
          onProgress: setActive,
          signal: abort.signal,
        });
      } finally {
        controller.current = null;
        setActive(null);
        await refresh(store);
      }
    },
    [store, settings, refresh],
  );

  const start = useCallback(
    async (plan: PackPlan) => {
      if (!store || active) {
        return;
      }
      const prepared = await prepareStorage(plan, typeof navigator.storage === "undefined" ? undefined : navigator.storage, canCache());
      if (!prepared.ok) {
        setRefusal(prepared.refusal);
        return;
      }
      setRefusal(null);
      await run(newPack(plan, uuidv7(), new Date(), prepared.persisted));
    },
    [store, active, run],
  );

  const resume = useCallback(
    async (id: string) => {
      const record = store && !active ? await store.get(id) : undefined;
      if (record) {
        setRefusal(null);
        await run(record);
      }
    },
    [store, active, run],
  );

  const pause = useCallback(() => {
    controller.current?.abort();
  }, []);

  const remove = useCallback(
    async (id: string) => {
      if (!store || active?.id === id) {
        return;
      }
      await store.delete(id);
      await refresh(store);
    },
    [store, active, refresh],
  );

  return { store, available, packs, active, refusal, start, resume, pause, remove };
}
