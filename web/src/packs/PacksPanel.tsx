// Copyright (c) 2026 Almoon-D. All rights reserved.
// The offline packs panel: what a pack of the selected area would hold and leave out, its
// estimated size and the download; the download's progress and pause; and the packs on
// this device, to open, resume or delete.
import { useEffect, useMemo, useState } from "react";

import type { AreaOfInterest, MapConfig, NationalMap, ParcelAnswer } from "../api.ts";
import { formatDate, formatMegabytes, lookup, t } from "../i18n/index.ts";
import { areaHeading } from "../search/areas.ts";
import type { Packs } from "./hooks.ts";
import { type Exclusion, type PackPlan, planPack } from "./plan.ts";
import type { PackRecord } from "./store.ts";

/** Whether the browser says it is online, kept current. */
function useOnline(): boolean {
  const [online, setOnline] = useState(() => navigator.onLine);
  useEffect(() => {
    const update = () => {
      setOnline(navigator.onLine);
    };
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  return online;
}

function exclusionName(exclusion: Exclusion): string {
  switch (exclusion.kind) {
    case "base_map":
      return lookup(`base.${exclusion.id}`, exclusion.id);
    case "cadastre":
      return t("packs.item.cadastre");
    case "geometry":
    case "detailed":
    case "national":
      return t(`packs.item.${exclusion.kind}`);
    default:
      return lookup(`layer.${exclusion.id}`, exclusion.id);
  }
}

/** The layers left out, one line per reason, so that 25 official layers stay readable. */
function Excluded({ excluded }: { excluded: readonly Exclusion[] }) {
  const reasons = [...new Set(excluded.map((e) => e.reason))];
  return (
    <details className="pack-excluded">
      <summary>{t("packs.excludedHeading")}</summary>
      <ul>
        {reasons.map((reason) => (
          <li key={reason} data-reason={reason}>
            {excluded
              .filter((e) => e.reason === reason)
              .map(exclusionName)
              .join("; ")}
            : {t(`packs.reason.${reason}`)}
          </li>
        ))}
      </ul>
    </details>
  );
}

function Holds({ config, plan }: { config: MapConfig; plan: PackPlan }) {
  const packs = config.packs;
  const candidates = plan.answer?.job.analysis?.candidates.length ?? 0;
  return (
    <>
      <p>{t("packs.holds", { label: plan.label })}</p>
      <ul className="pack-holds">
        {packs.base_maps.map((base) => (
          <li key={base.id}>
            {t("packs.base", {
              layer: lookup(`base.${base.id}`, base.id),
              count: plan.counts[base.id] ?? 0,
              min: plan.min_zoom,
              max: plan.max_zoom,
            })}
          </li>
        ))}
        {packs.layers.map((id) =>
          plan.files.some((f) => f.kind === "national" && f.layer === id) ? (
            <li key={`national-${id}`}>{t("packs.national", { layer: lookup(`layer.${id}`, id), count: plan.counts[id] ?? 0 })}</li>
          ) : null,
        )}
        {plan.files
          .filter((f) => f.kind === "image")
          .map((f) => (
            <li key={f.url}>{t("packs.image", { layer: lookup(`layer.${f.layer}`, f.layer) })}</li>
          ))}
        {plan.answer && <li>{t("packs.candidates", { count: candidates })}</li>}
        {plan.area && <li>{t("packs.geometry")}</li>}
      </ul>
    </>
  );
}

function PackItem({
  pack,
  busy,
  onOpen,
  onResume,
  onDelete,
}: {
  pack: PackRecord;
  busy: boolean;
  onOpen: () => void;
  onResume: () => void;
  onDelete: () => void;
}) {
  return (
    <li className="pack" data-state={pack.state} data-files={`${String(pack.stored_files)}/${String(pack.files.length)}`}>
      <strong>{pack.label}</strong> · {t(`packs.state.${pack.state}`)}
      <p className="note">
        {t("packs.summary", {
          files: pack.stored_files,
          total: pack.files.length,
          size: formatMegabytes(pack.stored_bytes),
          date: formatDate(pack.completed_at ?? pack.created_at),
        })}
      </p>
      {pack.stopped && <p className="note">{t(`packs.stopped.${pack.stopped}`)}</p>}
      {!pack.persisted && <p className="note">{t("packs.notPersisted")}</p>}
      {!pack.area && <p className="note">{t("packs.noArea")}</p>}
      <div className="draw-row">
        {pack.state === "complete" && pack.area && (
          <button type="button" className="secondary" onClick={onOpen}>
            {t("packs.open")}
          </button>
        )}
        {pack.state !== "complete" && (
          <button type="button" className="secondary" disabled={busy} onClick={onResume}>
            {t("packs.resume")}
          </button>
        )}
        <button type="button" className="secondary" disabled={busy} onClick={onDelete}>
          {t("packs.delete")}
        </button>
      </div>
    </li>
  );
}

interface Props {
  config: MapConfig;
  national: NationalMap | null;
  area: AreaOfInterest | null;
  /** The selected area's detailed map, once done. */
  answer: ParcelAnswer | null;
  packs: Packs;
  onOpen: (pack: PackRecord) => void;
}

export function PacksPanel({ config, national, area, answer, packs, onOpen }: Props) {
  const online = useOnline();
  const plan = useMemo(
    () => (area ? planPack(config, national, area, answer, areaHeading(area), window.location.origin) : null),
    [config, national, area, answer],
  );
  const { active, refusal } = packs;
  const max = formatMegabytes(config.packs.max_bytes);
  return (
    <section className="packs" aria-labelledby="packs-heading" data-active={active ? "true" : "false"}>
      <h2 id="packs-heading">{t("packs.heading")}</h2>
      {!online && (
        <p className="note" role="status">
          {t("packs.offline")}
        </p>
      )}
      {!packs.available ? (
        <p className="note">{t("packs.unavailable")}</p>
      ) : (
        <>
          {plan && !active && (
            <div className="pack-plan" data-estimate={plan.estimate_bytes} data-files={plan.files.length}>
              <p className="note">{t("packs.intro")}</p>
              <Holds config={config} plan={plan} />
              <p>{t("packs.estimate", { size: formatMegabytes(plan.estimate_bytes), max })}</p>
              <Excluded excluded={plan.excluded} />
              {plan.too_large ? (
                <p className="error" role="alert">
                  {t("packs.refusal.too_large", { max })}
                </p>
              ) : (
                <button
                  type="button"
                  disabled={!packs.store || !online}
                  onClick={() => {
                    void packs.start(plan);
                  }}
                >
                  {t("packs.download", { size: formatMegabytes(plan.estimate_bytes) })}
                </button>
              )}
            </div>
          )}
          {refusal && refusal !== "too_large" && (
            <p className="error" role="alert">
              {t(`packs.refusal.${refusal}`)}
            </p>
          )}
          {active && (
            <div className="pack-progress" role="status">
              <p>
                {t("packs.progress", {
                  label: active.label,
                  done: active.stored_files,
                  total: active.files.length,
                  size: formatMegabytes(active.stored_bytes),
                })}
              </p>
              <progress max={active.files.length} value={active.stored_files} />
              <button type="button" className="secondary" onClick={packs.pause}>
                {t("packs.pause")}
              </button>
            </div>
          )}
          <h3>{t("packs.listHeading")}</h3>
          {packs.packs.length === 0 ? (
            <p className="note">{t("packs.none")}</p>
          ) : (
            <ul className="pack-list">
              {packs.packs.map((pack) => (
                <PackItem
                  key={pack.id}
                  pack={pack}
                  busy={active !== null}
                  onOpen={() => {
                    onOpen(pack);
                  }}
                  onResume={() => {
                    void packs.resume(pack.id);
                  }}
                  onDelete={() => {
                    void packs.remove(pack.id);
                  }}
                />
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
