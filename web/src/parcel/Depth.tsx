// Copyright (c) 2026 Almoon-D. All rights reserved.
// The depth to water at a spot, with its range, the water table it comes from and that
// table's sources (or why the depth is unknown); and, at a tapped point, the same depth with
// the owner's wells read at rest as private levels of their own groundwater body, beside
// the public one, with the readings that did not enter and why (session 17).
import type { DepthEstimate, DepthWithWells, LevelLeftOut } from "../api.ts";
import { formatDate, formatNumber, lookup, t } from "../i18n/index.ts";

const metres = (value: number) => formatNumber(value, 0);

export function Depth({ depth }: { depth: DepthEstimate }) {
  const { water_table: table, sources } = depth;
  const own = depth.own_levels;
  if (depth.state === "unknown" || table === null || (sources.length === 0 && own.length === 0) || depth.depth_m === null) {
    return (
      <>
        <p className="note depth" data-depth="unknown" data-reason={depth.reason ?? ""}>
          {lookup(`detailed.depthUnknown.${depth.reason ?? ""}`, t("detailed.depthUnknown.not_imported"))}
        </p>
        {depth.karst && <p className="note karst">{t("detailed.karst")}</p>}
      </>
    );
  }
  return (
    <div className="depth" data-depth="estimated" data-depth-m={depth.depth_m} data-own-levels={own.length}>
      <p>
        {t("detailed.depth", {
          depth: metres(depth.depth_m),
          low: metres(depth.low_m ?? depth.depth_m),
          high: metres(depth.high_m ?? depth.depth_m),
        })}
      </p>
      {depth.karst && <p className="warning karst">{t("detailed.karst")}</p>}
      <p className="note">
        {t("detailed.depthDetail", {
          ground: metres(depth.ground_m ?? 0),
          table: metres(table.elevation_m),
          count: table.piezometers - own.length,
          body: table.body_label || table.body,
          nearest: `${formatNumber(table.nearest_m / 1000, 1)} km`,
        })}
      </p>
      <ul className="note sources">
        {sources.map((source) => (
          <li key={source.service_id} data-levels-source={source.service_id}>
            {t("detailed.depthSource", {
              from: formatDate(source.levels_from),
              to: formatDate(source.levels_to),
              attribution: source.attribution,
            })}
          </li>
        ))}
        {own.map((level) => (
          <li key={level.well_id} data-own-level={level.well_id}>
            {t("detailed.ownLevel", {
              distance: metres(level.distance_m),
              depth: formatNumber(level.ground_m - level.level_m, 2),
              count: level.readings,
              from: formatDate(level.first),
              to: formatDate(level.last),
            })}
          </li>
        ))}
      </ul>
    </div>
  );
}

const LEFT_OUT_ORDER: readonly LevelLeftOut[] = [
  "pumping",
  "pump_unknown",
  "recovering",
  "too_old",
  "outside_area",
  "no_ground_elevation",
  "outside_bodies",
];

/** The depth at a tapped point, public, and with the owner's readings at rest. */
export function DepthHere({ depth }: { depth: DepthWithWells }) {
  const own = depth.with_wells.own_levels.length;
  const left = LEFT_OUT_ORDER.flatMap((reason) => {
    const count = depth.left_out[reason] ?? 0;
    return count > 0 ? [t(`detailed.leftOut.${reason}`, { count })] : [];
  });
  return (
    <div className="depth-here" data-own-levels={own}>
      <h4>{t("detailed.depthHere")}</h4>
      <p className="note">{t("detailed.depthPublic")}</p>
      <div data-depth-kind="public">
        <Depth depth={depth.public} />
      </div>
      {own > 0 ? (
        <>
          <p className="note">{t("detailed.depthWithWells")}</p>
          <div data-depth-kind="with-wells">
            <Depth depth={depth.with_wells} />
          </div>
        </>
      ) : (
        <p className="note" data-depth-kind="no-wells">
          {t("detailed.depthNoWells")}
        </p>
      )}
      {left.length > 0 && (
        <p className="note" data-left-out>
          {t("detailed.leftOut", { list: left.join("; ") })}
        </p>
      )}
    </div>
  );
}
