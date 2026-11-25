// Copyright (c) 2026 Almoon-D. All rights reserved.
// The areas selected in this browser session: the list to switch between, and how each
// area and each reading of a search is named. Kept in this tab's sessionStorage only.
import type { AreaOfInterest, Interpretation } from "../api.ts";
import { formatNumber, lookup, t } from "../i18n/index.ts";

const STORAGE_KEY = "subphora.session-areas";
// Decimals of a degree shown with a reading: 0.00001° is about a metre.
const DEGREE_DIGITS = 5;

export interface SessionAreas {
  areas: AreaOfInterest[];
  /** The index of the selected area, or -1 when none is. */
  selected: number;
}

export const EMPTY_SESSION: SessionAreas = { areas: [], selected: -1 };

/** What makes two areas the same place: their origin, name and outline. */
export function areaKey(area: AreaOfInterest): string {
  return `${area.origin}|${area.label ?? ""}|${JSON.stringify(area.geometry.coordinates)}`;
}

/** Select the area, adding it (newest last) unless it is already listed; the oldest leaves
 * a full list. */
export function withArea(session: SessionAreas, area: AreaOfInterest, limit: number): SessionAreas {
  const key = areaKey(area);
  const existing = session.areas.findIndex((listed) => areaKey(listed) === key);
  if (existing >= 0) {
    return { areas: session.areas, selected: existing };
  }
  const areas = [...session.areas, area].slice(-Math.max(1, limit));
  return { areas, selected: areas.length - 1 };
}

export function selectedArea(session: SessionAreas): AreaOfInterest | null {
  return session.areas[session.selected] ?? null;
}

/** The session's areas from sessionStorage; an empty list when there are none or the
 * browser refuses storage. */
export function loadSession(storage: Pick<Storage, "getItem"> | null = sessionStorageOrNull()): SessionAreas {
  try {
    const raw = storage?.getItem(STORAGE_KEY);
    if (!raw) {
      return EMPTY_SESSION;
    }
    const parsed = JSON.parse(raw) as Partial<SessionAreas>;
    if (!Array.isArray(parsed.areas) || typeof parsed.selected !== "number") {
      return EMPTY_SESSION;
    }
    const selected = parsed.selected < parsed.areas.length ? parsed.selected : parsed.areas.length - 1;
    return { areas: parsed.areas, selected };
  } catch {
    return EMPTY_SESSION;
  }
}

/** Keep the list for a reload of this tab; a full or refused storage only loses that. */
export function saveSession(session: SessionAreas, storage: Pick<Storage, "setItem"> | null = sessionStorageOrNull()): void {
  try {
    storage?.setItem(STORAGE_KEY, JSON.stringify(session));
  } catch {
    // Storage full or disabled: the list still lives in the page.
  }
}

function sessionStorageOrNull(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

/** The heading of an area: what it is, and its name. */
export function areaHeading(area: AreaOfInterest): string {
  if (area.origin === "cadastral") {
    return t("parcel.heading", { reference: area.label ?? "" });
  }
  const kind = lookup(`origin.${area.origin}`, area.origin);
  return area.label ? `${kind}: ${area.label}` : kind;
}

/** A reading offered as a choice: its kind, what was read, and where or in what CRS. */
export function interpretationText(reading: Interpretation): string {
  const kind = lookup(`origin.${reading.origin}`, reading.origin);
  if (reading.kind === "coordinates") {
    const crs = reading.detail ? ` (${lookup(`crs.${reading.detail}`, reading.detail)})` : "";
    const where = reading.position
      ? ` ${t("choice.position", {
          lat: formatNumber(reading.position[1], DEGREE_DIGITS),
          lon: formatNumber(reading.position[0], DEGREE_DIGITS),
        })}`
      : "";
    return `${kind} ${reading.label}${crs}${where}`;
  }
  return reading.detail ? `${kind}: ${reading.label} (${reading.detail})` : `${kind}: ${reading.label}`;
}
