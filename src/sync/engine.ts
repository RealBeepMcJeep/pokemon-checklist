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
  downloadText,
  exportState,
  persist,
  setLocalChangeListener,
  setLocalReplaceListener,
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
  beforeImage,
  entriesFromState,
  isClearing,
  mergeDocument,
  parseRecordsSnapshot,
  type RecordEntry,
  type RecordKey,
  type SyncDocument,
} from "./records";
import {
  SYNC_SESSION_KEY,
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
  supersedes,
  viewWithLocalIntent,
  type ReplaceOp,
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
 * The server stamps every write with `serverTimestamp()`. A local change is written
 * immediately and published afterwards — never the other way round — so nothing a
 * player taps ever waits on the network. Each unsent edit also remembers when it
 * was made, in estimated server time, so the edit made last wins: a newer change
 * from another device or from chat is never overwritten by an older edit that
 * merely reached the server later.
 */

export type SyncPhase = "off" | "connecting" | "ready" | "pending" | "error";

export const syncPhase = signal<SyncPhase>("off");
export const syncPending = signal(0);
export const syncAccount = signal<{ uid: string; email: string } | null>(null);
export const syncMessage = signal("");
/** Whether the database connection is up; only meaningful while signed in. */
export const syncOnline = signal(false);

/** How long a failed record listener waits before listening again. */
const RELISTEN_DELAY = 30_000;

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
let pendingOp: ReplaceOp = "reset";
let publishInFlight: Promise<void> | null = null;
let publishQueued = false;
/** Server time minus this device's clock, from `.info/serverTimeOffset`. */
let serverOffset = 0;
// Nothing is sent while the connection is down, nor after it returns until the
// server's current records have arrived: sending first is how a stale offline edit
// (or an offline Reset) overwrote newer changes it had not seen yet.
let connectionDown = false;
let awaitingFresh = false;
/** Values this device published per record, to recognise their echoes. */
const sentValues = new Map<RecordKey, Set<string>>();

const serverNow = (): number => Date.now() + serverOffset;

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

/**
 * Forget edits the confirmed document now reflects, and drop the ones a newer
 * change from elsewhere has replaced. `previous` is the document before the latest
 * merge: only a record that changed in that merge can have replaced anything, and
 * this device's own writes echoing back never do. Returns how many were dropped.
 */
function dropSuperseded(previous: Record<RecordKey, RecordEntry>): number {
  let dropped = 0;
  for (const [key, intent] of Object.entries(localIntents)) {
    const remote = base.records[key];
    if (remote?.s === intent.s) {
      delete localIntents[key];
      continue;
    }
    if (!remote || remote === previous[key]) continue;
    if (sentValues.get(key)?.has(remote.s)) continue;
    if (supersedes(remote, intent)) {
      delete localIntents[key];
      dropped += 1;
    }
  }
  return dropped;
}

function supersededNotice(dropped: number): void {
  if (dropped === 0) return;
  const count = dropped === 1 ? "An older change" : `${dropped} older changes`;
  showNotice(`${count} made here gave way to newer ones from another device.`);
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
    ...(pendingReset && pendingOp === "restore" ? { op: "restore" as const } : {}),
    ...(Object.keys(localIntents).length > 0 ? { intents: localIntents } : {}),
    offset: serverOffset,
  });
}

/** Publish this device's edits that the confirmed document does not hold. */
async function publishNow(): Promise<void> {
  if (!database || !activeUid || !initialReadComplete) return;
  const run = generation;
  const uid = activeUid;
  const pending = owed();
  const keys = Object.keys(pending).sort((a, b) => a.localeCompare(b));
  syncPending.value = keys.length;
  if (connectionDown || awaitingFresh) {
    if (syncPhase.value !== "error") {
      syncPhase.value = keys.length > 0 ? "pending" : "ready";
    }
    return;
  }

  // A Reset or Restore is logged once, with the before-image of the records it
  // still changes. A record a newer change elsewhere has replaced is no longer
  // part of it, and one with nothing left to change is finished.
  const image = pendingReset?.filter(([key]) => key in pending) ?? [];
  if (pendingReset && image.length === 0) {
    pendingReset = null;
    writeBase(uid);
  }
  if (keys.length === 0) {
    lastPushed = "";
    syncPhase.value = "ready";
    return;
  }

  // Refuse to be the reason an account empties itself. This guards the bug that
  // wiped a real account: a device that had not yet adopted the account's data
  // published the difference between "empty" and "everything". Reset and Restore
  // are the explicit, user-confirmed exceptions, logged in the same atomic update.
  if (image.length === 0 && isWholeAccountClear(base, pending)) {
    lastPushed = "";
    syncPhase.value = "error";
    syncMessage.value =
      "Refused to send a change that would clear the whole checklist. Nothing was sent.";
    return;
  }

  const op = image.length > 0 ? pendingOp : "set";
  const signature = JSON.stringify([
    op,
    keys.map((key) => [key, pending[key].s]),
  ]);
  if (signature === lastPushed) return;

  const payload: Record<string, unknown> = {
    // The rules require these to exist on the state node, so the first publish
    // creates the document shape rather than only its records.
    "state/schema": 1,
    "state/updatedAt": serverTimestamp(),
  };
  const replaced = new Set(image.map(([key]) => key));
  for (const key of keys) {
    payload[`state/records/${key}`] = {
      s: pending[key].s,
      at: serverTimestamp(),
      by: uid,
    };
    if (!replaced.has(key)) {
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
    const values = sentValues.get(key) ?? new Set<string>();
    sentValues.set(key, values.add(pending[key].s));
  }
  if (image.length > 0) {
    const logRef = push(ref(database, `users/${uid}/log`));
    payload[`log/${logRef.key}`] = {
      op,
      at: serverTimestamp(),
      by: uid,
      dev: deviceId,
      // A reset's before-image is what it cleared; a restore's is what it replaced.
      [op === "reset" ? "cleared" : "before"]: image,
    };
  }
  const sent = image.length > 0 ? pendingReset : null;

  lastPushed = signature;
  syncPhase.value = "pending";
  try {
    await update(ref(database, `users/${uid}`), payload);
    if (!isCurrent(run, uid)) return;
    // Written atomically with its log event, so the replacement is done.
    if (sent && pendingReset === sent) {
      pendingReset = null;
      writeBase(uid);
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
    localIntentChanges(previous, state, serverNow(), uid),
  )) {
    if (base.records[key]?.s === entry.s) delete localIntents[key];
    else localIntents[key] = entry;
  }
  observedLocal = state;
  // Kept with the time each edit was made, so a reload still knows which is newer.
  writeBase(uid);
  void publish();
}

function recordReplace(before: SavedState, op: ReplaceOp, uid: string): void {
  if (ignoreLocalEvents || !activeUid || activeUid !== uid) return;
  // A replacement not sent yet merges into this one; its before-image is older, so
  // it is the true "before" for the records both touch.
  const earlier = pendingReset ?? [];
  const known = new Set(earlier.map(([key]) => key));
  const image = [
    ...earlier,
    ...beforeImage(before, exportState()).filter(([key]) => !known.has(key)),
  ];
  pendingReset = image.length > 0 ? image : null;
  pendingOp = op;
  writeBase(uid);
}

function armLocalListeners(uid: string): void {
  observedLocal = exportState();
  setLocalChangeListener((state) => recordLocalChange(uid, state));
  setLocalReplaceListener((before, op) => recordReplace(before, op, uid));
}

function applyRemote(uid: string, incoming: unknown, run: number): void {
  if (!isCurrent(run, uid) || !initialReadComplete) return;
  const previous = base.records;
  base = mergeDocument(base, {
    schema: 1,
    records: parseRecordsSnapshot(incoming),
    updatedAt: Date.now(),
  });
  const dropped = dropSuperseded(previous);
  writeBase(uid);

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
  supersededNotice(dropped);
  if (Object.keys(pending).length === 0 && !pendingReset) {
    lastPushed = "";
    syncPhase.value = "ready";
  } else {
    syncPhase.value = "pending";
  }
  if (awaitingFresh) {
    // The server's current records are in: anything still owed can go now.
    awaitingFresh = false;
    void publish();
  }
}

function subscribeConnection(uid: string, run: number): void {
  if (!database || unsubscribeConnection) return;
  const stopOffset = onValue(ref(database, ".info/serverTimeOffset"), (snapshot) => {
    if (!isCurrent(run, uid)) return;
    serverOffset = Number(snapshot.val()) || 0;
  });
  const stopConnected = onValue(ref(database, ".info/connected"), (snapshot) => {
    if (!isCurrent(run, uid)) return;
    const up = snapshot.val() === true;
    syncOnline.value = up;
    if (!up) {
      connectionDown = true;
      // Stop listening, so the return starts from what the server holds THEN
      // rather than from a cached copy that predates the outage.
      unsubscribeValue?.();
      unsubscribeValue = null;
      if (syncPhase.value !== "off" && syncPhase.value !== "error") {
        syncPhase.value = syncPending.value > 0 ? "pending" : "ready";
      }
      return;
    }
    const wasDown = connectionDown;
    connectionDown = false;
    syncMessage.value = "";
    if (!initialReadComplete) void loadInitial(uid, run);
    else if (wasDown || !unsubscribeValue) {
      awaitingFresh = true;
      subscribeValue(uid, run);
    } else void publish();
  });
  unsubscribeConnection = () => {
    stopOffset();
    stopConnected();
  };
}

function subscribeValue(uid: string, run: number): void {
  // While the connection is down, reconnecting subscribes (and waits for fresh data).
  if (!database || unsubscribeValue || connectionDown) return;
  unsubscribeValue = onValue(
    ref(database, `users/${uid}/state/records`),
    (snapshot) => applyRemote(uid, snapshot.val() ?? {}, run),
    (error) => {
      if (!isCurrent(run, uid)) return;
      // Firebase has already dropped a listener that failed. Listen again later,
      // and send nothing until the server's records are flowing again.
      unsubscribeValue = null;
      awaitingFresh = true;
      syncPhase.value = "error";
      syncMessage.value = describe(error);
      setTimeout(() => {
        if (isCurrent(run, uid)) subscribeValue(uid, run);
      }, RELISTEN_DELAY);
    },
  );
}

/**
 * This device's own edits since it last confirmed the account's document: how its
 * save differs from that document. Each keeps the time recorded when it was made;
 * one with no record of its time is dated so that it loses any close call that
 * would clear data. With no confirmed document to compare against (the sync store
 * was lost), only records the server has never held count, so nothing the server
 * has is overridden or cleared.
 */
function recoveredEdits(
  confirmed: SyncDocument,
  save: SavedState,
  uid: string,
): Record<RecordKey, RecordEntry> {
  const now = serverNow();
  if (Object.keys(confirmed.records).length === 0) {
    return Object.fromEntries(
      Object.entries(entriesFromState(save, now, uid)).filter(
        ([key, entry]) => !(key in base.records) && !isClearing(entry.s),
      ),
    );
  }
  const edits = pendingEntries(confirmed, save, now, uid);
  for (const [key, edit] of Object.entries(edits)) {
    const known = localIntents[key];
    if (known?.s === edit.s) edits[key] = known;
    else if (isClearing(edit.s)) {
      edits[key] = { ...edit, at: confirmed.records[key]?.at ?? 0 };
    }
  }
  return edits;
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

    ignoreLocalEvents = true;
    const device = exportState();
    const deviceHasProgress =
      Object.keys(device.species).length > 0 ||
      Object.keys(device.forms).length > 0 ||
      device.starred.length > 0;
    const hadAccountSave = setSyncAccount(uid, { adopt: !serverHasRecords });
    let dropped = 0;
    if (serverHasRecords) {
      // Only edits made here since this device's last confirmed copy are its own; the
      // rest of any difference is other devices' work. Without an account save there
      // are no known edits, and a set that would empty the account is never an edit.
      const save = exportState();
      let edits = hadAccountSave ? recoveredEdits(confirmed, save, uid) : {};
      if (!pendingReset && isWholeAccountClear(base, edits, 1)) edits = {};
      localIntents = edits;
      dropped = dropSuperseded(confirmed.records);
      applyState(
        saveFromView(viewWithLocalIntent(base, owed()), validPokemon, validForms),
      );
      // Keep the confirmed view (plus any real local intent) as the account save;
      // a synthetic empty save must never look like a deliberate whole-account clear
      // after a reload.
      persist();
      const lostTrack =
        hadAccountSave && Object.keys(confirmed.records).length === 0;
      if (lostTrack && JSON.stringify(exportState()) !== JSON.stringify(save)) {
        const added = Object.keys(edits).length;
        showNotice(
          `This device had lost its sync records, so the account's checklist is shown${
            added > 0 ? `, plus ${added} record${added === 1 ? "" : "s"} only this device had` : ""
          }. Nothing else from this device was sent; download its copy to restore anything missing.`,
          "error",
          {
            label: "Download this device's copy",
            run: () =>
              downloadText(
                "pokemon-checklist-this-device.json",
                `${JSON.stringify(save, null, 2)}\n`,
              ),
          },
        );
      } else if (!hadAccountSave && deviceHasProgress) {
        // Otherwise it looks as if this device's progress was just deleted.
        showNotice(
          "This account already has a checklist, so it is shown here. This device's own progress is kept: sign out to see it again.",
          "good",
        );
      }
    }
    if (!serverHasRecords) {
      // An empty account adopts everything this device holds.
      localIntents = entriesFromState(exportState(), serverNow(), uid);
    }
    ignoreLocalEvents = false;
    armLocalListeners(uid);
    writeBase(uid);
    supersededNotice(dropped);
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
    ignoreLocalEvents = false;
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
  pendingOp = stored?.op ?? "reset";
  serverOffset = stored?.offset ?? 0;
  // Last session's unsent edits, with the times they were made.
  localIntents = { ...(stored?.intents ?? {}) };
  initialReadComplete = false;
  // From here on this device expects a session, so a reload may touch auth.
  rememberSyncSession(storage);
  syncAccount.value = { uid: account.uid, email: account.email ?? "" };
  syncPhase.value = "connecting";
  // When the account's own save is already here it is shown now, so play while
  // connecting, or offline, lands on the account. Otherwise this device's own
  // checklist stays on screen until the server answers, and nothing done to it
  // (least of all a Reset) is taken as the account's.
  if (setSyncAccount(account.uid, { ifSaved: true })) armLocalListeners(account.uid);
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
 * Follow a sign-in made in another tab. A tab opened before it would otherwise keep
 * saving to this device's own, never-synced checklist for the rest of its life.
 * Storage events are local, so a player who never signs in still contacts nobody.
 */
export function followSignInFromOtherTabs(): void {
  window.addEventListener("storage", (event) => {
    if (event.key === SYNC_SESSION_KEY && event.newValue === "1") watchSyncAccount();
  });
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
    setLocalReplaceListener(null);
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
  pendingOp = "reset";
  serverOffset = 0;
  connectionDown = false;
  awaitingFresh = false;
  sentValues.clear();
  // A signed-out device must go back to touching nothing at all.
  forgetSyncSession(safeStorage());
  syncAccount.value = null;
  syncPending.value = 0;
  syncOnline.value = false;
  syncPhase.value = "off";
  syncMessage.value = "";
}
