// Copyright (c) 2026 Almoon-D. All rights reserved.
// The map: a base map (PNOA or the IGN maps), the official layers as tiles (each theme's
// regional layers clipped to their areas over its national one), Catastro's parcels as one
// image per view, the selected area's detailed map (one image of its chosen layer, and its
// numbered candidate spots), the selected area on top (an outline or a point), and what is
// being drawn.
import type { Feature, FeatureCollection } from "geojson";
import {
  addProtocol,
  type GeoJSONSource,
  type ImageSource,
  type LayerSpecification,
  type RasterSourceSpecification,
  type StyleSpecification,
  Map as MaplibreMap,
  Marker,
  MercatorCoordinate,
  NavigationControl,
  removeProtocol,
  setWorkerUrl,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import { useEffect, useRef, useState } from "react";

import {
  type AreaAnalysis,
  type AreaBoundary,
  type AreaOfInterest,
  fetchArea,
  type MapConfig,
  type NationalMap,
  type ParcelLayer,
  type Position,
} from "../api.ts";
import { lookup, t } from "../i18n/index.ts";
import { describeParcel } from "../parcel/parcel.ts";
import { areaHeading } from "../search/areas.ts";
import { cadastreImageUrl, cadastreVisible, imageSize, type MercatorBox } from "./cadastre.ts";
import { CLIP_PROTOCOL, clipHandler, clipTemplate } from "./clip.ts";
import { describeOverlays, describeRegional, type MapLayers, overlayTiles } from "./layers.ts";
import { describeNational } from "./national.ts";

// MapLibre finds its worker next to its own module, which bundling moves: name it.
setWorkerUrl(workerUrl);

// Half the width of the EPSG:3857 world, in metres: MapLibre's mercator units are 0…1.
const WEB_MERCATOR_HALF_EXTENT_M = 20037508.342789244;
const baseId = (id: string) => `base-${id}`;
const overlayId = (id: string) => `overlay-${id}`;
const regionalId = (id: string) => `regional-${id}`;
const nationalId = (id: string) => `national-${id}`;
const CADASTRE = "cadastre";
const AREA = "area";
const AREA_COLOUR = "#ffd400";
const PARCEL = "parcel";
const DRAFT = "draft";
const DRAFT_COLOUR = "#ff3b30";

/** What is being drawn: a point (the next click) or a polygon's vertices so far. */
export interface Draft {
  mode: "point" | "polygon";
  vertices: Position[];
}

/** The selected area's detailed map: its analysis and the layer drawn (none: null). */
export interface ParcelDrawing {
  analysis: AreaAnalysis;
  layer: ParcelLayer | null;
}

interface Props {
  config: MapConfig;
  /** The national map; its layers are drawn only once it is built. */
  national: NationalMap | null;
  area: AreaOfInterest | null;
  parcel: ParcelDrawing | null;
  layers: MapLayers;
  /** The last tapped point, marked on the map. */
  tapped: Position | null;
  /** While drawing, a click on the map belongs to the drawing, not to the tap. */
  draft: Draft | null;
  onZoom: (zoom: number) => void;
  onTap: (lon: number, lat: number, zoom: number) => void;
  onDraw: (lon: number, lat: number) => void;
}

const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] };

/** The drawing so far: its vertices, the line through them, and the closing side. */
function draftFeatures(draft: Draft | null): FeatureCollection {
  if (!draft || draft.vertices.length === 0) {
    return EMPTY;
  }
  const vertices = draft.vertices.map((v): [number, number] => [v[0], v[1]]);
  const features: Feature[] = vertices.map((coordinates) => ({
    type: "Feature",
    properties: {},
    geometry: { type: "Point", coordinates },
  }));
  const first = vertices[0];
  if (vertices.length > 1 && first) {
    const line = vertices.length > 2 ? [...vertices, first] : vertices;
    features.push({ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: line } });
  }
  return { type: "FeatureCollection", features };
}

function areaFeature(area: AreaOfInterest | null): FeatureCollection {
  if (!area) {
    return EMPTY;
  }
  const geometry =
    area.geometry.type === "Point"
      ? { type: "Point" as const, coordinates: [area.geometry.coordinates[0], area.geometry.coordinates[1]] }
      : {
          type: "MultiPolygon" as const,
          coordinates: area.geometry.coordinates.map((polygon) => polygon.map((ring) => ring.map((p) => [p[0], p[1]]))),
        };
  return { type: "FeatureCollection", features: [{ type: "Feature", properties: {}, geometry }] };
}

const AREA_LAYERS = [`${AREA}-fill`, `${AREA}-line`, `${AREA}-point`];

/** Show the selected area, its source credited in the map's attribution. A GeoJSON source
 * takes its attribution only when added, so the area's source is replaced each time; its
 * layers go back above the cadastre and below the drawing. */
function showArea(map: MaplibreMap, area: AreaOfInterest | null): void {
  for (const id of AREA_LAYERS) {
    if (map.getLayer(id)) {
      map.removeLayer(id);
    }
  }
  if (map.getSource(AREA)) {
    map.removeSource(AREA);
  }
  const attribution = area ? [...new Set(area.sources.map((s) => s.attribution))].join(", ") : "";
  map.addSource(AREA, { type: "geojson", data: areaFeature(area), ...(attribution ? { attribution } : {}) });
  const below = map.getLayer(`${DRAFT}-line`) ? `${DRAFT}-line` : undefined;
  map.addLayer(
    {
      id: `${AREA}-fill`,
      type: "fill",
      source: AREA,
      filter: ["==", ["geometry-type"], "Polygon"],
      paint: { "fill-color": AREA_COLOUR, "fill-opacity": 0.15 },
    },
    below,
  );
  map.addLayer(
    {
      id: `${AREA}-line`,
      type: "line",
      source: AREA,
      filter: ["==", ["geometry-type"], "Polygon"],
      paint: { "line-color": AREA_COLOUR, "line-width": 3 },
    },
    below,
  );
  map.addLayer(
    {
      id: `${AREA}-point`,
      type: "circle",
      source: AREA,
      filter: ["==", ["geometry-type"], "Point"],
      paint: { "circle-radius": 8, "circle-color": AREA_COLOUR, "circle-stroke-color": "#000", "circle-stroke-width": 2 },
    },
    below,
  );
}

/** The selected area (none yet) and the drawing, on top of every raster layer. */
function addVectorLayers(map: MaplibreMap): void {
  showArea(map, null);
  map.addSource(DRAFT, { type: "geojson", data: EMPTY });
  map.addLayer({
    id: `${DRAFT}-line`,
    type: "line",
    source: DRAFT,
    filter: ["==", ["geometry-type"], "LineString"],
    paint: { "line-color": DRAFT_COLOUR, "line-width": 2, "line-dasharray": [2, 1] },
  });
  map.addLayer({
    id: `${DRAFT}-vertex`,
    type: "circle",
    source: DRAFT,
    filter: ["==", ["geometry-type"], "Point"],
    paint: { "circle-radius": 5, "circle-color": DRAFT_COLOUR, "circle-stroke-color": "#fff", "circle-stroke-width": 2 },
  });
}

function mercatorBox(map: MaplibreMap): MercatorBox {
  const bounds = map.getBounds();
  const southWest = MercatorCoordinate.fromLngLat(bounds.getSouthWest());
  const northEast = MercatorCoordinate.fromLngLat(bounds.getNorthEast());
  const toMetres = (unit: number) => (unit - 0.5) * 2 * WEB_MERCATOR_HALF_EXTENT_M;
  return [toMetres(southWest.x), -toMetres(southWest.y), toMetres(northEast.x), -toMetres(northEast.y)];
}

function viewCorners(map: MaplibreMap): [[number, number], [number, number], [number, number], [number, number]] {
  const bounds = map.getBounds();
  const [west, south, east, north] = [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()];
  return [
    [west, north],
    [east, north],
    [east, south],
    [west, south],
  ];
}

const visibility = (visible: boolean): "visible" | "none" => (visible ? "visible" : "none");

/** Draw the chosen layer of a detailed map as one image over its box, under the area's
 * outline; none removes it. */
function showParcelLayer(map: MaplibreMap, analysis: AreaAnalysis | null, layer: ParcelLayer | null): void {
  if (map.getLayer(PARCEL)) {
    map.removeLayer(PARCEL);
  }
  if (map.getSource(PARCEL)) {
    map.removeSource(PARCEL);
  }
  if (!analysis || !layer) {
    return;
  }
  const [west, south, east, north] = analysis.bbox;
  map.addSource(PARCEL, {
    type: "image",
    url: `${window.location.origin}${layer.image}`,
    coordinates: [
      [west, north],
      [east, north],
      [east, south],
      [west, south],
    ],
  });
  map.addLayer(
    {
      id: PARCEL,
      type: "raster",
      source: PARCEL,
      paint: { "raster-opacity": layer.opacity, "raster-resampling": "nearest", "raster-fade-duration": 0 },
    },
    map.getLayer(`${AREA}-fill`) ? `${AREA}-fill` : undefined,
  );
}

/** A numbered marker per candidate spot. */
function candidateMarkers(map: MaplibreMap, analysis: AreaAnalysis | null): Marker[] {
  return (analysis?.candidates ?? []).map((candidate) => {
    const element = document.createElement("div");
    element.className = "candidate-marker";
    element.textContent = String(candidate.rank);
    element.title = t("detailed.candidate", { rank: candidate.rank });
    return new Marker({ element }).setLngLat([candidate.longitude, candidate.latitude]).addTo(map);
  });
}

/** Ask for one cadastral image of the current view, or hide the layer when off or zoomed out.
 * Returns whether the zoom allows the parcels to be drawn. */
function refreshCadastre(map: MaplibreMap, cadastre: MapConfig["cadastre"], layers: MapLayers): boolean {
  const reached = cadastreVisible(cadastre, map.getZoom());
  const visible = reached && layers.cadastre.visible;
  if (map.getLayer(CADASTRE)) {
    map.setLayoutProperty(CADASTRE, "visibility", visibility(visible));
    map.setPaintProperty(CADASTRE, "raster-opacity", layers.cadastre.opacity);
  }
  if (!visible) {
    return reached;
  }
  const canvas = map.getCanvas();
  const size = imageSize(canvas.clientWidth, canvas.clientHeight, window.devicePixelRatio, cadastre.max_image_px);
  const url = cadastreImageUrl(cadastre, mercatorBox(map), size);
  const coordinates = viewCorners(map);
  const source = map.getSource<ImageSource>(CADASTRE);
  if (source) {
    source.updateImage({ url, coordinates });
  } else {
    map.addSource(CADASTRE, { type: "image", url, coordinates });
    map.addLayer(
      {
        id: CADASTRE,
        type: "raster",
        source: CADASTRE,
        paint: { "raster-fade-duration": 0, "raster-opacity": layers.cadastre.opacity },
      },
      map.getLayer(`${AREA}-fill`) ? `${AREA}-fill` : undefined,
    );
  }
  return true;
}

/** The national layers drawn by the map: none until the map is built. */
function drawnNational(national: NationalMap | null): NationalMap["layers"] {
  return national?.built ? national.layers : [];
}

/** Apply the panel's choices to the map's layers. */
function applyLayers(map: MaplibreMap, config: MapConfig, national: NationalMap | null, layers: MapLayers): void {
  for (const layer of drawnNational(national)) {
    const state = layers.national[layer.id];
    map.setLayoutProperty(nationalId(layer.id), "visibility", visibility(state?.visible === true));
    map.setPaintProperty(nationalId(layer.id), "raster-opacity", state?.opacity ?? layer.opacity);
  }
  for (const base of config.base_maps) {
    map.setLayoutProperty(baseId(base.id), "visibility", visibility(base.id === layers.base));
  }
  for (const overlay of config.overlays) {
    const state = layers.overlays[overlay.id];
    for (const id of [overlayId(overlay.id), ...overlay.regional.map((r) => regionalId(r.id))]) {
      map.setLayoutProperty(id, "visibility", visibility(state?.visible === true));
      map.setPaintProperty(id, "raster-opacity", state?.opacity ?? overlay.opacity);
    }
  }
  if (map.getLayer(CADASTRE)) {
    map.setPaintProperty(CADASTRE, "raster-opacity", layers.cadastre.opacity);
  }
}

function initialStyle(config: MapConfig, national: NationalMap | null, layers: MapLayers): StyleSpecification {
  const origin = window.location.origin;
  const sources: Record<string, RasterSourceSpecification> = {};
  const nationalAttribution = national ? national.attributions.join(", ") : "";
  for (const layer of drawnNational(national)) {
    sources[nationalId(layer.id)] = {
      type: "raster",
      tiles: overlayTiles(layer, origin),
      tileSize: layer.tile_size,
      minzoom: layer.min_zoom,
      maxzoom: layer.max_zoom,
      // Tiles outside the regions built are never requested.
      ...(national?.bounds ? { bounds: national.bounds } : {}),
      attribution: nationalAttribution,
    };
  }
  for (const base of config.base_maps) {
    sources[baseId(base.id)] = {
      type: "raster",
      tiles: base.tiles,
      tileSize: base.tile_size,
      maxzoom: base.max_zoom,
      attribution: base.attribution,
    };
  }
  for (const overlay of config.overlays) {
    sources[overlayId(overlay.id)] = {
      type: "raster",
      tiles: overlayTiles(overlay, origin),
      tileSize: overlay.tile_size,
      minzoom: overlay.min_zoom,
      maxzoom: overlay.max_zoom,
      attribution: overlay.attribution,
    };
    for (const regional of overlay.regional) {
      sources[regionalId(regional.id)] = {
        type: "raster",
        tiles: overlayTiles(regional, origin).map((tile) => clipTemplate(regional.area_ids, overlay.tile_size, tile)),
        tileSize: overlay.tile_size,
        minzoom: regional.min_zoom,
        maxzoom: regional.max_zoom,
        // Tiles outside the areas' box are never requested.
        bounds: regional.bounds,
        attribution: regional.attribution,
      };
    }
  }
  const styleLayers: LayerSpecification[] = [
    ...config.base_maps.map(
      (base): LayerSpecification => ({
        id: baseId(base.id),
        type: "raster",
        source: baseId(base.id),
        layout: { visibility: visibility(base.id === layers.base) },
      }),
    ),
    // The national map over the base map and under the official layers.
    ...drawnNational(national).map(
      (layer): LayerSpecification => ({
        id: nationalId(layer.id),
        type: "raster",
        source: nationalId(layer.id),
        layout: { visibility: visibility(layers.national[layer.id]?.visible === true) },
        paint: { "raster-opacity": layers.national[layer.id]?.opacity ?? layer.opacity, "raster-resampling": "nearest" },
      }),
    ),
    ...config.overlays.flatMap((overlay): LayerSpecification[] => {
      const state = layers.overlays[overlay.id];
      const layout = { visibility: visibility(state?.visible === true) };
      const paint = { "raster-opacity": state?.opacity ?? overlay.opacity };
      // The national layer, then its regional layers right above it.
      return [
        { id: overlayId(overlay.id), type: "raster", source: overlayId(overlay.id), minzoom: overlay.min_zoom, layout, paint },
        ...overlay.regional.map(
          (r): LayerSpecification => ({
            id: regionalId(r.id),
            type: "raster",
            source: regionalId(r.id),
            minzoom: r.min_zoom,
            layout,
            paint,
          }),
        ),
      ];
    }),
  ];
  return { version: 8, sources, layers: styleLayers };
}

export function MapView({ config, national, area, parcel, layers, tapped, draft, onZoom, onTap, onDraw }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MaplibreMap | null>(null);
  const markerRef = useRef<Marker | null>(null);
  const candidatesRef = useRef<Marker[]>([]);
  // The handlers registered once read the latest choices and callbacks through these.
  const layersRef = useRef(layers);
  const onZoomRef = useRef(onZoom);
  const onTapRef = useRef(onTap);
  const onDrawRef = useRef(onDraw);
  const drawingRef = useRef(draft !== null);
  const [loaded, setLoaded] = useState(false);
  const [cadastreReached, setCadastreReached] = useState(false);
  // Areas whose boundary could not be read: their regional layers are not drawn.
  const [missingAreas, setMissingAreas] = useState<string[]>([]);

  // Regional tiles are clipped to their areas; each boundary is read once per page, and a
  // boundary that failed is not asked again for every tile (a reload asks again).
  useEffect(() => {
    const boundaries = new Map<string, Promise<AreaBoundary>>();
    const loadArea = (areaId: string): Promise<AreaBoundary> => {
      let boundary = boundaries.get(areaId);
      if (!boundary) {
        boundary = fetchArea(areaId).catch((error: unknown) => {
          setMissingAreas((areas) => (areas.includes(areaId) ? areas : [...areas, areaId]));
          throw error;
        });
        boundaries.set(areaId, boundary);
      }
      return boundary;
    };
    addProtocol(CLIP_PROTOCOL, clipHandler(loadArea));
    return () => {
      removeProtocol(CLIP_PROTOCOL);
    };
  }, []);

  useEffect(() => {
    layersRef.current = layers;
    onZoomRef.current = onZoom;
    onTapRef.current = onTap;
    onDrawRef.current = onDraw;
    drawingRef.current = draft !== null;
  });

  useEffect(() => {
    if (!container.current) {
      return;
    }
    const { cadastre, initial_view: view } = config;
    const map = new MaplibreMap({
      container: container.current,
      center: [view.longitude, view.latitude],
      zoom: view.zoom,
      // An untiled image is drawn north-up: no rotation or tilt.
      dragRotate: false,
      pitchWithRotate: false,
      touchPitch: false,
      // An image source carries no attribution of its own: the control names Catastro.
      attributionControl: { compact: false, customAttribution: cadastre.attribution },
      style: initialStyle(config, national, layersRef.current),
    });
    map.touchZoomRotate.disableRotation();
    map.keyboard.disableRotation();
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    mapRef.current = map;

    let timer: ReturnType<typeof setTimeout> | undefined;
    map.on("movestart", () => {
      clearTimeout(timer);
    });
    map.on("moveend", () => {
      clearTimeout(timer);
      onZoomRef.current(map.getZoom());
      timer = setTimeout(() => {
        setCadastreReached(refreshCadastre(map, cadastre, layersRef.current));
      }, cadastre.refresh_delay_ms);
    });
    map.on("click", (event) => {
      if (drawingRef.current) {
        onDrawRef.current(event.lngLat.lng, event.lngLat.lat);
      } else {
        onTapRef.current(event.lngLat.lng, event.lngLat.lat, map.getZoom());
      }
    });
    map.on("load", () => {
      addVectorLayers(map);
      setLoaded(true);
      onZoomRef.current(map.getZoom());
      setCadastreReached(refreshCadastre(map, cadastre, layersRef.current));
    });
    return () => {
      clearTimeout(timer);
      mapRef.current = null;
      map.remove();
    };
  }, [config, national]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded) {
      return;
    }
    applyLayers(map, config, national, layers);
  }, [layers, loaded, config, national]);

  // Only switching the cadastre on or off asks Catastro for an image; opacity does not.
  const cadastreOn = layers.cadastre.visible;
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded) {
      return;
    }
    setCadastreReached(refreshCadastre(map, config.cadastre, layersRef.current));
  }, [cadastreOn, loaded, config]);

  useEffect(() => {
    const map = mapRef.current;
    markerRef.current?.remove();
    markerRef.current = map && tapped ? new Marker().setLngLat([tapped[0], tapped[1]]).addTo(map) : null;
  }, [tapped, loaded]);

  // The drawing: its vertices on the map, a crosshair, and no zoom on a double click.
  const drawing = draft !== null;
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded) {
      return;
    }
    void map.getSource<GeoJSONSource>(DRAFT)?.setData(draftFeatures(draft));
    map.getCanvas().style.cursor = drawing ? "crosshair" : "";
    if (drawing) {
      map.doubleClickZoom.disable();
    } else {
      map.doubleClickZoom.enable();
    }
  }, [draft, drawing, loaded]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded) {
      return;
    }
    // A failed search or a cleared selection leaves no outline the card no longer shows.
    showArea(map, area);
    if (!area) {
      return;
    }
    const maxZoom = Math.max(...config.base_maps.map((b) => b.max_zoom));
    if (area.geometry.type === "Point") {
      map.jumpTo({ center: [area.centre[0], area.centre[1]], zoom: Math.min(config.point_zoom, maxZoom) });
      return;
    }
    const [west, south, east, north] = area.bbox;
    map.fitBounds(
      [
        [west, south],
        [east, north],
      ],
      { padding: config.area_padding_px, maxZoom, animate: false },
    );
  }, [area, loaded, config]);

  // The detailed map drawn: redrawn only when its analysis or its layer changes.
  const analysis = parcel?.analysis ?? null;
  const parcelLayer = parcel?.layer ?? null;
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded) {
      return;
    }
    showParcelLayer(map, analysis, parcelLayer);
  }, [analysis, parcelLayer, loaded]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded) {
      return;
    }
    candidatesRef.current = candidateMarkers(map, analysis);
    return () => {
      for (const marker of candidatesRef.current) {
        marker.remove();
      }
      candidatesRef.current = [];
    };
  }, [analysis, loaded]);

  const label = area ? areaHeading(area) : t("app.tagline");
  return (
    <div className="map-wrapper">
      <div
        ref={container}
        className="map"
        role="region"
        aria-label={label}
        data-area={area ? `${area.origin}:${area.label ?? ""}` : ""}
        data-draft={draft ? `${draft.mode}:${String(draft.vertices.length)}` : ""}
        data-base={loaded ? layers.base : ""}
        data-overlays={loaded ? describeOverlays(config, layers) : ""}
        data-regional={loaded ? describeRegional(config, layers) : ""}
        data-national={loaded ? describeNational(national, layers) : ""}
        data-parcel={loaded ? describeParcel(analysis, parcelLayer?.id ?? null) : ""}
      />
      {loaded && layers.cadastre.visible && !cadastreReached && <p className="map-hint">{t("map.cadastreHidden")}</p>}
      {missingAreas.length > 0 && <p className="map-hint">{t("map.areaMissing", { areas: missingAreas.map((id) => lookup(`area.${id}`, id)).join(", ") })}</p>}
    </div>
  );
}
