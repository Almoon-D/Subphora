// Copyright (c) 2026 Almoon-D. All rights reserved.
// The interpretive cross-section under a drawn line: while it is asked, why it failed, or
// the section itself — its cells coloured by unit and faded by confidence, "unknown"
// hatched, the ground, contacts, faults, boreholes and water table — with its vertical
// exaggeration, a legend, the "interpretation" label always shown, and what a tap on any
// part of it means.
import { type MouseEvent, useState } from "react";

import type { CrossSection, MapConfig, SectionCell, SectionColumn, SectionFailure } from "../api.ts";
import { formatDate, formatNumber, t } from "../i18n/index.ts";
import {
  contactLine,
  exaggeration,
  type Picked,
  pick,
  unitColour,
  verticalRange,
  waterTableStretches,
  withinReach,
} from "./section.ts";

export type SectionView =
  | { state: "asking" }
  | { state: "done"; section: CrossSection }
  | { state: "failed"; failure: SectionFailure };

const WIDTH = 1000;
const HEIGHT = 380;
const LEFT = 60;
const RIGHT = 12;
const TOP = 28;
const BOTTOM = 30;
const PLOT_W = WIDTH - LEFT - RIGHT;
const PLOT_H = HEIGHT - TOP - BOTTOM;
// How near, in pixels, a tap must be to a mark to pick it rather than the cell under it.
const PICK_PX = 6;
const WATER = "#1f6fd1";
const FAULT = "#c0392b";

function percent(value: number): string {
  return `${formatNumber(value * 100, 0)} %`;
}

function metres(value: number): string {
  return `${formatNumber(value, 0)} m`;
}

function unitName(section: CrossSection, index: number | null): string {
  const unit = index === null ? undefined : section.units[index];
  return unit?.label ?? t("section.noUnit");
}

function CellExplanation({ section, column, cell }: { section: CrossSection; column: SectionColumn; cell: SectionCell }) {
  const depth = t("section.depthRange", { top: metres(cell.top_m), bottom: metres(cell.top_m + section.row_m) });
  if (cell.state === "unknown" || cell.confidence === null || cell.depth_factor === null) {
    return (
      <>
        <p>
          <strong>{t("section.unknown")}</strong> · {depth}
        </p>
        <p className="note">
          {column.ground_m === null
            ? t("section.unknownNoGround")
            : t("section.unknownBelow", { reach: metres(column.reach_m) })}
        </p>
      </>
    );
  }
  const product = cell.depth_factor * column.fault_factor;
  const base = product > 0 ? cell.confidence / product : null;
  return (
    <>
      <p>
        <strong>{unitName(section, cell.unit)}</strong> · {depth}
      </p>
      <p>
        {t("section.confidence", {
          value: percent(cell.confidence),
          label: t(`explain.confidence.${cell.label ?? "low"}`),
        })}
      </p>
      <ul className="section-parts">
        <li>
          {column.evidence === null || column.evidence_m === null
            ? t("section.noEvidence")
            : t("section.evidence", {
                kind: t(`section.evidence.${column.evidence}`),
                distance: metres(column.evidence_m),
                factor: formatNumber(column.evidence_factor, 2),
              })}
        </li>
        {base !== null && <li>{t("section.mapAndEvidence", { value: percent(base) })}</li>}
        <li>{t("section.depthFactor", { factor: formatNumber(cell.depth_factor, 2) })}</li>
        {column.fault_factor < 1 && <li>{t("section.faultFactor", { factor: formatNumber(column.fault_factor, 2) })}</li>}
        <li>{t("section.reach", { reach: metres(column.reach_m) })}</li>
      </ul>
    </>
  );
}

function Explanation({ section, picked }: { section: CrossSection; picked: Picked }) {
  switch (picked.kind) {
    case "above":
      return <p className="note">{t("section.above")}</p>;
    case "cell":
      return <CellExplanation section={section} column={picked.column} cell={picked.cell} />;
    case "fault":
      return (
        <>
          <p>
            <strong>{t("section.fault", { kind: picked.fault.kind })}</strong> · {metres(picked.fault.distance_m)}
          </p>
          <p className="note">{t("section.faultNote")}</p>
        </>
      );
    case "borehole": {
      const b = picked.borehole;
      return (
        <>
          <p>
            <strong>{t("section.borehole", { kind: b.kind, depth: metres(b.depth_m) })}</strong>
          </p>
          <p>{t("section.boreholeOffset", { along: metres(b.distance_m), offset: metres(Math.abs(b.offset_m)) })}</p>
          <p className="note">{t("section.noLog")}</p>
        </>
      );
    }
    case "water": {
      const table = picked.point.water_table;
      if (!table) {
        return null;
      }
      return (
        <>
          <p>
            <strong>
              {t("section.water", {
                elevation: metres(table.elevation_m),
                low: metres(table.low_m),
                high: metres(table.high_m),
              })}
            </strong>
          </p>
          <p>
            {t("section.waterFrom", {
              body: table.body_label,
              count: table.piezometers,
              nearest: metres(table.nearest_m),
            })}
          </p>
        </>
      );
    }
    case "contact": {
      const c = picked.contact;
      const units = { before: unitName(section, c.before), after: unitName(section, c.after) };
      return (
        <>
          <p>
            <strong>{t("section.contact", units)}</strong> · {metres(c.distance_m)}
          </p>
          <p>
            {c.state === "projected" && c.apparent_dip_deg !== null && c.measurement && c.measurement_m !== null
              ? t("section.projected", {
                  apparent: formatNumber(Math.abs(c.apparent_dip_deg), 0),
                  toward: t(c.apparent_dip_deg >= 0 ? "section.towardEnd" : "section.towardStart"),
                  dip: formatNumber(c.measurement.dip_deg, 0),
                  direction:
                    c.measurement.direction_deg === null ? "—" : formatNumber(c.measurement.direction_deg, 0),
                  distance: metres(c.measurement_m),
                })
              : t(c.state === "at_fault" ? "section.contact.at_fault" : "section.contact.not_projected")}
          </p>
        </>
      );
    }
  }
}

function Drawing({ section, onPick }: { section: CrossSection; onPick: (picked: Picked | null) => void }) {
  const { bottom, top } = verticalRange(section);
  const span = top - bottom;
  const x = (distance: number) => LEFT + (distance / section.length_m) * PLOT_W;
  const y = (elevation: number) => TOP + ((top - elevation) / span) * PLOT_H;
  const half = section.column_m / 2;
  const ratio = exaggeration(PLOT_W, PLOT_H, section.length_m, span);

  const ground: string[][] = [[]];
  for (const point of section.profile) {
    const current = ground[ground.length - 1];
    if (point.ground_m === null) {
      if (current && current.length > 0) {
        ground.push([]);
      }
      continue;
    }
    current?.push(`${x(point.distance_m).toFixed(1)},${y(point.ground_m).toFixed(1)}`);
  }

  function onClick(event: MouseEvent<SVGSVGElement>) {
    const svg = event.currentTarget;
    const matrix = svg.getScreenCTM();
    if (!matrix) {
      return;
    }
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
    const distance = ((point.x - LEFT) / PLOT_W) * section.length_m;
    const elevation = top - ((point.y - TOP) / PLOT_H) * span;
    if (distance < 0 || distance > section.length_m || elevation < bottom || elevation > top) {
      onPick(null);
      return;
    }
    const along = (PICK_PX / PLOT_W) * section.length_m;
    const up = (PICK_PX / PLOT_H) * span;
    onPick(pick(section, distance, elevation, along, up));
  }

  const ticks = [0, 0.25, 0.5, 0.75, 1].map((share) => share * section.length_m);
  const levels = [0, 0.25, 0.5, 0.75, 1].map((share) => bottom + share * span);
  return (
    <>
      <svg
        className="section-svg"
        viewBox={`0 0 ${String(WIDTH)} ${String(HEIGHT)}`}
        role="img"
        aria-label={t("section.drawingLabel", { length: metres(section.length_m) })}
        onClick={onClick}
      >
        <defs>
          <pattern id="section-unknown" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="8" height="8" fill="#eeeeee" />
            <line x1="0" y1="0" x2="0" y2="8" stroke="#9a9a9a" strokeWidth="2" />
          </pattern>
        </defs>
        <g className="section-cells">
          {section.columns.flatMap((column) =>
            column.ground_m === null
              ? []
              : column.cells.map((cell) => {
                  const ground_m = column.ground_m ?? 0;
                  const y0 = y(ground_m - cell.top_m);
                  const y1 = y(ground_m - cell.top_m - section.row_m);
                  const interpreted = cell.state === "interpreted" && cell.unit !== null;
                  return (
                    <rect
                      key={`${String(column.distance_m)}-${String(cell.top_m)}`}
                      x={x(column.distance_m - half)}
                      y={y0}
                      width={Math.max(0.5, x(column.distance_m + half) - x(column.distance_m - half))}
                      height={Math.max(0.5, y1 - y0)}
                      fill={interpreted ? unitColour(cell.unit ?? 0) : "url(#section-unknown)"}
                      fillOpacity={interpreted ? 0.2 + 0.8 * (cell.confidence ?? 0) : 1}
                      data-state={cell.state}
                    />
                  );
                }),
          )}
        </g>
        {section.water_table.length > 0 &&
          waterTableStretches(section.water_table).map((stretch) => {
            const band = [
              ...stretch.map((p) => `${x(p.distance_m).toFixed(1)},${y(p.water_table?.high_m ?? 0).toFixed(1)}`),
              ...[...stretch]
                .reverse()
                .map((p) => `${x(p.distance_m).toFixed(1)},${y(p.water_table?.low_m ?? 0).toFixed(1)}`),
            ].join(" ");
            const line = stretch
              .map((p) => `${x(p.distance_m).toFixed(1)},${y(p.water_table?.elevation_m ?? 0).toFixed(1)}`)
              .join(" ");
            return (
              <g key={`water-${String(stretch[0]?.distance_m ?? 0)}`} className="section-water">
                <polygon points={band} fill={WATER} fillOpacity={0.15} />
                <polyline points={line} fill="none" stroke={WATER} strokeWidth={2} strokeDasharray="6 3" />
              </g>
            );
          })}
        {section.contacts
          .filter((c) => c.state !== "at_fault")
          .map((c) => {
            const drawn = withinReach(section, contactLine(c, section.faults, section.length_m, bottom));
            if (!drawn) {
              return null;
            }
            const [[x0, y0], [x1, y1]] = drawn;
            return (
              <line
                key={`contact-${String(c.distance_m)}`}
                x1={x(x0)}
                y1={y(y0)}
                x2={x(x1)}
                y2={y(y1)}
                stroke="#333"
                strokeWidth={1.5}
                strokeDasharray={c.state === "projected" ? undefined : "3 3"}
                data-contact={c.state}
              />
            );
          })}
        {section.faults.map((f) => (
          <g key={`fault-${String(f.distance_m)}`} data-fault="">
            <line x1={x(f.distance_m)} y1={TOP} x2={x(f.distance_m)} y2={TOP + PLOT_H} stroke={FAULT} strokeWidth={2} />
            <text x={x(f.distance_m) + 3} y={TOP + 12} fill={FAULT} fontSize={12}>
              F
            </text>
          </g>
        ))}
        {section.boreholes.map((b) =>
          b.ground_m === null ? null : (
            <rect
              key={`borehole-${String(b.distance_m)}`}
              x={x(b.distance_m) - 2}
              y={y(b.ground_m)}
              width={4}
              height={Math.max(1, y(b.ground_m - b.depth_m) - y(b.ground_m))}
              fill="#111"
              data-borehole=""
            />
          ),
        )}
        {ground.map(
          (points, index) =>
            points.length > 1 && (
              <polyline key={`ground-${String(index)}`} points={points.join(" ")} fill="none" stroke="#1d232a" strokeWidth={2} />
            ),
        )}
        <g className="section-axes" fontSize={11} fill="#5a6570">
          {ticks.map((d, index) => (
            <text
              key={`d-${String(d)}`}
              x={x(d)}
              y={HEIGHT - 10}
              textAnchor={index === 0 ? "start" : index === ticks.length - 1 ? "end" : "middle"}
            >
              {metres(d)}
            </text>
          ))}
          {levels.map((e) => (
            <text key={`e-${String(e)}`} x={LEFT - 6} y={y(e) + 4} textAnchor="end">
              {metres(e)}
            </text>
          ))}
        </g>
        <text x={LEFT + 6} y={TOP - 10} fontSize={14} fontWeight="bold" fill="#a4161a" className="section-stamp">
          {t("section.stamp")}
        </text>
      </svg>
      <p className="note" data-exaggeration={ratio.toFixed(2)}>
        {t("section.exaggeration", { ratio: formatNumber(ratio, ratio < 10 ? 1 : 0) })}
      </p>
    </>
  );
}

function Legend({ section }: { section: CrossSection }) {
  return (
    <ul className="section-legend">
      {section.units.map((u) => (
        <li key={u.index}>
          <span className="swatch" style={{ background: unitColour(u.index) }} />
          {u.label ?? t("section.noUnit")}
        </li>
      ))}
      <li>
        <span className="swatch unknown" />
        {t("section.legendUnknown")}
      </li>
      <li>
        <span className="swatch" style={{ background: WATER }} />
        {t("section.legendWater")}
      </li>
      <li>
        <span className="swatch" style={{ background: FAULT }} />
        {t("section.legendFault")}
      </li>
      <li>
        <span className="swatch" style={{ background: "#111" }} />
        {t("section.legendBorehole")}
      </li>
      <li className="note">{t("section.legendContacts")}</li>
      <li className="note">{t("section.legendConfidence")}</li>
    </ul>
  );
}

/** A failure's message, with the line's limits where it is about its length. */
function failureText(failure: SectionFailure, limits: MapConfig["section"]): string {
  switch (failure) {
    case "too_short":
      return t("section.error.too_short", { min: metres(limits.min_length_m) });
    case "too_long":
      return t("section.error.too_long", { max: metres(limits.max_length_m) });
    default:
      return t(`section.error.${failure}`);
  }
}

export function SectionPanel({
  view,
  limits,
  onClose,
}: {
  view: SectionView;
  limits: MapConfig["section"];
  onClose: () => void;
}) {
  const [picked, setPicked] = useState<Picked | null>(null);
  return (
    <section className="section-sheet" aria-labelledby="section-heading">
      <div className="section-header">
        <h2 id="section-heading">
          {t("section.heading")} <span className="section-badge">{t("section.stamp")}</span>
        </h2>
        <button type="button" className="secondary" onClick={onClose}>
          {t("section.close")}
        </button>
      </div>
      {view.state === "asking" && <p className="note">{t("section.asking")}</p>}
      {view.state === "failed" && (
        <p className="error" role="alert">
          {failureText(view.failure, limits)}
        </p>
      )}
      {view.state === "done" && (
        <>
          <p className="note">{t("section.interpretationNote")}</p>
          <Drawing section={view.section} onPick={setPicked} />
          <div className="section-explain" aria-live="polite">
            {picked ? <Explanation section={view.section} picked={picked} /> : <p className="note">{t("section.tapHint")}</p>}
          </div>
          <Legend section={view.section} />
          {view.section.gaps.length > 0 && (
            <ul className="missing">
              {view.section.gaps.map((gap) => (
                <li key={gap} data-gap={gap}>
                  {t(`section.gap.${gap}`)}
                </li>
              ))}
            </ul>
          )}
          <p className="note">
            {t("section.sources", {
              sources: [...new Set(Object.values(view.section.sources).map((s) => s.attribution))].join("; "),
              date: formatDate(
                Object.values(view.section.sources)
                  .map((s) => s.retrieved_at)
                  .sort()[0] ?? view.section.built_at,
              ),
            })}
          </p>
        </>
      )}
    </section>
  );
}
