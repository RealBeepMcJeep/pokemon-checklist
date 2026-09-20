import { GAME_MODES, type GameMode, type SavedState, type Status } from "../types";
import { DEFAULT_MODE, STATUS_ORDER } from "../domain";

/**
 * Sync payload shapes and the pure logic that merges them.
 *
 * The player's save (`SavedState`) is deliberately untouched by sync: it stays a
 * clean, exportable v3 document. What lives here is replica bookkeeping — which
 * record changed when, and by whom — which is rebuildable by construction and
 * therefore does not belong in a backup or a schema bump.
 *
 * Ordering authority is the server: every entry's `at` is written by the database
 * (`ServerValue.TIMESTAMP`), so device clock skew can never pick a winner.
 */

/** A single syncable value: "species:25", "form:25:alola", "star:25", "setting:mode". */
export type RecordKey = string;

export interface RecordEntry {
  /** The value: a status, "on"/"off" for a flag, or a mode name. */
  s: string;
  /** Server-assigned write time, in milliseconds. */
  at: number;
  /** UID that wrote it, used only to break exact ties deterministically. */
  by: string;
}

export interface SyncDocument {
  schema: 1;
  records: Record<RecordKey, RecordEntry>;
  updatedAt: number;
}

export type LogOp = "set" | "reset" | "undo";

export interface LogEntry {
  op: LogOp;
  at: number;
  by: string;
  /** For `set`: the record written, and its previous value. */
  key?: RecordKey;
  from?: string;
  to?: string;
  /** For `reset` and measured `undo`: the before-image of everything it changed. */
  cleared?: [RecordKey, string][];
}

export const speciesKey = (id: number): RecordKey => `species:${id}`;
export const formKey = (key: string): RecordKey => `form:${key}`;
export const starKey = (id: number): RecordKey => `star:${id}`;
export const SETTING_MODE: RecordKey = "setting:mode";
export const SETTING_FORMS: RecordKey = "setting:forms";

export const TOMBSTONE = "none";
export const STAR_ON = "on";
export const STAR_OFF = "off";

const isStatus = (value: string): value is Status =>
  STATUS_ORDER.includes(value as Status);
const isMode = (value: string): value is GameMode =>
  GAME_MODES.includes(value as GameMode);

/**
 * What "cleared" looks like in a key's own vocabulary. Flags say "off" rather
 * than "none" so the stored document reads sensibly when inspected by hand;
 * both are treated as absent when a document is turned back into a save.
 */
function clearedValue(key: RecordKey): string {
  return key.startsWith("star:") || key === SETTING_FORMS ? STAR_OFF : TOMBSTONE;
}

/**
 * Last write wins per record, with `by` breaking exact ties so two devices
 * writing in the same millisecond still converge on the same answer everywhere.
 * A tombstone is an ordinary entry: "the player set this back to none at 12:04"
 * is a fact that must beat an older "caught", or a merge would resurrect it.
 */
export function mergeEntry(
  local: RecordEntry | undefined,
  remote: RecordEntry | undefined,
): RecordEntry | undefined {
  if (!local) return remote;
  if (!remote) return local;
  if (remote.at !== local.at) return remote.at > local.at ? remote : local;
  const localClears = local.s === TOMBSTONE || local.s === STAR_OFF;
  const remoteClears = remote.s === TOMBSTONE || remote.s === STAR_OFF;
  if (localClears !== remoteClears) return remoteClears ? remote : local;
  if (remote.by === local.by) return local;
  return remote.by > local.by ? remote : local;
}

export function mergeDocument(
  local: SyncDocument,
  remote: SyncDocument,
): SyncDocument {
  const records: Record<RecordKey, RecordEntry> = { ...local.records };
  for (const [key, entry] of Object.entries(remote.records)) {
    const merged = mergeEntry(records[key], entry);
    if (merged) records[key] = merged;
  }
  return {
    schema: 1,
    records,
    updatedAt: Math.max(local.updatedAt, remote.updatedAt),
  };
}

/** The value a key holds in a document, or undefined when absent. */
export function readEntry(
  document: SyncDocument,
  key: RecordKey,
): RecordEntry | undefined {
  return document.records[key];
}

/**
 * Build entries for everything a save currently holds, stamped with one time and
 * author. This is what "adopt whatever is already on this device" writes when an
 * account signs in for the first time, and what a restore-from-backup publishes.
 */
export function entriesFromState(
  state: SavedState,
  at: number,
  by: string,
): Record<RecordKey, RecordEntry> {
  const records: Record<RecordKey, RecordEntry> = {};
  const stamp = (key: RecordKey, value: string): void => {
    records[key] = { s: value, at, by };
  };
  for (const [id, status] of Object.entries(state.species)) {
    if (status !== "none") stamp(speciesKey(Number(id)), status);
  }
  for (const [key, status] of Object.entries(state.forms)) {
    if (status !== "none") stamp(formKey(key), status);
  }
  for (const id of state.starred) stamp(starKey(id), STAR_ON);
  stamp(SETTING_MODE, state.settings.mode);
  stamp(SETTING_FORMS, state.settings.forms ? STAR_ON : STAR_OFF);
  return records;
}

/**
 * Only the keys whose value actually differs, including tombstones for values
 * that were cleared. Publishing a whole save on every change would make every
 * device fight over every record.
 */
export function diffEntries(
  before: Record<RecordKey, RecordEntry>,
  after: Record<RecordKey, RecordEntry>,
  at = Date.now(),
  by = "",
): Record<RecordKey, RecordEntry> {
  const changed: Record<RecordKey, RecordEntry> = {};
  for (const [key, entry] of Object.entries(after)) {
    if (before[key]?.s !== entry.s) changed[key] = entry;
  }
  for (const [key, entry] of Object.entries(before)) {
    if (!(key in after) && entry.s !== TOMBSTONE && entry.s !== STAR_OFF) {
      changed[key] = { s: clearedValue(key), at, by };
    }
  }
  return changed;
}

/**
 * Turn a merged document back into a save the app can apply. Unknown keys are
 * skipped rather than fatal: a newer build may write records this one has never
 * heard of, and that must not break an older client. The strict validator still
 * guards everything the player can import.
 */
export function stateFromDocument(
  document: SyncDocument,
  validPokemon: ReadonlySet<number>,
  validForms: ReadonlySet<string>,
): SavedState {
  const species: Record<string, Status> = {};
  const forms: Record<string, Status> = {};
  const starred: number[] = [];
  let mode: GameMode = DEFAULT_MODE;
  let formsTracked = false;

  for (const [key, entry] of Object.entries(document.records)) {
    if (entry.s === TOMBSTONE) continue;
    if (key.startsWith("species:")) {
      const id = Number(key.slice("species:".length));
      if (Number.isInteger(id) && validPokemon.has(id) && isStatus(entry.s)) {
        species[String(id)] = entry.s;
      }
    } else if (key.startsWith("form:")) {
      const form = key.slice("form:".length);
      if (validForms.has(form) && isStatus(entry.s)) forms[form] = entry.s;
    } else if (key.startsWith("star:")) {
      const id = Number(key.slice("star:".length));
      if (entry.s === STAR_ON && Number.isInteger(id) && validPokemon.has(id)) {
        starred.push(id);
      }
    } else if (key === SETTING_MODE && isMode(entry.s)) {
      mode = entry.s;
    } else if (key === SETTING_FORMS) {
      formsTracked = entry.s === STAR_ON;
    }
  }

  return {
    schemaVersion: 3,
    species,
    forms,
    starred: [...new Set(starred)].sort((a, b) => a - b),
    settings: { forms: formsTracked, mode },
  };
}

/** The before-image of everything a save holds that a Reset would clear. */
export function clearedByReset(
  state: SavedState,
): [RecordKey, string][] {
  const cleared: [RecordKey, string][] = [];
  for (const [id, status] of Object.entries(state.species)) {
    if (status !== "none") cleared.push([speciesKey(Number(id)), status]);
  }
  for (const [key, status] of Object.entries(state.forms)) {
    if (status !== "none") cleared.push([formKey(key), status]);
  }
  for (const id of state.starred) cleared.push([starKey(id), STAR_ON]);
  return cleared;
}

/**
 * Which records an undo may restore.
 *
 * Undoing a Reset restores only the records the Reset itself still owns — those
 * whose current entry is the Reset's own write. A species caught on another
 * device after the Reset is a newer fact and must survive the undo; restoring it
 * from the before-image would silently delete that catch.
 */
export function undoableFrom(
  document: SyncDocument,
  entry: LogEntry,
): [RecordKey, string][] {
  if (!entry.cleared) return [];
  const restorable: [RecordKey, string][] = [];
  for (const [key, value] of entry.cleared) {
    const current = document.records[key];
    const untouched =
      !current || (current.at === entry.at && current.by === entry.by);
    if (untouched && current?.s !== value) restorable.push([key, value]);
  }
  return restorable;
}

/**
 * Read a records map exactly as it arrives from the wire. Malformed or unknown
 * entries are dropped rather than fatal: another device may be running a newer
 * build, and one bad record must never break this one.
 */
export function parseRecordsSnapshot(
  value: unknown,
): Record<RecordKey, RecordEntry> {
  const records: Record<RecordKey, RecordEntry> = {};
  if (typeof value !== "object" || value === null) return records;
  for (const [key, raw] of Object.entries(value as Record<string, unknown>)) {
    if (typeof raw !== "object" || raw === null) continue;
    const candidate = raw as Record<string, unknown>;
    if (typeof candidate.s !== "string") continue;
    if (
      typeof candidate.at !== "number" ||
      !Number.isFinite(candidate.at) ||
      typeof candidate.by !== "string"
    ) {
      continue;
    }
    records[key] = { s: candidate.s, at: candidate.at, by: candidate.by };
  }
  return records;
}

/** The inverse of a single logged `set`, as a new value to write. */
export function inverseOfSet(entry: LogEntry): [RecordKey, string] | null {
  if (entry.op !== "set" || !entry.key) return null;
  return [entry.key, entry.from ?? TOMBSTONE];
}
