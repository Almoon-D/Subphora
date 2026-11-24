// Copyright (c) 2026 Almoon-D. All rights reserved.
// The map: a base map (PNOA or the IGN maps), the official layers as tiles, Catastro's
// parcels as one image per view, and the parcel found by the search outlined on top.
import {
  type GeoJSONSource,
  type ImageSource,
  type LayerSpecification,
  type RasterSourceSpecification,
  type StyleSpecification,
  Map as MaplibreMap,
  Marker,
  MercatorCoordinate,
  NavigationControl,
  setWorkerUrl,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import { useEffect, useRef, useState } from "react";

import type { MapConfig, Parcel, Position } from "../api.ts";
import { t } from "../i18n/index.ts";
import { cadastreImageUrl, cadastreVisible, imageSize, type MercatorBox } from "./cadastre.ts";
import { describeOverlays, type MapLayers, overlayTiles } from "./layers.ts";

// MapLibre finds its worker next to its own module, which bundling moves: name it.
setWorkerUrl(workerUrl);

// Half the width of the EPSG:3857 world, in metres: MapLibre's mercator units are 0…1.
const WEB_MERCATOR_HALF_EXTENT_M = 20037508.342789244;
const baseId = (id: string) => `base-${id}`;
const overlayId = (id: string) => `overlay-${id}`;
const CADASTRE = "cadastre";
const PARCEL = "parcel";
const PARCEL_COLOUR = "#ffd400";

interface Props {
  config: MapConfig;
  parcel: Parcel | null;
  layers: MapLayers;
  /** The last tapped point, marked on the map. */
  tapped: Position | null;
  onZoom: (zoom: number) => void;
  onTap: (lon: number, lat: number, zoom: number) => void;
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

const visibility = (visible: boolean) => (visible ? "visible" : "none");

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
      map.getLayer(`${PARCEL}-fill`) ? `${PARCEL}-fill` : undefined,
    );
  }
  return true;
}

/** Apply the panel's choices to the map's layers. */
function applyLayers(map: MaplibreMap, config: MapConfig, layers: MapLayers): void {
  for (const base of config.base_maps) {
    map.setLayoutProperty(baseId(base.id), "visibility", visibility(base.id === layers.base));
  }
  for (const overlay of config.overlays) {
    const state = layers.overlays[overlay.id];
    map.setLayoutProperty(overlayId(overlay.id), "visibility", visibility(state?.visible === true));
    map.setPaintProperty(overlayId(overlay.id), "raster-opacity", state?.opacity ?? overlay.opacity);
  }
  if (map.getLayer(CADASTRE)) {
    map.setPaintProperty(CADASTRE, "raster-opacity", layers.cadastre.opacity);
  }
}

function initialStyle(config: MapConfig, layers: MapLayers): StyleSpecification {
  const origin = window.location.origin;
  const sources: Record<string, RasterSourceSpecification> = {};
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
    ...config.overlays.map((overlay): LayerSpecification => {
      const state = layers.overlays[overlay.id];
      return {
        id: overlayId(overlay.id),
        type: "raster",
        source: overlayId(overlay.id),
        minzoom: overlay.min_zoom,
        layout: { visibility: visibility(state?.visible === true) },
        paint: { "raster-opacity": state?.opacity ?? overlay.opacity },
      };
    }),
  ];
  return { version: 8, sources, layers: styleLayers };
}

export function MapView({ config, parcel, layers, tapped, onZoom, onTap }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MaplibreMap | null>(null);
  const markerRef = useRef<Marker | null>(null);
  // The handlers registered once read the latest choices and callbacks through these.
  const layersRef = useRef(layers);
  const onZoomRef = useRef(onZoom);
  const onTapRef = useRef(onTap);
  const [loaded, setLoaded] = useState(false);
  const [cadastreReached, setCadastreReached] = useState(false);

  useEffect(() => {
    layersRef.current = layers;
    onZoomRef.current = onZoom;
    onTapRef.current = onTap;
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
      style: initialStyle(config, layersRef.current),
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
      onTapRef.current(event.lngLat.lng, event.lngLat.lat, map.getZoom());
    });
    map.on("load", () => {
      setLoaded(true);
      onZoomRef.current(map.getZoom());
      setCadastreReached(refreshCadastre(map, cadastre, layersRef.current));
    });
    return () => {
      clearTimeout(timer);
      mapRef.current = null;
      map.remove();
    };
  }, [config]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded) {
      return;
    }
    applyLayers(map, config, layers);
  }, [layers, loaded, config]);

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

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded) {
      return;
    }
    const source = map.getSource<GeoJSONSource>(PARCEL);
    if (!parcel) {
      // A failed or new search: no outline of a parcel the card no longer shows.
      void source?.setData({ type: "FeatureCollection", features: [] });
      return;
    }
    const data = { type: "Feature" as const, properties: {}, geometry: parcel.geometry };
    if (source) {
      void source.setData(data);
    } else {
      map.addSource(PARCEL, { type: "geojson", data: data as never });
      map.addLayer({
        id: `${PARCEL}-fill`,
        type: "fill",
        source: PARCEL,
        paint: { "fill-color": PARCEL_COLOUR, "fill-opacity": 0.15 },
      });
      map.addLayer({
        id: `${PARCEL}-line`,
        type: "line",
        source: PARCEL,
        paint: { "line-color": PARCEL_COLOUR, "line-width": 3 },
      });
    }
    const [west, south, east, north] = parcel.bbox;
    map.fitBounds(
      [
        [west, south],
        [east, north],
      ],
      { padding: config.parcel_padding_px, maxZoom: Math.max(...config.base_maps.map((b) => b.max_zoom)), animate: false },
    );
  }, [parcel, loaded, config]);

  const label = parcel ? t("parcel.heading", { reference: parcel.reference }) : t("app.tagline");
  return (
    <div className="map-wrapper">
      <div
        ref={container}
        className="map"
        role="region"
        aria-label={label}
        data-parcel={parcel?.reference ?? ""}
        data-base={loaded ? layers.base : ""}
        data-overlays={loaded ? describeOverlays(config, layers) : ""}
      />
      {loaded && layers.cadastre.visible && !cadastreReached && <p className="map-hint">{t("map.cadastreHidden")}</p>}
    </div>
  );
}
