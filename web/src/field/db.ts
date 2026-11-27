// Copyright (c) 2026 Almoon-D. All rights reserved.
// The device's store of field records (MASTER_PLAN §4.7, hard rule 5): IndexedDB is the
// source of truth on the device. A record, its file and its outbox entry are written in
// one transaction, and the page confirms a record only once that transaction completes.
// Records and files are only ever added, never changed; the outbox says what is left to
// send and leaves once both are on the server. A refused entry stays, with its reason.
// The owner's water levels typed at a well (session 17) go the same way: the reading and
// its outbox entry in one transaction, then to the registry. The device also keeps a copy
// of the registry as last read, so that a well can be chosen with no coverage.
import type { Registry, WellReading } from "../wells/wells.ts";
import type { Observation } from "./records.ts";

const NAME = "subphora-field";
const VERSION = 2;
const OBSERVATIONS = "observations";
const MEDIA = "media";
const OUTBOX = "outbox";
const WELL_READINGS = "well_readings";
const DEVICE = "device";
const REGISTRY_KEY = "registry";

/** A file as bytes with its type: structured-clone support for Blobs in IndexedDB differs
 * between browsers, an ArrayBuffer's does not. */
export interface StoredMedia {
  id: string;
  type: string;
  bytes: ArrayBuffer;
}

export interface OutboxEntry {
  id: string;
  /** What is sent: a field record (absent, as in entries written before readings), or a
   * water level for the well registry. */
  kind?: "well_reading";
  record_sent: boolean;
  /** Null when the record has no file. */
  media_sent: boolean | null;
  /** Why the server refused it (its error code), or null. */
  refused: string | null;
}

export interface Pending {
  entry: OutboxEntry;
  observation: Observation;
}

export interface PendingReading {
  entry: OutboxEntry;
  reading: WellReading;
}

/** The registry as last read from the server, and when. */
export interface RegistryCopy {
  key: typeof REGISTRY_KEY;
  registry: Registry;
  read_at: string;
}

function done(request: IDBRequest): Promise<void> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => {
      resolve();
    };
    request.onerror = () => {
      reject(request.error ?? new Error("IndexedDB request failed"));
    };
  });
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

export class FieldDb {
  private readonly db: IDBDatabase;

  constructor(db: IDBDatabase) {
    this.db = db;
  }

  close(): void {
    this.db.close();
  }

  /** Keep a record (and its file) with its outbox entry; resolves once it is on disk. */
  async record(observation: Observation, media: { type: string; bytes: ArrayBuffer } | null = null): Promise<void> {
    if ((media === null) !== (observation.media === null)) {
      throw new Error("a record and its file go together");
    }
    // "strict": the transaction completes only once the browser has flushed it to disk.
    const transaction = this.db.transaction([OBSERVATIONS, MEDIA, OUTBOX], "readwrite", { durability: "strict" });
    const written = completed(transaction);
    // add(), never put(): an id already kept fails the transaction instead of replacing it.
    transaction.objectStore(OBSERVATIONS).add(observation);
    if (media) {
      transaction.objectStore(MEDIA).add({ id: observation.id, type: media.type, bytes: media.bytes } satisfies StoredMedia);
    }
    const entry: OutboxEntry = { id: observation.id, record_sent: false, media_sent: media ? false : null, refused: null };
    transaction.objectStore(OUTBOX).add(entry);
    await written;
  }

  /** Keep a water level with its outbox entry; resolves once it is on disk. */
  async recordReading(reading: WellReading): Promise<void> {
    const transaction = this.db.transaction([WELL_READINGS, OUTBOX], "readwrite", { durability: "strict" });
    const written = completed(transaction);
    transaction.objectStore(WELL_READINGS).add(reading);
    const entry: OutboxEntry = { id: reading.id, kind: "well_reading", record_sent: false, media_sent: null, refused: null };
    transaction.objectStore(OUTBOX).add(entry);
    await written;
  }

  /** The water levels still in the outbox, by id. */
  async pendingReadings(): Promise<PendingReading[]> {
    const transaction = this.db.transaction([OUTBOX, WELL_READINGS], "readonly");
    const entries = await result(transaction.objectStore(OUTBOX).getAll() as IDBRequest<OutboxEntry[]>);
    const readings = transaction.objectStore(WELL_READINGS);
    const found = await Promise.all(
      entries
        .filter((entry) => entry.kind === "well_reading")
        .map(async (entry) => ({ entry, reading: await result(readings.get(entry.id) as IDBRequest<WellReading | undefined>) })),
    );
    return found.flatMap(({ entry, reading }) => (reading ? [{ entry, reading }] : []));
  }

  /** Replace the device's copy of the registry with the one just read. */
  async keepRegistry(registry: Registry, readAt: Date = new Date()): Promise<void> {
    const transaction = this.db.transaction(DEVICE, "readwrite");
    const written = completed(transaction);
    transaction.objectStore(DEVICE).put({ key: REGISTRY_KEY, registry, read_at: readAt.toISOString() } satisfies RegistryCopy);
    await written;
  }

  async registryCopy(): Promise<RegistryCopy | undefined> {
    const transaction = this.db.transaction(DEVICE, "readonly");
    return result(transaction.objectStore(DEVICE).get(REGISTRY_KEY) as IDBRequest<RegistryCopy | undefined>);
  }

  /** The field records in the outbox, by id: UUIDv7 ids sort by the millisecond they were
   * made in. */
  async pending(): Promise<Pending[]> {
    const transaction = this.db.transaction([OUTBOX, OBSERVATIONS], "readonly");
    const all = await result(transaction.objectStore(OUTBOX).getAll() as IDBRequest<OutboxEntry[]>);
    const entries = all.filter((entry) => entry.kind === undefined);
    const observations = transaction.objectStore(OBSERVATIONS);
    const found = await Promise.all(
      entries.map(async (entry) => ({ entry, observation: await result(observations.get(entry.id) as IDBRequest<Observation | undefined>) })),
    );
    return found.flatMap(({ entry, observation }) => (observation ? [{ entry, observation }] : []));
  }

  async media(id: string): Promise<StoredMedia | undefined> {
    const transaction = this.db.transaction(MEDIA, "readonly");
    return result(transaction.objectStore(MEDIA).get(id) as IDBRequest<StoredMedia | undefined>);
  }

  /** Change an outbox entry; it leaves the outbox once its record and file are both sent. */
  private async update(id: string, change: (entry: OutboxEntry) => OutboxEntry): Promise<void> {
    const transaction = this.db.transaction(OUTBOX, "readwrite");
    const written = completed(transaction);
    const store = transaction.objectStore(OUTBOX);
    const entry = await result(store.get(id) as IDBRequest<OutboxEntry | undefined>);
    if (entry) {
      const next = change(entry);
      if (next.record_sent && next.media_sent !== false && next.refused === null) {
        await done(store.delete(id));
      } else {
        await done(store.put(next));
      }
    }
    await written;
  }

  markRecordSent(id: string): Promise<void> {
    return this.update(id, (entry) => ({ ...entry, record_sent: true }));
  }

  markMediaSent(id: string): Promise<void> {
    return this.update(id, (entry) => ({ ...entry, media_sent: true }));
  }

  /** The server does not hold the record its file belongs to: send the record again. */
  markRecordUnsent(id: string): Promise<void> {
    return this.update(id, (entry) => ({ ...entry, record_sent: false }));
  }

  markRefused(id: string, code: string): Promise<void> {
    return this.update(id, (entry) => ({ ...entry, refused: code }));
  }

  /** Records and readings not yet wholly on the server, refused ones included. */
  async counts(): Promise<{ unsynced: number; refused: number }> {
    const transaction = this.db.transaction(OUTBOX, "readonly");
    const entries = await result(transaction.objectStore(OUTBOX).getAll() as IDBRequest<OutboxEntry[]>);
    return { unsynced: entries.length, refused: entries.filter((e) => e.refused !== null).length };
  }
}

export async function openFieldDb(factory: IDBFactory = indexedDB): Promise<FieldDb> {
  const request = factory.open(NAME, VERSION);
  request.onupgradeneeded = (event) => {
    const db = request.result;
    // Each version adds its stores to those of the versions before, which it keeps.
    if (event.oldVersion < 1) {
      db.createObjectStore(OBSERVATIONS, { keyPath: "id" });
      db.createObjectStore(MEDIA, { keyPath: "id" });
      db.createObjectStore(OUTBOX, { keyPath: "id" });
    }
    if (event.oldVersion < 2) {
      db.createObjectStore(WELL_READINGS, { keyPath: "id" });
      db.createObjectStore(DEVICE, { keyPath: "key" });
    }
  };
  return new FieldDb(await result(request));
}
