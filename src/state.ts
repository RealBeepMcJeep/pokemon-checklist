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
import { diffEntries, entriesFromState, rebaseState } from "./sync/records";
import { BUILD_LABEL } from "./version";

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
/**
 * Why this tab may not change the checklist, or null when it may: another tab of
 * the account is the one editing it, or a newer build of the app is open.
 */
export const readOnly = signal<null | "elsewhere" | "outdated">(null);
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
let otherTabListener: ((state: SavedState) => boolean) | null = null;

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
 * Given another tab's save of the same checklist to show. Returning true means the
 * listener has shown what belongs on screen itself (sync may know better than
 * that save); otherwise the save is shown as it is.
 */
export function setOtherTabListener(
  listener: ((state: SavedState) => boolean) | null,
): void {
  otherTabListener = listener;
}

/** Sync says whether this tab may edit. A newer build open elsewhere still wins. */
export function setEditable(editable: boolean): void {
  if (readOnly.value === "outdated") return;
  readOnly.value = editable ? null : "elsewhere";
  if (!editable) expireUndo();
}

// --- builds -------------------------------------------------------------------
//
// Two builds must never edit one checklist at once: an older one does not know the
// newer one's rules. Each tab announces its build when it loads. The tab that loads
// last runs what is deployed, so a tab that hears of a different build announced
// after it stops editing and asks to be reloaded.

const BUILD_KEY = "pokemon-checklist-build";

export function announceBuild(): void {
  try {
    localStorage.setItem(BUILD_KEY, JSON.stringify({ build: BUILD_LABEL, at: Date.now() }));
  } catch {
    // Without storage there is nothing for two tabs to share either.
  }
}

function hearBuild(event: StorageEvent): void {
  if (event.key !== BUILD_KEY || event.newValue === null) return;
  try {
    const { build } = JSON.parse(event.newValue) as { build?: unknown };
    if (typeof build !== "string" || build === BUILD_LABEL) return;
  } catch {
    return;
  }
  readOnly.value = "outdated";
  expireUndo();
  showNotice("A newer version is open in another tab. Reload this one to keep using it.", "error", {
    label: "Reload",
    run: () => location.reload(),
  });
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
  // Another checklist is about to be shown: nothing on screen can be undone into it.
  expireUndo();
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
  // Anything that changes a record an Undo would put back ends that Undo.
  if (undoable && !stillAsLeft(undoable)) expireUndo();
}

export function showNotice(
  message: string,
  kind: Notice["kind"] = "",
  action?: Notice["action"],
): void {
  undoable = null;
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
  const raw = localStorage.getItem(key);
  // Signed in, an account has its own save only. Signed out, an older build's key
  // is migrated on read, but only when there is no current save at all: an older
  // save never replaces a current one that merely could not be read.
  const candidates =
    activeUid || raw !== null
      ? [key, lastGoodKey(key)]
      : [key, lastGoodKey(key), ...LEGACY_STORAGE_KEYS];
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

/**
 * Put an unreadable save aside before anything can overwrite it. Each different
 * one gets its own slot (`:unreadable`, `:unreadable-2`, ...), so a second never
 * replaces the first.
 */
function keepUnreadable(key: string, text: string): boolean {
  try {
    for (let slot = 1; ; slot += 1) {
      const name = slot === 1 ? unreadableKey(key) : `${unreadableKey(key)}-${slot}`;
      const kept = localStorage.getItem(name);
      if (kept === text) return true;
      if (kept === null) {
        localStorage.setItem(name, text);
        return true;
      }
    }
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
  // With no readable copy of it at all, nothing is saved over the unreadable save.
  if (unreadable !== null && !found) heldKey = key;
  if (found) {
    applyState(found.state);
    // An older (or last good) copy rewrites itself under the current key. A legacy
    // entry is deliberately left behind so an older build still finds its own data.
    if (found.key !== key) persist();
  }
  if (heldKey === key) storageAvailable.value = false;
  if (unreadable !== null) {
    showNotice(
      `Your saved checklist could not be read, so ${
        found
          ? "the last copy that could be read is shown"
          : "a fresh checklist is shown that will not be saved"
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
  const base = seen.state;
  // First take the other tab's save as its storage event would have delivered it
  // (sync must learn of it the same way), then lay this tab's change on top.
  seen = { key, raw: stored, state: theirs.state };
  if (!otherTabListener?.(theirs.state)) applyState(theirs.state);
  applyState(
    rebaseState(exportState(), base, state, validPokemon, validForms),
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
      key === heldKey
        ? "Your saved checklist could not be read, so changes are not saved over it; they will disappear when this tab closes."
        : "Browser storage is unavailable; changes will disappear when this tab closes.",
      "error",
    );
  }
  // Sync must still receive an edit that lost local durability. Subsequent edits
  // also reach it while storageAvailable is false; offline-only has no listener.
  localChangeListener?.(state);
}

/**
 * Show the active save as stored, not as this tab last saw it: a tab that was
 * asleep may have missed another tab's last write.
 */
export function reloadSave(): void {
  try {
    useSave(readSave());
  } catch {
    // Unreadable storage: keep what is on screen.
  }
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
  /** This tab's own result, taken before saving could merge in another tab's. */
  after: SavedState;
  /** The records the change touched. */
  keys: string[];
  /** Reset or Restore: undone as a restore, so sync logs it as one event. */
  replace: boolean;
}

/** The change that the next notice can offer to undo. */
let lastChange: Change | null = null;
/** The change whose Undo the notice is showing. */
let undoable: Change | null = null;

function change(before: SavedState, after: SavedState, replace = false): Change {
  const keys = Object.keys(
    diffEntries(entriesFromState(before, 0, ""), entriesFromState(after, 0, "")),
  );
  return { before, after, keys, replace };
}

/** Whether every record the change touched still holds what it left there. */
function stillAsLeft({ after, keys }: Change): boolean {
  const now = entriesFromState(exportState(), 0, "");
  const then = entriesFromState(after, 0, "");
  return keys.every((key) => now[key]?.s === then[key]?.s);
}

/** Withdraw the notice's Undo: what it would put back has changed since. */
function expireUndo(): void {
  if (!undoable) return;
  undoable = null;
  const { message, kind, action } = notice.value;
  if (action?.label === "Undo") notice.value = { message, kind };
}

/**
 * Put back what one change changed, and nothing else: a record changed since, and
 * progress that arrived since (from another device or tab), stays. It goes through
 * the ordinary save path, so sync sends an undo as the plain edits it is.
 */
function undo(done: Change): void {
  if (readOnly.value) return;
  undoable = null;
  const target = rebaseState(
    exportState(),
    done.after,
    done.before,
    validPokemon,
    validForms,
    true,
  );
  if (done.replace) replaceState(target, "restore");
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
  const done = lastChange;
  lastChange = null;
  if (readOnly.value) {
    showReadOnly();
    return;
  }
  const saved = storageAvailable.value;
  showNotice(
    saved ? message : unsaved,
    saved ? "good" : "error",
    done ? { label: "Undo", run: () => undo(done) } : undefined,
  );
  undoable = done;
}

/** Say why nothing changed, when a view-only tab is tapped. */
export function showReadOnly(): void {
  showNotice(
    readOnly.value === "outdated"
      ? "A newer version is open in another tab. Reload this one to keep using it."
      : "This checklist is being edited in another tab.",
    "error",
  );
}

export function cycleSpecies(id: number): void {
  if (readOnly.value) return;
  const before = exportState();
  const status = speciesSignal(id);
  status.value = cycleStatus(status.value);
  const done = change(before, exportState());
  persist();
  lastChange = done;
}

export function cycleForm(key: string): void {
  if (readOnly.value) return;
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
  const done = change(before, exportState());
  persist();
  lastChange = done;
}

export function setMode(nextMode: GameMode): void {
  if (readOnly.value) return;
  mode.value = nextMode;
  persist();
}

export function toggleForms(): void {
  if (readOnly.value) return;
  formsTracked.value = !formsTracked.value;
  persist();
}

export function isStarred(id: number): boolean {
  return starred.value.includes(id);
}

/** Pin a species to the top of the Pokédex list, or release it again. */
export function toggleStar(id: number): void {
  if (readOnly.value) return;
  const before = exportState();
  const pinned = isStarred(id);
  starred.value = pinned
    ? starred.value.filter((entry) => entry !== id)
    : [...starred.value, id].sort((a, b) => a - b);
  const done = change(before, exportState());
  persist();
  lastChange = done;
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
  if (readOnly.value) return;
  const before = exportState();
  applyState(state);
  const done = change(before, exportState(), true);
  localReplaceListener?.(before, op);
  persist();
  lastChange = done;
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
  try {
    // A later write has replaced this one (and was taken in, or has its own event):
    // applying the older value now would roll that write back.
    if (localStorage.getItem(event.key) !== event.newValue) return;
  } catch {
    return;
  }
  const synced = interpretStoredState(event.newValue);
  if (synced.kind === "ignore") return;
  const state = synced.kind === "cleared" ? defaultState() : synced.state;
  seen = { key: activeSaveKey(), raw: event.newValue, state };
  if (!otherTabListener?.(state)) applyState(state);
  // An Undo still on offer is worth more than this message (and it has already
  // been withdrawn if the update touched what it would put back).
  if (undoable) return;
  if (synced.kind === "cleared") {
    showNotice("Progress was cleared in another tab.");
    return;
  }
  showNotice("Progress updated from another tab.", "good");
}

export function watchOtherTabs(): void {
  window.addEventListener("storage", syncFromStorage);
  window.addEventListener("storage", hearBuild);
}
