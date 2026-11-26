// Copyright (c) 2026 Almoon-D. All rights reserved.
// Field records as the server defines them (src/subphora/domain/field.py): append-only,
// with a UUIDv7 id made here, the UTC time, the position with its accuracy (or none,
// explicitly), the spot being walked to, and the kind's content.
import type { Position } from "../api.ts";
import { leg } from "./geodesy.ts";

export type ObservationKind = "note" | "photo" | "voice" | "track_point";

export interface Fix {
  longitude: number;
  latitude: number;
  accuracy_m: number;
  altitude_m: number | null;
  altitude_accuracy_m: number | null;
  heading_deg: number | null;
  speed_m_s: number | null;
  fixed_at: string;
}

/** The candidate spot the user is guided to: its detailed map's id and rank. */
export interface Target {
  area_id: string;
  rank: number;
  longitude: number;
  latitude: number;
}

export interface Media {
  content_type: string;
  size_bytes: number;
  sha256: string;
}

export interface Observation {
  id: string;
  kind: ObservationKind;
  recorded_at: string;
  position: Fix | null;
  target: Target | null;
  text: string | null;
  media: Media | null;
  track_id: string | null;
}

/** A UUID of version 7 (RFC 9562): 48 bits of Unix milliseconds, then random bits, so that
 * ids sort by the time they were made. */
export function uuidv7(now: number = Date.now(), random: Uint8Array = crypto.getRandomValues(new Uint8Array(10))): string {
  const bytes = new Uint8Array(16);
  let time = now;
  for (let index = 5; index >= 0; index -= 1) {
    bytes[index] = time % 256;
    time = Math.floor(time / 256);
  }
  bytes.set(random, 6);
  bytes[6] = ((bytes[6] ?? 0) & 0x0f) | 0x70;
  bytes[8] = ((bytes[8] ?? 0) & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

/** A fix as the Geolocation API reported it, an invalid optional value as null; none
 * when it reports no usable accuracy, since no position counts without one. */
export function fixOf(position: GeolocationPosition): Fix | null {
  const c = position.coords;
  if (!(Number.isFinite(c.accuracy) && c.accuracy > 0)) {
    return null;
  }
  const positive = (value: number | null) => (value !== null && Number.isFinite(value) && value > 0 ? value : null);
  const heading = c.heading !== null && Number.isFinite(c.heading) && c.heading >= 0 && c.heading < 360 ? c.heading : null;
  return {
    longitude: c.longitude,
    latitude: c.latitude,
    accuracy_m: c.accuracy,
    altitude_m: c.altitude !== null && Number.isFinite(c.altitude) ? c.altitude : null,
    altitude_accuracy_m: positive(c.altitudeAccuracy),
    heading_deg: heading,
    speed_m_s: c.speed !== null && Number.isFinite(c.speed) && c.speed >= 0 ? c.speed : null,
    fixed_at: new Date(position.timestamp).toISOString(),
  };
}

export const fixPosition = (fix: Fix): Position => [fix.longitude, fix.latitude];

interface Context {
  position: Fix | null;
  target: Target | null;
  now?: Date;
}

function base(kind: ObservationKind, { position, target, now = new Date() }: Context) {
  return {
    id: uuidv7(now.getTime()),
    kind,
    recorded_at: now.toISOString(),
    position,
    target,
  };
}

export function note(text: string, context: Context): Observation {
  return { ...base("note", context), text, media: null, track_id: null };
}

/** A media type without its parameters (`audio/webm;codecs=opus` is `audio/webm`). */
export function mediaType(type: string): string {
  return (type.split(";")[0] ?? "").trim().toLowerCase();
}

export async function sha256(bytes: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

export async function withMedia(
  kind: "photo" | "voice",
  bytes: ArrayBuffer,
  type: string,
  caption: string | null,
  context: Context,
): Promise<Observation> {
  const media = { content_type: mediaType(type), size_bytes: bytes.byteLength, sha256: await sha256(bytes) };
  return { ...base(kind, context), text: caption, media, track_id: null };
}

export function trackPoint(track_id: string, fix: Fix, context: Omit<Context, "position">): Observation {
  return { ...base("track_point", { ...context, position: fix }), text: null, media: null, track_id };
}

/** Whether a fix becomes the track's next point: the first one does; then once enough time
 * has passed since the last point, or the device has moved far enough from it. */
export function nextTrackPoint(last: Fix | null, fix: Fix, min_interval_s: number, min_distance_m: number): boolean {
  if (!last) {
    return true;
  }
  const elapsed_s = (Date.parse(fix.fixed_at) - Date.parse(last.fixed_at)) / 1000;
  if (elapsed_s >= min_interval_s) {
    return true;
  }
  return leg(fixPosition(last), fixPosition(fix)).distance_m >= min_distance_m;
}

/** Why a file cannot be recorded (none: it can): a type the server does not take, or a
 * file larger than it accepts. Refused here, so that nothing is kept that could never sync. */
export function mediaProblem(type: string, size: number, accepted: readonly string[], max_bytes: number): "type" | "size" | "empty" | null {
  if (size === 0) {
    return "empty";
  }
  if (!accepted.includes(mediaType(type))) {
    return "type";
  }
  return size > max_bytes ? "size" : null;
}
