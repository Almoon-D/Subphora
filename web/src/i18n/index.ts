// Copyright (c) 2026 Almoon-D. All rights reserved.
// Translation: one catalogue per language; Spanish is the only one today.
import { es, type MessageKey } from "./es.ts";

export type { MessageKey };

export const LOCALE = "es-ES";
export const LANGUAGE = "es";

type Params = Readonly<Record<string, string | number>>;

/** The message for a key built at run time (`layer.<id>`), or `fallback` when it has none. */
export function lookup(key: string, fallback: string): string {
  return (es as Readonly<Record<string, string>>)[key] ?? fallback;
}

/** The message for a key built at run time, with each `{name}` replaced by `params[name]`
 * (a missing one left as it is), or `fallback` when the key has none. */
export function lookupWith(key: string, params: Params, fallback: string): string {
  const template = (es as Readonly<Record<string, string>>)[key];
  if (template === undefined) {
    return fallback;
  }
  return template.replace(/\{(\w+)\}/g, (placeholder, name: string) => {
    const value = params[name];
    if (value === undefined) {
      return placeholder;
    }
    return typeof value === "number" ? formatNumber(value) : value;
  });
}

/** The text of a server's translated field in the interface's language, else English. */
export function translated(text: Readonly<Record<string, string>>): string {
  return text[LANGUAGE] ?? text.en ?? Object.values(text)[0] ?? "";
}

/** The message for `key`, with each `{name}` replaced by `params[name]`. */
export function t(key: MessageKey, params: Params = {}): string {
  return es[key].replace(/\{(\w+)\}/g, (_placeholder, name: string) => {
    const value = params[name];
    if (value === undefined) {
      throw new Error(`missing parameter ${name} for message ${key}`);
    }
    return typeof value === "number" ? formatNumber(value) : value;
  });
}

export function formatNumber(value: number, fractionDigits = 0): string {
  return new Intl.NumberFormat(LOCALE, {
    maximumFractionDigits: fractionDigits,
    minimumFractionDigits: fractionDigits,
    useGrouping: true,
  }).format(value);
}

/** An area in m², and in hectares once it reaches one. */
export function formatArea(squareMetres: number): string {
  const metres = `${formatNumber(squareMetres)} m²`;
  const hectare = 10_000;
  if (squareMetres < hectare) {
    return metres;
  }
  return `${metres} (${formatNumber(squareMetres / hectare, 2)} ha)`;
}

/** A size in bytes, in megabytes with one decimal. */
export function formatMegabytes(bytes: number): string {
  const megabyte = 1_048_576;
  return `${formatNumber(bytes / megabyte, 1)} MB`;
}

/** A date in the viewer's own time zone. */
export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat(LOCALE, { dateStyle: "long" }).format(new Date(iso));
}
