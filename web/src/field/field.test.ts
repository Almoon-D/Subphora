// Copyright (c) 2026 Almoon-D. All rights reserved.
// Field mode's mechanics without a browser: ids, distances and the "at the spot" rule,
// the track's sampling, the device store, the outbox against a server that behaves like
// ours (idempotent upserts) and fails in each way it can, the export, the tab's session,
// and the owner's water levels kept on the device and sent to the well registry.
import { IDBFactory } from "fake-indexeddb";
import { describe, expect, it } from "vitest";

import { type FieldDb, openFieldDb } from "./db.ts";
import { base64, EXPORT_FORMAT, exportName, unsyncedExport } from "./export.ts";
import { atSpot, circle, compassPoint, leg } from "./geodesy.ts";
import { syncOnce } from "./outbox.ts";
import {
  type Fix,
  fixOf,
  mediaProblem,
  mediaType,
  nextTrackPoint,
  note,
  type Observation,
  sha256,
  trackPoint,
  uuidv7,
  withMedia,
} from "./records.ts";
import { loadFieldSession, NO_FIELD, saveFieldSession } from "./session.ts";
import type { Registry, WellReading } from "../wells/wells.ts";

const DAIMIEL: [number, number] = [-3.61, 39.07];

function fixAt(lon: number, lat: number, accuracy = 5, at = "2026-11-26T10:00:00.000Z"): Fix {
  return {
    longitude: lon,
    latitude: lat,
    accuracy_m: accuracy,
    altitude_m: null,
    altitude_accuracy_m: null,
    heading_deg: null,
    speed_m_s: null,
    fixed_at: at,
  };
}

describe("ids", () => {
  it("makes canonical UUIDv7s that sort by time", () => {
    const id = uuidv7(Date.UTC(2026, 10, 26));
    expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    expect(id.slice(0, 13).replace("-", "")).toBe(Date.UTC(2026, 10, 26).toString(16).padStart(12, "0"));
    const ids = [3, 1, 2].map((ms) => uuidv7(Date.UTC(2026, 10, 26) + ms));
    expect([...ids].sort()).toEqual([ids[1], ids[2], ids[0]]);
    expect(new Set(Array.from({ length: 100 }, () => uuidv7(0))).size).toBe(100);
    // The version and variant bits win over whatever random bits come in.
    expect(uuidv7(0, new Uint8Array(10).fill(0xff))).toBe("00000000-0000-7fff-bfff-ffffffffffff");
  });
});

describe("geodesy", () => {
  it("measures on the ellipsoid", () => {
    const north = leg(DAIMIEL, [DAIMIEL[0], DAIMIEL[1] + 0.001]);
    // A thousandth of a degree of latitude at 39° N is 111.0 m on WGS84.
    expect(north.distance_m).toBeCloseTo(111.03, 1);
    expect(north.bearing_deg).toBeCloseTo(0, 6);
    expect(leg(DAIMIEL, [DAIMIEL[0] + 0.001, DAIMIEL[1]]).bearing_deg).toBeCloseTo(90, 1);
    expect(leg(DAIMIEL, [DAIMIEL[0] - 0.001, DAIMIEL[1]]).bearing_deg).toBeCloseTo(270, 1);
    expect(leg(DAIMIEL, DAIMIEL).distance_m).toBe(0);
  });

  it("draws an accuracy circle at its radius, closed", () => {
    const ring = circle(DAIMIEL, 25, 16);
    expect(ring).toHaveLength(17);
    expect(ring[0]).toEqual(ring[16]);
    for (const point of ring) {
      expect(leg(DAIMIEL, point).distance_m).toBeCloseTo(25, 6);
    }
  });

  it("is at the spot only close enough and with accuracy good enough", () => {
    expect(atSpot(4, 5, 10)).toBe(true);
    expect(atSpot(10, 10, 10)).toBe(true);
    expect(atSpot(10.1, 3, 10)).toBe(false);
    // Right on the spot, but the device cannot say so.
    expect(atSpot(0, 12, 10)).toBe(false);
  });

  it("names the compass point", () => {
    expect([0, 44, 46, 90, 180, 225, 270, 315, 359, -90].map(compassPoint)).toEqual([
      "n",
      "ne",
      "ne",
      "e",
      "s",
      "sw",
      "w",
      "nw",
      "n",
      "w",
    ]);
  });
});

describe("records", () => {
  it("reads a fix from the Geolocation API, invalid values as none", () => {
    const position = (coords: Partial<GeolocationCoordinates>) =>
      ({
        timestamp: Date.UTC(2026, 10, 26, 10),
        coords: { longitude: -3.61, latitude: 39.07, accuracy: 8, altitude: null, altitudeAccuracy: null, heading: null, speed: null, ...coords },
      }) as GeolocationPosition;
    expect(fixOf(position({}))).toEqual({ ...fixAt(-3.61, 39.07, 8), fixed_at: "2026-11-26T10:00:00.000Z" });
    const moving = fixOf(position({ heading: 45, speed: 1.5, altitude: 620, altitudeAccuracy: 4 }));
    expect(moving).toMatchObject({ heading_deg: 45, speed_m_s: 1.5, altitude_m: 620, altitude_accuracy_m: 4 });
    const odd = fixOf(position({ heading: Number.NaN, speed: -1, altitudeAccuracy: 0 }));
    expect(odd).toMatchObject({ heading_deg: null, speed_m_s: null, altitude_accuracy_m: null });
    expect(fixOf(position({ accuracy: 0 }))).toBeNull();
  });

  it("samples the track by time or by distance", () => {
    const first = fixAt(-3.61, 39.07);
    expect(nextTrackPoint(null, first, 10, 10)).toBe(true);
    expect(nextTrackPoint(first, fixAt(-3.61, 39.07001, 5, "2026-11-26T10:00:05.000Z"), 10, 10)).toBe(false);
    expect(nextTrackPoint(first, fixAt(-3.61, 39.07001, 5, "2026-11-26T10:00:10.000Z"), 10, 10)).toBe(true);
    expect(nextTrackPoint(first, fixAt(-3.61, 39.0701, 5, "2026-11-26T10:00:02.000Z"), 10, 10)).toBe(true);
  });

  it("refuses a file that could never sync", () => {
    const types = ["image/jpeg", "audio/webm"];
    expect(mediaType("audio/webm;codecs=opus")).toBe("audio/webm");
    expect(mediaProblem("audio/webm;codecs=opus", 10, types, 100)).toBeNull();
    expect(mediaProblem("image/gif", 10, types, 100)).toBe("type");
    expect(mediaProblem("image/jpeg", 101, types, 100)).toBe("size");
    expect(mediaProblem("image/jpeg", 0, types, 100)).toBe("empty");
  });

  it("declares a file by its type, size and SHA-256", async () => {
    const bytes = new TextEncoder().encode("abc").buffer;
    const photo = await withMedia("photo", bytes, "image/jpeg", null, { position: null, target: null });
    expect(photo.media).toEqual({
      content_type: "image/jpeg",
      size_bytes: 3,
      sha256: "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
    });
    expect(photo.position).toBeNull();
    expect(await sha256(new ArrayBuffer(0))).toBe("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
  });
});

/** A server that behaves like ours: an upsert by id, files after their record. */
class FakeServer {
  readonly records = new Map<string, string>();
  readonly files = new Map<string, number>();
  posts = 0;
  puts = 0;
  /** Each call takes the next failure, if any: thrown (network) or answered. */
  failures: ({ status: number; code?: string } | "network")[] = [];
  /** Codes to refuse records with, by id. */
  refuse = new Map<string, string>();
  /** The well registry: the wells it holds, and its readings by id. */
  wells = new Set<string>();
  readings = new Map<string, string>();
  readingPosts = 0;

  fetch: typeof fetch = (input, init) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const failure = this.failures.shift();
    if (failure === "network") {
      return Promise.reject(new TypeError("Failed to fetch"));
    }
    if (failure) {
      return Promise.resolve(Response.json({ code: failure.code ?? "x" }, { status: failure.status }));
    }
    if (init?.method === "POST" && url.endsWith("/api/wells/readings")) {
      this.readingPosts += 1;
      const { readings } = JSON.parse(init.body as string) as {
        readings: WellReading[];
      };
      const results = readings.map((r) => {
        if (!this.wells.has(r.well_id)) {
          return { id: r.id, outcome: "unknown_well" };
        }
        const body = JSON.stringify(r);
        const stored = this.readings.get(r.id);
        if (stored === undefined) {
          this.readings.set(r.id, body);
          return { id: r.id, outcome: "created" };
        }
        return {
          id: r.id,
          outcome: stored === body ? "duplicate" : "conflict",
        };
      });
      return Promise.resolve(Response.json({ results }));
    }
    if (init?.method === "POST") {
      this.posts += 1;
      const { observations } = JSON.parse(init.body as string) as { observations: Observation[] };
      const refused = observations.find((o) => this.refuse.has(o.id));
      if (refused) {
        return Promise.resolve(Response.json({ code: this.refuse.get(refused.id) }, { status: 422 }));
      }
      const results = observations.map((o) => {
        const body = JSON.stringify(o);
        const stored = this.records.get(o.id);
        if (stored === undefined) {
          this.records.set(o.id, body);
          return { id: o.id, outcome: "created" };
        }
        return { id: o.id, outcome: stored === body ? "duplicate" : "conflict" };
      });
      return Promise.resolve(Response.json({ results }));
    }
    this.puts += 1;
    const id = url.split("/").at(-2) ?? "";
    if (!this.records.has(id)) {
      return Promise.resolve(Response.json({ code: "unknown_observation" }, { status: 404 }));
    }
    const created = !this.files.has(id);
    this.files.set(id, (init?.body as ArrayBuffer).byteLength);
    return Promise.resolve(Response.json({ id, outcome: created ? "created" : "duplicate" }, { status: created ? 201 : 200 }));
  };
}

async function freshDb(): Promise<FieldDb> {
  return openFieldDb(new IDBFactory());
}

const PHOTO = new TextEncoder().encode("synthetic jpeg").buffer;
const context = { position: fixAt(...DAIMIEL), target: null };

async function fill(db: FieldDb): Promise<Observation[]> {
  const photo = await withMedia("photo", PHOTO, "image/jpeg", "Brocal", context);
  const track = uuidv7();
  const records = [
    note("Calizas", context),
    photo,
    trackPoint(track, fixAt(...DAIMIEL), { target: null }),
    trackPoint(track, fixAt(-3.6101, 39.0701), { target: null }),
  ];
  for (const record of records) {
    await db.record(record, record.media ? { type: "image/jpeg", bytes: PHOTO } : null);
  }
  return records;
}

describe("the device store", () => {
  it("keeps each record once, with its file, never replacing it", async () => {
    const db = await freshDb();
    const [first] = await fill(db);
    expect(await db.counts()).toEqual({ unsynced: 4, refused: 0 });
    if (!first) {
      throw new Error("no record");
    }
    await expect(db.record({ ...first, text: "otra" })).rejects.toThrow();
    const pending = await db.pending();
    expect(pending.map((p) => p.observation.kind).sort()).toEqual(["note", "photo", "track_point", "track_point"]);
    expect(pending.find((p) => p.observation.id === first.id)?.observation.text).toBe("Calizas");
    await expect(db.record(note("sin archivo", context), { type: "image/jpeg", bytes: PHOTO })).rejects.toThrow();
    expect(await db.counts()).toEqual({ unsynced: 4, refused: 0 });
  });
});

describe("the outbox", () => {
  it("sends every record and file once", async () => {
    const db = await freshDb();
    const records = await fill(db);
    const server = new FakeServer();
    expect(await syncOnce(db, 50, server.fetch)).toEqual({ state: "done", sent: 5 });
    expect(server.records.size).toBe(4);
    expect([...server.files.values()]).toEqual([PHOTO.byteLength]);
    expect(await db.counts()).toEqual({ unsynced: 0, refused: 0 });
    // The device keeps its records; only the outbox empties.
    expect(records).toHaveLength(4);
    expect(await syncOnce(db, 50, server.fetch)).toEqual({ state: "done", sent: 0 });
    expect(server.posts).toBe(1);
  });

  it("sends in batches", async () => {
    const db = await freshDb();
    await fill(db);
    const server = new FakeServer();
    await syncOnce(db, 3, server.fetch);
    expect(server.posts).toBe(2);
    expect(server.records.size).toBe(4);
  });

  it("stops when the network drops and resumes without duplicating", async () => {
    const db = await freshDb();
    await fill(db);
    const server = new FakeServer();
    server.failures = ["network"];
    expect(await syncOnce(db, 50, server.fetch)).toEqual({ state: "offline", sent: 0 });
    expect(await db.counts()).toEqual({ unsynced: 4, refused: 0 });
    expect((await syncOnce(db, 50, server.fetch)).state).toBe("done");
    expect(server.records.size).toBe(4);
    expect(await db.counts()).toEqual({ unsynced: 0, refused: 0 });
  });

  it("sends again a batch whose answer was lost, without duplicating", async () => {
    const db = await freshDb();
    await fill(db);
    const server = new FakeServer();
    let cut = true;
    // The records reach the server, then the connection drops before the answer.
    const flaky: typeof fetch = async (input, init) => {
      const answer = await server.fetch(input, init);
      if (cut) {
        cut = false;
        throw new TypeError("Failed to fetch");
      }
      return answer;
    };
    expect((await syncOnce(db, 50, flaky)).state).toBe("offline");
    expect(server.records.size).toBe(4);
    expect(await db.counts()).toEqual({ unsynced: 4, refused: 0 });
    expect(await syncOnce(db, 50, flaky)).toEqual({ state: "done", sent: 5 });
    expect(server.records.size).toBe(4);
    expect(server.posts).toBe(2);
    expect([...server.files.keys()]).toHaveLength(1);
  });

  it("counts a record the server already holds as sent", async () => {
    const db = await freshDb();
    const records = await fill(db);
    const server = new FakeServer();
    for (const record of records) {
      server.records.set(record.id, JSON.stringify(record));
    }
    expect((await syncOnce(db, 50, server.fetch)).state).toBe("done");
    expect(server.records.size).toBe(4);
    expect(await db.counts()).toEqual({ unsynced: 0, refused: 0 });
  });

  it("waits on a server error, with nothing marked", async () => {
    const db = await freshDb();
    await fill(db);
    const server = new FakeServer();
    server.failures = [{ status: 503, code: "store_unavailable" }];
    expect(await syncOnce(db, 50, server.fetch)).toEqual({ state: "server_error", sent: 0 });
    expect(await db.counts()).toEqual({ unsynced: 4, refused: 0 });
    expect((await syncOnce(db, 50, server.fetch)).state).toBe("done");
  });

  it("waits when the session has ended, refusing nothing", async () => {
    const db = await freshDb();
    await fill(db);
    const server = new FakeServer();
    server.failures = [{ status: 401, code: "unauthenticated" }];
    expect(await syncOnce(db, 50, server.fetch)).toEqual({ state: "signed_out", sent: 0 });
    expect(await db.counts()).toEqual({ unsynced: 4, refused: 0 });
    expect((await syncOnce(db, 50, server.fetch)).state).toBe("done");
  });

  it("keeps a refused record with its reason and sends the others", async () => {
    const db = await freshDb();
    const records = await fill(db);
    const server = new FakeServer();
    const refused = records[0]?.id ?? "";
    server.refuse.set(refused, "note_too_long");
    expect((await syncOnce(db, 50, server.fetch)).state).toBe("done");
    expect(server.records.has(refused)).toBe(false);
    expect(server.records.size).toBe(3);
    expect(await db.counts()).toEqual({ unsynced: 1, refused: 1 });
    expect((await db.pending())[0]?.entry.refused).toBe("note_too_long");
  });

  it("keeps a conflicting record instead of dropping it", async () => {
    const db = await freshDb();
    const records = await fill(db);
    const server = new FakeServer();
    const first = records[0];
    if (!first) {
      throw new Error("no record");
    }
    server.records.set(first.id, JSON.stringify({ ...first, text: "otra" }));
    await syncOnce(db, 50, server.fetch);
    expect(await db.counts()).toEqual({ unsynced: 1, refused: 1 });
    expect((await db.pending())[0]?.entry.refused).toBe("conflict");
  });

  it("sends a record again when the server lost it, once a round", async () => {
    const db = await freshDb();
    await fill(db);
    const server = new FakeServer();
    // The record is taken, then the server forgets it before its file arrives.
    const forgetful: typeof fetch = async (input, init) => {
      const answer = await server.fetch(input, init);
      if (init?.method === "POST") {
        server.records.clear();
      }
      return answer;
    };
    const report = await syncOnce(db, 50, forgetful);
    expect(report.state).toBe("done");
    // The photo's record was sent twice (once again after the 404) and still lacks its file.
    expect(server.posts).toBe(2);
    expect(await db.counts()).toEqual({ unsynced: 1, refused: 0 });
    expect((await db.pending())[0]?.entry).toMatchObject({ record_sent: false, media_sent: false });
    // With a server that keeps it, the next round finishes.
    expect((await syncOnce(db, 50, server.fetch)).state).toBe("done");
    expect(await db.counts()).toEqual({ unsynced: 0, refused: 0 });
  });

  it("refuses a file the server will not take, keeping it", async () => {
    const db = await freshDb();
    await fill(db);
    const server = new FakeServer();
    const realFetch = server.fetch;
    server.fetch = (input, init) =>
      init?.method === "PUT" ? Promise.resolve(Response.json({ code: "media_mismatch" }, { status: 400 })) : realFetch(input, init);
    await syncOnce(db, 50, server.fetch);
    expect(await db.counts()).toEqual({ unsynced: 1, refused: 1 });
  });
});

describe("the export", () => {
  it("holds every unsent record with its file", async () => {
    const db = await freshDb();
    const records = await fill(db);
    const exported = await unsyncedExport(db, new Date("2026-11-26T12:00:00Z"));
    expect(exported.format).toBe(EXPORT_FORMAT);
    expect(exported.exported_at).toBe("2026-11-26T12:00:00.000Z");
    expect(exported.records.map((r) => r.observation.id).sort()).toEqual(records.map((r) => r.id).sort());
    const photo = exported.records.find((r) => r.observation.kind === "photo");
    expect(photo?.media).toEqual({ type: "image/jpeg", base64: btoa("synthetic jpeg") });
    expect(exported.records.filter((r) => r.media === null)).toHaveLength(3);
    await syncOnce(db, 50, new FakeServer().fetch);
    expect((await unsyncedExport(db)).records).toEqual([]);
  });

  it("encodes large files and names the file by the moment", () => {
    const big = new Uint8Array(100_000).map((_, i) => i % 256);
    expect(atob(base64(big.buffer))).toHaveLength(100_000);
    expect(exportName(new Date(2026, 10, 26, 9, 5))).toBe("subphora-campo-20261126-0905.json");
  });
});

describe("the tab's field session", () => {
  it("is read back, and off when missing or broken", () => {
    const store = new Map<string, string>();
    const storage = {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => {
        store.set(key, value);
      },
    };
    expect(loadFieldSession(storage)).toEqual(NO_FIELD);
    const target = { area_id: "0123456789abcdef", rank: 2, longitude: -3.61, latitude: 39.07 };
    saveFieldSession({ on: true, target }, storage);
    expect(loadFieldSession(storage)).toEqual({ on: true, target });
    store.set("subphora.field", '{"on":true,"target":{"rank":"2"}}');
    expect(loadFieldSession(storage)).toEqual({ on: true, target: null });
    store.set("subphora.field", "{");
    expect(loadFieldSession(storage)).toEqual(NO_FIELD);
    expect(loadFieldSession(null)).toEqual(NO_FIELD);
    saveFieldSession(NO_FIELD, {
      setItem: () => {
        throw new Error("full");
      },
    });
  });
});

const WELL_ID = "0b9f4c1e-6d2a-4f3b-9c8e-1a2b3c4d5e6f";

function level(depth: number, pump: WellReading["pump"] = "stopped", well = WELL_ID): WellReading {
  return {
    id: uuidv7(),
    well_id: well,
    measured_at: "2026-11-20T08:00:00.000Z",
    depth_to_water_m: depth,
    reference: "casing_top",
    reference_height_m: 0.5,
    measured_by: "owner",
    pump,
    pump_minutes: pump === "unknown" ? null : 600,
  };
}

describe("the owner's water levels", () => {
  it("are kept on the device with their outbox entry, apart from field records", async () => {
    const db = await freshDb();
    await fill(db);
    const reading = level(13);
    await db.recordReading(reading);
    expect(await db.counts()).toEqual({ unsynced: 5, refused: 0 });
    expect((await db.pending()).map((p) => p.observation.id)).not.toContain(reading.id);
    expect(await db.pendingReadings()).toEqual([
      {
        entry: {
          id: reading.id,
          kind: "well_reading",
          record_sent: false,
          media_sent: null,
          refused: null,
        },
        reading,
      },
    ]);
    // Only ever added: the same id again fails instead of replacing it.
    await expect(db.recordReading({ ...reading, depth_to_water_m: 99 })).rejects.toThrow();
    expect((await db.pendingReadings())[0]?.reading.depth_to_water_m).toBe(13);
  });

  it("go to the registry once, after the field records, and leave the outbox", async () => {
    const db = await freshDb();
    await fill(db);
    const server = new FakeServer();
    server.wells.add(WELL_ID);
    const readings = [level(13), level(2, "running")];
    for (const reading of readings) {
      await db.recordReading(reading);
    }
    const report = await syncOnce(db, 50, server.fetch);
    expect(report).toEqual({ state: "done", sent: 7 });
    expect([...server.readings.keys()].sort()).toEqual(readings.map((r) => r.id).sort());
    expect(server.readingPosts).toBe(1);
    expect(await db.counts()).toEqual({ unsynced: 0, refused: 0 });
    // A later round sends nothing again.
    expect(await syncOnce(db, 50, server.fetch)).toEqual({
      state: "done",
      sent: 0,
    });
    expect(server.readingPosts).toBe(1);
  });

  it("wait offline, and a batch whose answer was lost goes again without duplicating", async () => {
    const db = await freshDb();
    const server = new FakeServer();
    server.wells.add(WELL_ID);
    const reading = level(13);
    await db.recordReading(reading);
    server.failures = ["network"];
    expect(await syncOnce(db, 50, server.fetch)).toEqual({
      state: "offline",
      sent: 0,
    });
    expect(await db.counts()).toEqual({ unsynced: 1, refused: 0 });
    // The server took it but the answer never came: the next round finds it held.
    server.readings.set(reading.id, JSON.stringify(reading));
    expect(await syncOnce(db, 50, server.fetch)).toEqual({
      state: "done",
      sent: 1,
    });
    expect(server.readings.size).toBe(1);
    expect(await db.counts()).toEqual({ unsynced: 0, refused: 0 });
  });

  it("are kept with the reason when refused, and a server error refuses nothing", async () => {
    const db = await freshDb();
    const server = new FakeServer();
    server.wells.add(WELL_ID);
    const orphan = level(13, "stopped", "11111111-2222-4333-8444-555555555555");
    const changed = level(14);
    await db.recordReading(orphan);
    await db.recordReading(changed);
    server.failures = [{ status: 503 }];
    expect(await syncOnce(db, 50, server.fetch)).toEqual({
      state: "server_error",
      sent: 0,
    });
    expect(await db.counts()).toEqual({ unsynced: 2, refused: 0 });
    server.readings.set(changed.id, JSON.stringify({ ...changed, depth_to_water_m: 1 }));
    expect(await syncOnce(db, 50, server.fetch)).toEqual({
      state: "done",
      sent: 0,
    });
    const refused = await db.pendingReadings();
    expect(refused.map((p) => [p.reading.id, p.entry.refused])).toEqual(
      [
        [orphan.id, "unknown_well"],
        [changed.id, "conflict"],
      ].sort((a, b) => (a[0] ?? "").localeCompare(b[0] ?? "")),
    );
    expect(await db.counts()).toEqual({ unsynced: 2, refused: 2 });
  });

  it("are refused one by one when a batch is refused", async () => {
    const db = await freshDb();
    const server = new FakeServer();
    server.wells.add(WELL_ID);
    const readings = [level(13), level(14)];
    for (const reading of readings) {
      await db.recordReading(reading);
    }
    server.failures = [
      { status: 400, code: "invalid_well" },
      { status: 400, code: "invalid_well" },
    ];
    expect(await syncOnce(db, 50, server.fetch)).toEqual({
      state: "done",
      sent: 1,
    });
    const left = await db.pendingReadings();
    expect(left.map((p) => p.entry.refused)).toEqual(["invalid_well"]);
  });

  it("are in the export until the registry has them", async () => {
    const db = await freshDb();
    const reading = level(13);
    await db.recordReading(reading);
    const exported = await unsyncedExport(db);
    expect(exported.records).toEqual([]);
    expect(exported.well_readings).toEqual([
      {
        reading,
        outbox: {
          id: reading.id,
          kind: "well_reading",
          record_sent: false,
          media_sent: null,
          refused: null,
        },
      },
    ]);
    const server = new FakeServer();
    server.wells.add(WELL_ID);
    await syncOnce(db, 50, server.fetch);
    expect((await unsyncedExport(db)).well_readings).toEqual([]);
  });

  it("keep the device's copy of the registry, and a store of the earlier version", async () => {
    const factory = new IDBFactory();
    // The store as the version before readings made it, with a record in its outbox.
    await new Promise<void>((resolve, reject) => {
      const request = factory.open("subphora-field", 1);
      request.onupgradeneeded = () => {
        const old = request.result;
        old.createObjectStore("observations", { keyPath: "id" }).add({ id: "a", kind: "note" });
        old.createObjectStore("media", { keyPath: "id" });
        old.createObjectStore("outbox", { keyPath: "id" }).add({
          id: "a",
          record_sent: false,
          media_sent: null,
          refused: null,
        });
      };
      request.onsuccess = () => {
        request.result.close();
        resolve();
      };
      request.onerror = () => {
        reject(request.error ?? new Error("open failed"));
      };
    });
    const db = await openFieldDb(factory);
    expect((await db.pending()).map((p) => p.observation.id)).toEqual(["a"]);
    expect(await db.registryCopy()).toBeUndefined();
    const registry: Registry = { wells: [], stamp: "0123456789abcdef" };
    await db.keepRegistry(registry, new Date("2026-11-27T07:00:00Z"));
    await db.keepRegistry({ ...registry, stamp: "fedcba9876543210" }, new Date("2026-11-27T08:00:00Z"));
    expect(await db.registryCopy()).toEqual({
      key: "registry",
      registry: { wells: [], stamp: "fedcba9876543210" },
      read_at: "2026-11-27T08:00:00.000Z",
    });
  });
});
