// Copyright (c) 2026 Almoon-D. All rights reserved.
import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import type { AreaOfInterest, Interpretation } from "../api.ts";
import { areaHeading, EMPTY_SESSION, interpretationText, loadSession, saveSession, selectedArea, withArea } from "./areas.ts";

const fixture = (name: string) =>
  JSON.parse(readFileSync(new URL(`../../e2e/fixtures/${name}`, import.meta.url), "utf-8")) as AreaOfInterest;
const SANTIAGO = fixture("area-santiago.json");
const CAMPOS = fixture("area-sigpac-campos.json");
const POINT = fixture("area-point-daimiel.json");

describe("withArea", () => {
  it("adds and selects a new area", () => {
    const one = withArea(EMPTY_SESSION, SANTIAGO, 3);
    const two = withArea(one, CAMPOS, 3);
    expect(two.areas).toEqual([SANTIAGO, CAMPOS]);
    expect(selectedArea(two)).toBe(CAMPOS);
  });

  it("selects an area already listed instead of adding it again", () => {
    const session = withArea(withArea(EMPTY_SESSION, SANTIAGO, 3), CAMPOS, 3);
    const again = withArea(session, structuredClone(SANTIAGO), 3);
    expect(again.areas).toHaveLength(2);
    expect(again.selected).toBe(0);
  });

  it("drops the oldest from a full list", () => {
    const full = [SANTIAGO, CAMPOS, POINT].reduce((session, area) => withArea(session, area, 2), EMPTY_SESSION);
    expect(full.areas).toEqual([CAMPOS, POINT]);
    expect(full.selected).toBe(1);
  });

  it("has no selection when empty", () => {
    expect(selectedArea(EMPTY_SESSION)).toBeNull();
  });
});

describe("the session's storage", () => {
  function memory(): Pick<Storage, "getItem" | "setItem"> {
    const items = new Map<string, string>();
    return { getItem: (key) => items.get(key) ?? null, setItem: (key, value) => void items.set(key, value) };
  }

  it("keeps the list across a reload", () => {
    const storage = memory();
    const session = withArea(withArea(EMPTY_SESSION, SANTIAGO, 3), CAMPOS, 3);
    saveSession(session, storage);
    expect(loadSession(storage)).toEqual(session);
  });

  it("starts empty when there is nothing, something else, or no storage", () => {
    const storage = memory();
    expect(loadSession(storage)).toEqual(EMPTY_SESSION);
    storage.setItem("subphora.session-areas", "not json");
    expect(loadSession(storage)).toEqual(EMPTY_SESSION);
    storage.setItem("subphora.session-areas", '{"areas":3,"selected":0}');
    expect(loadSession(storage)).toEqual(EMPTY_SESSION);
    expect(loadSession(null)).toEqual(EMPTY_SESSION);
  });

  it("clamps a selection beyond the list", () => {
    const storage = memory();
    storage.setItem("subphora.session-areas", JSON.stringify({ areas: [SANTIAGO], selected: 4 }));
    expect(loadSession(storage).selected).toBe(0);
  });

  it("survives a storage that refuses to write", () => {
    const refusing = {
      setItem: () => {
        throw new DOMException("full", "QuotaExceededError");
      },
    };
    expect(() => {
      saveSession(EMPTY_SESSION, refusing);
    }).not.toThrow();
  });
});

describe("names", () => {
  it("heads each area by what it is", () => {
    expect(areaHeading(SANTIAGO)).toBe("Parcela 7279701NH3477G");
    expect(areaHeading(CAMPOS)).toBe("Recinto SIGPAC: 34:48:0:0:13:12:1");
    expect(areaHeading({ ...POINT, origin: "drawn_polygon", label: null })).toBe("Polígono dibujado");
  });

  it("describes each reading of a search", () => {
    const utm: Interpretation = {
      kind: "coordinates",
      origin: "coordinates",
      label: "30 440000 4474000",
      detail: "EPSG:25830",
      position: [-3.7072, 40.41446],
      resolve: "/api/aoi/point?…",
    };
    expect(interpretationText(utm)).toBe(
      "Coordenadas 30 440000 4474000 (UTM huso 30, ETRS89) → lat. 40,41446; lon. -3,70720",
    );
    const place: Interpretation = {
      kind: "place",
      origin: "municipality",
      label: "Daimiel, Ciudad Real",
      detail: "Ciudad Real",
      position: null,
      resolve: "/api/aoi/place?…",
    };
    expect(interpretationText(place)).toBe("Municipio: Daimiel, Ciudad Real (Ciudad Real)");
    expect(interpretationText({ ...place, detail: null })).toBe("Municipio: Daimiel, Ciudad Real");
    expect(interpretationText({ ...utm, detail: null, position: null })).toBe("Coordenadas 30 440000 4474000");
  });
});
