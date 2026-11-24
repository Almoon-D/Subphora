// Copyright (c) 2026 Almoon-D. All rights reserved.
// The map: PNOA tiles as the base, Catastro's parcels as one image per view, and the
// parcel found by the search outlined on top.
import {
  type GeoJSONSource,
  type ImageSource,
  Map as MaplibreMap,
  MercatorCoordinate,
  NavigationControl,
  setWorkerUrl,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import { useEffect, useRef, useState } from "react";

import type { MapConfig, Parcel } from "../api.ts";
import { t } from "../i18n/index.ts";
import { cadastreImageUrl, cadastreVisible, imageSize, type MercatorBox } from "./cadastre.ts";

// MapLibre finds its worker next to its own module, which bundling moves: name it.
setWorkerUrl(workerUrl);

// Half the width of the EPSG:3857 world, in metres: MapLibre's mercator units are 0…1.
const WEB_MERCATOR_HALF_EXTENT_M = 20037508.342789244;
const BASE = "base";
const CADASTRE = "cadastre";
const PARCEL = "parcel";
const PARCEL_COLOUR = "#ffd400";

interface Props {
  config: MapConfig;
  parcel: Parcel | null;
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

/** Ask for one cadastral image of the current view, or hide the layer when zoomed out. */
function refreshCadastre(map: MaplibreMap, cadastre: MapConfig["cadastre"]): boolean {
  const visible = cadastreVisible(cadastre, map.getZoom());
  if (map.getLayer(CADASTRE)) {
    map.setLayoutProperty(CADASTRE, "visibility", visible ? "visible" : "none");
  }
  if (!visible) {
    return false;
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
      { id: CADASTRE, type: "raster", source: CADASTRE, paint: { "raster-fade-duration": 0 } },
      map.getLayer(`${PARCEL}-fill`) ? `${PARCEL}-fill` : undefined,
    );
  }
  return true;
}

export function MapView({ config, parcel }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MaplibreMap | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [cadastreShown, setCadastreShown] = useState(false);

  useEffect(() => {
    if (!container.current) {
      return;
    }
    const { base, cadastre, initial_view: view } = config;
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
      style: {
        version: 8,
        sources: {
          [BASE]: {
            type: "raster",
            tiles: base.tiles,
            tileSize: base.tile_size,
            maxzoom: base.max_zoom,
            attribution: base.attribution,
          },
        },
        layers: [{ id: BASE, type: "raster", source: BASE }],
      },
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
      timer = setTimeout(() => {
        setCadastreShown(refreshCadastre(map, cadastre));
      }, cadastre.refresh_delay_ms);
    });
    map.on("load", () => {
      setLoaded(true);
      setCadastreShown(refreshCadastre(map, cadastre));
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
      { padding: config.parcel_padding_px, maxZoom: config.base.max_zoom, animate: false },
    );
  }, [parcel, loaded, config]);

  const label = parcel ? t("parcel.heading", { reference: parcel.reference }) : t("app.tagline");
  return (
    <div className="map-wrapper">
      <div ref={container} className="map" role="region" aria-label={label} data-parcel={parcel?.reference ?? ""} />
      {loaded && !cadastreShown && <p className="map-hint">{t("map.cadastreHidden")}</p>}
    </div>
  );
}
