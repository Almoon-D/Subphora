// Copyright (c) 2026 Almoon-D. All rights reserved.
// The national water-potential map in the browser: which of its layers are drawn, whether a
// tap asks for the explanation, and how its legends and values read.
import type { InputValue, LegendClass, NationalMap } from "../api.ts";
import { formatNumber, t } from "../i18n/index.ts";
import type { MapLayers } from "./layers.ts";

/** The national layers drawn, in drawing order: what the map applied. */
export function describeNational(national: NationalMap | null, layers: MapLayers): string {
  if (!national?.built) {
    return "";
  }
  return national.layers
    .filter((l) => layers.national[l.id]?.visible)
    .map((l) => l.id)
    .join(" ");
}

/** Whether a tap asks the national map: built, a layer of it switched on, and the point in
 * the box of a region built (the API decides exactly, by the region's boundary). */
export function nationalAnswersTap(national: NationalMap | null, layers: MapLayers, lon: number, lat: number): boolean {
  if (!national?.built || !national.layers.some((l) => layers.national[l.id]?.visible)) {
    return false;
  }
  return national.regions.some(({ bbox: [west, south, east, north] }) => west <= lon && lon <= east && south <= lat && lat <= north);
}

const DIGITS: Readonly<Record<string, number>> = { index: 1, confidence: 1, twi: 0, deg: 0, m: 0, pct: 0, mm_yr: 0, ndvi: 2 };

/** A number in a unit, as the legend and the explanation write it. */
export function formatQuantity(value: number, unit: string): string {
  const digits = DIGITS[unit] ?? 2;
  const number = formatNumber(value, unit === "index" || unit === "confidence" ? 2 : digits);
  switch (unit) {
    case "deg":
      return `${number}°`;
    case "m":
      return value >= 1000 ? `${formatNumber(value / 1000, 1)} km` : `${number} m`;
    case "pct":
      return `${number} %`;
    case "km_km2":
      return `${number} km/km²`;
    case "mm_yr":
      return `${number} mm/año`;
    default:
      return number;
  }
}

/** "< 0,20", "0,20 – 0,40" or "≥ 0,80". */
export function legendText(item: LegendClass, unit: string): string {
  if (item.min === null && item.max !== null) {
    return `< ${formatQuantity(item.max, unit)}`;
  }
  if (item.max === null && item.min !== null) {
    return `≥ ${formatQuantity(item.min, unit)}`;
  }
  if (item.min !== null && item.max !== null) {
    return `${formatQuantity(item.min, unit)} – ${formatQuantity(item.max, unit)}`;
  }
  return "";
}

/** An input's value at the tapped cell, as text. */
export function valueText(value: InputValue): string {
  if (value.absent) {
    return t("explain.absent");
  }
  if (value.category !== null) {
    return value.label && value.label !== value.category ? `${value.category} (${value.label})` : value.category;
  }
  if (value.number !== null) {
    const quantity = formatQuantity(value.number, value.unit ?? "");
    return value.at_least ? t("explain.atLeast", { value: quantity }) : quantity;
  }
  return "";
}

/** A 0–1 share as a percentage. */
export function percent(share: number): string {
  return `${formatNumber(share * 100)}\u00a0%`;
}
