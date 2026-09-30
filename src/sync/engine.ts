import { effect, signal } from "@preact/signals";
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
  activeSaveKey,
  applyState,
  downloadText,
  exportState,
  persist,
  readOnly,
  setLocalChangeListener,
  setLocalReplaceListener,
  setOtherTabListener,
  setSyncAccount,
  showNotice,
  validForms,
  validPokemon,
} from "../state";
import { initFirebase, signOutOfSync, watchAuth } from "./firebase";
import { claimDeviceEditing, claimEditing, releaseEditing } from "../editing";
import type { User } from "firebase/auth";
import type { SavedState } from "../types";
import {
  TOMBSTONE,
  beforeImage,
  clearedValue,
  entriesFromState,
  isClearing,
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
  isProgressClear,
  isWholeAccountClear,
  SYNC_STORE_KEY,
  loadStore,
  localIntentChanges,
  pendingEntries,
  rememberSyncSession,
  saveFromView,
  saveKeyFor,
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
 *
 * An edit counts as sent only when the server acknowledges it. Firebase shows a
 * write to this page's own listeners at once, before the server has it, so until
 * the acknowledgement the edit stays recorded (and saved for a reload), and the
 * value is never taken as confirmed.
 *
 * Only one tab per account can change the checklist: the one holding the Web Lock
 * `pokemon-checklist-sync:<uid>`. Every other tab of that account is view-only and
 * follows the editor's saves; "Use this tab" steals the lock, and the tab it was
 * taken from turns view-only at once. Its unsent edits are already in the sync
 * store, where the new editor picks them up. Without Web Locks every tab edits.
 */

export type SyncPhase =
  | "off"
  | "connecting"
  | "ready"
  | "pending"
  | "error"
  | "elsewhere"
  | "outdated";

export const syncPhase = signal<SyncPhase>("off");
/** Edits not yet acknowledged by the server, including any in flight. */
export const syncPending = signal(0);
/** Clears held back because together they would empty the account. */
export const syncHeld = signal(0);
export const syncAccount = signal<{ uid: string; email: string } | null>(null);
export const syncMessage = signal("");
/** Whether the database connection is up; only meaningful while signed in. */
export const syncOnline = signal(false);

/** How long a failed record listener waits before listening again. */
const RELISTEN_DELAY = 30_000;

let database: Database | null = null;
let activeUid: string | null = null;
let deviceId = "";
/** What the server holds, as this page's database listener reports it. */
let base: SyncDocument = emptyDocument();
let lastPushed = "";
let unsubscribeValue: (() => void) | null = null;
let unsubscribeConnection: (() => void) | null = null;
let unsubscribeAuth: (() => void) | null = null;
// Between pressing "Sign in" and an account arriving. Firebase reports "signed out" as
// soon as auth starts; that report must not end a sign-in that has not finished yet.
let signInPending = false;
// Auth was started because another tab began signing in. Its first "signed out"
// report must not clear the session flag that tab is relying on.
let followedSignIn = false;
let generation = 0;
let initialReadComplete = false;
let initialReadInFlight = false;
let ignoreLocalEvents = false;
let observedLocal: SavedState | null = null;
let localIntents: Record<RecordKey, RecordEntry> = {};
let pendingReset: ResetImage | null = null;
let pendingOp: ReplaceOp = "reset";
/** The reset last written to the sync store by this tab, to recognise its own. */
let storedReset = "";
let publishInFlight: Promise<void> | null = null;
let publishQueued = false;
/** Server time minus this device's clock, from `.info/serverTimeOffset`. */
let serverOffset = 0;
// Nothing is sent while the connection is down, nor after it returns until the
// server's current records have arrived: sending first is how a stale offline edit
// (or an offline Reset) overwrote newer changes it had not seen yet.
let connectionDown = false;
let awaitingFresh = false;
/**
 * The write sent and not yet acknowledged: each record's value, and the confirmed
 * entry it replaces. Its echo is recognised by this, and cleared on acknowledgement.
 */
let inFlight: {
  sent: Record<RecordKey, RecordEntry>;
  before: Record<RecordKey, RecordEntry | undefined>;
} | null = null;
/**
 * Clears held back by the whole-account guard. They stay held, across reloads,
 * until the player sends or discards them; nothing else releases them.
 */
const heldKeys = new Set<RecordKey>();
let deniedRetried = false;
/** The replacement whose write is in flight: an undo of it starts its own image. */
let sentReplacement: ResetImage | null = null;
/** "lock": the one tab syncing this account. "alone": no Web Locks, every tab syncs. */
let leading: "lock" | "alone" | null = null;


const serverNow = (): number => Date.now() + serverOffset;
const lockName = (uid: string): string => `pokemon-checklist-sync:${uid}`;
const sameEntry = (left?: RecordEntry, right?: RecordEntry): boolean =>
  left?.s === right?.s && left?.at === right?.at && left?.by === right?.by;

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

/** Edits the server has not acknowledged: owed ones, and the write in flight. */
function unsentCount(): number {
  return new Set([...Object.keys(owed()), ...Object.keys(inFlight?.sent ?? {})])
    .size;
}

/**
 * The records the server has acknowledged. A value this page has written but the
 * server has not acknowledged is shown by Firebase all the same; it is replaced by
 * the entry it overwrote, so it is never saved as confirmed.
 */
function confirmedRecords(): Record<RecordKey, RecordEntry> {
  if (!inFlight) return base.records;
  const records = { ...base.records };
  for (const [key, sent] of Object.entries(inFlight.sent)) {
    if (records[key]?.s !== sent.s) continue;
    const before = inFlight.before[key];
    if (before) records[key] = before;
    else delete records[key];
  }
  return records;
}

/**
 * Forget edits the server now holds, and drop the ones a newer change from
 * elsewhere has replaced. `previous` is the document before the latest snapshot:
 * only a record that changed in it can have replaced anything. An edit in flight is
 * kept until it is acknowledged, and its own echo never counts as news. Returns
 * how many edits were dropped.
 */
function dropSuperseded(previous: Record<RecordKey, RecordEntry>): number {
  let dropped = 0;
  for (const [key, intent] of Object.entries(localIntents)) {
    const remote = base.records[key];
    const sent = inFlight?.sent[key];
    if (sent) {
      if (!remote || remote.s === sent.s || sameEntry(remote, previous[key])) continue;
    } else {
      if (remote?.s === intent.s) {
        delete localIntents[key];
        continue;
      }
      if (!remote || sameEntry(remote, previous[key])) continue;
    }
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

const isDenied = (error: unknown): boolean =>
  /permission_denied/i.test(error instanceof Error ? error.message : String(error));

function describe(error: unknown, writing = false): string {
  if (isDenied(error)) {
    return writing
      ? "The database refused a change. It is kept here and tried again."
      : "This account is not allowed to use the shared checklist.";
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
  let intents = localIntents;
  let reset = pendingReset;
  let op = pendingOp;
  if (leading === "alone") {
    // Without Web Locks another tab may be syncing this account and sharing this
    // store. Keep its unsent edits (still in the save, not yet on the server) and
    // its pending Reset, instead of writing over them.
    const stored = readStore(uid);
    const save = entriesFromState(exportState(), 0, "");
    intents = { ...localIntents };
    for (const [key, entry] of Object.entries(stored?.intents ?? {})) {
      const shown = save[key]?.s ?? clearedValue(key);
      if (!(key in intents) && shown === entry.s && base.records[key]?.s !== entry.s) {
        intents[key] = entry;
      }
    }
    if (!reset && stored?.reset && JSON.stringify(stored.reset) !== storedReset) {
      reset = stored.reset;
      op = stored.op ?? "reset";
    }
  }
  storedReset = reset ? JSON.stringify(reset) : "";
  saveStore(storage, {
    version: 1,
    deviceId,
    uid,
    email: syncAccount.value?.email ?? null,
    base: { schema: 1, records: confirmedRecords(), updatedAt: base.updatedAt },
    ...(reset ? { reset } : {}),
    ...(reset && op === "restore" ? { op: "restore" as const } : {}),
    ...(Object.keys(intents).length > 0 ? { intents } : {}),
    ...(heldKeys.size > 0 ? { held: [...heldKeys] } : {}),
    offset: serverOffset,
  });
}

function heldMessage(): string {
  const count = syncHeld.value;
  return `Held back ${count === 1 ? "1 clear" : `${count} clears`} that would empty the checklist on every device, in case that was a mistake. Everything else is sent.`;
}

/** Forget held clears the player has since changed, or that newer changes replaced. */
function pruneHeld(): void {
  for (const key of heldKeys) {
    const intent = localIntents[key];
    if (!intent || !isProgressClear(key, intent.s)) heldKeys.delete(key);
  }
  syncHeld.value = heldKeys.size;
}

/**
 * The player's answer about held clears: put those Pokémon back as the account has
 * them, or send the clears as one deliberate clear logged with what it cleared.
 */
export function resolveHeldClears(send: boolean): void {
  const uid = activeUid;
  if (!uid || heldKeys.size === 0 || readOnly.value) return;
  if (send) {
    const earlier = pendingReset && pendingReset !== sentReplacement ? pendingReset : [];
    const known = new Set(earlier.map(([key]) => key));
    const image: ResetImage = [...heldKeys]
      .filter((key) => !known.has(key))
      .map((key) => [key, base.records[key]?.s ?? clearedValue(key)]);
    if (earlier.length === 0) pendingOp = "reset";
    pendingReset = [...earlier, ...image];
  } else {
    for (const key of heldKeys) delete localIntents[key];
  }
  heldKeys.clear();
  syncHeld.value = 0;
  syncMessage.value = "";
  if (syncPhase.value === "error") syncPhase.value = "pending";
  if (!send) showView();
  writeBase(uid);
  void publish();
}

/** Show (and save) the confirmed document with this tab's unsent edits on top. */
function showView(): void {
  const ignoring = ignoreLocalEvents;
  ignoreLocalEvents = true;
  applyState(
    saveFromView(viewWithLocalIntent(base, owed()), validPokemon, validForms),
  );
  persist();
  ignoreLocalEvents = ignoring;
  observedLocal = exportState();
}

/** Publish this device's edits that the confirmed document does not hold. */
async function publishNow(): Promise<void> {
  if (!database || !activeUid || !initialReadComplete) return;
  const run = generation;
  const uid = activeUid;
  const pending = owed();
  syncPending.value = unsentCount();
  if (connectionDown || awaitingFresh) {
    if (syncPhase.value !== "error") {
      syncPhase.value = syncPending.value > 0 ? "pending" : "ready";
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
  const replaced = new Set(image.map(([key]) => key));

  // Refuse to be the reason an account empties itself. This guards the bug that
  // wiped a real account: a device that had not yet adopted the account's data
  // published the difference between "empty" and "everything". What a Reset or
  // Restore replaces on purpose is exempt; everything else is judged, and clears
  // that would empty the account are held back while the rest is still sent.
  // Clears already held count too, so holding some never lets the rest through;
  // and once held, only the player releases them (a record arriving elsewhere,
  // which would satisfy the guard, does not).
  pruneHeld();
  const judged = Object.fromEntries(
    Object.entries(pending).filter(([key]) => !replaced.has(key)),
  );
  if (isWholeAccountClear(base, judged)) {
    const before = heldKeys.size;
    for (const [key, entry] of Object.entries(judged)) {
      if (isProgressClear(key, entry.s)) heldKeys.add(key);
    }
    syncHeld.value = heldKeys.size;
    if (heldKeys.size > before) {
      writeBase(uid);
      showNotice(heldMessage(), "error");
    }
  }
  if (heldKeys.size > 0) {
    syncPhase.value = "error";
    syncMessage.value = heldMessage();
  }
  const keys = Object.keys(pending)
    .filter((key) => !heldKeys.has(key))
    .sort((a, b) => a.localeCompare(b));
  if (keys.length === 0) {
    lastPushed = "";
    if (heldKeys.size === 0) syncPhase.value = "ready";
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
  const sent: Record<RecordKey, RecordEntry> = {};
  const before: Record<RecordKey, RecordEntry | undefined> = {};
  for (const key of keys) {
    sent[key] = pending[key];
    before[key] = base.records[key];
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
  const sentReset = image.length > 0 ? pendingReset : null;
  sentReplacement = sentReset;

  lastPushed = signature;
  syncPhase.value = "pending";
  // Set before the call: Firebase shows the write to this page's listeners inside it.
  inFlight = { sent, before };
  try {
    await update(ref(database, `users/${uid}`), payload);
    if (!isCurrent(run, uid)) return;
    // Acknowledged: the server has these values now.
    inFlight = null;
    deniedRetried = false;
    for (const [key, entry] of Object.entries(sent)) {
      if (localIntents[key]?.s === entry.s) delete localIntents[key];
    }
    // Written atomically with its log event, so the replacement is done.
    if (sentReset && pendingReset === sentReset) pendingReset = null;
    sentReplacement = null;
    writeBase(uid);
    syncPending.value = unsentCount();
    syncPhase.value = heldKeys.size > 0 ? "error" : "ready";
    syncMessage.value = heldKeys.size > 0 ? heldMessage() : "";
  } catch (error) {
    if (!isCurrent(run, uid)) return;
    // Firebase has already undone the write locally; the edits are still recorded.
    inFlight = null;
    sentReplacement = null;
    lastPushed = "";
    writeBase(uid);
    syncPending.value = unsentCount();
    if (isDenied(error) && !deniedRetried) {
      // Most often a write the server had applied, sent again after its
      // acknowledgement was lost: its log entries exist and may not be written
      // twice. One more try, with fresh log entries, settles it.
      deniedRetried = true;
      syncMessage.value = describe(error, true);
      void publish();
      return;
    }
    syncPhase.value = "error";
    syncMessage.value = describe(error, true);
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
    // An edit back to what the server holds is no edit, unless a write to that
    // record is in flight: it may still land, and this is newer.
    if (!inFlight?.sent[key] && base.records[key]?.s === entry.s) {
      delete localIntents[key];
    } else localIntents[key] = entry;
  }
  observedLocal = state;
  // Kept with the time each edit was made, so a reload still knows which is newer.
  writeBase(uid);
  void publish();
}

function recordReplace(
  before: SavedState,
  after: SavedState,
  op: ReplaceOp,
  uid: string,
): void {
  if (ignoreLocalEvents || !activeUid || activeUid !== uid) return;
  // A replacement not sent yet merges into this one; its before-image is older, so
  // it is the true "before" for the records both touch. One already in flight is
  // not merged: an Undo of it logs what that replacement left, not what it found.
  const earlier = pendingReset && pendingReset !== sentReplacement ? pendingReset : [];
  const known = new Set(earlier.map(([key]) => key));
  const image = [
    ...earlier,
    ...beforeImage(before, after).filter(([key]) => !known.has(key)),
  ];
  pendingReset = image.length > 0 ? image : null;
  pendingOp = op;
  writeBase(uid);
}

/**
 * Another tab's save of this account arrived. The editor's own view is the
 * account's: other tabs cannot edit, so a save from one (at sign-in, say) is only
 * replaced by that view, never taken as edits. Where every tab edits (no Web
 * Locks), the save is shown with this tab's unsent edits laid back over it, and
 * none of it is taken as an edit here. It is saved back only where the other tab
 * left a record as the account has it, so two tabs holding different edits of one
 * record settle instead of overwriting each other for ever.
 */
function onOtherTabSave(state: SavedState): boolean {
  if (leading === "lock") {
    showView();
    return true;
  }
  const theirs = entriesFromState(state, 0, "");
  const records = { ...theirs, ...localIntents };
  const ignoring = ignoreLocalEvents;
  ignoreLocalEvents = true;
  applyState(
    saveFromView({ schema: 1, records, updatedAt: 0 }, validPokemon, validForms),
  );
  const missing = Object.entries(localIntents).some(([key, intent]) => {
    const shown = theirs[key]?.s ?? clearedValue(key);
    return shown !== intent.s && shown === (base.records[key]?.s ?? clearedValue(key));
  });
  if (missing) persist();
  ignoreLocalEvents = ignoring;
  observedLocal = exportState();
  return true;
}

function armLocalListeners(uid: string): void {
  observedLocal = exportState();
  setLocalChangeListener((state) => recordLocalChange(uid, state));
  setLocalReplaceListener((before, op) =>
    recordReplace(before, exportState(), op, uid),
  );
  setOtherTabListener(onOtherTabSave);
}

function applyRemote(uid: string, incoming: unknown, run: number): void {
  if (!isCurrent(run, uid) || !initialReadComplete) return;
  const previous = base.records;
  // Each snapshot is the whole record set, so it replaces the last: merging kept a
  // write the server had refused, because its local stamp was newer.
  base = {
    schema: 1,
    records: parseRecordsSnapshot(incoming),
    updatedAt: Date.now(),
  };
  const dropped = dropSuperseded(previous);
  pruneHeld();
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
  syncPending.value = unsentCount();
  supersededNotice(dropped);
  if (heldKeys.size === 0 && syncPhase.value !== "error") {
    syncPhase.value =
      syncPending.value === 0 && !pendingReset ? "ready" : "pending";
  }
  if (syncPending.value === 0 && !pendingReset) lastPushed = "";
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
    if (syncPhase.value !== "error") syncMessage.value = "";
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
 * was lost), only records the server has never held count, plus edits recorded
 * with their time this session, so nothing else the server has is overridden or
 * cleared.
 */
function recoveredEdits(
  confirmed: SyncDocument,
  save: SavedState,
  uid: string,
): Record<RecordKey, RecordEntry> {
  const now = serverNow();
  const shown = entriesFromState(save, now, uid);
  if (Object.keys(confirmed.records).length === 0) {
    const edits = Object.fromEntries(
      Object.entries(shown).filter(
        ([key, entry]) => !(key in base.records) && !isClearing(entry.s),
      ),
    );
    for (const [key, intent] of Object.entries(localIntents)) {
      if ((shown[key]?.s ?? clearedValue(key)) === intent.s) edits[key] = intent;
    }
    return edits;
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
    // What this device last confirmed, before the server's current copy replaces it.
    const confirmed = base;
    base = { schema: 1, records: remote, updatedAt: Date.now() };

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
      const edits = hadAccountSave ? recoveredEdits(confirmed, save, uid) : {};
      let discarded = 0;
      if (!pendingReset && isWholeAccountClear(base, edits, 1)) {
        // A recovered set that would empty the account is far likelier a stale copy
        // than the player's doing: its clears are not sent (held ones excepted, the
        // player decides those), but anything it adds still is.
        for (const [key, edit] of Object.entries(edits)) {
          if (isProgressClear(key, edit.s) && !heldKeys.has(key)) {
            delete edits[key];
            discarded += 1;
          }
        }
      }
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
            added > 0 ? `, plus ${added} record${added === 1 ? "" : "s"} changed here` : ""
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
      } else if (discarded > 0) {
        showNotice(
          `${discarded === 1 ? "1 Pokémon" : `${discarded} Pokémon`} cleared on this device ${discarded === 1 ? "was" : "were"} not sent, because clearing everything at once looked like a mistake; the account's checklist is shown. Use Reset to clear on purpose.`,
          "error",
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
 * Claim editing this account; the tab that holds it syncs. Until then (or after
 * another tab takes it) this tab is view-only and follows the editor's saves.
 * Resolves once this tab first edits.
 */
function claimAccount(uid: string): Promise<void> {
  return new Promise((started) => {
    claimEditing(lockName(uid), {
      waiting: () => {
        if (activeUid === uid) viewOnly(uid);
      },
      edit: (mode) => {
        if (activeUid !== uid) return;
        leading = mode;
        void edit(uid, generation).finally(started);
      },
      lost: () => yieldEditing(uid),
    });
  });
}

/** Another tab edits this account: this one follows its saves and changes nothing. */
function viewOnly(uid: string): void {
  syncPhase.value = "elsewhere";
  setLocalChangeListener(null);
  setLocalReplaceListener(null);
  setOtherTabListener(null);
  showHeldFromStore(uid);
}

/**
 * Stop editing (and syncing) here at once: another tab took the lock, or a newer
 * build is open. Every unsent edit is already in the sync store (it is written on
 * each change), where the next editor picks it up; nothing more is sent or stored
 * from here.
 */
function yieldEditing(uid: string): void {
  if (activeUid !== uid || !leading) return;
  generation += 1;
  leading = null;
  publishInFlight = null;
  publishQueued = false;
  unsubscribeValue?.();
  unsubscribeConnection?.();
  unsubscribeValue = null;
  unsubscribeConnection = null;
  database = null;
  initialReadComplete = false;
  initialReadInFlight = false;
  inFlight = null;
  syncOnline.value = false;
  viewOnly(uid);
}

/** A view-only tab still shows that clears are held, from the editor's store. */
function showHeldFromStore(uid: string): void {
  syncHeld.value = readStore(uid)?.held?.length ?? 0;
  syncMessage.value = syncHeld.value > 0 ? heldMessage() : "";
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
  const uid = account.uid;
  activeUid = uid;
  // From here on this device expects a session, so a reload may touch auth.
  rememberSyncSession(storage);
  syncAccount.value = { uid, email: account.email ?? "" };
  syncPhase.value = "connecting";
  // When the account's own save is already here it is shown now, so play while
  // connecting, or offline, lands on the account. Otherwise this device's own
  // checklist stays on screen until the server answers, and nothing done to it
  // (least of all a Reset) is taken as the account's.
  setSyncAccount(uid, { ifSaved: true });
  if (readOnly.value === "outdated") return newerBuildOpen();
  await claimAccount(uid);
}

/** Become the tab that edits (and syncs) this account. */
async function edit(uid: string, run: number): Promise<void> {
  const storage = safeStorage();
  if (!storage || run !== generation) return;
  syncPhase.value = "connecting";
  const { db } = initFirebase();
  database = db;
  deviceId = deviceIdFor(storage);
  // Everything is read from the store, including edits a previous editor had not
  // sent: it stored each one as it was made.
  const stored = readStore(uid);
  base = stored?.base ?? emptyDocument();
  pendingReset = stored?.reset ?? null;
  pendingOp = stored?.op ?? "reset";
  storedReset = pendingReset ? JSON.stringify(pendingReset) : "";
  serverOffset = stored?.offset ?? 0;
  // Last session's unsent edits (including any never acknowledged), with the times
  // they were made, and clears still held for the player to decide on.
  localIntents = { ...(stored?.intents ?? {}) };
  heldKeys.clear();
  for (const key of stored?.held ?? []) heldKeys.add(key);
  syncHeld.value = heldKeys.size;
  syncMessage.value = "";
  initialReadComplete = false;
  if (activeSaveKey() === saveKeyFor(uid)) armLocalListeners(uid);
  subscribeConnection(uid, run);
  await loadInitial(uid, run);
}

/** A newer build is open in another tab: this one stops editing for good. */
function newerBuildOpen(): void {
  if (!activeUid) return;
  yieldEditing(activeUid);
  syncPhase.value = "outdated";
  syncMessage.value = "";
}

function onAuthState(user: User | null, allowed: boolean): void {
  if (!user) {
    if (signInPending) return;
    // A tab that only followed another tab's sign-in keeps that tab's session flag.
    stopSync(!(followedSignIn && !activeUid));
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

/** What other tabs of this site change in storage that sync has to follow. */
function onStorage(event: StorageEvent): void {
  if (event.key === SYNC_SESSION_KEY) {
    // Another tab began signing in. A tab opened before it would otherwise keep
    // saving to this device's own, never-synced checklist for the rest of its life.
    if (event.newValue === "1" && !unsubscribeAuth) {
      followedSignIn = true;
      watchSyncAccount();
    }
    return;
  }
  const uid = activeUid;
  if (!uid || !event.key) return;
  if (leading) return;
  if (event.key === saveKeyFor(uid)) {
    // The editor has just written the account's first save here: show it.
    setSyncAccount(uid, { ifSaved: true });
  } else if (event.key === SYNC_STORE_KEY) {
    showHeldFromStore(uid);
  }
}

/**
 * Follow what other tabs do: a sign-in begun elsewhere, and, while another tab
 * edits, the account's first save and its held clears. A newer build opening in
 * another tab ends editing here. Storage events are local, so a player who never
 * signs in still contacts nobody.
 */
export function followSignInFromOtherTabs(): void {
  window.addEventListener("storage", onStorage);
  effect(() => {
    if (readOnly.value === "outdated") newerBuildOpen();
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

export function stopSync(forget = true): void {
  generation += 1;
  releaseEditing();
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
    setOtherTabListener(null);
    persist();
    // Back to the device's own checklist, which was never touched.
    setSyncAccount(null);
    activeUid = null;
  }
  leading = null;
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
  storedReset = "";
  serverOffset = 0;
  connectionDown = false;
  awaitingFresh = false;
  inFlight = null;
  heldKeys.clear();
  syncHeld.value = 0;
  sentReplacement = null;
  deniedRetried = false;
  // Signed out, one tab edits the device's own checklist.
  claimDeviceEditing();
  // A signed-out device must go back to touching nothing at all.
  if (forget) forgetSyncSession(safeStorage());
  syncAccount.value = null;
  syncPending.value = 0;
  syncOnline.value = false;
  syncPhase.value = "off";
  syncMessage.value = "";
}
