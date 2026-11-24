// Copyright (c) 2026 Almoon-D. All rights reserved.
// The layer panel: the base-map switch, then the cadastre and the official layers by group,
// each with its toggle, opacity, legend, zoom range and source.
import type { MapConfig, Overlay } from "../api.ts";
import { lookup, t } from "../i18n/index.ts";
import { type LayerState, type MapLayers, overlaysByGroup, reachesZoom, withOverlay } from "./layers.ts";

interface Props {
  config: MapConfig;
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
          {!overlay.feature_info && <p className="note">{t("layers.noInfo")}</p>}
        </>
      )}
      <p className="note source">{t("layers.source", { attribution: overlay.attribution })}</p>
    </li>
  );
}

export function LayerPanel({ config, layers, zoom, onChange }: Props) {
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
