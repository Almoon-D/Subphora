// Copyright (c) 2026 Almoon-D. All rights reserved.
// The API's answers, as the server defines them (src/subphora/api/), and how to ask.

export type Position = readonly [number, number];

export interface Provenance {
  service_id: string;
  publisher: string;
  attribution: string;
  retrieved_at: string;
}

export interface Parcel {
  reference: string;
  area_m2: number;
  municipality: string;
  province: string;
  province_code: string;
  region_code: string;
  geometry: { type: "MultiPolygon"; coordinates: Position[][][] };
  bbox: readonly [number, number, number, number];
  reference_point: Position;
  reference_point_local: { crs: string; x: number; y: number };
  sources: Provenance[];
}

export interface BaseMap {
  id: string;
  service_id: string;
  tiles: string[];
  tile_size: number;
  max_zoom: number;
  attribution: string;
}

/** An official layer: tiles from its service, or the API's relative proxy route. */
export interface Overlay {
  id: string;
  group: string;
  service_id: string;
  tiles: string[];
  proxied: boolean;
  tile_size: number;
  min_zoom: number;
  max_zoom: number;
  opacity: number;
  visible: boolean;
  /** Null: the service has no legend a person can read. */
  legend_url: string | null;
  /** Whether a tap asks the API what lies under it. */
  feature_info: boolean;
  attribution: string;
}

export interface MapConfig {
  initial_view: { longitude: number; latitude: number; zoom: number };
  parcel_padding_px: number;
  /** The first is the default. */
  base_maps: BaseMap[];
  cadastre: {
    service_id: string;
    url: string;
    params: Record<string, string>;
    min_zoom: number;
    refresh_delay_ms: number;
    max_image_px: number;
    attribution: string;
    visible: boolean;
    opacity: number;
  };
  overlay_groups: string[];
  overlays: Overlay[];
}

/** The allowed fields of one layer's features under a tapped point. */
export interface FeatureInfo {
  layer_id: string;
  features: { fields: { name: string; value: string }[] }[];
  source: Provenance;
}

/** Why a lookup failed: the server's codes, then the two the browser adds. */
export const LOOKUP_FAILURES = [
  "malformed_reference",
  "territory_not_supported",
  "parcel_not_found",
  "upstream_timeout",
  "upstream_error",
  "network",
  "unexpected",
] as const;

export type LookupFailure = (typeof LOOKUP_FAILURES)[number];

export type ParcelResult = { ok: true; parcel: Parcel } | { ok: false; failure: LookupFailure };

type Fetch = typeof fetch;

function isFailure(code: unknown): code is LookupFailure {
  return typeof code === "string" && (LOOKUP_FAILURES as readonly string[]).includes(code);
}

/** The parcel with this reference, or why there is none. Never throws. */
export async function fetchParcel(reference: string, fetchFn: Fetch = fetch): Promise<ParcelResult> {
  let response: Response;
  try {
    response = await fetchFn(`/api/parcels/${encodeURIComponent(reference.trim())}`);
  } catch {
    return { ok: false, failure: "network" };
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return { ok: false, failure: "unexpected" };
  }
  if (response.ok) {
    return { ok: true, parcel: body as Parcel };
  }
  const code = typeof body === "object" && body !== null && "code" in body ? body.code : null;
  return { ok: false, failure: isFailure(code) ? code : "unexpected" };
}

export async function fetchMapConfig(fetchFn: Fetch = fetch): Promise<MapConfig> {
  const response = await fetchFn("/api/map");
  if (!response.ok) {
    throw new Error(`GET /api/map answered ${String(response.status)}`);
  }
  return (await response.json()) as MapConfig;
}

/** Why a tap on a layer got no answer: the server's codes, then the two the browser adds. */
export const INFO_FAILURES = ["upstream_timeout", "upstream_error", "network", "unexpected"] as const;

export type InfoFailure = (typeof INFO_FAILURES)[number];

export type InfoResult =
  | { ok: true; layerId: string; info: FeatureInfo }
  | { ok: false; layerId: string; failure: InfoFailure };

function isInfoFailure(code: unknown): code is InfoFailure {
  return typeof code === "string" && (INFO_FAILURES as readonly string[]).includes(code);
}

/** What the layer has at (lon, lat), asked at the map's zoom. Never throws. */
export async function fetchFeatureInfo(
  layerId: string,
  lon: number,
  lat: number,
  zoom: number,
  fetchFn: Fetch = fetch,
): Promise<InfoResult> {
  const query = new URLSearchParams({ lon: lon.toFixed(6), lat: lat.toFixed(6), zoom: zoom.toFixed(2) });
  let response: Response;
  try {
    response = await fetchFn(`/api/layers/${encodeURIComponent(layerId)}/info?${query.toString()}`);
  } catch {
    return { ok: false, layerId, failure: "network" };
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return { ok: false, layerId, failure: "unexpected" };
  }
  if (response.ok) {
    return { ok: true, layerId, info: body as FeatureInfo };
  }
  const code = typeof body === "object" && body !== null && "code" in body ? body.code : null;
  return { ok: false, layerId, failure: isInfoFailure(code) ? code : "unexpected" };
}
