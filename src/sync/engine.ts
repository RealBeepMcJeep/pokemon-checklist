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
import {
  applyState,
  exportState,
  persist,
  setLocalChangeListener,
  setLocalResetListener,
  setSyncAccount,
  showNotice,
  validForms,
  validPokemon,
} from "../state";
import { initFirebase, signOutOfSync, watchAuth } from "./firebase";
import type { User } from "firebase/auth";
import type { SavedState } from "../types";
import {
  TOMBSTONE,
  clearedByReset,
  entriesFromState,
  mergeDocument,
  parseRecordsSnapshot,
  type RecordEntry,
  type RecordKey,
  type SyncDocument,
} from "./records";
import {
  availableStorage,
  deviceIdFor,
  emptyDocument,
  forgetSyncSession,
  isWholeAccountClear,
  loadStore,
  localIntentChanges,
  pendingEntries,
  rememberSyncSession,
  saveFromView,
  saveStore,
  viewWithLocalIntent,
  type ResetImage,
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
/** Whether the database connection is up; only meaningful while signed in. */
export const syncOnline = signal(false);

let database: Database | null = null;
let activeUid: string | null = null;
let deviceId = "";
let base: SyncDocument = emptyDocument();
let lastPushed = "";
let unsubscribeValue: (() => void) | null = null;
let unsubscribeConnection: (() => void) | null = null;
let unsubscribeAuth: (() => void) | null = null;
// Between pressing "Sign in" and an account arriving. Firebase reports "signed out" as
// soon as auth starts; that report must not end a sign-in that has not finished yet.
let signInPending = false;
let generation = 0;
let initialReadComplete = false;
let initialReadInFlight = false;
let ignoreLocalEvents = false;
let observedLocal: SavedState | null = null;
let localIntents: Record<RecordKey, RecordEntry> = {};
let pendingReset: ResetImage | null = null;
let resetTarget: Record<RecordKey, string> | null = null;
let resetSent = false;
let sentReset: ResetImage | null = null;
let publishInFlight: Promise<void> | null = null;
let publishQueued = false;

/**
 * What this device still owes the server: its own edits that the confirmed document
 * does not reflect yet. Only recorded local edits count. Any other difference between
 * the save and the document is a change from another device on its way in, and
 * treating it as owed would send an "undo" of that change.
 */
function owed(): Record<RecordKey, RecordEntry> {
  const out: Record<RecordKey, RecordEntry> = {};
  for (const [key, entry] of Object.entries(localIntents)) {
    if (base.records[key]?.s !== entry.s) out[key] = entry;
  }
  return out;
}

function safeStorage(): StorageLike | null {
  return availableStorage();
}

function isCurrent(run: number, uid: string): boolean {
  return run === generation && activeUid === uid && database !== null;
}

function describe(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  if (/permission_denied|PERMISSION_DENIED/i.test(message)) {
    return "This account is not allowed to use the shared checklist.";
  }
  return "Sync is offline; changes are kept here and sent when it reconnects.";
}

function readStore(uid: string) {
  const store = loadStore(
    safeStorage() ?? {
      getItem: () => null,
      setItem: () => {},
      removeItem: () => {},
    },
  );
  // A base belongs to one account. Another account's confirmed document must
  // never be reused, or this device would silently accept the wrong history.
  return store.uid === uid ? store : null;
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
    ...(pendingReset ? { reset: pendingReset } : {}),
  });
}

/** Publish everything the save holds that the confirmed document does not. */
async function publishNow(): Promise<void> {
  if (!database || !activeUid || !initialReadComplete) return;
  const run = generation;
  const uid = activeUid;
  const pending = owed();
  const keys = Object.keys(pending);
  syncPending.value = keys.length;
  if (keys.length === 0 && !pendingReset) {
    lastPushed = "";
    syncPhase.value = "ready";
    return;
  }

  // Refuse to be the reason an account empties itself. This guards the bug that
  // wiped a real account: a device that had not yet adopted the account's data
  // published the difference between "empty" and "everything". Reset is the
  // explicit, user-confirmed exception and is logged in the same atomic update.
  if (!pendingReset && isWholeAccountClear(base, pending)) {
    lastPushed = "";
    syncPhase.value = "error";
    syncMessage.value =
      "Refused to send a change that would clear the whole checklist. Nothing was sent.";
    return;
  }

  const signature = JSON.stringify([
    pendingReset ? "reset" : "set",
    keys
      .sort((a, b) => a.localeCompare(b))
      .map((key) => [key, pending[key].s]),
  ]);
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
    if (!pendingReset) {
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
  }
  if (pendingReset) {
    const logRef = push(ref(database, `users/${uid}/log`));
    payload[`log/${logRef.key}`] = {
      op: "reset",
      at: serverTimestamp(),
      by: uid,
      dev: deviceId,
      cleared: pendingReset,
    };
    resetTarget = Object.fromEntries(
      keys.map((key) => [key, pending[key].s]),
    );
    sentReset = pendingReset;
    resetSent = false;
  }

  lastPushed = signature;
  syncPhase.value = "pending";
  try {
    await update(ref(database, `users/${uid}`), payload);
    if (!isCurrent(run, uid)) return;
    if (pendingReset && sentReset && sameReset(pendingReset, sentReset)) {
      resetSent = true;
      settleResetIfAcknowledged(uid);
    }
    syncPhase.value = "ready";
    syncMessage.value = "";
  } catch (error) {
    if (!isCurrent(run, uid)) return;
    lastPushed = "";
    syncPhase.value = "error";
    syncMessage.value = describe(error);
  }
}

async function publish(): Promise<void> {
  if (publishInFlight) {
    publishQueued = true;
    return publishInFlight;
  }
  const work = publishNow();
  publishInFlight = work;
  try {
    await work;
  } finally {
    if (publishInFlight !== work) return;
    publishInFlight = null;
    if (publishQueued) {
      publishQueued = false;
      void publish();
    }
  }
}

function recordLocalChange(uid: string, state: SavedState): void {
  if (ignoreLocalEvents) return;
  const previous = observedLocal ?? state;
  for (const [key, entry] of Object.entries(
    localIntentChanges(previous, state, Date.now(), uid),
  )) {
    if (base.records[key]?.s === entry.s) delete localIntents[key];
    else localIntents[key] = entry;
  }
  observedLocal = state;
  void publish();
}

function sameReset(left: ResetImage, right: ResetImage): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function recordReset(before: SavedState, uid: string): void {
  if (ignoreLocalEvents || !activeUid || activeUid !== uid) return;
  const cleared = clearedByReset(before);
  pendingReset = cleared.length > 0 ? cleared : null;
  resetTarget = null;
  resetSent = false;
  sentReset = null;
  writeBase(uid);
}

function settleResetIfAcknowledged(uid: string): boolean {
  if (
    !pendingReset ||
    !sentReset ||
    !sameReset(pendingReset, sentReset) ||
    !resetSent ||
    !resetTarget
  ) {
    return false;
  }
  if (
    !Object.entries(resetTarget).every(
      ([key, value]) => base.records[key]?.s === value,
    )
  ) {
    return false;
  }
  pendingReset = null;
  resetTarget = null;
  resetSent = false;
  sentReset = null;
  writeBase(uid);
  return true;
}

function applyRemote(uid: string, incoming: unknown, run: number): void {
  if (!isCurrent(run, uid) || !initialReadComplete) return;
  base = mergeDocument(base, {
    schema: 1,
    records: parseRecordsSnapshot(incoming),
    updatedAt: Date.now(),
  });

  for (const [key, entry] of Object.entries(localIntents)) {
    if (base.records[key]?.s === entry.s) delete localIntents[key];
  }
  if (!settleResetIfAcknowledged(uid)) writeBase(uid);

  const pending = owed();
  applyState(
    saveFromView(viewWithLocalIntent(base, pending), validPokemon, validForms),
  );
  // Save what arrived. A save left behind the confirmed document is what later made
  // a whole checklist look like 64 deletions waiting to be sent.
  ignoreLocalEvents = true;
  persist();
  ignoreLocalEvents = false;
  observedLocal = exportState();
  syncPending.value = Object.keys(pending).length;
  if (Object.keys(pending).length === 0 && !pendingReset) {
    lastPushed = "";
    syncPhase.value = "ready";
  } else {
    syncPhase.value = "pending";
  }
}

function subscribeConnection(uid: string, run: number): void {
  if (!database || unsubscribeConnection) return;
  unsubscribeConnection = onValue(
    ref(database, ".info/connected"),
    (snapshot) => {
      if (!isCurrent(run, uid)) return;
      syncOnline.value = snapshot.val() === true;
      if (snapshot.val() === true) {
        syncMessage.value = "";
        if (!initialReadComplete) void loadInitial(uid, run);
        else void publish();
      } else if (syncPhase.value !== "off" && syncPhase.value !== "error") {
        syncPhase.value = syncPending.value > 0 ? "pending" : "ready";
      }
    },
  );
}

function subscribeValue(uid: string, run: number): void {
  if (!database || unsubscribeValue) return;
  unsubscribeValue = onValue(
    ref(database, `users/${uid}/state/records`),
    (snapshot) => applyRemote(uid, snapshot.val() ?? {}, run),
    (error) => {
      if (!isCurrent(run, uid)) return;
      syncPhase.value = "error";
      syncMessage.value = describe(error);
    },
  );
}

async function loadInitial(uid: string, run: number): Promise<void> {
  if (!database || !isCurrent(run, uid) || initialReadInFlight) return;
  initialReadInFlight = true;
  try {
    const snapshot = await get(ref(database, `users/${uid}/state/records`));
    if (!isCurrent(run, uid)) return;
    const remote = parseRecordsSnapshot(snapshot.val() ?? {});
    const serverHasRecords = Object.keys(remote).length > 0;
    // What this device last confirmed, before the server's current copy is merged in.
    const confirmed = base;
    base = mergeDocument(base, {
      schema: 1,
      records: remote,
      updatedAt: Date.now(),
    });
    writeBase(uid);

    ignoreLocalEvents = true;
    const device = exportState();
    const deviceHasProgress =
      Object.keys(device.species).length > 0 ||
      Object.keys(device.forms).length > 0 ||
      device.starred.length > 0;
    const hadAccountSave = setSyncAccount(uid, { adopt: !serverHasRecords });
    if (serverHasRecords) {
      // Only edits made here since this device's last confirmed copy are its own; the
      // rest of any difference is other devices' work. Without a confirmed copy there
      // are no known edits, and a set that would empty the account is never an edit.
      let edits =
        hadAccountSave && Object.keys(confirmed.records).length > 0
          ? pendingEntries(confirmed, exportState(), Date.now(), uid)
          : {};
      if (!pendingReset && isWholeAccountClear(base, edits, 1)) edits = {};
      localIntents = edits;
      applyState(
        saveFromView(viewWithLocalIntent(base, owed()), validPokemon, validForms),
      );
      // Keep the confirmed view (plus any real local intent) as the account save;
      // a synthetic empty save must never look like a deliberate whole-account clear
      // after a reload.
      persist();
      if (!hadAccountSave && deviceHasProgress) {
        // Otherwise it looks as if this device's progress was just deleted.
        showNotice(
          "This account already has a checklist, so it is shown here. This device's own progress is kept: sign out to see it again.",
          "good",
        );
      }
    }
    if (!serverHasRecords) {
      // An empty account adopts everything this device holds.
      localIntents = entriesFromState(exportState(), Date.now(), uid);
    }
    ignoreLocalEvents = false;
    observedLocal = exportState();
    initialReadComplete = true;
    subscribeValue(uid, run);
    await publish();
  } catch (error) {
    if (isCurrent(run, uid)) {
      initialReadComplete = false;
      syncPhase.value = "error";
      syncMessage.value = describe(error);
    }
  } finally {
    if (isCurrent(run, uid)) initialReadInFlight = false;
  }
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
  const run = generation;
  const { db } = initFirebase();
  database = db;
  activeUid = account.uid;
  deviceId = deviceIdFor(storage);
  const stored = readStore(account.uid);
  base = stored?.base ?? emptyDocument();
  pendingReset = stored?.reset ?? null;
  resetTarget = null;
  resetSent = false;
  sentReset = null;
  localIntents = {};
  observedLocal = exportState();
  initialReadComplete = false;
  // From here on this device expects a session, so a reload may touch auth.
  rememberSyncSession(storage);
  syncAccount.value = { uid: account.uid, email: account.email ?? "" };
  syncPhase.value = "connecting";
  setLocalChangeListener((state) => recordLocalChange(account.uid, state));
  setLocalResetListener((before) => recordReset(before, account.uid));
  subscribeConnection(account.uid, run);
  await loadInitial(account.uid, run);
}

function onAuthState(user: User | null, allowed: boolean): void {
  if (!user) {
    if (!signInPending) stopSync();
    return;
  }
  signInPending = false;
  if (!allowed) {
    stopSync();
    // Leave nothing behind: a disallowed session would otherwise be restored, and
    // refused again, on every later sign-in attempt.
    void signOutOfSync().catch(() => {});
    showNotice(
      `${user.email ?? "That account"} is not on the list for the shared checklist.`,
      "error",
    );
    return;
  }
  if (activeUid === user.uid) return;
  void startSync({ uid: user.uid, email: user.email }).catch((error) => {
    syncPhase.value = "error";
    syncMessage.value = describe(error);
  });
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
  if (unsubscribeAuth) return;
  unsubscribeAuth = watchAuth(onAuthState);
}

/**
 * Prepare for a sign-in, called BEFORE the provider is invoked.
 *
 * Sets the "this device has signed in before" flag first, so a reload during or
 * after signing in still looks for the session instead of coming back signed out.
 */
export function beginSignIn(): void {
  signInPending = true;
  rememberSyncSession(safeStorage());
  watchSyncAccount();
}

/** The player gave up on signing in: go back to touching nothing on the next load. */
export function cancelSignIn(): void {
  signInPending = false;
  if (!activeUid) forgetSyncSession(safeStorage());
}

export function stopSync(): void {
  generation += 1;
  publishInFlight = null;
  publishQueued = false;
  unsubscribeValue?.();
  unsubscribeConnection?.();
  unsubscribeValue = null;
  unsubscribeConnection = null;
  if (activeUid) {
    // Keep the account's own copy warm for the next offline session, without
    // notifying the publisher on the way out.
    setLocalChangeListener(null);
    setLocalResetListener(null);
    persist();
    // Back to the device's own checklist, which was never touched.
    setSyncAccount(null);
    activeUid = null;
  }
  database = null;
  base = emptyDocument();
  lastPushed = "";
  initialReadComplete = false;
  initialReadInFlight = false;
  ignoreLocalEvents = false;
  observedLocal = null;
  localIntents = {};
  pendingReset = null;
  resetTarget = null;
  resetSent = false;
  sentReset = null;
  // A signed-out device must go back to touching nothing at all.
  forgetSyncSession(safeStorage());
  syncAccount.value = null;
  syncPending.value = 0;
  syncOnline.value = false;
  syncPhase.value = "off";
  syncMessage.value = "";
}
