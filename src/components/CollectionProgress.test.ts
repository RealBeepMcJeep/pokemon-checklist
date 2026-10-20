import { afterEach, expect, it, vi } from "vitest";
afterEach(() => vi.unstubAllGlobals());
it("keeps device preferences across account, mode and tracking changes outside player and wire records", async () => {
  vi.resetModules();
  const values = new Map<string, string>();
  vi.stubGlobal("localStorage", { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => { values.set(key, value); }, removeItem: (key: string) => { values.delete(key); } });
  const state = await import("../state");
  const view = await import("./CollectionProgress");
  const { entriesFromState } = await import("../sync/records");
  expect(view.progressMetric.value).toBe("owned");
  state.formsTracked.value = true;
  expect(view.progressMetric.value).toBe("living");
  view.selectProgressMetric("registered");
  for (const uid of ["fixture-account-a", "fixture-account-b", null]) {
    state.setSyncAccount(uid, { adopt: false });
    expect(view.progressMetric.value).toBe("registered");
    const snapshot = state.exportState(), wire = entriesFromState(snapshot, 1, "fixture-client");
    view.selectProgressMetric("owned");
    expect(state.exportState()).toEqual(snapshot);
    expect(entriesFromState(state.exportState(), 1, "fixture-client")).toEqual(wire);
    state.formsTracked.value = !state.formsTracked.value;
    state.mode.value = state.mode.value === "sun" ? "moon" : "sun";
    expect(view.progressMetric.value).toBe("owned");
    view.selectProgressMetric("registered");
  }
  expect(values.get("pokemon-checklist-progress-v1")).toBe("registered");
});
