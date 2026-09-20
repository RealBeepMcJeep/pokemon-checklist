import { beforeEach, describe, expect, it } from "vitest";
import { STORAGE_KEY } from "../domain";
import type { SavedState } from "../types";
import {
  SYNC_STORE_KEY,
  deviceIdFor,
  emptyStore,
  isWholeAccountClear,
  loadStore,
  pendingEntries,
  saveFromView,
  saveKeyFor,
  saveStore,
  viewWithPending,
  type StorageLike,
} from "./outbox";
import {
  TOMBSTONE,
  speciesKey,
  type RecordEntry,
  type SyncDocument,
} from "./records";

const POKEMON = new Set([1, 25, 150]);
const FORMS = new Set(["25:alola"]);

const entry = (s: string, at: number, by = "uid-a"): RecordEntry => ({ s, at, by });
// A confirmed document always carries the settings records, because every
// publish includes them. Fixtures that omit them would create fake pending work.
const SETTINGS = {
  "setting:mode": entry("moon", 500),
  "setting:forms": entry("off", 500),
};
const document = (records: Record<string, RecordEntry>): SyncDocument => ({
  schema: 1,
  records,
  updatedAt: 0,
});
const save = (overrides: Partial<SavedState> = {}): SavedState => ({
  schemaVersion: 3,
  species: {},
  forms: {},
  starred: [],
  settings: { forms: false, mode: "moon" },
  ...overrides,
});

function fakeStorage(initial: Record<string, string> = {}) {
  const map = new Map(Object.entries(initial));
  return {
    getItem: (key: string) => (map.has(key) ? map.get(key)! : null),
    setItem: (key: string, value: string) => void map.set(key, value),
    keys: () => [...map.keys()],
    raw: (key: string) => map.get(key),
  } satisfies StorageLike & { keys: () => string[]; raw: (k: string) => string | undefined };
}

let storage: ReturnType<typeof fakeStorage>;
beforeEach(() => {
  storage = fakeStorage();
});

describe("account namespacing", () => {
  it("leaves the offline-only save exactly where it is", () => {
    expect(saveKeyFor(null)).toBe(STORAGE_KEY);
  });

  it("gives each account its own key, never the offline one", () => {
    const forAda = saveKeyFor("uid-ada");
    const forKid = saveKeyFor("uid-kid");
    expect(forAda).not.toBe(forKid);
    expect(forAda.startsWith(`${STORAGE_KEY}:`)).toBe(true);
    expect(forAda).not.toBe(STORAGE_KEY);
    expect(forKid).not.toBe(STORAGE_KEY);
  });
});

describe("store persistence", () => {
  it("starts empty when nothing is stored", () => {
    expect(loadStore(storage)).toEqual(emptyStore());
  });

  it("round-trips device, account and base", () => {
    const store = {
      version: 1 as const,
      deviceId: "dev-1",
      uid: "uid-a",
      email: "dad@example.com",
      base: document({ [speciesKey(25)]: entry("caught", 500) }),
    };
    saveStore(storage, store);
    expect(loadStore(storage)).toEqual(store);
    expect(storage.keys()).toEqual([SYNC_STORE_KEY]);
  });

  it("falls back to empty rather than throwing on junk", () => {
    for (const junk of ["{", "null", "[]", '{"version":99}', "not json at all"]) {
      expect(loadStore(fakeStorage({ [SYNC_STORE_KEY]: junk }))).toEqual(
        emptyStore(),
      );
    }
  });

  it("keeps the good entries when part of the base is malformed", () => {
    const raw = JSON.stringify({
      version: 1,
      deviceId: "dev-1",
      uid: "uid-a",
      email: null,
      base: {
        schema: 1,
        updatedAt: 0,
        records: {
          [speciesKey(25)]: entry("caught", 500),
          [speciesKey(1)]: { s: "caught", at: "soon", by: "uid-a" },
          [speciesKey(2)]: { nope: true },
        },
      },
    });
    const store = loadStore(fakeStorage({ [SYNC_STORE_KEY]: raw }));
    expect(Object.keys(store.base.records)).toEqual([speciesKey(25)]);
    expect(store.deviceId).toBe("dev-1");
  });

  it("keeps a device id stable and creates it once", () => {
    let calls = 0;
    const random = () => {
      calls += 1;
      return 0.42;
    };
    const first = deviceIdFor(storage, random);
    const second = deviceIdFor(storage, random);
    expect(first).toBe(second);
    expect(first.startsWith("dev-")).toBe(true);
    expect(calls).toBe(1);
  });
});

describe("pending work is derived, not queued", () => {
  it("is empty when the save matches the confirmed document", () => {
    const base = document({
      [speciesKey(25)]: entry("caught", 500),
      [speciesKey(1)]: entry(TOMBSTONE, 400),
      ...SETTINGS,
    });
    const current = save({ species: { "25": "caught" } });
    expect(pendingEntries(base, current, 9_000, "uid-a")).toEqual({});
  });

  it("publishes what changed, including a tombstone when progress is cleared", () => {
    const base = document({
      [speciesKey(25)]: entry("caught", 500),
      [speciesKey(1)]: entry("caught", 500),
      ...SETTINGS,
    });
    const current = save({ species: { "1": "seen" } });
    const pending = pendingEntries(base, current, 9_000, "uid-a");
    expect(pending[speciesKey(25)].s).toBe(TOMBSTONE);
    expect(pending[speciesKey(1)].s).toBe("seen");
    expect(Object.keys(pending).sort()).toEqual(
      [speciesKey(1), speciesKey(25)].sort(),
    );
  });

  it("empties itself once the server echoes the write back", () => {
    const current = save({ species: { "25": "caught" }, starred: [25] });
    const provisional = pendingEntries(document({}), current, 9_000, "uid-a");
    expect(Object.keys(provisional).sort()).toEqual(
      [speciesKey(25), "star:25", "setting:mode", "setting:forms"].sort(),
    );
    // The server stamps what it stored, slightly later, and echoes it.
    const echoed: Record<string, RecordEntry> = {};
    for (const [key, value] of Object.entries(provisional)) {
      echoed[key] = { ...value, at: 9_050 };
    }
    expect(pendingEntries(document(echoed), current, 9_100, "uid-a")).toEqual({});
  });
});

describe("what the device shows", () => {
  it("layers unpublished local edits over the confirmed document", () => {
    const base = document({ [speciesKey(25)]: entry("seen", 500, "uid-b") });
    const pending = { [speciesKey(25)]: entry("caught", 900, "uid-a") };
    const view = viewWithPending(base, pending);
    expect(view.records[speciesKey(25)].s).toBe("caught");
  });

  it("still loses to a genuinely newer remote write", () => {
    const base = document({ [speciesKey(25)]: entry("seen", 5_000, "uid-b") });
    const pending = { [speciesKey(25)]: entry("caught", 900, "uid-a") };
    const view = viewWithPending(base, pending);
    expect(view.records[speciesKey(25)].s).toBe("seen");
  });

  it("round-trips a view back into an applicable save", () => {
    const base = document({
      [speciesKey(25)]: entry("caught", 500),
      "star:150": entry("on", 500),
      "setting:mode": entry("ultra-moon", 500),
    });
    const view = viewWithPending(base, {});
    expect(saveFromView(view, POKEMON, FORMS)).toEqual({
      schemaVersion: 3,
      species: { "25": "caught" },
      forms: {},
      starred: [150],
      settings: { forms: false, mode: "ultra-moon" },
    });
  });
});

describe("the fail-safe against emptying an account", () => {
  const full = () =>
    document({
      [speciesKey(1)]: entry("caught", 100),
      [speciesKey(25)]: entry("caught", 100),
      [speciesKey(150)]: entry("caught", 100),
      [speciesKey(151)]: entry("caught", 100),
      [speciesKey(152)]: entry("caught", 100),
      [speciesKey(153)]: entry("caught", 100),
      ...SETTINGS,
    });

  it("flags the full-account clear produced by a deliberate Reset", () => {
    const base = full();
    const resetSave = save();
    const pending = pendingEntries(base, resetSave, 9_000, "uid-a");
    expect(isWholeAccountClear(base, pending)).toBe(true);
  });

  it("does not fire for an ordinary edit", () => {
    const base = full();
    const pending = pendingEntries(
      base,
      save({ species: { "25": "seen" } }),
      9_000,
      "uid-a",
    );
    expect(isWholeAccountClear(base, pending)).toBe(false);
  });

  it("does not fire for a small account, where clearing it is plausible", () => {
    const base = document({
      [speciesKey(1)]: entry("caught", 100),
      ...SETTINGS,
    });
    expect(isWholeAccountClear(base, pendingEntries(base, save(), 9_000, "uid-a"))).toBe(
      false,
    );
  });

  it("does not fire when there is nothing substantial left to clear", () => {
    const base = document({
      [speciesKey(1)]: entry(TOMBSTONE, 100),
      [speciesKey(25)]: entry(TOMBSTONE, 100),
      [speciesKey(150)]: entry(TOMBSTONE, 100),
      [speciesKey(151)]: entry(TOMBSTONE, 100),
      [speciesKey(152)]: entry(TOMBSTONE, 100),
      [speciesKey(153)]: entry(TOMBSTONE, 100),
      ...SETTINGS,
    });
    expect(isWholeAccountClear(base, pendingEntries(base, save(), 9_000, "uid-a"))).toBe(
      false,
    );
  });
});
