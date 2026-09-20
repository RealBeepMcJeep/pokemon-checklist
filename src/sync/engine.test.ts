import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  onValue: vi.fn(),
  push: vi.fn(() => ({ key: "event-1" })),
  ref: vi.fn((db: unknown, path: string) => ({ db, path })),
  serverTimestamp: vi.fn(() => ({ ".sv": "timestamp" })),
  update: vi.fn(),
  initFirebase: vi.fn(() => ({ auth: {}, db: {} })),
  watchAuth: vi.fn(() => vi.fn()),
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
}));

import {
  startSync,
  stopSync,
  syncAccount,
  syncPhase,
  watchSyncAccount,
} from "./engine";
import { cycleSpecies, resetState } from "../state";
import { speciesKey } from "./records";

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

beforeEach(() => {
  installStorage();
  connected = [];
  recordsChanged = [];
  mocks.get.mockReset();
  mocks.onValue.mockReset();
  mocks.onValue.mockImplementation((target: { path: string }, callback: (value: unknown) => void) => {
    if (target.path === ".info/connected") connected.push(callback as never);
    if (target.path.endsWith("/state/records")) recordsChanged.push(callback as never);
    return vi.fn();
  });
  mocks.push.mockClear();
  mocks.ref.mockClear();
  mocks.serverTimestamp.mockClear();
  mocks.update.mockReset().mockResolvedValue(undefined);
  mocks.watchAuth.mockReset().mockReturnValue(vi.fn());
  mocks.initFirebase.mockClear();
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

describe("auth watching", () => {
  it("registers one auth watcher even when startup and sign-in both ask for it", () => {
    watchSyncAccount();
    watchSyncAccount();
    expect(mocks.watchAuth).toHaveBeenCalledTimes(1);
  });
});
