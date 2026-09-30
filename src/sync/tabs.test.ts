import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Several tabs of one account, each with its own copy of the app's modules,
 * sharing one localStorage and one Web Locks manager, as a browser would. A write
 * in one tab reaches the others as a storage event, never the writer itself.
 */

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  onValue: vi.fn(),
  push: vi.fn(() => ({ key: `event-${Math.random()}` })),
  ref: vi.fn((db: unknown, path: string) => ({ db, path })),
  serverTimestamp: vi.fn(() => ({ ".sv": "timestamp" })),
  update: vi.fn(),
  initFirebase: vi.fn(() => ({ auth: {}, db: {} })),
  watchAuth: vi.fn(() => vi.fn()),
  signOutOfSync: vi.fn(async () => {}),
}));

vi.mock("firebase/database", () => ({
  get: mocks.get,
  onValue: mocks.onValue,
  push: mocks.push,
  ref: mocks.ref,
  serverTimestamp: mocks.serverTimestamp,
  update: mocks.update,
}));
vi.mock("./firebase", () => ({
  initFirebase: mocks.initFirebase,
  watchAuth: mocks.watchAuth,
  signOutOfSync: mocks.signOutOfSync,
}));

type Engine = typeof import("./engine");
type State = typeof import("../state");
type Editing = typeof import("../editing");
type Callback = (value: { val: () => unknown }) => void;

interface Tab {
  engine: Engine;
  state: State;
  editing: Editing;
  listeners: ((event: StorageEvent) => void)[];
  connected: Callback[];
  records: Callback[];
}

const settings = {
  "setting:mode": { s: "photonic-prismatic", at: 100, by: "uid-a" },
  "setting:forms": { s: "off", at: 100, by: "uid-a" },
};
const SAVE = "pokemon-checklist-state-v3:uid-a";
const snapshot = (records: Record<string, unknown>) => ({ val: () => records });

let storage = new Map<string, string>();
let tabs: Tab[] = [];
let current: Tab | null = null;
let queued: { from: Tab | null; key: string; newValue: string | null }[] = [];
/** What the database holds; a write shows at once in the writing tab, as Firebase does. */
let server: Record<string, unknown> = {};
let clock = 1_000_000;
/** Writes that never reach the server (a dead connection) while set. */
let dead = false;

/** A Web Locks manager shared by the tabs: one holder per name; `steal` takes it. */
function fakeLocks() {
  const holders = new Map<string, { token: object; abort: () => void }>();
  const waiting = new Map<string, (() => void)[]>();
  const next = (name: string) => waiting.get(name)?.shift()?.();
  const take = (name: string, callback: (lock: unknown) => unknown) =>
    new Promise((resolve, reject) => {
      const token = {};
      holders.set(name, {
        token,
        abort: () => {
          const error = new Error("The lock was stolen");
          error.name = "AbortError";
          reject(error);
        },
      });
      Promise.resolve(callback({ name })).then((value) => {
        if (holders.get(name)?.token === token) {
          holders.delete(name);
          next(name);
        }
        resolve(value);
      }, reject);
    });
  return {
    request(name: string, ...args: unknown[]) {
      const callback = args.at(-1) as (lock: unknown) => unknown;
      const options = (args.length > 1 ? args[0] : {}) as {
        ifAvailable?: boolean;
        steal?: boolean;
      };
      if (options.steal) {
        holders.get(name)?.abort();
        holders.delete(name);
        return take(name, callback);
      }
      if (!holders.has(name)) return take(name, callback);
      if (options.ifAvailable) return Promise.resolve(callback(null));
      return new Promise((resolve, reject) => {
        const queue = waiting.get(name) ?? [];
        queue.push(() => void take(name, callback).then(resolve, reject));
        waiting.set(name, queue);
      });
    },
  };
}

async function settle(): Promise<void> {
  for (let round = 0; round < 5; round += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

/**
 * Run in one tab, then deliver what it wrote to every other tab, and so on until
 * the tabs stop writing. `drop` models tabs that never see those writes.
 */
async function inTab(tab: Tab, act: () => unknown, drop = false): Promise<void> {
  current = tab;
  await act();
  await settle();
  current = null;
  if (drop) queued = [];
  await deliver();
}

async function deliver(): Promise<void> {
  let rounds = 0;
  while (queued.length > 0) {
    if (++rounds > 30) throw new Error("the tabs keep writing to each other");
    const events = queued;
    queued = [];
    for (const { from, key, newValue } of events) {
      for (const other of tabs) {
        if (other === from) continue;
        current = other;
        for (const listener of other.listeners) {
          listener({ key, newValue } as StorageEvent);
        }
        await settle();
        current = null;
      }
    }
  }
}

async function openTab(): Promise<Tab> {
  vi.resetModules();
  const engine = await import("./engine");
  const state = await import("../state");
  const editing = await import("../editing");
  const tab: Tab = { engine, state, editing, listeners: [], connected: [], records: [] };
  vi.stubGlobal("window", {
    addEventListener: (type: string, listener: (event: StorageEvent) => void) => {
      if (type === "storage") tab.listeners.push(listener);
    },
  });
  state.watchOtherTabs();
  engine.followSignInFromOtherTabs();
  tabs.push(tab);
  return tab;
}

async function signIn(tab: Tab): Promise<void> {
  // A tab that has to wait for the lock never finishes starting, so do not wait.
  await inTab(tab, () => void tab.engine.startSync({ uid: "uid-a", email: "x" }));
}

function recordsSent(): [string, string][] {
  return mocks.update.mock.calls.flatMap((call) =>
    Object.entries(call[1] as Record<string, { s?: string }>)
      .filter(([key]) => key.startsWith("state/records/"))
      .map(([key, value]) => [key.slice("state/records/".length), value.s!]),
  );
}

beforeEach(() => {
  storage = new Map();
  tabs = [];
  queued = [];
  server = { ...settings };
  clock = 1_000_000;
  dead = false;
  vi.spyOn(Date, "now").mockImplementation(() => clock);
  // As in a browser, only a write that changes a value raises an event elsewhere.
  (globalThis as { localStorage?: unknown }).localStorage = {
    getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, value: string) => {
      if (storage.get(key) === value) return;
      storage.set(key, value);
      queued.push({ from: current, key, newValue: value });
    },
    removeItem: (key: string) => {
      if (!storage.delete(key)) return;
      queued.push({ from: current, key, newValue: null });
    },
  };
  vi.stubGlobal("navigator", { locks: fakeLocks() });
  mocks.get.mockReset().mockImplementation(async () => snapshot(server));
  mocks.onValue.mockReset().mockImplementation((target: { path: string }, callback: Callback) => {
    if (current && target.path === ".info/connected") current.connected.push(callback);
    if (current && target.path.endsWith("/state/records")) current.records.push(callback);
    return vi.fn();
  });
  mocks.update.mockReset().mockImplementation(
    (_target: unknown, payload: Record<string, { s: string }>) => {
      const shown = { ...server };
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("state/records/")) {
          shown[key.slice("state/records/".length)] = { s: value.s, at: clock, by: "uid-a" };
        }
      }
      const writer = tabs.find((tab) => tab.engine.syncPhase.value !== "elsewhere");
      writer?.records.at(-1)?.(snapshot(shown));
      if (dead) return new Promise(() => {});
      server = shown;
      return Promise.resolve();
    },
  );
});

afterEach(() => {
  for (const tab of tabs) tab.engine.stopSync();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("one tab edits an account", () => {
  async function twoTabs() {
    const a = await openTab();
    const b = await openTab();
    await signIn(a);
    await signIn(b);
    mocks.update.mockClear();
    return { a, b };
  }

  it("lets only the lock holder change anything", async () => {
    const { a, b } = await twoTabs();
    expect(a.state.readOnly.value).toBeNull();
    expect(b.state.readOnly.value).toBe("elsewhere");
    expect(b.engine.syncPhase.value).toBe("elsewhere");
    expect(b.records).toHaveLength(0); // the view-only tab never touches the database

    await inTab(a, () => a.state.cycleSpecies(25));

    expect(recordsSent()).toEqual([["species:25", "caught"]]);
  });

  it("keeps a view-only tab's controls inert while it follows the editor", async () => {
    const { a, b } = await twoTabs();
    const before = storage.get(SAVE);
    const shown = b.state.exportState();
    current = b;
    b.state.cycleSpecies(25);
    b.state.cycleForm([...b.state.formDefinitions.keys()][0]);
    b.state.toggleStar(25);
    b.state.setMode("moon");
    b.state.toggleForms();
    b.state.resetState();
    b.state.restoreState({ ...b.state.defaultState(), species: { "1": "caught" } });
    current = null;
    // Nothing changed on screen, and nothing was written for any tab to see.
    expect(b.state.exportState()).toEqual(shown);
    expect(storage.get(SAVE)).toBe(before);
    expect(queued).toEqual([]);
    expect(mocks.update).not.toHaveBeenCalled();

    await inTab(a, () => a.state.cycleSpecies(150));
    expect(b.state.speciesStatus(150)).toBe("caught");
  });

  it("moves editing with Use this tab, and sends the old editor's unsent edit once", async () => {
    const { a, b } = await twoTabs();
    await inTab(a, () => a.connected[0]?.({ val: () => false }));
    await inTab(a, () => a.state.cycleSpecies(25)); // offline: stored, not sent
    expect(recordsSent()).toEqual([]);

    await inTab(b, () => b.editing.useThisTab());

    expect(b.state.readOnly.value).toBeNull();
    expect(a.state.readOnly.value).toBe("elsewhere");
    expect(recordsSent()).toEqual([["species:25", "caught"]]);
    // The old editor sends nothing more, even when its connection returns.
    await inTab(a, () => a.connected[0]?.({ val: () => true }));
    await inTab(a, () => a.state.cycleSpecies(4));
    expect(recordsSent()).toEqual([["species:25", "caught"]]);
    expect(a.state.speciesStatus(25)).toBe("caught");

    // And it can take editing back the same way.
    await inTab(a, () => a.editing.useThisTab());
    expect(a.state.readOnly.value).toBeNull();
    expect(b.state.readOnly.value).toBe("elsewhere");
  });

  it("stops the old editor writing the sync store once editing moves", async () => {
    const { a, b } = await twoTabs();
    await inTab(b, () => b.editing.useThisTab());
    await inTab(b, () => b.connected.at(-1)?.({ val: () => false }));
    await inTab(b, () => b.state.cycleSpecies(25)); // the new editor's unsent edit
    // Something arrives on the old editor's (no longer current) listener.
    await inTab(a, () => a.records.at(-1)?.(snapshot(server)));

    const store = JSON.parse(storage.get("pokemon-checklist-sync-v1")!);
    expect(store.intents["species:25"].s).toBe("caught");
  });

  it("shows a view-only tab that the editor is holding clears", async () => {
    const { a, b } = await twoTabs();
    server = {
      ...server,
      "species:1": { s: "caught", at: 900_000, by: "uid-a" },
      "species:4": { s: "caught", at: 900_000, by: "uid-a" },
    };
    await inTab(a, () => a.records.at(-1)!(snapshot(server)));
    await inTab(a, () => a.connected[0]?.({ val: () => false }));
    await inTab(a, () => {
      for (const id of [1, 1, 4, 4]) a.state.cycleSpecies(id); // both cleared
    });
    await inTab(a, () => a.connected[0]?.({ val: () => true }));
    await inTab(a, () => a.records.at(-1)!(snapshot(server)));

    expect(a.engine.syncHeld.value).toBe(2);
    expect(b.engine.syncHeld.value).toBe(2);
  });

  it("gives a duplicated tab (same session storage) no way to edit alongside", async () => {
    const session = new Map([["pokemon-checklist-tab", "tab-original"]]);
    vi.stubGlobal("sessionStorage", {
      getItem: (key: string) => session.get(key) ?? null,
      setItem: (key: string, value: string) => void session.set(key, value),
    });
    const { a, b } = await twoTabs(); // b is a's duplicate
    await inTab(a, () => a.state.cycleSpecies(1));
    await inTab(b, () => b.state.cycleSpecies(150)); // inert, not lost: never made

    expect(recordsSent()).toEqual([["species:1", "caught"]]);
    expect(b.state.speciesStatus(150)).toBe("none");
    expect(b.state.speciesStatus(1)).toBe("caught");
  });

  it("re-sends an unacknowledged edit after a reload, never over a newer change", async () => {
    const a = await openTab();
    await signIn(a);
    server = { ...server, "species:25": { s: "seen", at: 900_000, by: "uid-a" } };
    await inTab(a, () => a.records.at(-1)!(snapshot(server)));
    dead = true; // the write is shown locally, never acknowledged
    await inTab(a, () => a.state.cycleSpecies(25)); // seen -> none at 1,000,000
    // The tab is killed; later the phone catches 25; the tab is reopened.
    await inTab(a, () => a.engine.stopSync(false));
    tabs = [];
    dead = false;
    mocks.update.mockClear();
    clock = 1_600_000;
    server = { ...server, "species:25": { s: "caught", at: 1_300_000, by: "uid-a" } };
    const again = await openTab();
    await signIn(again);

    expect(recordsSent()).toEqual([]);
    expect(again.state.speciesStatus(25)).toBe("caught");
  });

  it("hands editing to the newer build when one opens in another tab", async () => {
    const { a, b } = await twoTabs();
    await inTab(b, () => {
      for (const listener of a.listeners) {
        listener({
          key: "pokemon-checklist-build",
          newValue: JSON.stringify({ build: "v9.9.9 - newer", at: clock }),
        } as StorageEvent);
      }
    });

    expect(a.state.readOnly.value).toBe("outdated");
    expect(a.engine.syncPhase.value).toBe("outdated");
    expect(b.state.readOnly.value).toBeNull();
    await inTab(a, () => a.state.cycleSpecies(25));
    await inTab(b, () => b.state.cycleSpecies(4));
    expect(recordsSent()).toEqual([["species:4", "caught"]]);
  });
});

describe("tabs without Web Locks", () => {
  it("N5: two tabs holding different edits of one record settle", async () => {
    vi.stubGlobal("navigator", {});
    const a = await openTab();
    const b = await openTab();
    await signIn(a);
    await signIn(b);
    await inTab(a, () => a.connected[0]?.({ val: () => false }));
    await inTab(b, () => b.connected[0]?.({ val: () => false }));
    // deliver() throws if the tabs keep writing to each other.
    await inTab(a, () => a.state.cycleSpecies(25)); // caught
    await inTab(b, () => b.state.cycleSpecies(25)); // seen, in the other tab

    expect(a.state.speciesStatus(25)).toBe("caught");
    expect(b.state.speciesStatus(25)).toBe("seen");
  });

  it("N6: editing still starts when Web Locks refuse", async () => {
    vi.stubGlobal("navigator", {
      locks: { request: () => Promise.reject(new Error("SecurityError")) },
    });
    const a = await openTab();
    await signIn(a);
    await inTab(a, () => a.state.cycleSpecies(25));

    expect(a.state.readOnly.value).toBeNull();
    expect(recordsSent()).toEqual([["species:25", "caught"]]);
  });

  it("keeps an Undo on offer when another tab's update does not touch it", async () => {
    vi.stubGlobal("navigator", {});
    const a = await openTab();
    const b = await openTab();
    await signIn(a);
    await signIn(b);
    await inTab(b, () => {
      b.state.cycleSpecies(25);
      b.state.savedNotice("Status");
    });
    await inTab(a, () => a.state.cycleSpecies(150));

    expect(b.state.speciesStatus(150)).toBe("caught");
    expect(b.state.notice.value.action?.label).toBe("Undo");
  });
});
