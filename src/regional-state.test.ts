import { beforeEach, describe, expect, it } from "vitest";
import { applyState, cycleForm, defaultState, exportState, readOnly, toggleStar, isStarred, toggleForms } from "./state";
import { aggregateRegionalStatus, hasUnresolvedRegionalOwnership } from "./regional";

beforeEach(() => {
  const values = new Map<string, string>();
  globalThis.localStorage = { getItem: key => values.get(key) ?? null,
    setItem: (key, value) => { values.set(key, value); }, removeItem: key => { values.delete(key); },
    clear: () => values.clear(), key: index => [...values.keys()][index] ?? null,
    get length() { return values.size; },
  };
  readOnly.value = null;
  applyState({ ...defaultState(), species: { "52": "caught" }, forms: { "52:alolan": "caught", "52:kanto": "caught" } });
});

describe("independent regional edits", () => {
  it("favorites one owned form without favoriting its owned counterpart", () => {
    toggleStar(52, "alolan");
    expect(exportState()).toMatchObject({ starred: [], starredForms: ["52:alolan"] });
    expect(isStarred(52, "kanto")).toBe(false);
    toggleStar(52, "kanto");
    toggleStar(52, "alolan");
    expect(exportState()).toMatchObject({ starred: [], starredForms: ["52:kanto"] });
  });
  it("folds only regional forms into one aggregate and never downgrades legacy ownership", () => {
    expect(aggregateRegionalStatus(["none", "none"])).toBe("none");
    expect(aggregateRegionalStatus(["seen", "none"])).toBe("seen");
    expect(aggregateRegionalStatus(["seen", "caught"])).toBe("caught");
    // A generic record with no form evidence is preserved, not assigned to Kanto.
    expect(hasUnresolvedRegionalOwnership("caught", ["none", "none"])).toBe(true);
    expect(hasUnresolvedRegionalOwnership("caught", ["none", "caught"])).toBe(false);
    expect(hasUnresolvedRegionalOwnership("none", ["none", "none"])).toBe(false);
    // A Seen form is not evidence of which form a generic Caught record owns.
    expect(hasUnresolvedRegionalOwnership("caught", ["seen", "none"])).toBe(true);
    expect(hasUnresolvedRegionalOwnership("seen", ["seen", "none"])).toBe(false);
  });
  it("keeps generic legacy ownership unresolved rather than assigning it to a form", () => {
    applyState({ ...defaultState(), species: { "52": "caught" }, forms: {} });
    expect(exportState().forms).toEqual({});
    expect(hasUnresolvedRegionalOwnership(exportState().species["52"], [
      exportState().forms["52:alolan"] ?? "none", exportState().forms["52:kanto"] ?? "none"])).toBe(true);
    // Merely enabling tracking must not fabricate a form record.
    toggleForms();
    expect(exportState().forms).toEqual({});
    expect(exportState().species["52"]).toBe("caught");
  });
  it("toggles tracking without touching any ownership or favorite record", () => {
    applyState({ ...defaultState(), schemaVersion: 5, species: { "52": "caught" }, forms: { "52:alolan": "caught" },
      starredForms: ["52:alolan"] });
    const before = exportState();
    toggleForms();
    expect(exportState().species).toEqual(before.species);
    expect(exportState().forms).toEqual(before.forms);
    expect(exportState()).toMatchObject({ starred: before.starred, starredForms: ["52:alolan"] });
  });
  it("keeps a species owned only while at least one regional form remains owned", () => {
    cycleForm("52:alolan");
    expect(exportState().species["52"]).toBe("caught");
    cycleForm("52:kanto");
    expect(exportState().species["52"]).toBe("seen");
    cycleForm("52:alolan");
    cycleForm("52:kanto");
    expect(exportState().species["52"]).toBeUndefined();
  });
});
