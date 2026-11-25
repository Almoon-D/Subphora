// Copyright (c) 2026 Almoon-D. All rights reserved.
// What the layer panel switches, and which layers draw and answer a tap at a zoom. A
// theme's regional layers follow its switch and opacity: one panel entry per theme.
import type { LayerDetail, MapConfig, NationalMap, Overlay, RegionalOverlay } from "../api.ts";

export interface LayerState {
  visible: boolean;
  /** 0…1 */
  opacity: number;
}

export interface MapLayers {
  /** The id of the base map shown. */
  base: string;
  cadastre: LayerState;
  overlays: Record<string, LayerState>;
  /** The national map's layers (none when it could not be read). */
  national: Record<string, LayerState>;
}

/** The layers as the configuration starts them: the first base map, the configured states. */
export function initialLayers(config: MapConfig, national: NationalMap | null = null): MapLayers {
  const first = config.base_maps[0];
  if (!first) {
    throw new Error("the map configuration has no base map");
  }
  return {
    base: first.id,
    cadastre: { visible: config.cadastre.visible, opacity: config.cadastre.opacity },
    overlays: Object.fromEntries(config.overlays.map((o) => [o.id, { visible: o.visible, opacity: o.opacity }])),
    national: Object.fromEntries((national?.layers ?? []).map((l) => [l.id, { visible: l.visible, opacity: l.opacity }])),
  };
}

export function withNational(layers: MapLayers, id: string, change: Partial<LayerState>): MapLayers {
  const current = layers.national[id];
  if (!current) {
    return layers;
  }
  return { ...layers, national: { ...layers.national, [id]: { ...current, ...change } } };
}

export function withOverlay(layers: MapLayers, id: string, change: Partial<LayerState>): MapLayers {
  const current = layers.overlays[id];
  if (!current) {
    return layers;
  }
  return { ...layers, overlays: { ...layers.overlays, [id]: { ...current, ...change } } };
}

/** Tile URLs MapLibre can fetch: the proxy's relative route made absolute. */
export function overlayTiles(overlay: Pick<Overlay, "tiles">, origin: string): string[] {
  return overlay.tiles.map((tile) => (tile.startsWith("/") ? `${origin}${tile}` : tile));
}

export function reachesZoom(overlay: Pick<Overlay, "min_zoom">, zoom: number): boolean {
  return zoom >= overlay.min_zoom;
}

function inBounds(regional: RegionalOverlay, lon: number, lat: number): boolean {
  const [west, south, east, north] = regional.bounds;
  return west <= lon && lon <= east && south <= lat && lat <= north;
}

/** Whether a tap at (lon, lat, zoom) can be answered for the theme: by its national layer,
 * or by a regional one whose bounds hold the point (the API decides which, exactly). */
export function answersTap(overlay: Overlay, lon: number, lat: number, zoom: number): boolean {
  if (overlay.feature_info && reachesZoom(overlay, zoom)) {
    return true;
  }
  return overlay.regional.some((r) => r.feature_info && reachesZoom(r, zoom) && inBounds(r, lon, lat));
}

/** The themes a tap asks about: switched on and able to answer there. */
export function queryableOverlays(config: MapConfig, layers: MapLayers, lon: number, lat: number, zoom: number): Overlay[] {
  return config.overlays.filter((o) => layers.overlays[o.id]?.visible === true && answersTap(o, lon, lat, zoom));
}

/** "1:25.000", "celdas de 250 m" or null when the publisher states neither. */
export function scaleOf(detail: LayerDetail): { kind: "scale" | "cell"; value: number } | null {
  if (detail.scale_denominator !== null) {
    return { kind: "scale", value: detail.scale_denominator };
  }
  if (detail.cell_m !== null) {
    return { kind: "cell", value: detail.cell_m };
  }
  return null;
}

/** The overlays of each group, in the configuration's order. */
export function overlaysByGroup(config: MapConfig): [string, Overlay[]][] {
  return config.overlay_groups.map((group) => [group, config.overlays.filter((o) => o.group === group)]);
}

/** The ids of the regional layers drawn, in drawing order: what the map applied. */
export function describeRegional(config: MapConfig, layers: MapLayers): string {
  return config.overlays
    .filter((o) => layers.overlays[o.id]?.visible)
    .flatMap((o) => o.regional.map((r) => r.id))
    .join(" ");
}

/** "id:opacity" of every overlay drawn, in drawing order: what the map applied. */
export function describeOverlays(config: MapConfig, layers: MapLayers): string {
  return config.overlays
    .filter((o) => layers.overlays[o.id]?.visible)
    .map((o) => `${o.id}:${String(layers.overlays[o.id]?.opacity ?? 0)}`)
    .join(" ");
}
