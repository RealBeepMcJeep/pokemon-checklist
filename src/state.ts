import { batch, computed, signal, type Signal } from "@preact/signals";
import { ENCOUNTERS_BY_MODE, POKEMON } from "./data";
import {
  DEFAULT_MODE,
  LEGACY_STORAGE_KEYS,
  STATE_VERSION,
  buildFormDefinitions,
  canonicalState,
  cycleStatus,
  formsForMode,
  validateState,
} from "./domain";
import type { GameMode, SavedState, Status } from "./types";
import { saveKeyFor, type ReplaceOp } from "./sync/outbox";
import { rebaseState } from "./sync/records";

export interface Notice {
  message: string;
  kind: "" | "good" | "error";
  /** One tap beside the message, such as Undo. */
  action?: { label: string; run: () => void };
}

export const formDefinitions = buildFormDefinitions(ENCOUNTERS_BY_MODE);
export const validPokemon: ReadonlySet<number> = new Set(
  POKEMON.map(({ id }) => id),
);
export const validForms: ReadonlySet<string> = new Set(formDefinitions.keys());
const speciesSignals = new Map(
  POKEMON.map(({ id }) => [id, signal<Status>("none")] as const),
);
const formSignals = new Map(
  [...formDefinitions.keys()].map(
    (key) => [key, signal<Status>("none")] as const,
  ),
);

export const mode = signal<GameMode>(DEFAULT_MODE);
export const formsTracked = signal(false);
export const selectedDex = signal<number | null>(null);
export const searchTerm = signal("");
export const focusedLocation = signal<string | null>(null);
export const drawerOpen = signal(false);
export const sidebarHidden = signal(false);
export const notice = signal<Notice>({ message: "", kind: "" });
export const storageAvailable = signal(true);
/** Dex numbers pinned to the top of the Pokédex list, ascending. */
export const starred = signal<number[]>([]);

export const activeEncounters = computed(() => ENCOUNTERS_BY_MODE[mode.value]);
/** Forms obtainable in the active mode only, e.g. 14-17 rather than all 54 across
 * every mode: the denominator a player can actually complete. */
export const activeFormDefinitions = computed(() =>
  formsForMode(activeEncounters.value),
);
export const caughtCount = computed(
  () =>
    [...speciesSignals.values()].filter((status) => status.value === "caught")
      .length,
);
export const seenCount = computed(
  () =>
    [...speciesSignals.values()].filter((status) => status.value === "seen")
      .length,
);
export const formsCaught = computed(() => {
  let count = 0;
  for (const key of activeFormDefinitions.value.keys()) {
    if (formSignals.get(key)?.value === "caught") count++;
  }
  return count;
});

// --- accounts ---------------------------------------------------------------
//
// An offline-only player never sets any of this: `activeUid` stays null, the save
// key stays the familiar one, and behaviour is exactly what it has always been.
// Sync is the only subscriber to the change listener.

let activeUid: string | null = null;
let localChangeListener: ((state: SavedState) => void) | null = null;
let localReplaceListener:
  | ((before: SavedState, op: ReplaceOp) => void)
  | null = null;

/** The localStorage key the player's save belongs to right now. */
export function activeSaveKey(): string {
  return saveKeyFor(activeUid);
}

/**
 * Called after local persistence is attempted. Publishing rides on this, so
 * nothing in the app has to know that sync exists.
 */
export function setLocalChangeListener(
  listener: ((state: SavedState) => void) | null,
): void {
  localChangeListener = listener;
}

/** Told about a deliberate Reset or Restore, which sync publishes as one logged event. */
export function setLocalReplaceListener(
  listener: ((before: SavedState, op: ReplaceOp) => void) | null,
): void {
  localReplaceListener = listener;
}

/**
 * Point the app at a signed-in account's save, or back at the device's own.
 *
 * When that account already has a save here, it becomes what you see. When it has
 * none, whatever is in memory is written under the account's key: first sign-in
 * adopts the progress this device already holds rather than discarding it. The
 * device's own save is never deleted, so signing out returns to it untouched.
 */
export function setSyncAccount(
  uid: string | null,
  { adopt = true, ifSaved = false }: { adopt?: boolean; ifSaved?: boolean } = {},
): boolean {
  if (uid === activeUid) return true;
  const previous = activeUid;
  activeUid = uid;
  let read: StoredSave | null = null;
  try {
    read = readSave();
  } catch {
    // Unreadable storage: nothing is found, and nothing is written over it.
    heldKey = activeSaveKey();
  }
  if (ifSaved && !read?.found) {
    // Only switch to a save that is here and readable.
    activeUid = previous;
    return false;
  }
  if (read && useSave(read)) {
    if (read.unreadable === null) {
      showNotice(
        uid
          ? "Signed in: showing this account's checklist."
          : "Signed out: showing this device's checklist.",
        "good",
      );
    }
    return true;
  }
  if (!adopt || read?.unreadable != null) {
    // The account already has a collection elsewhere and this device has never
    // held it. Starting empty lets the account's own data arrive rather than
    // pushing stale offline progress over it as a brand-new write. Nor is another
    // checklist ever carried over a save that could not be read: signing out once
    // silently wrote the account's checklist over the device's own that way.
    applyState(defaultState());
  }
  persist();
  return false;
}

export function speciesSignal(id: number): Signal<Status> {
  const result = speciesSignals.get(id);
  if (!result) throw new Error(`Unknown Pokémon number ${id}`);
  return result;
}

export function formSignal(key: string): Signal<Status> {
  const result = formSignals.get(key);
  if (!result) throw new Error(`Unknown form ${key}`);
  return result;
}

export const speciesStatus = (id: number): Status => speciesSignal(id).value;

export function defaultState(): SavedState {
  return {
    schemaVersion: STATE_VERSION,
    species: {},
    forms: {},
    starred: [],
    settings: { forms: false, mode: DEFAULT_MODE },
  };
}

export function exportState(): SavedState {
  const species: Record<string, Status> = {};
  for (const [id, status] of speciesSignals) {
    if (status.value !== "none") species[String(id)] = status.value;
  }
  const forms: Record<string, Status> = {};
  for (const [key, status] of formSignals) {
    if (status.value !== "none") forms[key] = status.value;
  }
  return canonicalState({
    schemaVersion: STATE_VERSION,
    species,
    forms,
    starred: [...starred.value],
    settings: { forms: formsTracked.value, mode: mode.value },
  });
}

export function applyState(state: SavedState): void {
  batch(() => {
    for (const [id, status] of speciesSignals) {
      status.value = state.species[String(id)] || "none";
    }
    for (const [key, status] of formSignals) {
      status.value = state.forms[key] || "none";
    }
    formsTracked.value = state.settings.forms;
    mode.value = state.settings.mode;
    starred.value = [...state.starred];
  });
}

export function showNotice(
  message: string,
  kind: Notice["kind"] = "",
  action?: Notice["action"],
): void {
  notice.value = action ? { message, kind, action } : { message, kind };
}

// --- saving ------------------------------------------------------------------
//
// A save that cannot be read is never written over and never hides a readable
// one. Every write also refreshes a "last good" copy, which is what loads if the
// save itself is later found unreadable; the unreadable text is kept aside.

const lastGoodKey = (key: string): string => `${key}:last-good`;
const unreadableKey = (key: string): string => `${key}:unreadable`;

/** A key that must not be written: its unreadable save could not be kept aside. */
let heldKey: string | null = null;
/** What this tab last saw under the save key, to notice another tab's write. */
let seen: { key: string; raw: string | null; state: SavedState } | null = null;

interface StoredSave {
  found: { key: string; state: SavedState } | null;
  /** The save key's own text, when it holds something that cannot be read. */
  unreadable: string | null;
  raw: string | null;
}

function readSave(): StoredSave {
  const key = activeSaveKey();
  // Signed in, an account has its own save only. Signed out, an older build's key
  // is still migrated on read.
  const candidates = activeUid
    ? [key, lastGoodKey(key)]
    : [key, lastGoodKey(key), ...LEGACY_STORAGE_KEYS];
  const raw = localStorage.getItem(key);
  let unreadable: string | null = null;
  for (const candidate of candidates) {
    const text = candidate === key ? raw : localStorage.getItem(candidate);
    if (text === null) continue;
    try {
      const state = validateState(JSON.parse(text), validPokemon, validForms);
      return { found: { key: candidate, state }, unreadable, raw };
    } catch {
      if (candidate === key) unreadable = text;
    }
  }
  return { found: null, unreadable, raw };
}

/** Put an unreadable save aside before anything can overwrite it. */
function keepUnreadable(key: string, text: string): boolean {
  try {
    if (localStorage.getItem(unreadableKey(key)) !== text) {
      localStorage.setItem(unreadableKey(key), text);
    }
    return true;
  } catch {
    heldKey = key;
    return false;
  }
}

/** Show what `readSave` found; whether a readable save was applied. */
function useSave({ found, unreadable, raw }: StoredSave): boolean {
  const key = activeSaveKey();
  heldKey = null;
  seen = { key, raw, state: found?.state ?? defaultState() };
  const kept = unreadable === null || keepUnreadable(key, unreadable);
  if (found) {
    applyState(found.state);
    // An older (or last good) copy rewrites itself under the current key. A legacy
    // entry is deliberately left behind so an older build still finds its own data.
    if (found.key !== key) persist();
  }
  if (unreadable !== null) {
    showNotice(
      `Your saved checklist could not be read, so ${
        found ? "the last copy that could be read is shown" : "a fresh one is started"
      }. ${
        kept
          ? "The unreadable copy is kept on this device."
          : "Nothing will be saved over it."
      }`,
      "error",
      {
        label: "Download unreadable copy",
        run: () => downloadText("pokemon-checklist-unreadable.json", unreadable),
      },
    );
  }
  return found !== null;
}

/** Hand the player a file: a copy kept for recovery. */
export function downloadText(name: string, text: string): void {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([text], { type: "application/json" }));
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 0);
}

/**
 * Lay this tab's change over another tab's newer save instead of writing a stale
 * whole checklist over it. A tab can miss the other's storage event entirely — one
 * restored from the back/forward cache does — and then its next tap wrote back an
 * old copy, erasing everything the other tab had saved.
 */
function withOtherTabsChanges(key: string, state: SavedState): SavedState {
  if (seen?.key !== key) return state;
  const stored = localStorage.getItem(key);
  if (stored === null || stored === seen.raw) return state;
  const theirs = interpretStoredState(stored);
  if (theirs.kind !== "apply") {
    keepUnreadable(key, stored);
    return state;
  }
  applyState(
    rebaseState(theirs.state, seen.state, state, validPokemon, validForms),
  );
  return exportState();
}

export function persist(): void {
  lastChange = null;
  let state = exportState();
  const key = activeSaveKey();
  try {
    state = withOtherTabsChanges(key, state);
    if (key === heldKey) throw new Error("the unreadable save could not be kept");
    const raw = JSON.stringify(state);
    localStorage.setItem(key, raw);
    seen = { key, raw, state };
    // Tried on every write, so one failure (a full quota) is not forever.
    storageAvailable.value = true;
    try {
      localStorage.setItem(lastGoodKey(key), raw);
    } catch {
      // The save itself is what matters; this copy is a spare.
    }
  } catch {
    storageAvailable.value = false;
    showNotice(
      "Browser storage is unavailable; changes will disappear when this tab closes.",
      "error",
    );
  }
  // Sync must still receive an edit that lost local durability. Subsequent edits
  // also reach it while storageAvailable is false; offline-only has no listener.
  localChangeListener?.(state);
}

export function initializeState(): void {
  try {
    useSave(readSave());
  } catch {
    // Storage cannot even be read, so nothing may be written over what is there.
    heldKey = activeSaveKey();
    applyState(defaultState());
    storageAvailable.value = false;
    showNotice(
      "Saved data could not be read; starting a fresh checklist that will not be saved.",
      "error",
    );
  }
}

// --- changes and undo -----------------------------------------------------------

interface Change {
  before: SavedState;
  after: SavedState;
  /** Reset or Restore: undone as a restore, so sync logs it as one event. */
  replace: boolean;
}

/** The change that the next notice can offer to undo. */
let lastChange: Change | null = null;

function remember(before: SavedState, replace = false): void {
  lastChange = { before, after: exportState(), replace };
}

/**
 * Put back what one change changed, and nothing else: progress that arrived since
 * (from another device or tab) stays. It goes through the ordinary save path, so
 * sync sends an undo as the plain edits it is.
 */
function undo({ before, after, replace }: Change): void {
  const target = rebaseState(exportState(), after, before, validPokemon, validForms);
  if (replace) replaceState(target, "restore");
  else {
    applyState(target);
    persist();
  }
  lastChange = null;
  changeNotice("Undone.");
}

/**
 * Report a change the player just made, offering Undo when it can be undone.
 * A success message never hides that the change could not be saved.
 */
export function changeNotice(
  message: string,
  unsaved = `${message} Browser storage is unavailable, so this is not saved.`,
): void {
  const change = lastChange;
  lastChange = null;
  const saved = storageAvailable.value;
  showNotice(
    saved ? message : unsaved,
    saved ? "good" : "error",
    change ? { label: "Undo", run: () => undo(change) } : undefined,
  );
}

export function cycleSpecies(id: number): void {
  const before = exportState();
  const status = speciesSignal(id);
  status.value = cycleStatus(status.value);
  persist();
  remember(before);
}

export function cycleForm(key: string): void {
  const before = exportState();
  const status = formSignal(key);
  const next = cycleStatus(status.value);
  const form = formDefinitions.get(key);
  if (!form) throw new Error(`Unknown form ${key}`);
  batch(() => {
    status.value = next;
    if (next === "caught") speciesSignal(form.speciesId).value = "caught";
    if (next === "seen" && speciesStatus(form.speciesId) === "none") {
      speciesSignal(form.speciesId).value = "seen";
    }
  });
  persist();
  remember(before);
}

export function setMode(nextMode: GameMode): void {
  mode.value = nextMode;
  persist();
}

export function toggleForms(): void {
  formsTracked.value = !formsTracked.value;
  persist();
}

export function isStarred(id: number): boolean {
  return starred.value.includes(id);
}

/** Pin a species to the top of the Pokédex list, or release it again. */
export function toggleStar(id: number): void {
  const before = exportState();
  const pinned = isStarred(id);
  starred.value = pinned
    ? starred.value.filter((entry) => entry !== id)
    : [...starred.value, id].sort((a, b) => a - b);
  persist();
  remember(before);
  changeNotice(
    pinned ? "Unstarred." : "Starred. It stays at the top until you unstar it.",
  );
}

export function parseState(text: string): SavedState {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error("This backup is not valid JSON");
  }
  return validateState(parsed, validPokemon, validForms);
}

/**
 * Replace the whole checklist on purpose. Sync publishes this as one logged event
 * with a before-image, exempt from the guard that refuses accidental wipes.
 */
function replaceState(state: SavedState, op: ReplaceOp): void {
  const before = exportState();
  applyState(state);
  localReplaceListener?.(before, op);
  persist();
  remember(before, true);
}

export function restoreState(state: SavedState): void {
  replaceState(state, "restore");
}

export function resetState(): void {
  replaceState(defaultState(), "reset");
}

export function savedNotice(subject: "Status" | "Form status"): void {
  changeNotice(
    `${subject} saved.`,
    `${subject} changed, but it will disappear when this tab closes.`,
  );
}

/**
 * How a value found under the save key should be treated.
 *
 * `cleared` is deliberately distinct from `ignore`: a removed save means the
 * other tab emptied the checklist, while an unreadable one must never replace
 * progress this tab still holds.
 */
export type SyncedState =
  | { kind: "apply"; state: SavedState }
  | { kind: "cleared" }
  | { kind: "ignore" };

export function interpretStoredState(raw: string | null): SyncedState {
  if (raw === null) return { kind: "cleared" };
  try {
    return {
      kind: "apply",
      state: validateState(JSON.parse(raw), validPokemon, validForms),
    };
  } catch {
    return { kind: "ignore" };
  }
}

/**
 * Mirror progress written by another tab of the same origin. Browsers fire
 * `storage` only in the tabs that did not write, so applying a received state
 * cannot echo back into a write loop — and this never calls persist() itself.
 * Two tabs of the offline copy share a `file://` origin in Chromium and sync too,
 * although browsers are free to isolate local files and are not required to.
 */
export function syncFromStorage(event: StorageEvent): void {
  if (event.key !== activeSaveKey()) return;
  const synced = interpretStoredState(event.newValue);
  if (synced.kind === "ignore") return;
  const state = synced.kind === "cleared" ? defaultState() : synced.state;
  seen = { key: activeSaveKey(), raw: event.newValue, state };
  applyState(state);
  if (synced.kind === "cleared") {
    showNotice("Progress was cleared in another tab.");
    return;
  }
  showNotice("Progress updated from another tab.", "good");
}

export function watchOtherTabs(): void {
  window.addEventListener("storage", syncFromStorage);
}
