import { beforeEach, describe, expect, it } from "vitest";
import {
  exportState,
  initializeState,
  interpretStoredState,
  isStarred,
  resetState,
  starred,
  toggleStar,
} from "./state";

const current = JSON.stringify({
  schemaVersion: 3,
  species: { "731": "caught" },
  forms: {},
  starred: [25],
  settings: { forms: false, mode: "photonic-prismatic" },
});

/** Minimal localStorage so state.ts can persist outside a browser. */
function installStorage(seed: Record<string, string> = {}): Map<string, string> {
  const store = new Map(Object.entries(seed));
  (globalThis as { localStorage?: unknown }).localStorage = {
    getItem: (key: string) => (store.has(key) ? store.get(key)! : null),
    setItem: (key: string, value: string) => void store.set(key, value),
    removeItem: (key: string) => void store.delete(key),
  };
  return store;
}

describe("cross-tab state", () => {
  it("applies a state another tab saved", () => {
    const synced = interpretStoredState(current);
    expect(synced.kind).toBe("apply");
    if (synced.kind !== "apply") return;
    expect(synced.state.species["731"]).toBe("caught");
    expect(synced.state.starred).toEqual([25]);
  });

  it("treats a removed save as cleared rather than unreadable", () => {
    expect(interpretStoredState(null).kind).toBe("cleared");
  });

  it("ignores unparseable payloads instead of wiping progress", () => {
    expect(interpretStoredState("{not json").kind).toBe("ignore");
  });

  it("ignores parseable payloads that are not a valid state", () => {
    expect(interpretStoredState(JSON.stringify({ species: {} })).kind).toBe(
      "ignore",
    );
  });

  it("ignores a state naming a Pokémon outside the National Dex", () => {
    const invalid = JSON.stringify({
      schemaVersion: 3,
      species: { "808": "caught" },
      forms: {},
      starred: [],
      settings: { forms: false, mode: "photonic-prismatic" },
    });
    expect(interpretStoredState(invalid).kind).toBe("ignore");
  });

  it("migrates a v1 payload written by an older tab", () => {
    const legacy = JSON.stringify({
      schemaVersion: 1,
      species: { "25": "seen" },
      forms: {},
      settings: { forms: false },
    });
    const synced = interpretStoredState(legacy);
    expect(synced.kind).toBe("apply");
    if (synced.kind !== "apply") return;
    expect(synced.state.species["25"]).toBe("seen");
    expect(synced.state.settings.mode).toBe("photonic-prismatic");
    expect(synced.state.starred).toEqual([]);
  });

  it("migrates a v2 payload without dropping progress", () => {
    const previous = JSON.stringify({
      schemaVersion: 2,
      species: { "25": "seen", "731": "caught" },
      forms: {},
      settings: { forms: true, mode: "ultra-sun" },
    });
    const synced = interpretStoredState(previous);
    expect(synced.kind).toBe("apply");
    if (synced.kind !== "apply") return;
    expect(synced.state.species).toEqual({ "25": "seen", "731": "caught" });
    expect(synced.state.settings).toEqual({ forms: true, mode: "ultra-sun" });
    expect(synced.state.starred).toEqual([]);
  });
});

describe("starred species", () => {
  beforeEach(() => {
    // Reset explicitly: the module-level signals are shared between tests, so
    // leaving stars behind would make these order-dependent.
    installStorage();
    resetState();
  });

  it("starts with nothing starred", () => {
    expect(exportState().starred).toEqual([]);
    expect(isStarred(731)).toBe(false);
  });

  it("pins a species and releases it again", () => {
    toggleStar(731);
    expect(isStarred(731)).toBe(true);
    expect(exportState().starred).toEqual([731]);

    toggleStar(731);
    expect(isStarred(731)).toBe(false);
    expect(exportState().starred).toEqual([]);
  });

  it("keeps the starred list in ascending order however it is filled", () => {
    toggleStar(731);
    toggleStar(25);
    toggleStar(1);
    expect(starred.value).toEqual([1, 25, 731]);
  });

  it("writes stars to the current storage key so they survive a reload", () => {
    const store = installStorage();
    toggleStar(25);
    const raw = store.get("pokemon-checklist-state-v3");
    expect(raw).toBeTruthy();
    expect(JSON.parse(raw!).starred).toEqual([25]);
  });
});

describe("storage migration", () => {
  it("upgrades a v2 save onto the current key without losing progress", () => {
    const store = installStorage({
      "pokemon-checklist-state-v2": JSON.stringify({
        schemaVersion: 2,
        species: { "25": "seen" },
        forms: {},
        settings: { forms: false, mode: "sun" },
      }),
    });

    initializeState();

    expect(exportState().species["25"]).toBe("seen");
    expect(exportState().settings.mode).toBe("sun");
    expect(exportState().starred).toEqual([]);

    const upgraded = store.get("pokemon-checklist-state-v3");
    expect(upgraded).toBeTruthy();
    expect(JSON.parse(upgraded!).schemaVersion).toBe(3);
    // The legacy entry stays put so an older build still finds its own data.
    expect(store.get("pokemon-checklist-state-v2")).toBeTruthy();
  });
});
