import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Two tabs signed into one account, each with its own copy of the app's modules,
 * sharing one localStorage and one Web Locks manager, as a browser would. A write
 * in one tab reaches the other as a storage event, never the writer itself.
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
type Callback = (value: { val: () => unknown }) => void;

interface Tab {
  engine: Engine;
  state: State;
  listeners: ((event: StorageEvent) => void)[];
  connected: Callback[];
  records: Callback[];
}

const settings = {
  "setting:mode": { s: "photonic-prismatic", at: 100, by: "uid-a" },
  "setting:forms": { s: "off", at: 100, by: "uid-a" },
};
const snapshot = (records: Record<string, unknown>) => ({ val: () => records });

let storage = new Map<string, string>();
let tabs: Tab[] = [];
let current: Tab | null = null;
let queued: { from: Tab | null; key: string; newValue: string | null }[] = [];

/** A Web Locks manager shared by the tabs: one holder per name, the rest queue. */
function fakeLocks() {
  const held = new Set<string>();
  const waiting = new Map<string, (() => void)[]>();
  const grant = async (name: string, callback: (lock: unknown) => unknown) => {
    held.add(name);
    try {
      return await callback({ name });
    } finally {
      held.delete(name);
      waiting.get(name)?.shift()?.();
    }
  };
  return {
    request(name: string, ...args: unknown[]) {
      const callback = args.at(-1) as (lock: unknown) => unknown;
      const options = (args.length > 1 ? args[0] : {}) as { ifAvailable?: boolean };
      if (!held.has(name)) return grant(name, callback);
      if (options.ifAvailable) return Promise.resolve(callback(null));
      return new Promise((resolve) => {
        const queue = waiting.get(name) ?? [];
        queue.push(() => void grant(name, callback).then(resolve));
        waiting.set(name, queue);
      });
    },
  };
}

async function settle(): Promise<void> {
  for (let round = 0; round < 5; round += 1) {
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
}

/** Run in one tab, then deliver what it wrote to every other tab. */
async function inTab(tab: Tab, act: () => unknown): Promise<void> {
  current = tab;
  await act();
  await settle();
  current = null;
  while (queued.length > 0) {
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
  const tab: Tab = { engine, state, listeners: [], connected: [], records: [] };
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

function sent(): Record<string, unknown>[] {
  return mocks.update.mock.calls.map((call) => call[1] as Record<string, unknown>);
}

beforeEach(() => {
  storage = new Map();
  tabs = [];
  queued = [];
  (globalThis as { localStorage?: unknown }).localStorage = {
    getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, value: string) => {
      storage.set(key, value);
      queued.push({ from: current, key, newValue: value });
    },
    removeItem: (key: string) => void storage.delete(key),
  };
  vi.stubGlobal("navigator", { locks: fakeLocks() });
  mocks.get.mockReset().mockResolvedValue(snapshot(settings));
  mocks.onValue.mockReset().mockImplementation((target: { path: string }, callback: Callback) => {
    if (current && target.path === ".info/connected") current.connected.push(callback);
    if (current && target.path.endsWith("/state/records")) current.records.push(callback);
    return vi.fn();
  });
  mocks.update.mockReset().mockResolvedValue(undefined);
});

afterEach(() => {
  for (const tab of tabs) tab.engine.stopSync();
  vi.unstubAllGlobals();
});

describe("two tabs of one account", () => {
  async function twoTabs() {
    const a = await openTab();
    const b = await openTab();
    await inTab(a, () => a.engine.startSync({ uid: "uid-a", email: "x" }));
    // Waits for as long as A syncs, so it is not awaited.
    await inTab(b, () => void b.engine.startSync({ uid: "uid-a", email: "x" }));
    mocks.update.mockClear();
    return { a, b };
  }

  it("lets only one tab sync, and sends the other tab's taps from it", async () => {
    const { a, b } = await twoTabs();
    expect(a.engine.syncPhase.value).not.toBe("elsewhere");
    expect(b.engine.syncPhase.value).toBe("elsewhere");
    expect(b.records).toHaveLength(0); // the other tab never touches the database

    await inTab(b, () => b.state.cycleSpecies(25));

    expect(sent()).toHaveLength(1);
    expect(sent()[0][`state/records/species:25`]).toEqual(
      expect.objectContaining({ s: "caught" }),
    );
    expect(a.state.speciesStatus(25)).toBe("caught");
  });

  it("sends a Reset made in the other tab as a logged Reset", async () => {
    const { a, b } = await twoTabs();
    await inTab(b, () => {
      b.state.cycleSpecies(25);
      b.state.cycleSpecies(150);
    });
    mocks.update.mockClear();

    await inTab(b, () => b.state.resetState());

    const ops = sent().flatMap((payload) =>
      Object.entries(payload)
        .filter(([key]) => key.startsWith("log/"))
        .map(([, value]) => (value as { op: string }).op),
    );
    expect(ops).toContain("reset");
    expect(ops).not.toContain("set");
    expect(a.state.speciesStatus(150)).toBe("none");
  });

  it("sends the other tab's tap even when a save here takes it in before its event", async () => {
    const { a, b } = await twoTabs();
    // B taps; before A gets the storage event, a server update makes A save.
    current = b;
    b.state.cycleSpecies(25);
    current = null;
    await inTab(a, () =>
      a.records.at(-1)!(
        snapshot({ ...settings, "species:150": { s: "caught", at: 200, by: "uid-a" } }),
      ),
    );

    expect(sent().at(-1)).toHaveProperty(
      "state/records/species:25",
      expect.objectContaining({ s: "caught" }),
    );
    expect(a.state.speciesStatus(150)).toBe("caught");
    expect(b.state.speciesStatus(150)).toBe("caught");
    expect(b.state.speciesStatus(25)).toBe("caught");
  });

  it("does not lose a tap when the syncing tab is closed before it sees it", async () => {
    const { a, b } = await twoTabs();
    // Tab A is killed: it never receives the storage event for B's tap.
    tabs = tabs.filter((tab) => tab !== a);
    await inTab(b, () => b.state.cycleSpecies(25));

    // Closing A releases its lock, and B takes over syncing.
    await inTab(b, () => a.engine.stopSync(false));
    expect(b.engine.syncPhase.value).not.toBe("elsewhere");
    expect(sent().at(-1)).toHaveProperty(
      "state/records/species:25",
      expect.objectContaining({ s: "caught" }),
    );
  });
});
