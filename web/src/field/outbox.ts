// Copyright (c) 2026 Almoon-D. All rights reserved.
// The outbox (MASTER_PLAN §4.7): sends the device's unsent records in batches, then each
// file after its record, to the server's idempotent endpoints. A record the server
// already holds comes back as a duplicate and counts as sent, so a sync retried after a
// cut connection or a reload never duplicates anything. A refusal is kept with its reason;
// a network failure or a server error stops the round, to be tried again later.
import type { FieldDb, Pending } from "./db.ts";
import type { Observation } from "./records.ts";

export type SyncState = "done" | "offline" | "server_error";

export interface SyncReport {
  state: SyncState;
  /** Records and files the server took (or already had) in this round. */
  sent: number;
}

type Outcome = "created" | "duplicate" | "conflict";

const RECORDS = "/api/field/observations";
const mediaPath = (id: string) => `${RECORDS}/${id}/media`;

class Stop extends Error {
  readonly state: SyncState;

  constructor(state: SyncState) {
    super(state);
    this.state = state;
  }
}

async function ask(fetcher: typeof fetch, url: string, init: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetcher(url, init);
  } catch {
    throw new Stop("offline");
  }
  if (response.status >= 500) {
    throw new Stop("server_error");
  }
  return response;
}

async function code(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { code?: unknown };
    return typeof body.code === "string" ? body.code : `http_${String(response.status)}`;
  } catch {
    return `http_${String(response.status)}`;
  }
}

async function postRecords(fetcher: typeof fetch, records: Observation[]): Promise<Response> {
  return ask(fetcher, RECORDS, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ observations: records }),
  });
}

/** Send records in one request; a refused batch is sent again one record at a time, so
 * that only the record the server refuses is marked, with its reason. Returns the ids the
 * server took (or already had). */
async function sendRecords(db: FieldDb, fetcher: typeof fetch, batch: Pending[]): Promise<string[]> {
  const response = await postRecords(
    fetcher,
    batch.map((p) => p.observation),
  );
  if (!response.ok) {
    if (batch.length > 1) {
      const sent: string[] = [];
      for (const one of batch) {
        sent.push(...(await sendRecords(db, fetcher, [one])));
      }
      return sent;
    }
    const [only] = batch;
    if (only) {
      await db.markRefused(only.entry.id, await code(response));
    }
    return [];
  }
  const { results } = (await response.json()) as { results: { id: string; outcome: Outcome }[] };
  const sent: string[] = [];
  for (const { id, outcome } of results) {
    if (outcome === "conflict") {
      await db.markRefused(id, "conflict");
    } else {
      await db.markRecordSent(id);
      sent.push(id);
    }
  }
  return sent;
}

type MediaOutcome = "sent" | "refused" | "resend";

async function sendMedia(db: FieldDb, fetcher: typeof fetch, id: string): Promise<MediaOutcome> {
  const media = await db.media(id);
  if (!media) {
    await db.markRefused(id, "media_missing");
    return "refused";
  }
  const response = await ask(fetcher, mediaPath(id), {
    method: "PUT",
    headers: { "Content-Type": media.type },
    body: media.bytes,
  });
  if (response.ok) {
    await db.markMediaSent(id);
    return "sent";
  }
  const reason = await code(response);
  if (reason === "unknown_observation") {
    await db.markRecordUnsent(id);
    return "resend";
  }
  await db.markRefused(id, reason);
  return "refused";
}

/** One round: every unsent record in batches, then every unsent file, until nothing is
 * left that the server has not refused, or the network or the server fails. Every pass
 * moves each entry it tries on (sent, refused, or its record back once to send again),
 * or leaves it for the next round, so a round always ends. */
export async function syncOnce(db: FieldDb, batchSize: number, fetcher: typeof fetch = fetch): Promise<SyncReport> {
  let sent = 0;
  // Entries not to try again in this round, and those whose record was put back once.
  const later = new Set<string>();
  const resent = new Set<string>();
  try {
    for (;;) {
      const waiting = (await db.pending()).filter((p) => p.entry.refused === null && !later.has(p.entry.id));
      const records = waiting.filter((p) => !p.entry.record_sent).slice(0, batchSize);
      const files = waiting.filter((p) => p.entry.record_sent && p.entry.media_sent === false);
      if (records.length === 0 && files.length === 0) {
        return { state: "done", sent };
      }
      if (records.length > 0) {
        const taken = new Set(await sendRecords(db, fetcher, records));
        sent += taken.size;
        // An answer that leaves a record out: it waits for the next round.
        for (const record of records) {
          if (!taken.has(record.entry.id)) {
            later.add(record.entry.id);
          }
        }
      }
      for (const file of files) {
        const outcome = await sendMedia(db, fetcher, file.entry.id);
        if (outcome === "sent") {
          sent += 1;
        } else if (outcome === "resend") {
          if (resent.has(file.entry.id)) {
            later.add(file.entry.id);
          }
          resent.add(file.entry.id);
        }
      }
    }
  } catch (error) {
    if (error instanceof Stop) {
      return { state: error.state, sent };
    }
    throw error;
  }
}
