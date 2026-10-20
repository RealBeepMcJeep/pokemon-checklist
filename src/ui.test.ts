import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ui.ts reads the viewport when it loads; a phone-sized one is enough here.
vi.stubGlobal("window", {
  matchMedia: () => ({ matches: false, addEventListener: () => {} }),
  addEventListener: () => {},
});

const { reset, exportJSON } = await import("./ui");
const state = await import("./state");
const { STATE_VERSION } = await import("./domain");

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

it("redirects removed stock SOS leaf hashes to a verified reachable native caller", async () => {
  const { safeId } = await import("./domain");
  const { jumpTo } = await import("./ui");
  state.mode.value = "sun";
  state.unlocks.value = ["sos"];
  const place = state.activeEncounters.peek().islands.flatMap(island => island.locations).find(item => item.name === "Route 1")!;
  const leaf = place.groups.flatMap(group => group.encounters).find(row => row.speciesId === 10 && row.sosRules?.length)!;
  expect(leaf).toBeTruthy();
  const callers = new Set(leaf.sosRules!.flatMap(rule => rule.callerIds).map(id => `encounter-${safeId(id)}`));
  expect(callers.size).toBeGreaterThan(0);
  const before = state.exportState();
  const replaceState = vi.fn();
  const target = { closest: () => null, parentElement: null, isConnected: true, scrollIntoView: vi.fn(), focus: vi.fn() };
  vi.stubGlobal("document", { getElementById: (id: string) => callers.has(id) ? target : null });
  vi.stubGlobal("history", { replaceState });
  vi.stubGlobal("requestAnimationFrame", vi.fn());
  jumpTo(`#encounter-${safeId(leaf.id)}`, place.id);
  expect(replaceState).toHaveBeenCalledOnce();
  expect(callers.has(String(replaceState.mock.calls[0][2]).slice(1))).toBe(true);
  expect(state.exportState()).toEqual(before);
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

it("downloads a correctly versioned backup that reimports exact form favorites", async () => {
  state.setFormFavorite(52, "kanto", true);
  const before = state.exportState();
  const link = { href: "", download: "", click: vi.fn(), remove: vi.fn() };
  let saved: Blob | undefined;
  vi.stubGlobal("document", { createElement: () => link, body: { appendChild: vi.fn() } });
  const create = vi.spyOn(URL, "createObjectURL").mockImplementation(blob => {
    saved = blob as Blob;
    return "blob:synthetic-backup";
  });
  const revoke = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
  vi.useFakeTimers();
  try {
    exportJSON();
    expect(link.download).toBe(`pokemon-checklist-state-v${STATE_VERSION}.json`);
    expect(link.click).toHaveBeenCalledOnce();
    expect(state.parseState(await saved!.text())).toEqual(before);
    expect(state.exportState()).toEqual(before);
    vi.runAllTimers();
  } finally {
    vi.clearAllTimers();
    vi.useRealTimers();
    create.mockRestore();
    revoke.mockRestore();
  }
});
