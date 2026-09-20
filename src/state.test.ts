import { beforeEach, describe, expect, it } from "vitest";
import {
  activeSaveKey,
  applyState,
  cycleSpecies,
  exportState,
  initializeState,
  interpretStoredState,
  notice,
  persist,
  isStarred,
  resetState,
  setLocalChangeListener,
  setSyncAccount,
  starred,
  storageAvailable,
  toggleStar,
} from "./state";
import { STORAGE_KEY } from "./domain";

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

describe("account saves", () => {
  let store: Map<string, string>;

  beforeEach(() => {
    store = installStorage();
    setSyncAccount(null);
    resetState();
  });

  it("keeps the device's own key while signed out", () => {
    expect(activeSaveKey()).toBe(STORAGE_KEY);
    cycleSpecies(25);
    expect(exportState().species["25"]).toBe("caught");
  });

  it("namespaces the save per account and adopts what the device holds", () => {
    cycleSpecies(25);
    const deviceSave = store.get(STORAGE_KEY);
    expect(deviceSave).toContain("caught");

    setSyncAccount("uid-dad");

    expect(activeSaveKey()).toBe(`${STORAGE_KEY}:uid-dad`);
    // Adopted: the account now holds the progress this device already had.
    expect(store.get(`${STORAGE_KEY}:uid-dad`)).toBe(deviceSave);
    // And the device's own save is untouched, so signing out returns to it.
    expect(store.get(STORAGE_KEY)).toBe(deviceSave);
    expect(exportState().species["25"]).toBe("caught");
  });

  it("shows an account's existing save instead of adopting over it", () => {
    const accountSave = JSON.stringify({
      schemaVersion: 3,
      species: { "1": "caught" },
      forms: {},
      starred: [],
      settings: { forms: false, mode: "photonic-prismatic" },
    });
    store.set(`${STORAGE_KEY}:uid-dad`, accountSave);
    cycleSpecies(25);

    setSyncAccount("uid-dad");

    expect(exportState().species["1"]).toBe("caught");
    expect(exportState().species["25"]).toBeUndefined();
    expect(store.get(`${STORAGE_KEY}:uid-dad`)).toBe(accountSave);
  });

  it("returns to the device's save when signing out", () => {
    cycleSpecies(25);
    setSyncAccount("uid-dad");
    cycleSpecies(1);
    expect(exportState().species["1"]).toBe("caught");

    setSyncAccount(null);

    expect(activeSaveKey()).toBe(STORAGE_KEY);
    expect(exportState().species["25"]).toBe("caught");
    expect(exportState().species["1"]).toBeUndefined();
  });

  it("does not reload from storage when the same account is set twice", () => {
    setSyncAccount("uid-dad");
    cycleSpecies(1);
    setSyncAccount("uid-dad");
    expect(exportState().species["1"]).toBe("caught");
  });

  it("tells the listener about local changes, never about a remote apply", () => {
    let calls = 0;
    setLocalChangeListener(() => {
      calls += 1;
    });

    cycleSpecies(25);
    expect(calls).toBe(1);

    // A state that arrived from elsewhere is not a local change, so publishing
    // must not be triggered by applying it.
    applyState({
      schemaVersion: 3,
      species: { "150": "caught" },
      forms: {},
      starred: [],
      settings: { forms: false, mode: "moon" },
    });
    expect(calls).toBe(1);

    setLocalChangeListener(null);
  });
});

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

describe("storage failures", () => {
  it("still notifies sync of the current state when persistence fails", () => {
    installStorage();
    storageAvailable.value = true;
    setLocalChangeListener(null);
    resetState();

    let received: ReturnType<typeof exportState> | null = null;
    (globalThis as { localStorage?: unknown }).localStorage = {
      getItem: () => null,
      setItem: () => {
        throw new Error("quota exceeded");
      },
      removeItem: () => {},
    };
    setLocalChangeListener((state) => {
      received = state;
    });

    cycleSpecies(25);

    expect(received).not.toBeNull();
    expect(received!.species["25"]).toBe("caught");
    expect(storageAvailable.value).toBe(false);
    expect(notice.value.kind).toBe("error");
    expect(notice.value.message).toMatch(/disappear when this tab closes/);
    setLocalChangeListener(null);
    storageAvailable.value = true;
  });

  it("keeps storage errors inside the state boundary", () => {
    (globalThis as { localStorage?: unknown }).localStorage = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    };
    expect(() => initializeState()).not.toThrow();
    expect(() => persist()).not.toThrow();
    storageAvailable.value = true;
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
