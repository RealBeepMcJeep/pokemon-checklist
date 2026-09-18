import { signal } from "@preact/signals";
import {
  get,
  onValue,
  push,
  ref,
  serverTimestamp,
  update,
  type Database,
} from "firebase/database";
import { ENCOUNTERS_BY_MODE, POKEMON } from "../data";
import { buildFormDefinitions } from "../domain";
import {
  applyState,
  exportState,
  persist,
  setLocalChangeListener,
  setSyncAccount,
  showNotice,
} from "../state";
import { initFirebase, watchAuth } from "./firebase";
import type { User } from "firebase/auth";
import {
  TOMBSTONE,
  mergeDocument,
  parseRecordsSnapshot,
  type SyncDocument,
} from "./records";
import {
  deviceIdFor,
  emptyDocument,
  forgetSyncSession,
  loadStore,
  pendingEntries,
  rememberSyncSession,
  saveFromView,
  saveStore,
  viewWithPending,
  type StorageLike,
} from "./outbox";

/**
 * The half of sync that talks to the database.
 *
 * Everything it decides is pure logic imported from `records.ts` and `outbox.ts`;
 * this file only performs the I/O, so the parts that can be wrong are the parts
 * that are unit tested.
 *
 * The server owns ordering: every write carries `serverTimestamp()`, so no device
 * clock can win an argument. A local change is written immediately and published
 * afterwards — never the other way round — so nothing a player taps ever waits
 * on the network.
 */

export type SyncPhase = "off" | "connecting" | "ready" | "pending" | "error";

export const syncPhase = signal<SyncPhase>("off");
export const syncPending = signal(0);
export const syncAccount = signal<{ uid: string; email: string } | null>(null);
export const syncMessage = signal("");

const validPokemon = new Set(POKEMON.map(({ id }) => id));
const validForms = new Set(
  buildFormDefinitions(ENCOUNTERS_BY_MODE).keys(),
);

let database: Database | null = null;
let activeUid: string | null = null;
let deviceId = "";
let base: SyncDocument = emptyDocument();
let lastPushed = "";
let unsubscribeValue: (() => void) | null = null;
let unsubscribeConnection: (() => void) | null = null;

function safeStorage(): StorageLike | null {
  try {
    localStorage.getItem("probe");
    return localStorage;
  } catch {
    return null;
  }
}

function describe(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  if (/permission_denied|PERMISSION_DENIED/i.test(message)) {
    return "This account is not allowed to use the shared checklist.";
  }
  return "Sync is offline; changes are kept here and sent when it reconnects.";
}

function readBase(uid: string): SyncDocument {
  const store = loadStore(safeStorage() ?? { getItem: () => null, setItem: () => {} });
  // A base belongs to one account. Another account's confirmed document must
  // never be reused, or this device would silently accept the wrong history.
  return store.uid === uid ? store.base : emptyDocument();
}

function writeBase(uid: string): void {
  const storage = safeStorage();
  if (!storage) return;
  saveStore(storage, {
    version: 1,
    deviceId,
    uid,
    email: syncAccount.value?.email ?? null,
    base,
  });
}

/** Publish everything the save holds that the confirmed document does not. */
async function publish(): Promise<void> {
  if (!database || !activeUid) return;
  const uid = activeUid;
  const pending = pendingEntries(base, exportState(), Date.now(), uid);
  const keys = Object.keys(pending);
  syncPending.value = keys.length;
  if (keys.length === 0) {
    lastPushed = "";
    syncPhase.value = "ready";
    return;
  }

  // The same values may already be in flight; the echo is what clears the diff,
  // so re-sending identical payloads would only add traffic.
  const signature = JSON.stringify(keys.sort().map((key) => [key, pending[key].s]));
  if (signature === lastPushed) return;

  const payload: Record<string, unknown> = {
    // The rules require these to exist on the state node, so the first publish
    // creates the document shape rather than only its records.
    "state/schema": 1,
    "state/updatedAt": serverTimestamp(),
  };
  for (const key of keys) {
    payload[`state/records/${key}`] = {
      s: pending[key].s,
      at: serverTimestamp(),
      by: uid,
    };
    const logRef = push(ref(database, `users/${uid}/log`));
    payload[`log/${logRef.key}`] = {
      op: "set",
      at: serverTimestamp(),
      by: uid,
      dev: deviceId,
      key,
      from: base.records[key]?.s ?? TOMBSTONE,
      to: pending[key].s,
    };
  }

  lastPushed = signature;
  syncPhase.value = "pending";
  try {
    await update(ref(database, `users/${uid}`), payload);
    syncPhase.value = "ready";
    syncMessage.value = "";
  } catch (error) {
    lastPushed = "";
    syncPhase.value = "error";
    syncMessage.value = describe(error);
  }
}

function applyRemote(uid: string, incoming: unknown): void {
  base = mergeDocument(base, {
    schema: 1,
    records: parseRecordsSnapshot(incoming),
    updatedAt: Date.now(),
  });
  writeBase(uid);
  const pending = pendingEntries(base, exportState(), Date.now(), uid);
  syncPending.value = Object.keys(pending).length;
  // Applying is not a local change: persist() would notify the publisher, and the
  // view already equals what the server holds plus anything still unpublished.
  applyState(saveFromView(viewWithPending(base, pending), validPokemon, validForms));
  if (Object.keys(pending).length === 0) {
    lastPushed = "";
    syncPhase.value = "ready";
  } else {
    syncPhase.value = "pending";
  }
}

function subscribe(uid: string): void {
  if (!database) return;
  unsubscribeValue = onValue(
    ref(database, `users/${uid}/state/records`),
    (snapshot) => applyRemote(uid, snapshot.val() ?? {}),
    (error) => {
      syncPhase.value = "error";
      syncMessage.value = describe(error);
    },
  );
  unsubscribeConnection = onValue(ref(database, ".info/connected"), (snapshot) => {
    if (snapshot.val() === true) {
      syncMessage.value = "";
      void publish();
    } else if (syncPhase.value !== "off" && syncPhase.value !== "error") {
      syncPhase.value = syncPending.value > 0 ? "pending" : "ready";
    }
  });
}

/**
 * Begin syncing an account. Reads what the server holds before touching anything:
 * a brand-new account adopts the progress this device already has, while an
 * account that already has a collection keeps it and this device takes its word.
 */
export async function startSync(account: {
  uid: string;
  email: string | null;
}): Promise<void> {
  const storage = safeStorage();
  if (!storage) {
    syncPhase.value = "error";
    syncMessage.value = "This browser cannot store data, so sync stays off.";
    return;
  }
  stopSync();
  const { db } = initFirebase();
  database = db;
  activeUid = account.uid;
  deviceId = deviceIdFor(storage);
  // From here on this device expects a session, so a reload may touch auth.
  rememberSyncSession(storage);
  syncAccount.value = { uid: account.uid, email: account.email ?? "" };
  base = readBase(account.uid);
  syncPhase.value = "connecting";

  let serverHasRecords = false;
  try {
    const snapshot = await get(ref(db, `users/${account.uid}/state/records`));
    const remote = parseRecordsSnapshot(snapshot.val() ?? {});
    serverHasRecords = Object.keys(remote).length > 0;
    base = mergeDocument(base, {
      schema: 1,
      records: remote,
      updatedAt: Date.now(),
    });
    writeBase(account.uid);
  } catch (error) {
    syncPhase.value = "error";
    syncMessage.value = describe(error);
    return;
  }

  // Adopt the device's offline progress only into an account that is empty.
  setSyncAccount(account.uid, { adopt: !serverHasRecords });

  subscribe(account.uid);
  setLocalChangeListener(() => {
    void publish();
  });
  await publish();
}

function onAuthState(user: User | null, allowed: boolean): void {
  if (!user) {
    stopSync();
    return;
  }
  if (!allowed) {
    stopSync();
    showNotice(
      `${user.email ?? "That account"} is not on the list for the shared checklist.`,
      "error",
    );
    return;
  }
  void startSync({ uid: user.uid, email: user.email });
}

/**
 * Connect auth state to sync, and the seam the sign-in control uses.
 *
 * The app calls this on load ONLY when this device has signed in before, because
 * initialising Firebase Auth is not traffic-free: on mobile user agents the SDK
 * eagerly fetches its sign-in iframe and GAPI helper even for a signed-out visitor.
 * A player who never signs in must be able to say their device never contacted
 * anyone, and this is what makes that true.
 */
export function watchSyncAccount(): void {
  watchAuth(onAuthState);
}

export function stopSync(): void {
  unsubscribeValue?.();
  unsubscribeConnection?.();
  unsubscribeValue = null;
  unsubscribeConnection = null;
  if (activeUid) {
    // Keep the account's own copy warm for the next offline session, without
    // notifying the publisher on the way out.
    setLocalChangeListener(null);
    persist();
    // Back to the device's own checklist, which was never touched.
    setSyncAccount(null);
    activeUid = null;
  }
  database = null;
  base = emptyDocument();
  lastPushed = "";
  // A signed-out device must go back to touching nothing at all.
  forgetSyncSession(safeStorage());
  syncAccount.value = null;
  syncPending.value = 0;
  syncPhase.value = "off";
  syncMessage.value = "";
}
