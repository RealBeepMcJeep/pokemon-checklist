import { GAME_MODES, UNLOCKS, type Unlock, type GameMode, type SavedState, type Status } from "../types";
import { DEFAULT_MODE, STATUS_ORDER, STATE_VERSION, canonicalState } from "../domain";
import { REGIONAL_IDS, isRegional, projectRegionalSpeciesStatus } from "../regional";

/**
 * Sync payload shapes and the pure logic that merges them.
 *
 * The player's save (`SavedState`) is deliberately untouched by sync: it stays a
 * clean, exportable versioned document. What lives here is replica bookkeeping — which
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

export const speciesKey = (id: number): RecordKey => `species:${id}`;
export const formKey = (key: string): RecordKey => `form:${key}`;
export const starKey = (id: number): RecordKey => `star:${id}`;
export const formStarKey = (key: string): RecordKey => `starform:${key}`;
/** Explicit unresolved intent, distinct from the old aggregate compatibility bridge. */
export const legacyStarKey = (id: number): RecordKey => `starlegacy:${id}`;
export const SETTING_MODE: RecordKey = "setting:mode";
export const SETTING_FORMS: RecordKey = "setting:forms";

export const TOMBSTONE = "none";
export const STAR_ON = "on";
export const STAR_OFF = "off";

const isStatus = (value: string): value is Status =>
  STATUS_ORDER.includes(value as Status);
const isMode = (value: string): value is GameMode =>
  GAME_MODES.includes(value as GameMode);

/** Whether a value clears its record: a tombstone, or a flag switched off. */
export const isClearing = (value: string): boolean =>
  value === TOMBSTONE || value === STAR_OFF;

/**
 * What "cleared" looks like in a key's own vocabulary. Flags say "off" rather
 * than "none" so the stored document reads sensibly when inspected by hand;
 * both are treated as absent when a document is turned back into a save.
 */
export function clearedValue(key: RecordKey): string {
  return key.startsWith("star:") || key.startsWith("starform:") || key.startsWith("starlegacy:") || key === SETTING_FORMS || key.startsWith("setting:unlock:") ? STAR_OFF : TOMBSTONE;
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
  const localClears = isClearing(local.s);
  const remoteClears = isClearing(remote.s);
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
  const formStars = "starredForms" in state ? state.starredForms : [];
  for (const key of formStars) stamp(formStarKey(key), STAR_ON);
  if (state.schemaVersion >= 5) for (const id of state.starred) {
    if (isRegional(id) && !formStars.some(key => Number(key.split(":")[0]) === id)) stamp(legacyStarKey(id), STAR_ON);
  }
  // Old analysis/read-only clients still receive a species-level favorite view.
  for (const id of new Set([...state.starred, ...formStars.map(key => Number(key.split(":")[0]))])) stamp(starKey(id), STAR_ON);
  for (const flag of state.settings.unlocks ?? []) stamp(`setting:unlock:${flag}`, STAR_ON);
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
 * The before-image of a whole-checklist replacement (Reset, Restore): each record
 * it changes, with the value it held before. This is what the sync log keeps so
 * the replacement can be understood, and undone, later.
 */
export function beforeImage(
  before: SavedState,
  after: SavedState,
): [RecordKey, string][] {
  const old = entriesFromState(before, 0, "");
  return Object.keys(diffEntries(old, entriesFromState(after, 0, ""))).map(
    (key) => [key, old[key]?.s ?? clearedValue(key)],
  );
}

/**
 * `onto`, with only the records that changed between `from` and `to` changed the
 * same way. Everything else keeps the value `onto` has, so replaying one change
 * (an undo, or this tab's edit over another tab's newer save) never reverts
 * unrelated progress that arrived in the meantime. With `onlyUnchanged`, a record
 * `onto` no longer holds at its `from` value is left alone too (an Undo must not
 * override a record changed after the change it undoes).
 */
export function rebaseState(
  onto: SavedState,
  from: SavedState,
  to: SavedState,
  validPokemon: ReadonlySet<number>,
  validForms: ReadonlySet<string>,
  onlyUnchanged = false,
): SavedState {
  const fromEntries = entriesFromState(from, 0, "");
  const ontoEntries = entriesFromState(onto, 0, "");
  const change = diffEntries(fromEntries, entriesFromState(to, 0, ""));
  if (onlyUnchanged) {
    for (const key of Object.keys(change)) {
      if (ontoEntries[key]?.s !== fromEntries[key]?.s) delete change[key];
    }
  }
  return stateFromDocument(
    {
      schema: 1,
      records: { ...ontoEntries, ...change },
      updatedAt: 0,
    },
    validPokemon,
    validForms,
  );
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
  const starredForms: string[] = [];
  const explicitFormStars = new Set<number>();
  const unresolvedStars = new Map<number, RecordEntry>();
  const latestFormStar = new Map<number, number>();
  let mode: GameMode = DEFAULT_MODE;
  let formsTracked = false;
  const unlocks: Unlock[] = [];

  for (const [key, entry] of Object.entries(document.records)) {
    if (key.startsWith("starlegacy:")) {
      const match = /^starlegacy:([1-9][0-9]*)$/.exec(key);
      const id = match ? Number(match[1]) : 0;
      if (validPokemon.has(id) && isRegional(id) && (entry.s === STAR_ON || entry.s === STAR_OFF)) {
        explicitFormStars.add(id);
        if (entry.s === STAR_ON) unresolvedStars.set(id, entry);
      }
      continue;
    }
    if (key.startsWith("starform:")) {
      const form = key.slice("starform:".length);
      if (validForms.has(form) && (entry.s === STAR_ON || entry.s === STAR_OFF)) {
        const id = Number(form.split(":")[0]);
        explicitFormStars.add(id);
        latestFormStar.set(id, Math.max(latestFormStar.get(id) ?? -Infinity, entry.at));
        if (entry.s === STAR_ON) starredForms.push(form);
      }
      continue;
    }
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
    } else if (key.startsWith("setting:unlock:") && entry.s === STAR_ON) {
      const flag = key.slice("setting:unlock:".length) as Unlock;
      if (UNLOCKS.includes(flag)) unlocks.push(flag);
    } else if (key === SETTING_MODE && isMode(entry.s)) {
      mode = entry.s;
    } else if (key === SETTING_FORMS) {
      formsTracked = entry.s === STAR_ON;
    }
  }

  for (const id of REGIONAL_IDS) {
    if (!validPokemon.has(id)) continue;
    const status = projectRegionalSpeciesStatus(species[String(id)] ?? "none", [
      forms[`${id}:alolan`] ?? "none", forms[`${id}:kanto`] ?? "none",
    ]);
    if (status !== "none") species[String(id)] = status;
  }
  return canonicalState({
    schemaVersion: STATE_VERSION,
    species,
    forms,
    starred: [...new Set(starred)].filter(id => !explicitFormStars.has(id) || (unresolvedStars.has(id) && unresolvedStars.get(id)!.at >= (latestFormStar.get(id) ?? -Infinity))).sort((a, b) => a - b),
    starredForms,
    settings: { forms: formsTracked, mode, unlocks: UNLOCKS.filter(flag => unlocks.includes(flag)) },
  });
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
