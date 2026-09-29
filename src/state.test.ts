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
  restoreState,
  savedNotice,
  setLocalChangeListener,
  setLocalReplaceListener,
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
  beforeEach(() => {
    // storageAvailable is a module-level signal shared between tests; assert
    // each test's starting state instead of relying on a previous test's
    // cleanup line to have left it true.
    storageAvailable.value = true;
  });

  it("still notifies sync of the current state when persistence fails", () => {
    installStorage();
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

const saveOf = (species: Record<string, string>, extra: object = {}) =>
  JSON.stringify({
    schemaVersion: 3,
    species,
    forms: {},
    starred: [],
    settings: { forms: false, mode: "photonic-prismatic" },
    ...extra,
  });
// A save this build cannot read, such as one written by a newer build.
const FUTURE = JSON.stringify({ schemaVersion: 4, species: { "25": "caught" } });

describe("a save that cannot be read never hides a good one", () => {
  beforeEach(() => {
    installStorage();
    setSyncAccount(null);
    resetState();
  });

  it("loads the last good copy and keeps the unreadable save aside", () => {
    const store = installStorage();
    cycleSpecies(150); // written as the save and as its last good copy
    store.set(STORAGE_KEY, FUTURE);
    applyState(JSON.parse(saveOf({})));

    initializeState();

    expect(exportState().species).toEqual({ "150": "caught" });
    expect(store.get(`${STORAGE_KEY}:unreadable`)).toBe(FUTURE);
    expect(JSON.parse(store.get(STORAGE_KEY)!).species).toEqual({ "150": "caught" });
    expect(notice.value.kind).toBe("error");
    expect(notice.value.action?.label).toMatch(/unreadable copy/);
    expect(storageAvailable.value).toBe(true);
  });

  it("never loads an older build's save over a current one it cannot read", () => {
    const legacy = JSON.stringify({
      schemaVersion: 2,
      species: { "25": "seen" },
      forms: {},
      settings: { forms: false, mode: "sun" },
    });
    const store = installStorage({
      [STORAGE_KEY]: "{truncated",
      "pokemon-checklist-state-v2": legacy,
    });

    initializeState();
    cycleSpecies(1);

    expect(exportState().species).toEqual({ "1": "caught" });
    expect(store.get(STORAGE_KEY)).toBe("{truncated");
    expect(store.get("pokemon-checklist-state-v2")).toBe(legacy);
    expect(store.get(`${STORAGE_KEY}:unreadable`)).toBe("{truncated");
    expect(storageAvailable.value).toBe(false);
  });

  it("starts a fresh, unsaved checklist when nothing else can be read", () => {
    const store = installStorage({ [STORAGE_KEY]: FUTURE });
    initializeState();
    cycleSpecies(1);
    expect(store.get(STORAGE_KEY)).toBe(FUTURE);
    expect(store.get(`${STORAGE_KEY}:unreadable`)).toBe(FUTURE);
    expect(storageAvailable.value).toBe(false);
    expect(notice.value.message).toMatch(/not saved/);
  });

  it("keeps every different unreadable save, never only the latest", () => {
    const store = installStorage({ [STORAGE_KEY]: FUTURE });
    initializeState();
    store.set(STORAGE_KEY, "{another");
    initializeState();
    initializeState();
    expect(store.get(`${STORAGE_KEY}:unreadable`)).toBe(FUTURE);
    expect(store.get(`${STORAGE_KEY}:unreadable-2`)).toBe("{another");
    expect(store.get(`${STORAGE_KEY}:unreadable-3`)).toBeUndefined();
  });

  it("never writes the account's checklist over an unreadable device save on sign-out", () => {
    const store = installStorage({ [STORAGE_KEY]: FUTURE });
    setSyncAccount("uid-dad");
    cycleSpecies(1); // the account's progress

    setSyncAccount(null);

    expect(exportState().species["1"]).toBeUndefined();
    expect(store.get(`${STORAGE_KEY}:unreadable`)).toBe(FUTURE);
    expect(store.get(STORAGE_KEY)).not.toContain('"1":"caught"');
    expect(notice.value.kind).toBe("error");
  });
});

describe("saving recovers and never hides a failure", () => {
  beforeEach(() => {
    installStorage();
    setSyncAccount(null);
    initializeState();
    resetState();
  });

  it("tries storage again after a failed write", () => {
    let full = true;
    const store = new Map<string, string>();
    (globalThis as { localStorage?: unknown }).localStorage = {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => {
        if (full) throw new Error("quota exceeded");
        store.set(key, value);
      },
      removeItem: (key: string) => void store.delete(key),
    };
    cycleSpecies(25);
    expect(storageAvailable.value).toBe(false);

    full = false;
    cycleSpecies(1);

    expect(storageAvailable.value).toBe(true);
    expect(JSON.parse(store.get(STORAGE_KEY)!).species).toEqual({
      "1": "caught",
      "25": "caught",
    });
  });

  it("does not cover a failed save with a success message", () => {
    (globalThis as { localStorage?: unknown }).localStorage = {
      getItem: () => null,
      setItem: () => {
        throw new Error("quota exceeded");
      },
      removeItem: () => {},
    };
    toggleStar(25);
    expect(notice.value.kind).toBe("error");
    expect(notice.value.message).toMatch(/not saved/);
  });
});

describe("two tabs of the same save", () => {
  it("keeps another tab's newer save when this tab writes next", () => {
    const store = installStorage();
    setSyncAccount(null);
    resetState();
    initializeState();
    cycleSpecies(25);
    // Another tab saves while this one misses the event (a page restored from the
    // back/forward cache does): it caught 150 and starred 1.
    store.set(STORAGE_KEY, saveOf({ "25": "caught", "150": "caught" }, { starred: [1] }));

    cycleSpecies(731);

    const saved = JSON.parse(store.get(STORAGE_KEY)!);
    expect(saved.species).toEqual({ "25": "caught", "150": "caught", "731": "caught" });
    expect(saved.starred).toEqual([1]);
    expect(exportState().species["150"]).toBe("caught");
  });
});

describe("undo", () => {
  beforeEach(() => {
    installStorage();
    setSyncAccount(null);
    setLocalReplaceListener(null);
    resetState();
  });

  it("offers one tap that reverts only the change it reports", () => {
    cycleSpecies(25);
    savedNotice("Status");
    const action = notice.value.action;
    expect(action?.label).toBe("Undo");
    // Something else arrives before the tap (another device, another tab).
    applyState(JSON.parse(saveOf({ "25": "caught", "150": "caught" })));

    action!.run();

    expect(exportState().species).toEqual({ "150": "caught" });
    expect(notice.value.message).toBe("Undone.");
    expect(notice.value.action).toBeUndefined();
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!).species).toEqual({ "150": "caught" });
  });

  it("undoes only this tab's change when saving took in another tab's", () => {
    const store = installStorage();
    initializeState();
    // Another tab saved 150 while this one missed the event.
    store.set(STORAGE_KEY, saveOf({ "150": "caught" }));
    cycleSpecies(731);
    savedNotice("Status");
    expect(exportState().species).toEqual({ "150": "caught", "731": "caught" });

    notice.value.action!.run();

    expect(exportState().species).toEqual({ "150": "caught" });
  });

  it("withdraws Undo when another account's checklist is shown", () => {
    cycleSpecies(25);
    savedNotice("Status");
    setSyncAccount("uid-new"); // no save of its own: adopts, with no notice
    expect(notice.value.action).toBeUndefined();
    setSyncAccount(null);
  });

  it("does not offer to undo a change it did not report", () => {
    cycleSpecies(25);
    persist(); // anything saved in between ends that offer
    savedNotice("Status");
    expect(notice.value.action).toBeUndefined();
  });

  it("undoes a Reset or Restore as a restore that sync can log", () => {
    const events: string[] = [];
    setLocalReplaceListener((_, op) => events.push(op));
    cycleSpecies(25);
    toggleStar(25);
    restoreState(JSON.parse(saveOf({ "1": "seen" })));
    resetState();
    savedNotice("Status");

    notice.value.action!.run();

    expect(exportState().species).toEqual({ "1": "seen" });
    expect(events).toEqual(["restore", "reset", "restore"]);
    setLocalReplaceListener(null);
  });
});
