// Copyright (c) 2026 Almoon-D. All rights reserved.
// The manual export (MASTER_PLAN §4.7): every record not yet wholly on the server, with
// its file, in one JSON file the user keeps, so that no field data depends on the sync.
import type { FieldDb, OutboxEntry } from "./db.ts";
import type { Observation } from "./records.ts";

export const EXPORT_FORMAT = "subphora-field-export";
export const EXPORT_VERSION = 1;

export interface ExportedRecord {
  observation: Observation;
  outbox: OutboxEntry;
  /** The file in base64, with its type; null when the record has none. */
  media: { type: string; base64: string } | null;
}

export interface FieldExport {
  format: typeof EXPORT_FORMAT;
  version: typeof EXPORT_VERSION;
  exported_at: string;
  records: ExportedRecord[];
}

export function base64(bytes: ArrayBuffer): string {
  const view = new Uint8Array(bytes);
  // In slices: String.fromCharCode takes a bounded number of arguments.
  const slice = 0x8000;
  let binary = "";
  for (let start = 0; start < view.length; start += slice) {
    binary += String.fromCharCode(...view.subarray(start, start + slice));
  }
  return btoa(binary);
}

export async function unsyncedExport(db: FieldDb, now: Date = new Date()): Promise<FieldExport> {
  const records: ExportedRecord[] = [];
  for (const { entry, observation } of await db.pending()) {
    const media = observation.media ? await db.media(observation.id) : undefined;
    records.push({
      observation,
      outbox: entry,
      media: media ? { type: media.type, base64: base64(media.bytes) } : null,
    });
  }
  return { format: EXPORT_FORMAT, version: EXPORT_VERSION, exported_at: now.toISOString(), records };
}

/** The file's name: the moment of the export, in the viewer's own time. */
export function exportName(now: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  const date = `${String(now.getFullYear())}${pad(now.getMonth() + 1)}${pad(now.getDate())}`;
  return `subphora-campo-${date}-${pad(now.getHours())}${pad(now.getMinutes())}.json`;
}

/** Hand the export to the browser as a download. */
export function download(data: FieldExport, now: Date = new Date()): void {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = exportName(now);
  document.body.append(link);
  link.click();
  link.remove();
  // The download has started from the URL; let the click finish before releasing it.
  setTimeout(() => {
    URL.revokeObjectURL(url);
  }, 0);
}
