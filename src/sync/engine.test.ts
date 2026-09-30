import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  goOffline: vi.fn(),
  onValue: vi.fn(),
  push: vi.fn(() => ({ key: "event-1" })),
  ref: vi.fn((db: unknown, path: string) => ({ db, path })),
  serverTimestamp: vi.fn(() => ({ ".sv": "timestamp" })),
  update: vi.fn(),
  initFirebase: vi.fn(() => ({ auth: {}, db: {} })),
  watchAuth: vi.fn(() => vi.fn()),
  signOutOfSync: vi.fn(async () => {}),
}));

vi.mock("firebase/database", () => ({
  get: mocks.get,
  goOffline: mocks.goOffline,
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

import {
  resolveHeldClears,
  startSync,
  stopSync,
  syncAccount,
  syncHeld,
  syncMessage,
  syncPending,
  syncPhase,
  watchSyncAccount,
} from "./engine";
import {
  cycleSpecies,
  notice,
  resetState,
  restoreState,
  savedNotice,
  speciesStatus,
  syncFromStorage,
  toggleStar,
} from "../state";
import { speciesKey } from "./records";
import { SYNC_SESSION_KEY } from "./outbox";

let storage = new Map<string, string>();

function installStorage(): void {
  storage = new Map();
  (globalThis as { localStorage?: unknown }).localStorage = {
    getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, value: string) => void storage.set(key, value),
    removeItem: (key: string) => void storage.delete(key),
  };
}

function snapshot(records: Record<string, unknown>) {
  return { val: () => records };
}

let connected: ((value: { val: () => unknown }) => void)[] = [];
let recordsChanged: ((value: { val: () => unknown }) => void)[] = [];
let recordsFailed: ((error: Error) => void)[] = [];

beforeEach(() => {
  installStorage();
  connected = [];
  recordsChanged = [];
  recordsFailed = [];
  mocks.get.mockReset();
  mocks.onValue.mockReset();
  mocks.onValue.mockImplementation(
    (
      target: { path: string },
      callback: (value: unknown) => void,
      onError?: (error: Error) => void,
    ) => {
      if (target.path === ".info/connected") connected.push(callback as never);
      if (target.path.endsWith("/state/records")) {
        recordsChanged.push(callback as never);
        if (onError) recordsFailed.push(onError);
      }
      return vi.fn();
    },
  );
  mocks.push.mockClear();
  mocks.ref.mockClear();
  mocks.serverTimestamp.mockClear();
  mocks.update.mockReset().mockResolvedValue(undefined);
  mocks.watchAuth.mockReset().mockReturnValue(vi.fn());
  mocks.initFirebase.mockClear();
  mocks.signOutOfSync.mockClear();
  stopSync();
});

afterEach(() => {
  stopSync();
});

describe("sync startup lifecycle", () => {
  it("keeps sync off when storage can be read but not written", async () => {
    (globalThis as { localStorage?: unknown }).localStorage = {
      getItem: () => null,
      setItem: () => {
        throw new Error("quota exceeded");
      },
      removeItem: () => {},
    };

    await expect(
      startSync({ uid: "uid-a", email: "realbeepmcjeep@gmail.com" }),
    ).resolves.toBeUndefined();

    expect(syncPhase.value).toBe("error");
    expect(mocks.initFirebase).not.toHaveBeenCalled();
  });

  it("serializes rapid local reversals and publishes the latest payload second", async () => {
    resetState();
    mocks.get.mockResolvedValue(
      snapshot({
        "setting:mode": { s: "photonic-prismatic", at: 100, by: "uid-a" },
        "setting:forms": { s: "off", at: 100, by: "uid-a" },
      }),
    );
    await startSync({ uid: "uid-a", email: "realbeepmcjeep@gmail.com" });

    let settleFirst!: () => void;
    mocks.update
      .mockImplementationOnce(
        () => new Promise<void>((resolve) => (settleFirst = resolve)),
      )
      .mockResolvedValue(undefined);

    cycleSpecies(25); // caught: starts the first write
    cycleSpecies(25); // seen: coalesces while caught is in flight
    cycleSpecies(25); // none: the latest intent is a clear

    expect(mocks.update).toHaveBeenCalledTimes(1);
    settleFirst();
    await vi.waitFor(() => expect(mocks.update).toHaveBeenCalledTimes(2));

    const secondPayload = mocks.update.mock.calls[1][1] as Record<string, unknown>;
    expect(secondPayload["state/records/species:25"]).toEqual(
      expect.objectContaining({ s: "none" }),
    );
  });

  it("recovers an initial read failure when the connection returns without publishing first", async () => {
    mocks.get
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(
        snapshot({
          [speciesKey(25)]: { s: "caught", at: 100, by: "uid-a" },
          "setting:mode": { s: "moon", at: 100, by: "uid-a" },
          "setting:forms": { s: "off", at: 100, by: "uid-a" },
        }),
      );

    await startSync({ uid: "uid-a", email: "realbeepmcjeep@gmail.com" });

    expect(syncPhase.value).toBe("error");
    expect(mocks.update).not.toHaveBeenCalled();
    expect(connected).toHaveLength(1);

    connected[0]({ val: () => true });
    await vi.waitFor(() => expect(mocks.get).toHaveBeenCalledTimes(2));
    expect(mocks.update).not.toHaveBeenCalled();
  });

  it("ignores a stale start that finishes after a newer account", async () => {
    let finishFirst!: (value: unknown) => void;
    mocks.get
      .mockImplementationOnce(() => new Promise((resolve) => (finishFirst = resolve)))
      .mockResolvedValueOnce(snapshot({}));

    const first = startSync({ uid: "uid-a", email: "realbeepmcjeep@gmail.com" });
    await Promise.resolve();
    await startSync({ uid: "uid-b", email: "realbeepmcjeep@gmail.com" });
    finishFirst(snapshot({ [speciesKey(25)]: { s: "caught", at: 99, by: "uid-a" } }));
    await first;

    expect(syncAccount.value?.uid).toBe("uid-b");
  });

  it("does not publish a reset when the default empty checklist is unchanged", async () => {
    resetState();
    mocks.get.mockResolvedValue(
      snapshot({
        "setting:mode": { s: "photonic-prismatic", at: 100, by: "uid-a" },
        "setting:forms": { s: "off", at: 100, by: "uid-a" },
      }),
    );
    await startSync({ uid: "uid-a", email: "realbeepmcjeep@gmail.com" });
    mocks.update.mockClear();

    resetState();
    await Promise.resolve();

    expect(mocks.update).not.toHaveBeenCalled();
  });

  it("settles a reset echo that arrives before the write promise", async () => {
    resetState();
    mocks.get.mockResolvedValue(
      snapshot({
        [speciesKey(1)]: { s: "caught", at: 100, by: "uid-a" },
        [speciesKey(25)]: { s: "caught", at: 100, by: "uid-a" },
        [speciesKey(150)]: { s: "caught", at: 100, by: "uid-a" },
        [speciesKey(151)]: { s: "caught", at: 100, by: "uid-a" },
        [speciesKey(152)]: { s: "caught", at: 100, by: "uid-a" },
        "setting:mode": { s: "moon", at: 100, by: "uid-a" },
        "setting:forms": { s: "off", at: 100, by: "uid-a" },
      }),
    );
    await startSync({ uid: "uid-a", email: "realbeepmcjeep@gmail.com" });
    mocks.update.mockReset();
    let settleUpdate!: () => void;
    mocks.update.mockImplementationOnce(
      () => new Promise<void>((resolve) => (settleUpdate = resolve)),
    );

    resetState();
    await vi.waitFor(() => expect(mocks.update).toHaveBeenCalledTimes(1));
    recordsChanged[0]({
      val: () => ({
        [speciesKey(1)]: { s: "none", at: 200, by: "uid-a" },
        [speciesKey(25)]: { s: "none", at: 200, by: "uid-a" },
        [speciesKey(150)]: { s: "none", at: 200, by: "uid-a" },
        [speciesKey(151)]: { s: "none", at: 200, by: "uid-a" },
        [speciesKey(152)]: { s: "none", at: 200, by: "uid-a" },
        "setting:mode": { s: "photonic-prismatic", at: 200, by: "uid-a" },
        "setting:forms": { s: "off", at: 200, by: "uid-a" },
      }),
    });

    settleUpdate();
    await vi.waitFor(() => {
      const saved = JSON.parse(storage.get("pokemon-checklist-sync-v1")!);
      expect(saved.reset).toBeUndefined();
    });
    connected[0]({ val: () => true });
    await Promise.resolve();
    expect(mocks.update).toHaveBeenCalledTimes(1);
  });

  it("publishes an intentional reset as an atomic reset log instead of the clear guard", async () => {
    mocks.get.mockResolvedValue(
      snapshot({
        [speciesKey(1)]: { s: "caught", at: 100, by: "uid-a" },
        [speciesKey(25)]: { s: "caught", at: 100, by: "uid-a" },
        [speciesKey(150)]: { s: "caught", at: 100, by: "uid-a" },
        [speciesKey(151)]: { s: "caught", at: 100, by: "uid-a" },
        [speciesKey(152)]: { s: "caught", at: 100, by: "uid-a" },
        "setting:mode": { s: "moon", at: 100, by: "uid-a" },
        "setting:forms": { s: "off", at: 100, by: "uid-a" },
      }),
    );
    await startSync({ uid: "uid-a", email: "realbeepmcjeep@gmail.com" });
    mocks.update.mockClear();

    resetState();
    await vi.waitFor(() => expect(mocks.update).toHaveBeenCalled());

    const payload = mocks.update.mock.calls[0][1] as Record<string, unknown>;
    expect(Object.values(payload)).toContainEqual(
      expect.objectContaining({ op: "reset", cleared: expect.any(Array) }),
    );
    expect(payload[`state/records/${speciesKey(1)}`]).toEqual(
      expect.objectContaining({ s: "none" }),
    );
  });
});

describe("first sign-in never loses a checklist", () => {
  const DEVICE_SAVE = "pokemon-checklist-state-v3";
  const settings = {
    "setting:mode": { s: "photonic-prismatic", at: 100, by: "uid-a" },
    "setting:forms": { s: "off", at: 100, by: "uid-a" },
  };

  function published(): Record<string, { s: string }> {
    return Object.assign(
      {},
      ...mocks.update.mock.calls.map((call) => call[1] as Record<string, { s: string }>),
    );
  }

  it("adopts this device's progress into an empty account", async () => {
    resetState();
    cycleSpecies(25); // caught, while signed out
    const deviceSave = localStorage.getItem(DEVICE_SAVE);
    mocks.get.mockResolvedValue(snapshot({}));

    await startSync({ uid: "uid-a", email: "realbeepmcjeep@gmail.com" });

    expect(published()[`state/records/${speciesKey(25)}`]).toEqual(
      expect.objectContaining({ s: "caught" }),
    );
    expect(speciesStatus(25)).toBe("caught");
    expect(localStorage.getItem(DEVICE_SAVE)).toBe(deviceSave);
  });

  it("shows an account's existing checklist without clearing it or this device's", async () => {
    resetState();
    cycleSpecies(25); // this device: Pikachu caught
    const deviceSave = localStorage.getItem(DEVICE_SAVE);
    mocks.get.mockResolvedValue(
      snapshot({ ...settings, [speciesKey(150)]: { s: "caught", at: 100, by: "uid-a" } }),
    );

    await startSync({ uid: "uid-a", email: "realbeepmcjeep@gmail.com" });

    // The account's collection is shown, and nothing in it is cleared.
    expect(speciesStatus(150)).toBe("caught");
    expect(published()[`state/records/${speciesKey(150)}`]).toBeUndefined();
    for (const [key, value] of Object.entries(published())) {
      if (key.startsWith("state/records/")) expect(value.s).not.toBe("none");
    }
    // This device's own progress is untouched, said so, and back after signing out.
    expect(localStorage.getItem(DEVICE_SAVE)).toBe(deviceSave);
    expect(notice.value.message).toContain("sign out");
    stopSync();
    expect(speciesStatus(25)).toBe("caught");
    expect(speciesStatus(150)).toBe("none");
  });
});

describe("an old copy on this device never overrides the account", () => {
  const ACCOUNT_SAVE = "pokemon-checklist-state-v3:uid-a";
  const blankSave = {
    schemaVersion: 3,
    species: {},
    forms: {},
    starred: [],
    settings: { forms: false, mode: "photonic-prismatic" },
  };
  const serverRecords = {
    "setting:mode": { s: "photonic-prismatic", at: 100, by: "uid-a" },
    "setting:forms": { s: "off", at: 100, by: "uid-a" },
    [speciesKey(25)]: { s: "caught", at: 100, by: "uid-a" },
    [speciesKey(150)]: { s: "caught", at: 100, by: "uid-a" },
    "star:25": { s: "on", at: 100, by: "uid-a" },
  };

  function storeBase(records: Record<string, unknown>): void {
    localStorage.setItem(
      "pokemon-checklist-sync-v1",
      JSON.stringify({
        version: 1,
        deviceId: "dev-desk",
        uid: "uid-a",
        email: "realbeepmcjeep@gmail.com",
        base: { schema: 1, records, updatedAt: 0 },
      }),
    );
  }

  function sentClears(): string[] {
    return mocks.update.mock.calls.flatMap((call) =>
      Object.entries(call[1] as Record<string, { s?: string }>)
        .filter(([key, value]) => key.startsWith("state/records/") && (value.s === "none" || value.s === "off"))
        .map(([key]) => key),
    );
  }

  it("shows the account when this device's saved copy is blank (the 64-to-send bug)", async () => {
    storeBase(serverRecords);
    localStorage.setItem(ACCOUNT_SAVE, JSON.stringify(blankSave));
    mocks.get.mockResolvedValue(snapshot(serverRecords));

    await startSync({ uid: "uid-a", email: "realbeepmcjeep@gmail.com" });

    expect(speciesStatus(25)).toBe("caught");
    expect(speciesStatus(150)).toBe("caught");
    expect(syncPending.value).toBe(0);
    expect(sentClears()).toEqual([]);
  });

  it("shows the account when this device never confirmed anything for it", async () => {
    localStorage.setItem(ACCOUNT_SAVE, JSON.stringify(blankSave));
    mocks.get.mockResolvedValue(snapshot(serverRecords));

    await startSync({ uid: "uid-a", email: "realbeepmcjeep@gmail.com" });

    expect(speciesStatus(150)).toBe("caught");
    expect(syncPending.value).toBe(0);
    expect(sentClears()).toEqual([]);
  });

  it("still sends a real offline change without undoing another device's", async () => {
    const before = { ...serverRecords };
    delete (before as Record<string, unknown>)[speciesKey(150)]; // the phone caught Mewtwo later
    storeBase(before);
    localStorage.setItem(
      ACCOUNT_SAVE,
      JSON.stringify({ ...blankSave, species: { 25: "caught", 6: "caught" }, starred: [25] }),
    ); // this device caught Charizard while offline
    mocks.get.mockResolvedValue(snapshot(serverRecords));

    await startSync({ uid: "uid-a", email: "realbeepmcjeep@gmail.com" });

    expect(speciesStatus(6)).toBe("caught");
    expect(speciesStatus(150)).toBe("caught");
    expect(sentClears()).toEqual([]);
    expect(mocks.update.mock.calls.at(-1)![1]).toHaveProperty(`state/records/${speciesKey(6)}`);
  });

  it("applies another device's change mid-session instead of undoing it", async () => {
    const withoutMewtwo = { ...serverRecords };
    delete (withoutMewtwo as Record<string, unknown>)[speciesKey(150)];
    mocks.get.mockResolvedValue(snapshot(withoutMewtwo));
    await startSync({ uid: "uid-a", email: "realbeepmcjeep@gmail.com" });
    mocks.update.mockClear();

    recordsChanged.at(-1)!(snapshot({ ...withoutMewtwo, [speciesKey(150)]: { s: "caught", at: 200, by: "uid-a" } }));
    await Promise.resolve();

    expect(speciesStatus(150)).toBe("caught");
    expect(syncPending.value).toBe(0);
    expect(sentClears()).toEqual([]);
  });
});

describe("auth watching", () => {
  it("registers one auth watcher even when startup and sign-in both ask for it", () => {
    watchSyncAccount();
    watchSyncAccount();
    expect(mocks.watchAuth).toHaveBeenCalledTimes(1);
  });
});

describe("sign-in flow", () => {
  type Listener = (user: { uid: string; email: string } | null, allowed: boolean) => void;

  // The auth watcher registers once per module, so each case loads a fresh engine.
  async function freshEngine() {
    vi.resetModules();
    let listener: Listener | undefined;
    mocks.watchAuth.mockImplementation(((callback: Listener) => {
      listener = callback;
      return vi.fn();
    }) as never);
    const engine = await import("./engine");
    return { engine, fire: (...args: Parameters<Listener>) => listener!(...args) };
  }

  it("keeps the sign-in flag through Firebase's initial signed-out event", async () => {
    // Firebase reports "signed out" as soon as auth starts. Clearing the flag then made a
    // full-page sign-in come back to a page that never looked for its session.
    const { engine, fire } = await freshEngine();
    engine.beginSignIn();
    fire(null, false);
    expect(localStorage.getItem(SYNC_SESSION_KEY)).toBe("1");
  });

  it("forgets the flag when a sign-in is abandoned", async () => {
    const { engine, fire } = await freshEngine();
    engine.beginSignIn();
    fire(null, false);
    engine.cancelSignIn();
    expect(localStorage.getItem(SYNC_SESSION_KEY)).toBe("0");
  });

  it("signs a disallowed account straight back out", async () => {
    const { engine, fire } = await freshEngine();
    engine.beginSignIn();
    fire({ uid: "stranger", email: "stranger@example.com" }, false);
    expect(mocks.signOutOfSync).toHaveBeenCalledTimes(1);
    expect(engine.syncAccount.value).toBeNull();
    expect(localStorage.getItem(SYNC_SESSION_KEY)).toBe("0");
  });

  it("follows a sign-in made in another tab", async () => {
    const { engine } = await freshEngine();
    const listeners: ((event: { key: string; newValue: string | null }) => void)[] = [];
    vi.stubGlobal("window", {
      addEventListener: (type: string, listener: (typeof listeners)[number]) => {
        if (type === "storage") listeners.push(listener);
      },
    });
    engine.followSignInFromOtherTabs();
    expect(mocks.watchAuth).not.toHaveBeenCalled();

    listeners.forEach((listener) => listener({ key: "unrelated", newValue: "1" }));
    listeners.forEach((listener) => listener({ key: SYNC_SESSION_KEY, newValue: "0" }));
    expect(mocks.watchAuth).not.toHaveBeenCalled();
    listeners.forEach((listener) => listener({ key: SYNC_SESSION_KEY, newValue: "1" }));
    expect(mocks.watchAuth).toHaveBeenCalledTimes(1);
    vi.unstubAllGlobals();
  });

  it("L5: following another tab's sign-in never clears that tab's session flag", async () => {
    const { engine, fire } = await freshEngine();
    const listeners: ((event: { key: string; newValue: string | null }) => void)[] = [];
    vi.stubGlobal("window", {
      addEventListener: (type: string, listener: (typeof listeners)[number]) => {
        if (type === "storage") listeners.push(listener);
      },
    });
    engine.followSignInFromOtherTabs();
    localStorage.setItem(SYNC_SESSION_KEY, "1"); // set by the tab that is signing in
    listeners.forEach((listener) => listener({ key: SYNC_SESSION_KEY, newValue: "1" }));

    fire(null, false); // Firebase's first report here: not signed in (yet)

    expect(localStorage.getItem(SYNC_SESSION_KEY)).toBe("1");
    vi.unstubAllGlobals();
  });
});

describe("the edit made last wins", () => {
  const settings = {
    "setting:mode": { s: "photonic-prismatic", at: 100, by: "uid-a" },
    "setting:forms": { s: "off", at: 100, by: "uid-a" },
  };
  const five = {
    ...settings,
    [speciesKey(1)]: { s: "caught", at: 100, by: "uid-a" },
    [speciesKey(25)]: { s: "caught", at: 100, by: "uid-a" },
    [speciesKey(150)]: { s: "caught", at: 100, by: "uid-a" },
    [speciesKey(151)]: { s: "caught", at: 100, by: "uid-a" },
    [speciesKey(152)]: { s: "caught", at: 100, by: "uid-a" },
  };
  const payloads = () =>
    mocks.update.mock.calls.map((call) => call[1] as Record<string, Record<string, unknown>>);
  const logOps = (payload: Record<string, Record<string, unknown>>) =>
    Object.entries(payload)
      .filter(([key]) => key.startsWith("log/"))
      .map(([, value]) => value.op);

  async function signedIn(records: Record<string, unknown>) {
    resetState();
    mocks.get.mockResolvedValue(snapshot(records));
    await startSync({ uid: "uid-a", email: "realbeepmcjeep@gmail.com" });
    mocks.update.mockClear();
  }

  /** Drop the connection, act, then reconnect to what the server holds now. */
  async function offline(act: () => void, server: Record<string, unknown>) {
    connected[0]({ val: () => false });
    act();
    await Promise.resolve();
    expect(mocks.update).not.toHaveBeenCalled();
    connected[0]({ val: () => true });
    // Still nothing: the server's current records have not arrived yet.
    await Promise.resolve();
    expect(mocks.update).not.toHaveBeenCalled();
    recordsChanged.at(-1)!(snapshot(server));
    await Promise.resolve();
  }

  it("does not let an offline Reset clear what another device changed later", async () => {
    await signedIn(five);
    await offline(resetState, {
      ...five,
      [speciesKey(25)]: { s: "seen", at: Date.now() + 60_000, by: "uid-a" },
    });

    await vi.waitFor(() => expect(mocks.update).toHaveBeenCalledTimes(1));
    const [payload] = payloads();
    expect(payload[`state/records/${speciesKey(1)}`]).toEqual(
      expect.objectContaining({ s: "none" }),
    );
    expect(payload[`state/records/${speciesKey(25)}`]).toBeUndefined();
    const reset = Object.values(payload).find((value) => value.op === "reset")!;
    expect((reset.cleared as [string, string][]).map(([key]) => key)).not.toContain(
      speciesKey(25),
    );
    expect(speciesStatus(25)).toBe("seen");
  });

  it("drops a stale offline edit when a newer correction arrives, and says so", async () => {
    await signedIn(settings);
    await offline(() => cycleSpecies(25), {
      ...settings,
      [speciesKey(25)]: { s: "seen", at: Date.now() + 60_000, by: "chat:uid-a" },
    });

    await Promise.resolve();
    expect(mocks.update).not.toHaveBeenCalled();
    expect(speciesStatus(25)).toBe("seen");
    expect(notice.value.message).toMatch(/gave way to newer ones/);
  });

  it("still sends an offline edit that is newer than the change that arrived", async () => {
    await signedIn(settings);
    await offline(() => cycleSpecies(25), {
      ...settings,
      [speciesKey(25)]: { s: "seen", at: Date.now() - 60_000, by: "chat:uid-a" },
    });

    await vi.waitFor(() => expect(mocks.update).toHaveBeenCalledTimes(1));
    expect(payloads()[0][`state/records/${speciesKey(25)}`]).toEqual(
      expect.objectContaining({ s: "caught" }),
    );
    expect(speciesStatus(25)).toBe("caught");
  });

  it("keeps an edit's time across a reload", async () => {
    const clock = vi.spyOn(Date, "now").mockReturnValue(1_000_000);
    await signedIn(settings);
    connected[0]({ val: () => false });
    cycleSpecies(25); // made offline at 1,000,000
    stopSync();
    // Chat corrects it at 1,500,000; this device comes back at 2,000,000.
    clock.mockReturnValue(2_000_000);
    mocks.get.mockResolvedValue(
      snapshot({
        ...settings,
        [speciesKey(25)]: { s: "seen", at: 1_500_000, by: "chat:uid-a" },
      }),
    );
    await startSync({ uid: "uid-a", email: "realbeepmcjeep@gmail.com" });

    expect(speciesStatus(25)).toBe("seen");
    expect(mocks.update).not.toHaveBeenCalled();
    clock.mockRestore();
  });

  it("never mistakes its own echo for a newer change", async () => {
    await signedIn(settings);
    let settleFirst!: () => void;
    mocks.update
      .mockImplementationOnce(() => new Promise<void>((resolve) => (settleFirst = resolve)))
      .mockResolvedValue(undefined);

    cycleSpecies(25); // caught: in flight
    cycleSpecies(25); // seen: made before the server stamps "caught"
    recordsChanged.at(-1)!(
      snapshot({ ...settings, [speciesKey(25)]: { s: "caught", at: Date.now() + 1_000, by: "uid-a" } }),
    );
    settleFirst();

    await vi.waitFor(() => expect(mocks.update).toHaveBeenCalledTimes(2));
    expect(payloads()[1][`state/records/${speciesKey(25)}`]).toEqual(
      expect.objectContaining({ s: "seen" }),
    );
  });

  it("logs a reset once and gives an edit made meanwhile its own entry", async () => {
    await signedIn(five);
    let settleFirst!: () => void;
    mocks.update
      .mockImplementationOnce(() => new Promise<void>((resolve) => (settleFirst = resolve)))
      .mockResolvedValue(undefined);

    resetState();
    // Firebase applies a write locally at once, so the reset echoes before its ack.
    const cleared = Object.fromEntries(
      Object.entries(five).map(([key, entry]) => [
        key,
        key.startsWith("species:") ? { ...entry, s: "none", at: Date.now() } : entry,
      ]),
    );
    recordsChanged.at(-1)!(snapshot(cleared));
    cycleSpecies(1); // caught again before the reset is confirmed
    settleFirst();

    await vi.waitFor(() => expect(mocks.update).toHaveBeenCalledTimes(2));
    expect(logOps(payloads()[0])).toContain("reset");
    expect(logOps(payloads()[1])).toEqual(["set"]);
    expect(payloads()[1][`state/records/${speciesKey(1)}`]).toEqual(
      expect.objectContaining({ s: "caught" }),
    );
  });

  it("publishes a confirmed restore instead of refusing it as a wipe", async () => {
    await signedIn(five);
    restoreState({
      schemaVersion: 3,
      species: { "7": "caught" },
      forms: {},
      starred: [],
      settings: { forms: false, mode: "photonic-prismatic" },
    });

    await vi.waitFor(() => expect(mocks.update).toHaveBeenCalledTimes(1));
    const [payload] = payloads();
    expect(payload[`state/records/${speciesKey(1)}`]).toEqual(
      expect.objectContaining({ s: "none" }),
    );
    expect(payload[`state/records/${speciesKey(7)}`]).toEqual(
      expect.objectContaining({ s: "caught" }),
    );
    const restore = Object.values(payload).find((value) => value.op === "restore")!;
    expect(restore).toEqual(
      expect.objectContaining({ at: expect.anything(), by: "uid-a" }),
    );
    expect(restore.before).toContainEqual([speciesKey(1), "caught"]);
    expect(logOps(payload)).toEqual(["restore"]);
    expect(syncPhase.value).not.toBe("error");
  });

  it("undoes an unsent Reset without sending anything", async () => {
    await signedIn(five);
    await offline(() => {
      resetState();
      savedNotice("Status");
      notice.value.action!.run();
    }, five);

    await Promise.resolve();
    expect(mocks.update).not.toHaveBeenCalled();
    expect(speciesStatus(25)).toBe("caught");
    expect(JSON.parse(storage.get("pokemon-checklist-sync-v1")!).reset).toBeUndefined();
  });

  it("listens again after the record listener fails", async () => {
    vi.useFakeTimers();
    await signedIn(settings);
    expect(recordsChanged).toHaveLength(1);

    recordsFailed[0](new Error("PERMISSION_DENIED"));
    expect(syncPhase.value).toBe("error");
    vi.advanceTimersByTime(30_000);

    expect(recordsChanged).toHaveLength(2);
    vi.useRealTimers();
  });
});

describe("sign-in keeps the checklist on screen honest", () => {
  const ACCOUNT_SAVE = "pokemon-checklist-state-v3:uid-a";
  const settings = {
    "setting:mode": { s: "photonic-prismatic", at: 100, by: "uid-a" },
    "setting:forms": { s: "off", at: 100, by: "uid-a" },
  };
  const accountSave = (species: Record<string, string>) =>
    JSON.stringify({
      schemaVersion: 3,
      species,
      forms: {},
      starred: [],
      settings: { forms: false, mode: "photonic-prismatic" },
    });

  it("shows the account's own save while connecting, and sends what is tapped there", async () => {
    const server = { ...settings, [speciesKey(1)]: { s: "caught", at: 100, by: "uid-a" } };
    localStorage.setItem(
      "pokemon-checklist-sync-v1",
      JSON.stringify({
        version: 1,
        deviceId: "dev-desk",
        uid: "uid-a",
        email: null,
        base: { schema: 1, records: server, updatedAt: 0 },
      }),
    );
    localStorage.setItem(ACCOUNT_SAVE, accountSave({ "1": "caught" }));
    let answer!: (value: unknown) => void;
    mocks.get.mockImplementationOnce(() => new Promise((resolve) => (answer = resolve)));

    const started = startSync({ uid: "uid-a", email: "realbeepmcjeep@gmail.com" });
    expect(speciesStatus(1)).toBe("caught");
    cycleSpecies(150); // tapped before the server answers
    await vi.waitFor(() => expect(mocks.get).toHaveBeenCalled());
    answer(snapshot(server));
    await started;

    await vi.waitFor(() => expect(mocks.update).toHaveBeenCalled());
    expect(mocks.update.mock.calls.at(-1)![1]).toHaveProperty(
      `state/records/${speciesKey(150)}`,
    );
    expect(speciesStatus(150)).toBe("caught");
  });

  it("never takes a Reset of this device's own checklist as the account's", async () => {
    resetState();
    cycleSpecies(25); // this device's own progress, signed out
    let answer!: (value: unknown) => void;
    mocks.get.mockImplementationOnce(() => new Promise((resolve) => (answer = resolve)));

    const started = startSync({ uid: "uid-a", email: "realbeepmcjeep@gmail.com" });
    resetState(); // on the device's checklist, still on screen
    await vi.waitFor(() => expect(mocks.get).toHaveBeenCalled());
    answer(snapshot({ ...settings, [speciesKey(25)]: { s: "caught", at: 100, by: "uid-a" } }));
    await started;
    await Promise.resolve();

    expect(speciesStatus(25)).toBe("caught");
    expect(mocks.update).not.toHaveBeenCalled();
  });

  it("adds only what the server lacks when this device lost its sync records", async () => {
    localStorage.setItem(ACCOUNT_SAVE, accountSave({ "25": "caught", "6": "caught" }));
    mocks.get.mockResolvedValue(
      snapshot({
        ...settings,
        [speciesKey(25)]: { s: "seen", at: 100, by: "uid-a" },
        [speciesKey(150)]: { s: "caught", at: 100, by: "uid-a" },
      }),
    );

    await startSync({ uid: "uid-a", email: "realbeepmcjeep@gmail.com" });

    await vi.waitFor(() => expect(mocks.update).toHaveBeenCalledTimes(1));
    const sent = Object.keys(mocks.update.mock.calls[0][1] as object).filter((key) =>
      key.startsWith("state/records/"),
    );
    expect(sent).toEqual([`state/records/${speciesKey(6)}`]);
    expect(speciesStatus(25)).toBe("seen");
    expect(speciesStatus(150)).toBe("caught");
    expect(notice.value.message).toMatch(/lost its sync records/);
    expect(notice.value.action?.label).toMatch(/Download/);
  });

  it("keeps a tap made while connecting even when the sync records were lost", async () => {
    localStorage.setItem(ACCOUNT_SAVE, accountSave({ "1": "caught" }));
    let answer!: (value: unknown) => void;
    mocks.get.mockImplementationOnce(() => new Promise((resolve) => (answer = resolve)));

    const started = startSync({ uid: "uid-a", email: "realbeepmcjeep@gmail.com" });
    await vi.waitFor(() => expect(mocks.get).toHaveBeenCalled());
    cycleSpecies(25); // caught, while connecting; the server says seen
    answer(
      snapshot({
        ...settings,
        [speciesKey(1)]: { s: "caught", at: 100, by: "uid-a" },
        [speciesKey(25)]: { s: "seen", at: 100, by: "uid-a" },
      }),
    );
    await started;

    await vi.waitFor(() => expect(mocks.update).toHaveBeenCalled());
    expect(mocks.update.mock.calls[0][1]).toHaveProperty(
      `state/records/${speciesKey(25)}`,
      expect.objectContaining({ s: "caught" }),
    );
    expect(speciesStatus(25)).toBe("caught");
  });
});

describe("adversarial review", () => {
  const settings = {
    "setting:mode": { s: "photonic-prismatic", at: 100, by: "uid-a" },
    "setting:forms": { s: "off", at: 100, by: "uid-a" },
  };
  const ACCOUNT_SAVE = "pokemon-checklist-state-v3:uid-a";
  const sentRecords = () =>
    mocks.update.mock.calls.map((call) =>
      Object.fromEntries(
        Object.entries(call[1] as Record<string, { s?: string }>)
          .filter(([key]) => key.startsWith("state/records/"))
          .map(([key, value]) => [key.slice("state/records/".length), value.s]),
      ),
    );

  async function signedIn(records: Record<string, unknown>) {
    resetState();
    mocks.get.mockResolvedValue(snapshot(records));
    await startSync({ uid: "uid-a", email: "realbeepmcjeep@gmail.com" });
    connected[0]({ val: () => true });
    mocks.update.mockClear();
  }

  /** Firebase shows a write to the page's own listeners inside update(). */
  function echoLocally(records: Record<string, unknown>, reply: Promise<void>) {
    mocks.update.mockImplementation(
      (_target: unknown, payload: Record<string, { s: string }>) => {
        const shown: Record<string, unknown> = { ...records };
        for (const [key, value] of Object.entries(payload)) {
          if (key.startsWith("state/records/")) {
            shown[key.slice("state/records/".length)] = { s: value.s, at: Date.now(), by: "uid-a" };
          }
        }
        recordsChanged.at(-1)!(snapshot(shown));
        return reply;
      },
    );
  }

  it("H1: re-sends a tap whose write was shown locally but never acknowledged", async () => {
    await signedIn(settings);
    echoLocally(settings, new Promise(() => {})); // a half-dead connection
    cycleSpecies(25);
    await Promise.resolve();
    expect(mocks.update).toHaveBeenCalledTimes(1);
    // Not acknowledged, so it still counts as unsent (sign-out reports it).
    expect(syncPending.value).toBe(1);

    stopSync(); // the tab is killed
    mocks.update.mockReset().mockResolvedValue(undefined);
    mocks.get.mockResolvedValue(snapshot(settings)); // the server never got it
    await startSync({ uid: "uid-a", email: "realbeepmcjeep@gmail.com" });

    await vi.waitFor(() => expect(mocks.update).toHaveBeenCalled());
    expect(sentRecords().at(-1)).toHaveProperty(speciesKey(25), "caught");
    expect(speciesStatus(25)).toBe("caught");
  });

  it("H1: a refused write is sent again rather than taken as confirmed", async () => {
    await signedIn(settings);
    mocks.update.mockImplementationOnce(
      (_target: unknown, payload: Record<string, { s: string }>) => {
        const optimistic = payload[`state/records/${speciesKey(25)}`];
        recordsChanged.at(-1)!(
          snapshot({ ...settings, [speciesKey(25)]: { s: optimistic.s, at: Date.now() + 5_000, by: "uid-a" } }),
        );
        // Refused: Firebase reverts the local write before rejecting.
        recordsChanged.at(-1)!(snapshot(settings));
        return Promise.reject(new Error("write failed: disconnected"));
      },
    );
    cycleSpecies(25);
    await vi.waitFor(() => expect(syncPhase.value).toBe("error"));
    expect(syncPending.value).toBe(1);
    const stored = JSON.parse(storage.get("pokemon-checklist-sync-v1")!);
    expect(stored.base.records[speciesKey(25)]).toBeUndefined();
    expect(stored.intents[speciesKey(25)].s).toBe("caught");

    connected[0]({ val: () => false });
    connected[0]({ val: () => true });
    recordsChanged.at(-1)!(snapshot(settings));
    await vi.waitFor(() => expect(mocks.update).toHaveBeenCalledTimes(2));
    expect(sentRecords()[1]).toHaveProperty(speciesKey(25), "caught");
  });

  it("M1: an echo is matched to the write in flight, not to any value once sent", async () => {
    const clock = vi.spyOn(Date, "now").mockReturnValue(1_000_000);
    await signedIn(settings);
    cycleSpecies(25); // caught, sent and acknowledged
    await vi.waitFor(() => expect(mocks.update).toHaveBeenCalledTimes(1));
    recordsChanged.at(-1)!(
      snapshot({ ...settings, [speciesKey(25)]: { s: "caught", at: 1_000_010, by: "uid-a" } }),
    );
    mocks.update.mockClear();
    connected[0]({ val: () => false });
    clock.mockReturnValue(2_000_000);
    cycleSpecies(25); // seen, offline
    cycleSpecies(25); // none, offline, at 2,000,000
    clock.mockReturnValue(4_000_000);
    connected[0]({ val: () => true });
    // Chat marked it caught at 3,000,000: newer than the offline clear.
    recordsChanged.at(-1)!(
      snapshot({ ...settings, [speciesKey(25)]: { s: "caught", at: 3_000_000, by: "chat:uid-a" } }),
    );
    await Promise.resolve();

    expect(sentRecords().flatMap((sent) => Object.entries(sent))).not.toContainEqual([
      speciesKey(25),
      "none",
    ]);
    expect(speciesStatus(25)).toBe("caught");
    clock.mockRestore();
  });

  it("H2: another tab's save is not taken as this tab's edits (no Web Locks)", async () => {
    await signedIn(settings);
    connected[0]({ val: () => false });
    cycleSpecies(25); // caught, offline, unsent
    // Tab B, which knows nothing of that edit, writes its view of the account save.
    const theirs = JSON.stringify({
      schemaVersion: 3,
      species: {},
      forms: {},
      starred: [],
      settings: { forms: false, mode: "photonic-prismatic" },
    });
    storage.set(ACCOUNT_SAVE, theirs);
    syncFromStorage({ key: ACCOUNT_SAVE, newValue: theirs } as StorageEvent);
    expect(speciesStatus(25)).toBe("caught");
    cycleSpecies(40);
    connected[0]({ val: () => true });
    recordsChanged.at(-1)!(snapshot(settings));

    await vi.waitFor(() => expect(mocks.update).toHaveBeenCalled());
    const sent = Object.assign({}, ...sentRecords());
    expect(sent[speciesKey(25)]).toBe("caught");
    expect(sent[speciesKey(40)]).toBe("caught");
  });

  it("H2: a store rewrite keeps another tab's unsent edits and pending Reset", async () => {
    await signedIn(settings);
    connected[0]({ val: () => false });
    // Another tab (no Web Locks) recorded an unsent catch and a Reset, and saved them.
    const save = JSON.parse(storage.get(ACCOUNT_SAVE)!);
    save.species = { "151": "caught" };
    storage.set(ACCOUNT_SAVE, JSON.stringify(save));
    syncFromStorage({ key: ACCOUNT_SAVE, newValue: JSON.stringify(save) } as StorageEvent);
    const store = JSON.parse(storage.get("pokemon-checklist-sync-v1")!);
    store.intents = { [speciesKey(151)]: { s: "caught", at: Date.now(), by: "uid-a" } };
    store.reset = [[speciesKey(7), "caught"]];
    storage.set("pokemon-checklist-sync-v1", JSON.stringify(store));

    cycleSpecies(25); // this tab writes the store

    const after = JSON.parse(storage.get("pokemon-checklist-sync-v1")!);
    expect(after.intents[speciesKey(151)].s).toBe("caught");
    expect(after.intents[speciesKey(25)].s).toBe("caught");
    expect(after.reset).toEqual([[speciesKey(7), "caught"]]);
  });

  it("M3: an Undo expires when a record it would put back changes elsewhere", async () => {
    await signedIn(settings);
    cycleSpecies(25);
    savedNotice("Status");
    const undo = notice.value.action!;
    await vi.waitFor(() => expect(syncPending.value).toBe(0)); // acknowledged
    recordsChanged.at(-1)!(
      snapshot({ ...settings, [speciesKey(25)]: { s: "caught", at: Date.now(), by: "uid-a" } }),
    );
    expect(notice.value.action?.label).toBe("Undo"); // its own echo changes nothing
    // Later chat corrects it to seen.
    recordsChanged.at(-1)!(
      snapshot({ ...settings, [speciesKey(25)]: { s: "seen", at: Date.now() + 60_000, by: "chat:uid-a" } }),
    );
    expect(notice.value.action).toBeUndefined();

    mocks.update.mockClear();
    undo.run(); // even a stale reference must not clear the newer value
    await Promise.resolve();
    expect(speciesStatus(25)).toBe("seen");
    expect(sentRecords().flatMap((sent) => Object.keys(sent))).not.toContain(speciesKey(25));
  });

  it("L1: holds back clears that would empty the account, and still sends the rest", async () => {
    await signedIn({
      ...settings,
      [speciesKey(1)]: { s: "caught", at: 100, by: "uid-a" },
      [speciesKey(4)]: { s: "caught", at: 100, by: "uid-a" },
    });
    connected[0]({ val: () => false });
    cycleSpecies(1);
    cycleSpecies(1); // none
    cycleSpecies(4);
    cycleSpecies(4); // none: together these empty the account
    toggleStar(807); // unrelated
    connected[0]({ val: () => true });
    recordsChanged.at(-1)!(
      snapshot({
        ...settings,
        [speciesKey(1)]: { s: "caught", at: 100, by: "uid-a" },
        [speciesKey(4)]: { s: "caught", at: 100, by: "uid-a" },
      }),
    );

    await vi.waitFor(() => expect(mocks.update).toHaveBeenCalledTimes(1));
    expect(sentRecords()[0]).toEqual({ "star:807": "on" });
    await vi.waitFor(() => expect(syncPhase.value).toBe("error"));
    expect(syncPending.value).toBe(2);
    expect(syncMessage.value).toMatch(/Held back clearing 2 Pokémon/);
  });

  it("L4: a refused re-send after a lost acknowledgement is retried with fresh log ids", async () => {
    await signedIn(settings);
    mocks.update.mockRejectedValueOnce(new Error("PERMISSION_DENIED: Permission denied"));
    cycleSpecies(25);
    await vi.waitFor(() => expect(mocks.update).toHaveBeenCalledTimes(2));
    await vi.waitFor(() => expect(syncPhase.value).toBe("ready"));
    expect(sentRecords()[1]).toHaveProperty(speciesKey(25), "caught");
  });
});

describe("held clears, recovery and replacements", () => {
  const settings = {
    "setting:mode": { s: "photonic-prismatic", at: 100, by: "uid-a" },
    "setting:forms": { s: "off", at: 100, by: "uid-a" },
  };
  const two = {
    ...settings,
    [speciesKey(1)]: { s: "caught", at: 100, by: "uid-a" },
    [speciesKey(4)]: { s: "caught", at: 100, by: "uid-a" },
  };
  const ACCOUNT_SAVE = "pokemon-checklist-state-v3:uid-a";
  const sentRecords = () =>
    Object.assign(
      {},
      ...mocks.update.mock.calls.map((call) =>
        Object.fromEntries(
          Object.entries(call[1] as Record<string, { s?: string }>)
            .filter(([key]) => key.startsWith("state/records/"))
            .map(([key, value]) => [key.slice("state/records/".length), value.s]),
        ),
      ),
    ) as Record<string, string>;
  const logOps = () =>
    mocks.update.mock.calls.flatMap((call) =>
      Object.entries(call[1] as Record<string, { op?: string }>)
        .filter(([key]) => key.startsWith("log/"))
        .map(([, value]) => value.op),
    );

  async function signedIn(records: Record<string, unknown>) {
    resetState();
    mocks.get.mockResolvedValue(snapshot(records));
    await startSync({ uid: "uid-a", email: "realbeepmcjeep@gmail.com" });
    connected[0]({ val: () => true });
    mocks.update.mockClear();
  }

  /** Clear both of the account's records while offline, then reconnect. */
  async function clearBothOffline(server: Record<string, unknown>) {
    connected[0]({ val: () => false });
    cycleSpecies(1);
    cycleSpecies(1);
    cycleSpecies(4);
    cycleSpecies(4);
    connected[0]({ val: () => true });
    recordsChanged.at(-1)!(snapshot(server));
    await vi.waitFor(() => expect(syncHeld.value).toBe(2));
  }

  it("N4: held clears stay held when the account gains a record, and across a reload", async () => {
    await signedIn(two);
    await clearBothOffline(two);
    // Another device adds a record; the guard alone would now let both clears go.
    const three = { ...two, [speciesKey(7)]: { s: "caught", at: 200, by: "uid-a" } };
    recordsChanged.at(-1)!(snapshot(three));
    cycleSpecies(40); // an unrelated edit still goes
    await vi.waitFor(() => expect(sentRecords()[speciesKey(40)]).toBe("caught"));
    expect(sentRecords()[speciesKey(1)]).toBeUndefined();
    expect(sentRecords()[speciesKey(4)]).toBeUndefined();

    stopSync();
    mocks.update.mockClear();
    mocks.get.mockResolvedValue(snapshot(three));
    await startSync({ uid: "uid-a", email: "realbeepmcjeep@gmail.com" });
    expect(syncHeld.value).toBe(2);
    expect(speciesStatus(1)).toBe("none");
    expect(sentRecords()[speciesKey(1)]).toBeUndefined();
  });

  it("N4: held clears are sent only when the player says so, as a logged clear", async () => {
    await signedIn(two);
    await clearBothOffline(two);
    resolveHeldClears(true);
    await vi.waitFor(() => expect(sentRecords()[speciesKey(1)]).toBe("none"));
    expect(sentRecords()[speciesKey(4)]).toBe("none");
    expect(logOps()).toEqual(["reset"]);
    expect(syncHeld.value).toBe(0);
  });

  it("will not send held clears while a Restore is still being sent", async () => {
    await signedIn(two);
    await clearBothOffline(two);
    // A Restore (adding #7) goes out, and its write is not answered yet.
    let fail!: (error: Error) => void;
    mocks.update.mockImplementationOnce(
      () => new Promise<void>((_resolve, reject) => (fail = reject)),
    );
    restoreState({
      schemaVersion: 3,
      species: { "7": "caught" },
      forms: {},
      starred: [],
      settings: { forms: false, mode: "photonic-prismatic" },
    });
    await vi.waitFor(() => expect(mocks.update).toHaveBeenCalledTimes(1));

    resolveHeldClears(true);
    expect(notice.value.message).toMatch(/still being sent/);
    expect(syncHeld.value).toBe(2);

    // The Restore's write fails: sent again, still as the logged Restore it was.
    fail(new Error("disconnected"));
    connected[0]({ val: () => false });
    connected[0]({ val: () => true });
    recordsChanged.at(-1)!(snapshot(two));
    await vi.waitFor(() => expect(mocks.update).toHaveBeenCalledTimes(2));
    expect(logOps().at(-1)).toBe("restore");
  });

  it("N4: putting held clears back restores those Pokémon", async () => {
    await signedIn(two);
    await clearBothOffline(two);
    resolveHeldClears(false);
    expect(speciesStatus(1)).toBe("caught");
    expect(speciesStatus(4)).toBe("caught");
    expect(syncHeld.value).toBe(0);
    expect(syncPending.value).toBe(0);
  });

  it("N3: a recovered set that would empty the account keeps what it adds", async () => {
    localStorage.setItem(
      "pokemon-checklist-sync-v1",
      JSON.stringify({ version: 1, deviceId: "dev", uid: "uid-a", email: null, base: { schema: 1, records: two, updatedAt: 0 } }),
    );
    localStorage.setItem(
      ACCOUNT_SAVE,
      JSON.stringify({
        schemaVersion: 3,
        species: { "6": "caught" },
        forms: {},
        starred: [],
        settings: { forms: false, mode: "photonic-prismatic" },
      }),
    );
    mocks.get.mockResolvedValue(snapshot(two));

    await startSync({ uid: "uid-a", email: "realbeepmcjeep@gmail.com" });

    await vi.waitFor(() => expect(sentRecords()[speciesKey(6)]).toBe("caught"));
    expect(sentRecords()[speciesKey(1)]).toBeUndefined();
    expect(speciesStatus(1)).toBe("caught");
    expect(notice.value.message).toMatch(/not sent/);
  });

  it("N7: undoing a Reset still in flight logs the Restore with what the Reset left", async () => {
    await signedIn(two);
    let settle!: () => void;
    mocks.update.mockImplementationOnce(
      (_target: unknown, payload: Record<string, { s: string }>) => {
        const shown: Record<string, unknown> = { ...two };
        for (const [key, value] of Object.entries(payload)) {
          if (key.startsWith("state/records/")) {
            shown[key.slice("state/records/".length)] = { s: value.s, at: Date.now(), by: "uid-a" };
          }
        }
        recordsChanged.at(-1)!(snapshot(shown));
        return new Promise<void>((resolve) => (settle = resolve));
      },
    );
    resetState();
    savedNotice("Status");
    notice.value.action!.run(); // Undo, while the Reset is in flight
    settle();

    await vi.waitFor(() => expect(mocks.update).toHaveBeenCalledTimes(2));
    const restore = Object.values(mocks.update.mock.calls[1][1] as Record<string, { op?: string; before?: unknown }>)
      .find((value) => value.op === "restore")!;
    expect(restore.before).toContainEqual([speciesKey(1), "none"]);
    expect(restore.before).not.toContainEqual([speciesKey(1), "caught"]);
  });
});
