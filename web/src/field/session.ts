// Copyright (c) 2026 Almoon-D. All rights reserved.
// Whether field mode is on and the spot being walked to, kept for a reload of this tab
// (sessionStorage, like the session's areas). The records themselves live in IndexedDB.
import type { Target } from "./records.ts";

const STORAGE_KEY = "subphora.field";

export interface FieldSession {
  on: boolean;
  target: Target | null;
}

export const NO_FIELD: FieldSession = { on: false, target: null };

function isTarget(value: unknown): value is Target {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const t = value as Record<string, unknown>;
  return (
    typeof t.area_id === "string" &&
    typeof t.rank === "number" &&
    typeof t.longitude === "number" &&
    typeof t.latitude === "number"
  );
}

/** The tab's field session; field mode off when there is none or it cannot be read. */
export function loadFieldSession(storage: Pick<Storage, "getItem"> | null = sessionStorageOrNull()): FieldSession {
  try {
    const raw = storage?.getItem(STORAGE_KEY);
    if (!raw) {
      return NO_FIELD;
    }
    const parsed = JSON.parse(raw) as { on?: unknown; target?: unknown };
    return { on: parsed.on === true, target: isTarget(parsed.target) ? parsed.target : null };
  } catch {
    return NO_FIELD;
  }
}

export function saveFieldSession(session: FieldSession, storage: Pick<Storage, "setItem"> | null = sessionStorageOrNull()): void {
  try {
    storage?.setItem(STORAGE_KEY, JSON.stringify(session));
  } catch {
    // Storage full or disabled: field mode still works in the page.
  }
}

function sessionStorageOrNull(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}
