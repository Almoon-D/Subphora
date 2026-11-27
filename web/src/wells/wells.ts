// Copyright (c) 2026 Almoon-D. All rights reserved.
// The owner's well registry in the browser (decision 0040): its records, the calls that
// read and change it, and the checks a well's form makes before sending it. The registry is
// private: it is asked for only from this server, never kept by the service worker.
import type { DomainValidation } from "../api.ts";

export type WellOutcome = "productive" | "dry" | "unknown";
export const OUTCOMES: readonly WellOutcome[] = ["productive", "dry", "unknown"];

export interface Well {
  id: string;
  name: string;
  longitude: number;
  latitude: number;
  depth_m: number | null;
  flow_l_s: number | null;
  outcome: WellOutcome;
  drilled_on: string | null;
  note: string | null;
}

export interface WellReading {
  id: string;
  well_id: string;
  measured_at: string;
  depth_to_water_m: number;
}

export interface WellRecord {
  well: Well;
  readings: WellReading[];
}

export interface Registry {
  wells: WellRecord[];
  stamp: string;
}

export type Change = "created" | "updated" | "unchanged" | "conflict";

export interface ImportReport {
  rows: number;
  wells: Record<Change, number>;
  readings: Record<Change, number>;
  conflict_rows: number[];
}

export interface OwnerValidation {
  validations: DomainValidation[];
  off_map: number;
  unknown_outcome: number;
}

export const WELLS_FAILURES = [
  "invalid_well",
  "invalid_csv",
  "too_large",
  "unknown_well",
  "conflict",
  "store_unavailable",
  "network",
  "unexpected",
] as const;

export type WellsFailure = (typeof WELLS_FAILURES)[number];

/** A failure with the server's detail (where a record or file is wrong, never its content). */
export interface Failed {
  ok: false;
  failure: WellsFailure;
  detail: string | null;
}

export type Answer<T> = { ok: true; body: T } | Failed;

type Fetch = typeof fetch;

const WELLS = "/api/wells";

async function ask<T>(request: () => Promise<Response>, empty = false): Promise<Answer<T>> {
  let response: Response;
  try {
    response = await request();
  } catch {
    return { ok: false, failure: "network", detail: null };
  }
  if (response.ok && empty) {
    return { ok: true, body: undefined as T };
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return { ok: false, failure: "unexpected", detail: null };
  }
  if (response.ok) {
    return { ok: true, body: body as T };
  }
  const record = typeof body === "object" && body !== null ? (body as Record<string, unknown>) : {};
  const code = record.code;
  const known = typeof code === "string" && (WELLS_FAILURES as readonly string[]).includes(code);
  return {
    ok: false,
    failure: known ? (code as WellsFailure) : "unexpected",
    detail: typeof record.detail === "string" ? record.detail : null,
  };
}

function json(method: string, body: unknown): RequestInit {
  return { method, headers: { "content-type": "application/json" }, body: JSON.stringify(body), cache: "no-store" };
}

export function fetchRegistry(fetchFn: Fetch = fetch): Promise<Answer<Registry>> {
  return ask(() => fetchFn(WELLS, { cache: "no-store" }));
}

export function saveWell(well: Well, fetchFn: Fetch = fetch): Promise<Answer<{ id: string; change: Change }>> {
  return ask(() => fetchFn(`${WELLS}/${encodeURIComponent(well.id)}`, json("PUT", well)));
}

export function deleteWell(id: string, fetchFn: Fetch = fetch): Promise<Answer<undefined>> {
  return ask(() => fetchFn(`${WELLS}/${encodeURIComponent(id)}`, { method: "DELETE" }), true);
}

export function addReading(reading: WellReading, fetchFn: Fetch = fetch): Promise<Answer<{ id: string; change: Change }>> {
  return ask(() => fetchFn(`${WELLS}/${encodeURIComponent(reading.well_id)}/readings`, json("POST", reading)));
}

export function importWells(file: Blob, fetchFn: Fetch = fetch): Promise<Answer<ImportReport>> {
  return ask(() =>
    fetchFn(`${WELLS}/import`, { method: "POST", headers: { "content-type": "text/csv" }, body: file, cache: "no-store" }),
  );
}

export function fetchOwnerValidation(fetchFn: Fetch = fetch): Promise<Answer<OwnerValidation>> {
  return ask(() => fetchFn(`${WELLS}/validation`, { cache: "no-store" }));
}

/** What the owner typed in a well's form; numbers as typed, so a decimal comma works. */
export interface WellForm {
  name: string;
  longitude: string;
  latitude: string;
  depth_m: string;
  flow_l_s: string;
  outcome: WellOutcome;
  drilled_on: string;
  note: string;
}

export type FormProblem = "name" | "position" | "depth" | "flow";

export const EMPTY_FORM: WellForm = {
  name: "",
  longitude: "",
  latitude: "",
  depth_m: "",
  flow_l_s: "",
  outcome: "unknown",
  drilled_on: "",
  note: "",
};

/** A number as typed (a decimal comma read as a point); null when blank; NaN when not one. */
export function typedNumber(text: string): number | null {
  const trimmed = text.trim();
  if (trimmed === "") {
    return null;
  }
  const value = Number(trimmed.replace(",", "."));
  return Number.isFinite(value) ? value : Number.NaN;
}

/** The well a form describes, or the first thing wrong with it (the server checks the
 * lengths its settings allow). */
export function wellFromForm(form: WellForm, id: string): { ok: true; well: Well } | { ok: false; problem: FormProblem } {
  const name = form.name.trim();
  if (name === "") {
    return { ok: false, problem: "name" };
  }
  const longitude = typedNumber(form.longitude);
  const latitude = typedNumber(form.latitude);
  if (longitude === null || latitude === null || !(Math.abs(longitude) <= 180 && Math.abs(latitude) <= 90)) {
    return { ok: false, problem: "position" };
  }
  const depth = typedNumber(form.depth_m);
  if (depth !== null && !(depth >= 0)) {
    return { ok: false, problem: "depth" };
  }
  const flow = typedNumber(form.flow_l_s);
  if (flow !== null && !(flow >= 0)) {
    return { ok: false, problem: "flow" };
  }
  const note = form.note.trim();
  return {
    ok: true,
    well: {
      id,
      name,
      longitude,
      latitude,
      depth_m: depth,
      flow_l_s: flow,
      outcome: form.outcome,
      drilled_on: form.drilled_on === "" ? null : form.drilled_on,
      note: note === "" ? null : note,
    },
  };
}

/** A form filled with a well, to correct it. */
export function formOf(well: Well): WellForm {
  const text = (value: number | null) => (value === null ? "" : String(value));
  return {
    name: well.name,
    longitude: String(well.longitude),
    latitude: String(well.latitude),
    depth_m: text(well.depth_m),
    flow_l_s: text(well.flow_l_s),
    outcome: well.outcome,
    drilled_on: well.drilled_on ?? "",
    note: well.note ?? "",
  };
}

/** A new random id for a well or a reading (the server accepts any UUID). */
export function newId(): string {
  return crypto.randomUUID();
}

/** A reading of a well at a local date and time (``datetime-local``) and depth to water. */
export function readingOf(wellId: string, localTime: string, depth: string, id: string = newId()): WellReading | null {
  const level = typedNumber(depth);
  const when = new Date(localTime);
  if (level === null || Number.isNaN(level) || localTime === "" || Number.isNaN(when.getTime())) {
    return null;
  }
  return { id, well_id: wellId, measured_at: when.toISOString(), depth_to_water_m: level };
}
