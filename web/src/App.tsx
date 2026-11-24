// Copyright (c) 2026 Almoon-D. All rights reserved.
// The page: a search box, the parcel found, the layer panel, what a tap found, and the map.
import { useEffect, useRef, useState, type SubmitEvent } from "react";

import {
  fetchFeatureInfo,
  fetchMapConfig,
  fetchParcel,
  type LookupFailure,
  type MapConfig,
  type Parcel,
  type Position,
} from "./api.ts";
import { formatArea, formatDate, formatNumber, t } from "./i18n/index.ts";
import { InfoPanel, type Tap } from "./map/InfoPanel.tsx";
import { LayerPanel } from "./map/LayerPanel.tsx";
import { initialLayers, type MapLayers, queryableOverlays } from "./map/layers.ts";
import { MapView } from "./map/MapView.tsx";

type Search =
  | { state: "idle" }
  | { state: "searching" }
  | { state: "found"; parcel: Parcel }
  | { state: "failed"; message: string };

function failureMessage(failure: LookupFailure): string {
  switch (failure) {
    case "network":
      return t("error.network");
    case "unexpected":
      return t("error.unexpected");
    default:
      return t(`error.${failure}`);
  }
}

function ParcelCard({ parcel }: { parcel: Parcel }) {
  const local = parcel.reference_point_local;
  const sources = [...new Set(parcel.sources.map((s) => s.attribution))].join(", ");
  const dates = parcel.sources.map((s) => s.retrieved_at).sort();
  const oldest = dates[0] ?? "";
  return (
    <section className="parcel" aria-live="polite">
      <h2>{t("parcel.heading", { reference: parcel.reference })}</h2>
      <p>{t("parcel.place", { municipality: parcel.municipality, province: parcel.province })}</p>
      <p>{t("parcel.area", { area: formatArea(parcel.area_m2) })}</p>
      <p>{t("parcel.point", { crs: local.crs, x: formatNumber(local.x), y: formatNumber(local.y) })}</p>
      <p className="note">{t("parcel.precision")}</p>
      <p className="note">{t("parcel.sources", { sources, date: formatDate(oldest) })}</p>
    </section>
  );
}

export function App() {
  const [config, setConfig] = useState<MapConfig | null>(null);
  const [configFailed, setConfigFailed] = useState(false);
  const [reference, setReference] = useState("");
  const [search, setSearch] = useState<Search>({ state: "idle" });
  const [layers, setLayers] = useState<MapLayers | null>(null);
  const [zoom, setZoom] = useState(0);
  const [tapped, setTapped] = useState<Position | null>(null);
  const [tap, setTap] = useState<Tap>({ state: "none" });
  // Only the answers to the latest tap are shown.
  const tapCount = useRef(0);

  useEffect(() => {
    fetchMapConfig().then(
      (loaded) => {
        setConfig(loaded);
        setLayers(initialLayers(loaded));
      },
      () => {
        setConfigFailed(true);
      },
    );
  }, []);

  async function onTap(lon: number, lat: number, tapZoom: number) {
    if (!config || !layers) {
      return;
    }
    setTapped([lon, lat]);
    const asked = queryableOverlays(config, layers, tapZoom);
    const count = ++tapCount.current;
    if (asked.length === 0) {
      setTap({ state: "none" });
      return;
    }
    setTap({ state: "loading" });
    const results = await Promise.all(asked.map((o) => fetchFeatureInfo(o.id, lon, lat, tapZoom)));
    if (count === tapCount.current) {
      setTap({ state: "done", results });
    }
  }

  async function onSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!reference.trim()) {
      setSearch({ state: "failed", message: t("search.empty") });
      return;
    }
    setSearch({ state: "searching" });
    const result = await fetchParcel(reference);
    setSearch(
      result.ok ? { state: "found", parcel: result.parcel } : { state: "failed", message: failureMessage(result.failure) },
    );
  }

  const parcel = search.state === "found" ? search.parcel : null;
  return (
    <div className="app">
      <aside className="panel">
        <h1>{t("app.title")}</h1>
        <form
          role="search"
          onSubmit={(event) => {
            void onSubmit(event);
          }}
        >
          <label htmlFor="reference">{t("search.label")}</label>
          <div className="search-row">
            <input
              id="reference"
              name="reference"
              autoComplete="off"
              spellCheck={false}
              placeholder={t("search.placeholder")}
              aria-describedby="reference-hint"
              value={reference}
              onChange={(event) => {
                setReference(event.target.value);
              }}
            />
            <button type="submit" disabled={search.state === "searching"}>
              {search.state === "searching" ? t("search.searching") : t("search.submit")}
            </button>
          </div>
          <p id="reference-hint" className="note">
            {t("search.hint")}
          </p>
        </form>
        {search.state === "failed" && (
          <p className="error" role="alert">
            {search.message}
          </p>
        )}
        {parcel && <ParcelCard parcel={parcel} />}
        {config && layers && (
          <>
            <InfoPanel tap={tap} />
            <LayerPanel config={config} layers={layers} zoom={zoom} onChange={setLayers} />
          </>
        )}
        {configFailed && (
          <p className="error" role="alert">
            {t("app.mapUnavailable")}
          </p>
        )}
      </aside>
      <main className="map-area">
        {config && layers ? (
          <MapView
            config={config}
            parcel={parcel}
            layers={layers}
            tapped={tapped}
            onZoom={setZoom}
            onTap={(lon, lat, tapZoom) => {
              void onTap(lon, lat, tapZoom);
            }}
          />
        ) : (
          !configFailed && <p>{t("app.loading")}</p>
        )}
      </main>
    </div>
  );
}
