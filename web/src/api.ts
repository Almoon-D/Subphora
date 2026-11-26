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

/** How detailed and recent a layer is, as its publisher states it; null: not stated. */
export interface LayerDetail {
  scale_denominator: number | null;
  cell_m: number | null;
  edition: number | null;
}

/** A regional layer of a theme: drawn and asked only inside its areas (decision 0023). */
export interface RegionalOverlay {
  id: string;
  service_id: string;
  publisher: string;
  tiles: string[];
  proxied: boolean;
  min_zoom: number;
  /** The deepest zoom its service draws; MapLibre enlarges that level beyond it. */
  max_zoom: number;
  area_ids: string[];
  /** West, south, east, north: the box enclosing its areas. */
  bounds: [number, number, number, number];
  legend_url: string | null;
  feature_info: boolean;
  attribution: string;
  detail: LayerDetail;
}

/** One map theme: its national layer (tiles from its service, or the API's relative proxy
 * route) and the regional layers drawn over it inside their areas. */
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
  /** Whether a tap asks the API what the national layer holds. */
  feature_info: boolean;
  attribution: string;
  publisher: string;
  detail: LayerDetail;
  regional: RegionalOverlay[];
}

/** An area's official boundary, rounded to a grid shared by every area. */
export interface AreaBoundary {
  id: string;
  kind: "region" | "district";
  bbox: [number, number, number, number];
  geometry: { type: "MultiPolygon"; coordinates: Position[][][] };
  source: Provenance;
  grid_deg: number;
}

export interface MapConfig {
  initial_view: { longitude: number; latitude: number; zoom: number };
  area_padding_px: number;
  /** The zoom a selected point is shown at. */
  point_zoom: number;
  search: {
    /** The browser stops adding vertices to a drawn polygon here. */
    max_vertices: number;
    /** How many of this session's areas the panel lists. */
    session_areas: number;
  };
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

export type FallbackReason = "no_feature" | "upstream_error" | "upstream_timeout" | "boundary_unavailable";

/** The allowed fields of one theme's features under a tapped point, from the layer that
 * answered, and the regional layers asked before it that gave no answer. */
export interface FeatureInfo {
  layer_id: string;
  features: { fields: { name: string; value: string }[] }[];
  source: Provenance;
  answered_by: {
    level: "national" | "regional";
    layer_id: string;
    publisher: string;
    detail: LayerDetail;
    area_id: string | null;
  };
  fallbacks: { layer_id: string; reason: FallbackReason }[];
}

export type AoiOrigin =
  | "cadastral"
  | "sigpac_enclosure"
  | "sigpac_parcel"
  | "municipality"
  | "place"
  | "street"
  | "address"
  | "coordinates"
  | "drawn_point"
  | "drawn_polygon";

export type AoiGeometry =
  | { type: "Point"; coordinates: Position }
  | { type: "MultiPolygon"; coordinates: Position[][][] };

/** The area the rest of the app analyses, whatever found it (src/subphora/domain/aoi.py). */
export interface AreaOfInterest {
  origin: AoiOrigin;
  /** A reference, an address, typed coordinates; null for a drawn polygon. */
  label: string | null;
  geometry: AoiGeometry;
  bbox: readonly [number, number, number, number];
  centre: Position;
  centre_local: { crs: string; x: number; y: number };
  /** Null for a point. */
  area_m2: number | null;
  municipality: string | null;
  province: string;
  province_code: string;
  region_code: string;
  /** False where only the territory's box placed the point (Ceuta, Melilla). */
  land_checked: boolean;
  sources: Provenance[];
  parcel: Parcel | null;
}

/** One reading of the search text; `resolve` is the API path that returns its area. */
export interface Interpretation {
  kind: "cadastral" | "sigpac" | "coordinates" | "place";
  origin: AoiOrigin;
  label: string;
  detail: string | null;
  position: Position | null;
  resolve: string;
}

/** Why a search, a choice or a drawing gave no area: the server's codes, then the two the
 * browser adds. */
export const SEARCH_FAILURES = [
  "empty_query",
  "malformed_reference",
  "malformed_sigpac",
  "malformed_coordinates",
  "wrong_utm_zone",
  "outside_country",
  "invalid_polygon",
  "territory_not_supported",
  "not_found",
  "no_match",
  "upstream_timeout",
  "upstream_error",
  "network",
  "unexpected",
] as const;

export type SearchFailure = (typeof SEARCH_FAILURES)[number];

/** A failure, and the service it came from when one is named (`catastro-wfs-parcels`…). */
export interface Failed {
  ok: false;
  failure: SearchFailure;
  source: string | null;
}

export type SearchResult = { ok: true; interpretations: Interpretation[] } | Failed;
export type AreaResult = { ok: true; area: AreaOfInterest } | Failed;

type Fetch = typeof fetch;

function isFailure(code: unknown): code is SearchFailure {
  return typeof code === "string" && (SEARCH_FAILURES as readonly string[]).includes(code);
}

/** The body of a successful answer, or the failure it reports. Never throws. */
async function ask(request: () => Promise<Response>): Promise<{ ok: true; body: unknown } | Failed> {
  let response: Response;
  try {
    response = await request();
  } catch {
    return { ok: false, failure: "network", source: null };
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return { ok: false, failure: "unexpected", source: null };
  }
  if (response.ok) {
    return { ok: true, body };
  }
  const record = typeof body === "object" && body !== null ? (body as Record<string, unknown>) : {};
  const source = typeof record.source === "string" ? record.source : null;
  return { ok: false, failure: isFailure(record.code) ? record.code : "unexpected", source };
}

/** Every reading of what was typed. */
export async function searchText(text: string, fetchFn: Fetch = fetch): Promise<SearchResult> {
  const answer = await ask(() => fetchFn(`/api/search?${new URLSearchParams({ q: text.trim() }).toString()}`));
  if (!answer.ok) {
    return answer;
  }
  return { ok: true, interpretations: (answer.body as { interpretations: Interpretation[] }).interpretations };
}

/** The area an interpretation resolves to; only the API's own /api/aoi/ paths are asked. */
export async function resolveArea(path: string, fetchFn: Fetch = fetch): Promise<AreaResult> {
  if (!path.startsWith("/api/aoi/")) {
    return { ok: false, failure: "unexpected", source: null };
  }
  const answer = await ask(() => fetchFn(path));
  return answer.ok ? { ok: true, area: answer.body as AreaOfInterest } : answer;
}

/** A point clicked on the map while drawing one. */
export function drawnPoint(lon: number, lat: number, fetchFn: Fetch = fetch): Promise<AreaResult> {
  const query = new URLSearchParams({ crs: "OGC:CRS84", x: String(lon), y: String(lat), origin: "drawn_point" });
  return resolveArea(`/api/aoi/point?${query.toString()}`, fetchFn);
}

/** A polygon drawn on the map: its vertices, the ring closed here. */
export async function drawnPolygon(vertices: readonly Position[], fetchFn: Fetch = fetch): Promise<AreaResult> {
  const first = vertices[0];
  const ring = first ? [...vertices, first] : [];
  const answer = await ask(() =>
    fetchFn("/api/aoi/polygon", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ type: "Polygon", coordinates: [ring] }),
    }),
  );
  return answer.ok ? { ok: true, area: answer.body as AreaOfInterest } : answer;
}

export async function fetchMapConfig(fetchFn: Fetch = fetch): Promise<MapConfig> {
  const response = await fetchFn("/api/map");
  if (!response.ok) {
    throw new Error(`GET /api/map answered ${String(response.status)}`);
  }
  return (await response.json()) as MapConfig;
}

/** Why a tap on a layer got no answer: the server's codes, then the two the browser adds. */
export const INFO_FAILURES = [
  "no_feature_info",
  "upstream_timeout",
  "upstream_error",
  "network",
  "unexpected",
] as const;

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

/** An area's boundary, for drawing a regional layer inside it. Throws when it cannot. */
export async function fetchArea(areaId: string, fetchFn: Fetch = fetch): Promise<AreaBoundary> {
  const response = await fetchFn(`/api/areas/${encodeURIComponent(areaId)}`);
  if (!response.ok) {
    throw new Error(`GET /api/areas/${areaId} answered ${String(response.status)}`);
  }
  return (await response.json()) as AreaBoundary;
}

/** One class of a national layer's legend: values from `min` (inclusive) to `max`. */
export interface LegendClass {
  min: number | null;
  max: number | null;
  colour: string;
}

/** A layer of the national map: PNG tiles from the API (a relative route). */
export interface NationalLayer {
  id: string;
  variable: string;
  tiles: string[];
  min_zoom: number;
  max_zoom: number;
  tile_size: number;
  opacity: number;
  visible: boolean;
  /** "index", "confidence", "deg", "m" or "twi". */
  unit: string;
  legend: LegendClass[];
}

export interface NationalRegion {
  id: string;
  name: string;
  bbox: [number, number, number, number];
  built_at: string;
}

/** The national water-potential map; `built` is false before the first build. */
export interface NationalMap {
  /** A relative potential index until the model is calibrated: never a probability. */
  kind: "index";
  built: boolean;
  rendered_at: string | null;
  bounds: [number, number, number, number] | null;
  regions: NationalRegion[];
  layers: NationalLayer[];
  attributions: string[];
}

export async function fetchNational(fetchFn: Fetch = fetch): Promise<NationalMap> {
  const response = await fetchFn("/api/national");
  if (!response.ok) {
    throw new Error(`GET /api/national answered ${String(response.status)}`);
  }
  return (await response.json()) as NationalMap;
}

/** An input's value at a cell: a number, a category, or absent (no feature there). */
export interface InputValue {
  number: number | null;
  unit: string | null;
  at_least: boolean;
  category: string | null;
  label: string | null;
  absent: boolean;
}

export interface InputSource {
  service_id: string;
  publisher: string;
  attribution: string;
  retrieved_at: string;
  detail: LayerDetail;
  resolution_m: number | null;
}

export interface Contribution {
  criterion: string;
  weight: number;
  /** The weight renormalised over the inputs present. */
  share: number;
  value: InputValue;
  suitability: number;
  contribution: number;
  source: InputSource;
}

export interface MissingInput {
  criterion: string;
  weight: number;
  reason: "no_dataset" | "no_data";
}

export type ConfidenceLabel = "low" | "medium" | "high";

export interface Confidence {
  value: number;
  label: ConfidenceLabel;
  components: { id: string; weight: number; value: number; measured: boolean }[];
}

export type ValidationState = "validated" | "no_better_than_chance" | "not_enough_labels" | "not_validated";

export interface AucInterval {
  value: number;
  low: number;
  high: number;
  level: number;
}

/** How well the model discriminates known wells in one hydrogeological domain. */
export interface DomainValidation {
  /** A groundwater body's code, or "none" outside every body. */
  domain: string;
  label: string;
  state: ValidationState;
  design: "presence_absence" | "presence_background" | null;
  productive: number;
  dry: number;
  background: number;
  blocks: number;
  auc: AucInterval | null;
  calibration: { intercept: number; slope: number; level: number; brier_out_of_fold: number } | null;
  no_calibration: "not_validated" | "no_dry_labels" | "too_few_labels" | null;
  excluded_criteria: string[];
  labels_source: string;
  validated_at: string | null;
}

/** The calibrated probability of a productive well, only where the domain is calibrated. */
export interface Probability {
  value: number;
  low: number;
  high: number;
  level: number;
  domain: string;
}

export interface PotentialEstimate {
  /** "probability" only where the cell's domain is calibrated; the score stays the index. */
  kind: "index" | "probability";
  /** Null where no input is present: no estimate there. */
  score: number | null;
  confidence: Confidence;
  contributions: Contribution[];
  missing: MissingInput[];
  validation: DomainValidation;
  probability: Probability | null;
}

export interface CellExplanation {
  longitude: number;
  latitude: number;
  grid: string;
  region_id: string;
  region_name: string;
  cell_m: number;
  built_at: string;
  estimate: PotentialEstimate;
}

export const EXPLAIN_FAILURES = ["not_built", "outside_built_area", "unreadable", "network", "unexpected"] as const;

export type ExplainFailure = (typeof EXPLAIN_FAILURES)[number];

export type ExplainResult = { ok: true; explanation: CellExplanation } | { ok: false; failure: ExplainFailure };

/** The national map's estimate at (lon, lat), explained. Never throws. */
export async function fetchExplanation(lon: number, lat: number, fetchFn: Fetch = fetch): Promise<ExplainResult> {
  const query = new URLSearchParams({ lon: lon.toFixed(6), lat: lat.toFixed(6) });
  let response: Response;
  try {
    response = await fetchFn(`/api/national/explain?${query.toString()}`);
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
    return { ok: true, explanation: body as CellExplanation };
  }
  const code = typeof body === "object" && body !== null && "code" in body ? body.code : null;
  const known = typeof code === "string" && (EXPLAIN_FAILURES as readonly string[]).includes(code);
  return { ok: false, failure: known ? (code as ExplainFailure) : "unexpected" };
}

/** What a candidate's legal status says; "not evaluated" until the legal filter exists. */
export interface LegalStatus {
  state: "not_evaluated" | "rules_not_loaded";
  source: string;
  assessed_at: string;
  disclaimer: string;
  reason: string | null;
}

export type DepthUnknown = "not_imported" | "outside_bodies" | "no_piezometer_nearby" | "no_ground_elevation";

export interface WaterTable {
  elevation_m: number;
  low_m: number;
  high_m: number;
  body: string;
  body_label: string;
  piezometers: number;
  nearest_m: number;
}

/** The depth to water at a spot: estimated with its range and source, or unknown and why. */
export interface DepthEstimate {
  state: "estimated" | "unknown";
  reason: DepthUnknown | null;
  ground_m: number | null;
  water_table: WaterTable | null;
  depth_m: number | null;
  low_m: number | null;
  high_m: number | null;
  /** Carbonate rock (possible karst): the depth is unreliable. */
  karst: boolean;
  source: { attribution: string; file_name: string; imported_at: string; levels_from: string; levels_to: string } | null;
}

/** The drilling cost range in euros; amounts are decimal strings. */
export interface DrillingCost {
  currency: "EUR";
  low: string;
  high: string;
  drilled_low_m: string;
  drilled_high_m: string;
  per_metre_low: string;
  per_metre_high: string;
  fixed_low: string;
  fixed_high: string;
  source: string;
  priced_on: string;
}

/** A spot of the area worth a closer look, with everything that explains its score. */
export interface Candidate {
  rank: number;
  longitude: number;
  latitude: number;
  local: { crs: string; x: number; y: number };
  estimate: PotentialEstimate;
  legal: LegalStatus;
  depth: DepthEstimate;
  /** Exactly when the depth is estimated. */
  cost: DrillingCost | null;
}

export interface CriterionSummary {
  criterion: string;
  weight: number;
  mean_share: number;
  mean_contribution: number;
  /** The share of the scored cells where the input is present. */
  present_share: number;
  source: InputSource;
}

/** The area's mean index and confidence, and what forms them. */
export interface AreaSummary {
  kind: "index";
  cells: number;
  scored_cells: number;
  mean_index: number | null;
  mean_confidence: Confidence | null;
  contributions: CriterionSummary[];
  missing: MissingInput[];
  /** The validation of each hydrogeological domain with a cell in the area. */
  validation: DomainValidation[];
}

export interface AreaAnalysis {
  id: string;
  label: string | null;
  crs: string;
  cell_m: number;
  /** West, south, east, north: where the layers' images lie. */
  bbox: [number, number, number, number];
  area_m2: number;
  built_at: string;
  layers: string[];
  summary: AreaSummary;
  candidates: Candidate[];
  no_candidates: "no_score" | "low_confidence" | null;
  sources: Record<string, InputSource>;
  terrain_model: string;
}

export type JobState = "queued" | "running" | "done" | "failed";

export const PARCEL_FAILURES = [
  "invalid_area",
  "too_large",
  "outside_coverage",
  "unknown_job",
  "not_ready",
  "outside_grid",
  "unknown_layer",
  "upstream_error",
  "upstream_timeout",
  "computing_failed",
  "unreadable",
  "network",
  "unexpected",
] as const;

export type ParcelFailure = (typeof PARCEL_FAILURES)[number];

export interface ParcelJob {
  id: string;
  state: JobState;
  failure: ParcelFailure | null;
  detail: string | null;
  /** When to ask again while the job is queued or running. */
  poll_after_s: number;
  analysis: AreaAnalysis | null;
}

/** A layer of the detailed map: one image over the area (a relative route). */
export interface ParcelLayer {
  id: string;
  variable: string;
  image: string;
  opacity: number;
  visible: boolean;
  unit: string;
  legend: LegendClass[];
}

export interface ParcelAnswer {
  job: ParcelJob;
  layers: ParcelLayer[];
}

export type ParcelResult = { ok: true; answer: ParcelAnswer } | { ok: false; failure: ParcelFailure };

export interface ParcelExplanation {
  longitude: number;
  latitude: number;
  area_id: string;
  cell_m: number;
  built_at: string;
  estimate: PotentialEstimate;
}

export type ParcelExplainResult = { ok: true; explanation: ParcelExplanation } | { ok: false; failure: ParcelFailure };

/** The body of an answer of /api/parcel, or its failure code. Never throws. */
async function askParcel(request: () => Promise<Response>): Promise<{ ok: true; body: unknown } | { ok: false; failure: ParcelFailure }> {
  let response: Response;
  try {
    response = await request();
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
    return { ok: true, body };
  }
  const code = typeof body === "object" && body !== null && "code" in body ? body.code : null;
  const known = typeof code === "string" && (PARCEL_FAILURES as readonly string[]).includes(code);
  return { ok: false, failure: known ? (code as ParcelFailure) : "unexpected" };
}

/** Start (or find) the detailed map of an area. */
export async function startParcel(area: AreaOfInterest, fetchFn: Fetch = fetch): Promise<ParcelResult> {
  const answer = await askParcel(() =>
    fetchFn("/api/parcel", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(area),
    }),
  );
  return answer.ok ? { ok: true, answer: answer.body as ParcelAnswer } : answer;
}

/** The job of a detailed map, as it stands. */
export async function fetchParcel(id: string, fetchFn: Fetch = fetch): Promise<ParcelResult> {
  const answer = await askParcel(() => fetchFn(`/api/parcel/${encodeURIComponent(id)}`));
  return answer.ok ? { ok: true, answer: answer.body as ParcelAnswer } : answer;
}

/** The detailed map's estimate at (lon, lat), explained. */
export async function fetchParcelExplanation(
  id: string,
  lon: number,
  lat: number,
  fetchFn: Fetch = fetch,
): Promise<ParcelExplainResult> {
  const query = new URLSearchParams({ lon: lon.toFixed(7), lat: lat.toFixed(7) });
  const answer = await askParcel(() => fetchFn(`/api/parcel/${encodeURIComponent(id)}/explain?${query.toString()}`));
  return answer.ok ? { ok: true, explanation: answer.body as ParcelExplanation } : answer;
}
