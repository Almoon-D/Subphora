// Copyright (c) 2026 Almoon-D. All rights reserved.
import { describe, expect, it } from "vitest";

import type { Finding, LegalStatus } from "../api.ts";
import { findingNotes, findingText, isBlocked, sortedFindings, sourceText } from "./legal.ts";

function finding(changes: Partial<Finding>): Finding {
  return {
    rule_id: "rdph-87-2-distance",
    area: "ES",
    title: { en: "Minimum distance", es: "Distancia mínima" },
    source: {
      name: "Reglamento del Dominio Público Hidráulico",
      url: "https://www.boe.es/",
      article: "art. 87.2",
      published: "2026-06-03",
      checked: "2026-11-24",
    },
    outcome: "clear",
    message: "point_far_enough",
    values: { distance: 248.8, minimum: 100, method: "inventory" },
    uncertain: null,
    ...changes,
  };
}

describe("a legal finding", () => {
  it("fills its message with its values", () => {
    expect(findingText(finding({}))).toBe("El punto de agua inventariado más cercano está a 249 m (mínimo: 100 m).");
  });

  it("translates the reason a body triggers a rule", () => {
    const text = findingText(
      finding({ message: "authorisation_body", values: { body: "Mancha", because: "marked:andalusia-preventive-control" } }),
    );
    expect(text).toBe("Masa Mancha: la masa está en control preventivo.");
  });

  it("falls back to its key for a message the interface does not know", () => {
    expect(findingText(finding({ message: "new_message" }))).toBe("new_message");
  });

  it("says how its distance was measured and what it assumed", () => {
    const notes = findingNotes(
      finding({ values: { method: "terrain", assumed: "strictest", official: "unread" }, uncertain: { en: "x", es: "Duda" } }),
    );
    expect(notes).toHaveLength(4);
    expect(notes[0]).toContain("modelo del terreno");
    expect(notes[1]).toContain("más exigente");
    expect(notes[2]).toContain("dominio público hidráulico");
    expect(notes[3]).toBe("Duda");
  });

  it("names its source with the article and dates", () => {
    const text = sourceText(finding({}));
    expect(text).toContain("art. 87.2");
    expect(text).toContain("2026");
  });

  it("is shown with what stops a well first", () => {
    const order = sortedFindings([
      finding({ outcome: "clear" }),
      finding({ outcome: "blocks" }),
      finding({ outcome: "notice" }),
      finding({ outcome: "authorisation" }),
    ]).map((f) => f.outcome);
    expect(order).toEqual(["blocks", "authorisation", "notice", "clear"]);
  });
});

describe("a legal status", () => {
  it("marks a spot only where a rule forbids the well", () => {
    const status = { state: "probably_not_allowed" } as LegalStatus;
    expect(isBlocked(status)).toBe(true);
    expect(isBlocked({ ...status, state: "rules_not_loaded" })).toBe(false);
  });
});
