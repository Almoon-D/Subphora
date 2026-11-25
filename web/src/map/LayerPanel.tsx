// Copyright (c) 2026 Almoon-D. All rights reserved.
// The layer panel: the base-map switch, then the cadastre and the official layers by group,
// one entry per theme, each with its toggle, opacity, legend, zoom range and sources: the
// national layer and, where one qualifies, the regional layers drawn over it in their areas.
import type { LayerDetail, MapConfig, NationalLayer, NationalMap, Overlay } from "../api.ts";
import { formatDate, lookup, t } from "../i18n/index.ts";
import {
  type LayerState,
  type MapLayers,
  overlaysByGroup,
  reachesZoom,
  scaleOf,
  withNational,
  withOverlay,
} from "./layers.ts";
import { legendText } from "./national.ts";

interface Props {
  config: MapConfig;
  /** Null when the national map could not be read. */
  national: NationalMap | null;
  layers: MapLayers;
  zoom: number;
  onChange: (layers: MapLayers) => void;
}

const PERCENT = 100;

function Opacity({ title, state, onChange }: { title: string; state: LayerState; onChange: (o: number) => void }) {
  const value = Math.round(state.opacity * PERCENT);
  return (
    <div className="opacity">
      <input
        type="range"
        min={0}
        max={PERCENT}
        step={5}
        value={value}
        aria-label={t("layers.opacity", { title })}
        onChange={(event) => {
          onChange(Number(event.target.value) / PERCENT);
        }}
      />
      <span aria-hidden="true">{t("layers.opacityValue", { value })}</span>
    </div>
  );
}

function Legend({ overlay, title }: { overlay: Overlay; title: string }) {
  if (!overlay.legend_url) {
    return <p className="note">{t("layers.noLegend")}</p>;
  }
  return (
    <details className="legend">
      <summary>{t("layers.legend")}</summary>
      <img src={overlay.legend_url} alt={t("layers.legendAlt", { title })} loading="lazy" />
      <a href={overlay.legend_url} target="_blank" rel="noopener noreferrer">
        {t("layers.legendOpen")}
      </a>
    </details>
  );
}

/** "1:25.000 · 2023", with "no indicada" for what the publisher does not state. */
export function describeDetail(detail: LayerDetail): string {
  const scale = scaleOf(detail);
  const scaleText = !scale
    ? t("detail.noScale")
    : scale.kind === "scale"
      ? t("detail.scale", { value: scale.value })
      : t("detail.cell", { value: scale.value });
  const edition = detail.edition === null ? t("detail.noEdition") : t("detail.edition", { year: String(detail.edition) });
  return `${scaleText} · ${edition}`;
}

function Sources({ overlay }: { overlay: Overlay }) {
  return (
    <ul className="note sources">
      <li data-source={overlay.id}>
        {t("layers.national", { publisher: overlay.publisher, detail: describeDetail(overlay.detail) })}
      </li>
      {overlay.regional.map((regional) => (
        <li key={regional.id} data-source={regional.id}>
          {t("layers.regional", {
            title: lookup(`layer.${regional.id}`, regional.id),
            areas: regional.area_ids.map((id) => lookup(`area.${id}`, id)).join(", "),
            detail: describeDetail(regional.detail),
          })}
        </li>
      ))}
    </ul>
  );
}

/** A theme whose national layer gives no values may still answer where a regional one does. */
function TapNote({ overlay }: { overlay: Overlay }) {
  const answering = overlay.regional.filter((r) => r.feature_info);
  if (answering.length === 0) {
    return <p className="note">{t("layers.noInfo")}</p>;
  }
  const areas = answering.flatMap((r) => r.area_ids.map((id) => lookup(`area.${id}`, id)));
  const list = new Intl.ListFormat("es", { type: "conjunction" }).format(areas);
  return <p className="note">{t("layers.infoRegionalOnly", { areas: list })}</p>;
}

function OverlayControl({
  overlay,
  state,
  zoom,
  onChange,
}: {
  overlay: Overlay;
  state: LayerState;
  zoom: number;
  onChange: (change: Partial<LayerState>) => void;
}) {
  const title = lookup(`layer.${overlay.id}`, overlay.id);
  return (
    <li className="layer" data-layer={overlay.id}>
      <label className="toggle">
        <input
          type="checkbox"
          checked={state.visible}
          onChange={(event) => {
            onChange({ visible: event.target.checked });
          }}
        />
        {title}
      </label>
      {state.visible && (
        <>
          <Opacity
            title={title}
            state={state}
            onChange={(opacity) => {
              onChange({ opacity });
            }}
          />
          {!reachesZoom(overlay, zoom) && <p className="note hint">{t("layers.fromZoom", { zoom: overlay.min_zoom })}</p>}
          <Legend overlay={overlay} title={title} />
          {!overlay.feature_info && <TapNote overlay={overlay} />}
        </>
      )}
      <Sources overlay={overlay} />
      <p className="note source">
        {t("layers.source", {
          attribution: [overlay.attribution, ...overlay.regional.map((r) => r.attribution)].join("; "),
        })}
      </p>
    </li>
  );
}

/** A national layer's legend: one swatch per class, the index never called a probability. */
function NationalLegend({ layer }: { layer: NationalLayer }) {
  return (
    <div className="national-legend" data-legend={layer.id}>
      <p className="note">{lookup(`national.unit.${layer.unit}`, layer.unit)}</p>
      <ul>
        {layer.legend.map((item) => (
          <li key={item.colour}>
            <span className="swatch" style={{ background: item.colour }} aria-hidden="true" />
            {legendText(item, layer.unit)}
          </li>
        ))}
      </ul>
    </div>
  );
}

function NationalControls({
  national,
  layers,
  onChange,
}: {
  national: NationalMap | null;
  layers: MapLayers;
  onChange: (layers: MapLayers) => void;
}) {
  if (!national) {
    return (
      <fieldset>
        <legend>{t("group.national")}</legend>
        <p className="note">{t("national.unavailable")}</p>
      </fieldset>
    );
  }
  return (
    <fieldset className="national" data-built={String(national.built)}>
      <legend>{t("group.national")}</legend>
      <p className="note">{t("national.kindNote")}</p>
      {!national.built && <p className="note hint">{t("national.notBuilt")}</p>}
      {national.built && (
        <p className="note">
          {t("national.built", {
            regions: national.regions.map((r) => r.name).join(", "),
            date: formatDate(national.rendered_at ?? ""),
          })}
        </p>
      )}
      {national.built && (
        <ul>
          {national.layers.map((layer) => {
            const state = layers.national[layer.id];
            const title = lookup(`layer.${layer.id}`, layer.id);
            return (
              state && (
                <li key={layer.id} className="layer" data-layer={layer.id}>
                  <label className="toggle">
                    <input
                      type="checkbox"
                      checked={state.visible}
                      onChange={(event) => {
                        onChange(withNational(layers, layer.id, { visible: event.target.checked }));
                      }}
                    />
                    {title}
                  </label>
                  {state.visible && (
                    <>
                      <Opacity
                        title={title}
                        state={state}
                        onChange={(opacity) => {
                          onChange(withNational(layers, layer.id, { opacity }));
                        }}
                      />
                      <NationalLegend layer={layer} />
                    </>
                  )}
                </li>
              )
            );
          })}
        </ul>
      )}
      <p className="note source">{t("national.source", { attribution: national.attributions.join("; ") })}</p>
    </fieldset>
  );
}

export function LayerPanel({ config, national, layers, zoom, onChange }: Props) {
  const cadastreTitle = t("layer.cadastre");
  return (
    <section className="layers" aria-labelledby="layers-heading">
      <h2 id="layers-heading">{t("layers.heading")}</h2>
      <fieldset>
        <legend>{t("layers.base")}</legend>
        {config.base_maps.map((base) => (
          <label key={base.id} className="toggle">
            <input
              type="radio"
              name="base-map"
              value={base.id}
              checked={layers.base === base.id}
              onChange={() => {
                onChange({ ...layers, base: base.id });
              }}
            />
            {lookup(`base.${base.id}`, base.id)}
          </label>
        ))}
      </fieldset>
      <fieldset>
        <legend>{t("layers.cadastre")}</legend>
        <label className="toggle">
          <input
            type="checkbox"
            checked={layers.cadastre.visible}
            onChange={(event) => {
              onChange({ ...layers, cadastre: { ...layers.cadastre, visible: event.target.checked } });
            }}
          />
          {cadastreTitle}
        </label>
        {layers.cadastre.visible && (
          <Opacity
            title={cadastreTitle}
            state={layers.cadastre}
            onChange={(opacity) => {
              onChange({ ...layers, cadastre: { ...layers.cadastre, opacity } });
            }}
          />
        )}
        <p className="note source">{t("layers.source", { attribution: config.cadastre.attribution })}</p>
      </fieldset>
      <NationalControls national={national} layers={layers} onChange={onChange} />
      {overlaysByGroup(config).map(([group, overlays]) => (
        <fieldset key={group}>
          <legend>{lookup(`group.${group}`, group)}</legend>
          <ul>
            {overlays.map((overlay) => {
              const state = layers.overlays[overlay.id];
              return (
                state && (
                  <OverlayControl
                    key={overlay.id}
                    overlay={overlay}
                    state={state}
                    zoom={zoom}
                    onChange={(change) => {
                      onChange(withOverlay(layers, overlay.id, change));
                    }}
                  />
                )
              );
            })}
          </ul>
        </fieldset>
      ))}
    </section>
  );
}
