import { STORAGE_KEY } from "../domain";
import type { SavedState } from "../types";
import {
  diffEntries,
  entriesFromState,
  mergeDocument,
  stateFromDocument,
  TOMBSTONE,
  type RecordEntry,
  type RecordKey,
  type SyncDocument,
} from "./records";

/**
 * The local half of sync: what this device last knew the server to hold, and how
 * to work out what still needs publishing.
 *
 * There is deliberately NO operation queue. The store keeps `base` — the last
 * document the server confirmed — and the pending work is derived on demand as
 * `diff(base, currentSave)`. Consequences worth having:
 *
 *  - Retrying a failed publish is free and idempotent: the diff is recomputed, not
 *    replayed from a queue that could drift out of step with the save.
 *  - A reload loses nothing: both sides of the diff are persisted.
 *  - The diff empties itself when the server echoes the write back, so there is no
 *    acknowledgement bookkeeping to get wrong.
 */

export const SYNC_STORE_KEY = "pokemon-checklist-sync-v1";
export const SYNC_SESSION_KEY = "pokemon-checklist-sync-session";

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export interface SyncStore {
  version: 1;
  /** Stable per browser, recorded in log entries so a change can be traced. */
  deviceId: string;
  /** The account this store belongs to; null while signed out. */
  uid: string | null;
  email: string | null;
  /** The last document the server confirmed. */
  base: SyncDocument;
}

/**
 * Whether this browser is expected to have a signed-in account.
 *
 * This exists to protect the offline promise. Initialising Firebase Auth is not
 * free of network traffic: on mobile user agents the SDK eagerly loads its
 * sign-in iframe and GAPI helper even for a signed-out visitor. So the app touches
 * auth on load ONLY when this device has signed in before, and a player who never
 * signs in is never contacted by anything.
 */
export function syncSessionExpected(storage: StorageLike | null): boolean {
  if (!storage) return false;
  try {
    return storage.getItem(SYNC_SESSION_KEY) === "1";
  } catch {
    return false;
  }
}

export function rememberSyncSession(storage: StorageLike | null): void {
  try {
    storage?.setItem(SYNC_SESSION_KEY, "1");
  } catch {
    // Storage being unavailable only means sync stays off.
  }
}

export function forgetSyncSession(storage: StorageLike | null): void {
  try {
    storage?.setItem(SYNC_SESSION_KEY, "0");
  } catch {
    // Nothing to do: without storage there was no session to remember.
  }
}

export function emptyDocument(): SyncDocument {
  return { schema: 1, records: {}, updatedAt: 0 };
}

export function emptyStore(): SyncStore {
  return {
    version: 1,
    deviceId: "",
    uid: null,
    email: null,
    base: emptyDocument(),
  };
}

/**
 * Where the player's own save lives. Signed out — the offline-only case — this is
 * the familiar key, untouched. Signed in, each account gets its own namespace, so
 * a second account on the same device can neither read nor clobber the first.
 */
export function saveKeyFor(uid: string | null): string {
  return uid ? `${STORAGE_KEY}:${uid}` : STORAGE_KEY;
}

function isEntry(value: unknown): value is RecordEntry {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.s === "string" &&
    typeof candidate.at === "number" &&
    Number.isFinite(candidate.at) &&
    typeof candidate.by === "string"
  );
}

/**
 * Read the store, falling back to an empty one on anything unexpected. Nothing
 * here is player progress — it is all rebuildable from the save — so a corrupt
 * store costs a re-publish, never data.
 */
export function loadStore(storage: StorageLike): SyncStore {
  const raw = storage.getItem(SYNC_STORE_KEY);
  if (raw === null) return emptyStore();
  try {
    const parsed = JSON.parse(raw) as Partial<SyncStore>;
    if (parsed.version !== 1) return emptyStore();
    const records: Record<RecordKey, RecordEntry> = {};
    const base = parsed.base?.records;
    if (typeof base === "object" && base !== null) {
      for (const [key, entry] of Object.entries(base)) {
        if (isEntry(entry)) records[key] = entry;
      }
    }
    return {
      version: 1,
      deviceId: typeof parsed.deviceId === "string" ? parsed.deviceId : "",
      uid: typeof parsed.uid === "string" ? parsed.uid : null,
      email: typeof parsed.email === "string" ? parsed.email : null,
      base: { schema: 1, records, updatedAt: 0 },
    };
  } catch {
    return emptyStore();
  }
}

export function saveStore(storage: StorageLike, store: SyncStore): void {
  storage.setItem(SYNC_STORE_KEY, JSON.stringify(store));
}

/** A stable identifier for this browser, created once and kept. */
export function deviceIdFor(storage: StorageLike, random = Math.random): string {
  const store = loadStore(storage);
  if (store.deviceId) return store.deviceId;
  const id = `dev-${random().toString(36).slice(2, 10)}`;
  saveStore(storage, { ...store, deviceId: id });
  return id;
}

/**
 * What still has to reach the server: every record where the local save differs
 * from the last confirmed document, tombstones included.
 */
export function pendingEntries(
  base: SyncDocument,
  save: SavedState,
  at: number,
  by: string,
): Record<RecordKey, RecordEntry> {
  return diffEntries(base.records, entriesFromState(save, at, by));
}

/**
 * What this device should display: the confirmed document with any local edits
 * layered on top.
 *
 * The layering matters. A local edit that has not been published yet will be
 * stamped by the server *when it is published* — later than anything already
 * there — so dropping it merely because a remote change arrived first would
 * discard a change that has legitimately won. Publishing (and the echo that
 * follows) replaces these provisional stamps with the server's own.
 */
export function viewWithPending(
  base: SyncDocument,
  pending: Record<RecordKey, RecordEntry>,
): SyncDocument {
  return mergeDocument(base, {
    schema: 1,
    records: pending,
    updatedAt: 0,
  });
}

/** The document a signed-in device should end up showing, as a save. */
export function saveFromView(
  view: SyncDocument,
  validPokemon: ReadonlySet<number>,
  validForms: ReadonlySet<string>,
): SavedState {
  return stateFromDocument(view, validPokemon, validForms);
}

/**
 * Would this publish clear everything the account holds?
 *
 * A fail-safe, not a policy. An empty local save meeting a full confirmed document
 * is far more likely to be a bug than a player deleting a whole collection, and the
 * cost of guessing wrong is their data — which is what happened once: a device that
 * started from empty against a full account published tombstones for every record.
 * A deliberate Reset also becomes ordinary per-record changes through the same
 * derived diff, so this guard only stops an accidental whole-account clear.
 */
export function isWholeAccountClear(
  base: SyncDocument,
  pending: Record<RecordKey, RecordEntry>,
): boolean {
  // Only PROGRESS records count. Settings are records too, but they clear by taking
  // a different value ("off", a mode name) rather than a tombstone, so counting them
  // as live would make the cleared count unreachable and the guard would stay silent
  // through the very wipe it exists to stop.
  const live = Object.entries(base.records).filter(
    ([key, entry]) => isProgress(key) && isLive(key, entry.s),
  ).length;
  if (live < 5) return false;
  const cleared = Object.entries(pending).filter(
    ([key, entry]) => isProgress(key) && isCleared(key, entry.s),
  ).length;
  return cleared >= live;
}

function isProgress(key: string): boolean {
  return key.startsWith("species:") || key.startsWith("star:");
}

/** A star is live while it is "on"; a species is live at any status but none. */
function isLive(key: string, status: string): boolean {
  return key.startsWith("star:") ? status === "on" : status !== TOMBSTONE;
}

/** A cleared star is "off", not a tombstone: the two keys clear differently. */
function isCleared(key: string, status: string): boolean {
  return key.startsWith("star:") ? status === "off" : status === TOMBSTONE;
}
