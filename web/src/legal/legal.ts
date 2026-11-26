// Copyright (c) 2026 Almoon-D. All rights reserved.
// The texts of a legal status: each finding's message from its key and values, the notes on
// how its distances were measured, and the order findings are shown in (what stops or
// conditions a well first).
import type { Finding, LegalStatus, Outcome } from "../api.ts";
import { formatDate, lookup, lookupWith, translated } from "../i18n/index.ts";

const ORDER: readonly Outcome[] = ["blocks", "authorisation", "check", "notice", "clear", "not_applicable"];

/** Findings, the ones that stop or condition the well first. */
export function sortedFindings(findings: readonly Finding[]): Finding[] {
  return [...findings].sort((a, b) => ORDER.indexOf(a.outcome) - ORDER.indexOf(b.outcome));
}

/** The finding's message, with its values (a reason code translated too). */
export function findingText(finding: Finding): string {
  const values: Record<string, string | number> = { ...finding.values };
  if (typeof values.because === "string") {
    values.because = lookup(`legal.because.${values.because.split(":")[0] ?? ""}`, values.because);
  }
  return lookupWith(`legal.message.${finding.message}`, values, finding.message);
}

/** The notes on how the finding's measures were taken or assumed. */
export function findingNotes(finding: Finding): string[] {
  const notes: string[] = [];
  const { method, assumed, official } = finding.values;
  if (typeof method === "string") {
    notes.push(lookup(`legal.method.${method}`, method));
  }
  if (assumed === "strictest") {
    notes.push(lookup("legal.assumed.strictest", assumed));
  }
  if (official === "unread") {
    notes.push(lookup("legal.official.unread", official));
  }
  if (finding.uncertain) {
    notes.push(translated(finding.uncertain));
  }
  return notes;
}

/** Where the rule is written, and when it was published and read. */
export function sourceText(finding: Finding): string {
  const { source } = finding;
  return lookupWith(
    "legal.source",
    {
      name: source.name,
      article: source.article,
      published: formatDate(source.published),
      checked: formatDate(source.checked),
    },
    source.name,
  );
}

/** Whether a candidate lies where a rule forbids the well. */
export function isBlocked(status: LegalStatus): boolean {
  return status.state === "probably_not_allowed";
}
