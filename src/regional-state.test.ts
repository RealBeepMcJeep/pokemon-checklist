import { beforeEach, describe, expect, it } from "vitest";
import { applyState, cycleForm, defaultState, exportState, readOnly, toggleStar, isStarred } from "./state";

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
