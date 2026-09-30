import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ui.ts reads the viewport when it loads; a phone-sized one is enough here.
vi.stubGlobal("window", {
  matchMedia: () => ({ matches: false, addEventListener: () => {} }),
  addEventListener: () => {},
});

const { reset } = await import("./ui");
const state = await import("./state");

beforeEach(() => {
  const store = new Map<string, string>();
  (globalThis as { localStorage?: unknown }).localStorage = {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => void store.set(key, value),
    removeItem: (key: string) => void store.delete(key),
  };
  state.readOnly.value = null;
  state.applyState(state.defaultState());
  state.cycleSpecies(25);
});

afterEach(() => {
  vi.unstubAllGlobals();
  state.readOnly.value = null;
});

describe("Reset after its confirm dialog", () => {
  it("resets when this tab still edits", async () => {
    vi.stubGlobal("confirm", () => true);
    await reset();
    expect(state.speciesStatus(25)).toBe("none");
  });

  it("does nothing if another tab took editing while the dialog was open", async () => {
    vi.stubGlobal("confirm", () => {
      // The steal happened while the dialog blocked this tab; its news is queued.
      setTimeout(() => state.setEditable(false), 0);
      return true;
    });
    await reset();
    expect(state.speciesStatus(25)).toBe("caught");
    expect(state.notice.value.message).toMatch(/edited in another tab/);
  });
});
