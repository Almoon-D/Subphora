// Copyright (c) 2026 Almoon-D. All rights reserved.
// What the layer panel switches, and which layers draw and answer a tap at a zoom.
import type { MapConfig, Overlay } from "../api.ts";

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
}

/** The layers as the configuration starts them: the first base map, the configured states. */
export function initialLayers(config: MapConfig): MapLayers {
  const first = config.base_maps[0];
  if (!first) {
    throw new Error("the map configuration has no base map");
  }
  return {
    base: first.id,
    cadastre: { visible: config.cadastre.visible, opacity: config.cadastre.opacity },
    overlays: Object.fromEntries(config.overlays.map((o) => [o.id, { visible: o.visible, opacity: o.opacity }])),
  };
}

export function withOverlay(layers: MapLayers, id: string, change: Partial<LayerState>): MapLayers {
  const current = layers.overlays[id];
  if (!current) {
    return layers;
  }
  return { ...layers, overlays: { ...layers.overlays, [id]: { ...current, ...change } } };
}

/** Tile URLs MapLibre can fetch: the proxy's relative route made absolute. */
export function overlayTiles(overlay: Overlay, origin: string): string[] {
  return overlay.tiles.map((tile) => (tile.startsWith("/") ? `${origin}${tile}` : tile));
}

export function reachesZoom(overlay: Overlay, zoom: number): boolean {
  return zoom >= overlay.min_zoom;
}

/** The overlays a tap at `zoom` asks about: switched on, drawn there, with feature info. */
export function queryableOverlays(config: MapConfig, layers: MapLayers, zoom: number): Overlay[] {
  return config.overlays.filter(
    (o) => o.feature_info && layers.overlays[o.id]?.visible === true && reachesZoom(o, zoom),
  );
}

/** The overlays of each group, in the configuration's order. */
export function overlaysByGroup(config: MapConfig): [string, Overlay[]][] {
  return config.overlay_groups.map((group) => [group, config.overlays.filter((o) => o.group === group)]);
}

/** "id:opacity" of every overlay drawn, in drawing order: what the map applied. */
export function describeOverlays(config: MapConfig, layers: MapLayers): string {
  return config.overlays
    .filter((o) => layers.overlays[o.id]?.visible)
    .map((o) => `${o.id}:${String(layers.overlays[o.id]?.opacity ?? 0)}`)
    .join(" ");
}
