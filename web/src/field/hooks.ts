// Copyright (c) 2026 Almoon-D. All rights reserved.
// Field mode's live state: the device's position, the store on the device, and the outbox
// that empties it when there is coverage.
import { useCallback, useEffect, useRef, useState } from "react";

import type { FieldConfig } from "../api.ts";
import { type FieldDb, openFieldDb } from "./db.ts";
import { syncOnce, type SyncState } from "./outbox.ts";
import { type Fix, fixOf } from "./records.ts";

/** Why there is no current position: the browser has no geolocation, the user refused it,
 * the device cannot locate itself, or no fix came in time. */
export type PositionProblem = "unsupported" | "denied" | "unavailable" | "timeout";

export interface Located {
  /** The latest fix; kept when a later one fails, with the problem said. */
  fix: Fix | null;
  problem: PositionProblem | null;
}

function problemOf(error: GeolocationPositionError): PositionProblem {
  switch (error.code) {
    case error.PERMISSION_DENIED:
      return "denied";
    case error.TIMEOUT:
      return "timeout";
    default:
      return "unavailable";
  }
}

/** Watch the device's position while `active`. */
export function useGeolocation(config: FieldConfig["geolocation"], active: boolean): Located {
  const supported = typeof navigator !== "undefined" && "geolocation" in navigator;
  const [located, setLocated] = useState<Located>({ fix: null, problem: null });
  useEffect(() => {
    if (!active || !supported) {
      return;
    }
    const watch = navigator.geolocation.watchPosition(
      (position) => {
        const fix = fixOf(position);
        setLocated((current) => (fix ? { fix, problem: null } : { ...current, problem: "unavailable" }));
      },
      (error) => {
        setLocated((current) => ({ ...current, problem: problemOf(error) }));
      },
      { enableHighAccuracy: config.high_accuracy, timeout: config.timeout_ms, maximumAge: config.maximum_age_ms },
    );
    return () => {
      navigator.geolocation.clearWatch(watch);
    };
  }, [active, supported, config.high_accuracy, config.timeout_ms, config.maximum_age_ms]);
  return supported ? located : { fix: null, problem: "unsupported" };
}

export type Store = { state: "opening" } | { state: "open"; db: FieldDb } | { state: "unavailable" };

/** The device's field store, opened once for the page. */
export function useFieldDb(): Store {
  const [store, setStore] = useState<Store>({ state: "opening" });
  useEffect(() => {
    let opened: FieldDb | null = null;
    let cancelled = false;
    openFieldDb().then(
      (db) => {
        if (cancelled) {
          db.close();
          return;
        }
        opened = db;
        setStore({ state: "open", db });
      },
      () => {
        if (!cancelled) {
          setStore({ state: "unavailable" });
        }
      },
    );
    return () => {
      cancelled = true;
      opened?.close();
    };
  }, []);
  return store;
}

export interface OutboxView {
  unsynced: number;
  refused: number;
  syncing: boolean;
  /** How the last round ended; null before the first. */
  last: SyncState | null;
  /** Count again after a record is kept. */
  refresh: () => void;
  sync: () => void;
}

/** The outbox: counted, and sent on opening, when the browser comes online, on demand,
 * and every `retry_s` while anything waits. One round at a time in this page, and in
 * every page of this browser where the Web Locks API exists. */
export function useOutbox(db: FieldDb | null, config: FieldConfig | null): OutboxView {
  const batchSize = config?.sync_batch_size ?? 0;
  const retrySeconds = config?.sync_retry_s ?? 0;
  const [counts, setCounts] = useState({ unsynced: 0, refused: 0 });
  const [syncing, setSyncing] = useState(false);
  const [last, setLast] = useState<SyncState | null>(null);
  const running = useRef(false);
  // A sync asked for during a round runs once the round ends.
  const again = useRef(false);
  const syncRef = useRef<() => void>(() => undefined);

  const refresh = useCallback(() => {
    if (db) {
      void db.counts().then(setCounts);
    }
  }, [db]);

  const sync = useCallback(() => {
    if (!db || batchSize === 0) {
      return;
    }
    if (running.current) {
      again.current = true;
      return;
    }
    running.current = true;
    setSyncing(true);
    const round = () => syncOnce(db, batchSize);
    const locked: Promise<SyncState | null> =
      typeof navigator !== "undefined" && "locks" in navigator
        ? navigator.locks.request("subphora-field-sync", { ifAvailable: true }, async (lock) =>
            lock ? (await round()).state : null,
          )
        : round().then((report) => report.state);
    void locked
      .catch((): SyncState => "server_error")
      .then((state) => {
        if (state) {
          setLast(state);
        }
        running.current = false;
        setSyncing(false);
        refresh();
        if (again.current) {
          again.current = false;
          syncRef.current();
        }
      });
  }, [db, batchSize, refresh]);

  useEffect(() => {
    syncRef.current = sync;
  }, [sync]);

  useEffect(() => {
    if (!db) {
      return;
    }
    refresh();
    sync();
    window.addEventListener("online", sync);
    return () => {
      window.removeEventListener("online", sync);
    };
  }, [db, sync, refresh]);

  const waiting = counts.unsynced - counts.refused > 0;
  useEffect(() => {
    if (!waiting || retrySeconds <= 0) {
      return;
    }
    const timer = setInterval(sync, retrySeconds * 1000);
    return () => {
      clearInterval(timer);
    };
  }, [waiting, sync, retrySeconds]);

  return { ...counts, syncing, last, refresh, sync };
}
