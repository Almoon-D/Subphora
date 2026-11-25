// Copyright (c) 2026 Almoon-D. All rights reserved.
// The page: one search box (with an explicit choice when the text reads several ways), the
// drawing tools, the selected area and this session's others, the layer panel, what a tap
// found, and the map.
import { useEffect, useRef, useState, type SubmitEvent } from "react";

import {
  type AreaOfInterest,
  type AreaResult,
  drawnPoint,
  drawnPolygon,
  type ExplainResult,
  type Failed,
  fetchExplanation,
  fetchFeatureInfo,
  fetchMapConfig,
  fetchNational,
  type Interpretation,
  type MapConfig,
  type NationalMap,
  type Position,
  resolveArea,
  searchText,
} from "./api.ts";
import { formatArea, formatDate, formatNumber, lookup, t } from "./i18n/index.ts";
import { InfoPanel, type Tap } from "./map/InfoPanel.tsx";
import { LayerPanel } from "./map/LayerPanel.tsx";
import { initialLayers, type MapLayers, queryableOverlays } from "./map/layers.ts";
import { type Draft, MapView } from "./map/MapView.tsx";
import { nationalAnswersTap } from "./map/national.ts";
import {
  areaHeading,
  areaKey,
  interpretationText,
  loadSession,
  saveSession,
  selectedArea,
  type SessionAreas,
  withArea,
} from "./search/areas.ts";

type Search =
  | { state: "idle" }
  | { state: "searching" }
  | { state: "choosing"; interpretations: Interpretation[] }
  | { state: "failed"; message: string };

function failureMessage({ failure, source }: Failed): string {
  switch (failure) {
    case "network":
      return t("error.network");
    case "unexpected":
      return t("error.unexpected");
    case "not_found":
    case "upstream_timeout":
    case "upstream_error":
      return t(`error.${failure}`, { service: lookup(`service.${source ?? ""}`, t("service.unknown")) });
    default:
      return t(`error.${failure}`);
  }
}

function Sources({ area }: { area: AreaOfInterest }) {
  if (area.sources.length === 0) {
    return <p className="note">{t("aoi.noSource")}</p>;
  }
  const sources = [...new Set(area.sources.map((s) => s.attribution))].join(", ");
  const oldest = area.sources.map((s) => s.retrieved_at).sort()[0] ?? "";
  return <p className="note">{t("parcel.sources", { sources, date: formatDate(oldest) })}</p>;
}

function AreaCard({ area }: { area: AreaOfInterest }) {
  const local = area.centre_local;
  const coordinates = { crs: local.crs, x: formatNumber(local.x), y: formatNumber(local.y) };
  const parcel = area.parcel;
  let size: string | null = null;
  if (area.area_m2 !== null) {
    const key = parcel ? "parcel.area" : area.origin.startsWith("sigpac") ? "aoi.sigpacArea" : "aoi.area";
    size = t(key, { area: formatArea(area.area_m2) });
  }
  const place = area.municipality
    ? t("parcel.place", { municipality: area.municipality, province: area.province })
    : t("aoi.province", { province: area.province });
  const centreKey = parcel ? "parcel.point" : area.geometry.type === "Point" ? "aoi.point" : "aoi.centre";
  return (
    <section className="area" aria-live="polite">
      <h2>{areaHeading(area)}</h2>
      <p>{place}</p>
      {size && <p>{size}</p>}
      <p>{t(centreKey, coordinates)}</p>
      {parcel && <p className="note">{t("parcel.precision")}</p>}
      {!area.land_checked && <p className="note">{t("aoi.notChecked")}</p>}
      <Sources area={area} />
    </section>
  );
}

function DrawTools({
  draft,
  max,
  busy,
  onStart,
  onUndo,
  onFinish,
  onCancel,
}: {
  draft: Draft | null;
  max: number;
  busy: boolean;
  onStart: (mode: Draft["mode"]) => void;
  onUndo: () => void;
  onFinish: () => void;
  onCancel: () => void;
}) {
  if (busy) {
    return <p className="note">{t("draw.sending")}</p>;
  }
  if (!draft) {
    return (
      <div className="draw-row">
        <button
          type="button"
          className="secondary"
          onClick={() => {
            onStart("point");
          }}
        >
          {t("draw.point")}
        </button>
        <button
          type="button"
          className="secondary"
          onClick={() => {
            onStart("polygon");
          }}
        >
          {t("draw.polygon")}
        </button>
      </div>
    );
  }
  const count = draft.vertices.length;
  return (
    <div className="drawing" role="group" aria-label={t(draft.mode === "point" ? "draw.point" : "draw.polygon")}>
      <p className="note">
        {draft.mode === "point" ? t("draw.pointHint") : t("draw.polygonHint", { count, max })}
      </p>
      {draft.mode === "polygon" && count >= max && <p className="note">{t("draw.full")}</p>}
      <div className="draw-row">
        {draft.mode === "polygon" && (
          <>
            <button type="button" disabled={count < 3} onClick={onFinish}>
              {t("draw.finish")}
            </button>
            <button type="button" className="secondary" disabled={count === 0} onClick={onUndo}>
              {t("draw.undo")}
            </button>
          </>
        )}
        <button type="button" className="secondary" onClick={onCancel}>
          {t("draw.cancel")}
        </button>
      </div>
    </div>
  );
}

function SessionList({ session, onSelect }: { session: SessionAreas; onSelect: (index: number) => void }) {
  if (session.areas.length < 2) {
    return null;
  }
  return (
    <section className="session">
      <h2>{t("session.heading")}</h2>
      <ul>
        {session.areas.map((area, index) => (
          <li key={areaKey(area)}>
            <button
              type="button"
              className="link"
              aria-current={index === session.selected ? "true" : undefined}
              onClick={() => {
                onSelect(index);
              }}
            >
              {areaHeading(area)}
            </button>
          </li>
        ))}
      </ul>
      <p className="note">{t("session.hint")}</p>
    </section>
  );
}

export function App() {
  const [config, setConfig] = useState<MapConfig | null>(null);
  // Null when the national map could not be read: the rest of the page works without it.
  const [national, setNational] = useState<NationalMap | null>(null);
  const [configFailed, setConfigFailed] = useState(false);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState<Search>({ state: "idle" });
  const [session, setSession] = useState<SessionAreas>(() => loadSession());
  const [draft, setDraft] = useState<Draft | null>(null);
  const [sending, setSending] = useState(false);
  const [layers, setLayers] = useState<MapLayers | null>(null);
  const [zoom, setZoom] = useState(0);
  const [tapped, setTapped] = useState<Position | null>(null);
  const [tap, setTap] = useState<Tap>({ state: "idle" });
  // Only the answers to the latest tap, and to the latest search, are shown.
  const tapCount = useRef(0);
  const searchCount = useRef(0);

  useEffect(() => {
    Promise.all([fetchMapConfig(), fetchNational().catch(() => null)]).then(
      ([loaded, nationalMap]) => {
        setConfig(loaded);
        setNational(nationalMap);
        setLayers(initialLayers(loaded, nationalMap));
      },
      () => {
        setConfigFailed(true);
      },
    );
  }, []);

  useEffect(() => {
    saveSession(session);
  }, [session]);

  async function onTap(lon: number, lat: number, tapZoom: number) {
    if (!config || !layers) {
      return;
    }
    setTapped([lon, lat]);
    const asked = queryableOverlays(config, layers, lon, lat, tapZoom);
    const askNational = nationalAnswersTap(national, layers, lon, lat);
    const count = ++tapCount.current;
    if (asked.length === 0 && !askNational) {
      setTap({ state: "nothing" });
      return;
    }
    setTap({ state: "loading" });
    const explained: Promise<ExplainResult | null> = askNational ? fetchExplanation(lon, lat) : Promise.resolve(null);
    const [nationalResult, results] = await Promise.all([
      explained,
      Promise.all(asked.map((o) => fetchFeatureInfo(o.id, lon, lat, tapZoom))),
    ]);
    if (count === tapCount.current) {
      setTap({ state: "done", results, national: nationalResult });
    }
  }

  /** Select the area of an answer, or say why there is none (and select nothing). */
  function settle(result: AreaResult, count: number) {
    if (count !== searchCount.current) {
      return;
    }
    if (result.ok) {
      setSession((current) => withArea(current, result.area, config?.search.session_areas ?? 1));
      setSearch({ state: "idle" });
    } else {
      setSession((current) => ({ ...current, selected: -1 }));
      setSearch({ state: "failed", message: failureMessage(result) });
    }
  }

  async function choose(reading: Interpretation) {
    const count = ++searchCount.current;
    setSearch({ state: "searching" });
    settle(await resolveArea(reading.resolve), count);
  }

  async function onSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setDraft(null);
    if (!query.trim()) {
      setSearch({ state: "failed", message: t("error.empty_query") });
      return;
    }
    const count = ++searchCount.current;
    setSearch({ state: "searching" });
    const answer = await searchText(query);
    if (count !== searchCount.current) {
      return;
    }
    if (!answer.ok) {
      settle(answer, count);
      return;
    }
    const [only, ...others] = answer.interpretations;
    if (only && others.length === 0) {
      settle(await resolveArea(only.resolve), count);
    } else {
      setSearch({ state: "choosing", interpretations: answer.interpretations });
    }
  }

  async function send(request: Promise<AreaResult>) {
    const count = ++searchCount.current;
    setSending(true);
    const result = await request;
    setSending(false);
    setDraft(null);
    settle(result, count);
  }

  function onDraw(lon: number, lat: number) {
    if (!draft || sending) {
      return;
    }
    if (draft.mode === "point") {
      void send(drawnPoint(lon, lat));
      return;
    }
    const max = config?.search.max_vertices ?? 0;
    if (draft.vertices.length < max) {
      setDraft({ ...draft, vertices: [...draft.vertices, [lon, lat]] });
    }
  }

  const area = selectedArea(session);
  const searching = search.state === "searching";
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
          <label htmlFor="search">{t("search.label")}</label>
          <div className="search-row">
            <input
              id="search"
              name="search"
              autoComplete="off"
              spellCheck={false}
              placeholder={t("search.placeholder")}
              aria-describedby="search-hint"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
              }}
            />
            <button type="submit" disabled={searching}>
              {searching ? t("search.searching") : t("search.submit")}
            </button>
          </div>
          <p id="search-hint" className="note">
            {t("search.hint")}
          </p>
        </form>
        {config && (
          <DrawTools
            draft={draft}
            max={config.search.max_vertices}
            busy={sending}
            onStart={(mode) => {
              setSearch({ state: "idle" });
              setDraft({ mode, vertices: [] });
            }}
            onUndo={() => {
              setDraft((current) => current && { ...current, vertices: current.vertices.slice(0, -1) });
            }}
            onFinish={() => {
              if (draft) {
                void send(drawnPolygon(draft.vertices));
              }
            }}
            onCancel={() => {
              setDraft(null);
            }}
          />
        )}
        {search.state === "choosing" && (
          <section className="choices" aria-labelledby="choices-heading">
            <h2 id="choices-heading">{t("choice.heading")}</h2>
            <p className="note">{t("choice.hint")}</p>
            <ul>
              {search.interpretations.map((reading) => (
                <li key={reading.resolve}>
                  <button
                    type="button"
                    className="link"
                    onClick={() => {
                      void choose(reading);
                    }}
                  >
                    {interpretationText(reading)}
                  </button>
                </li>
              ))}
            </ul>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setSearch({ state: "idle" });
              }}
            >
              {t("choice.cancel")}
            </button>
          </section>
        )}
        {search.state === "failed" && (
          <p className="error" role="alert">
            {search.message}
          </p>
        )}
        {area && <AreaCard area={area} />}
        <SessionList
          session={session}
          onSelect={(index) => {
            setSearch({ state: "idle" });
            setSession((current) => ({ ...current, selected: index }));
          }}
        />
        {config && layers && (
          <>
            <InfoPanel tap={tap} />
            <LayerPanel config={config} national={national} layers={layers} zoom={zoom} onChange={setLayers} />
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
            national={national}
            area={area}
            layers={layers}
            tapped={tapped}
            draft={draft}
            onZoom={setZoom}
            onTap={(lon, lat, tapZoom) => {
              void onTap(lon, lat, tapZoom);
            }}
            onDraw={onDraw}
          />
        ) : (
          !configFailed && <p>{t("app.loading")}</p>
        )}
      </main>
    </div>
  );
}
