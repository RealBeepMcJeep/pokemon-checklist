import { STORAGE_KEY } from "../domain";
import type { SavedState } from "../types";
import {
  diffEntries,
  entriesFromState,
  mergeDocument,
  stateFromDocument,
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
 * First sign-in on a device that already holds offline progress: everything the
 * local save contains becomes pending, so the account adopts it. This is the
 * deliberate opposite of starting empty, which would silently discard a
 * collection built before the account existed.
 */
export function adoptionEntries(
  save: SavedState,
  at: number,
  by: string,
): Record<RecordKey, RecordEntry> {
  return entriesFromState(save, at, by);
}
