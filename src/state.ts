import { batch, computed, signal, type Signal } from "@preact/signals";
import { ENCOUNTERS_BY_MODE, POKEMON } from "./data";
import {
  DEFAULT_MODE,
  LEGACY_STORAGE_KEYS,
  STATE_VERSION,
  STORAGE_KEY,
  buildFormDefinitions,
  canonicalState,
  cycleStatus,
  validateState,
} from "./domain";
import type { GameMode, SavedState, Status } from "./types";

export interface Notice {
  message: string;
  kind: "" | "good" | "error";
}

export const formDefinitions = buildFormDefinitions(ENCOUNTERS_BY_MODE);
const validPokemon = new Set(POKEMON.map(({ id }) => id));
const validForms = new Set(formDefinitions.keys());
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
export const activeLocations = computed(() =>
  activeEncounters.value.islands.flatMap((island) => island.locations),
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
export const formsCaught = computed(
  () =>
    [...formSignals.values()].filter((status) => status.value === "caught")
      .length,
);

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
export const formStatus = (key: string): Status => formSignal(key).value;

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

export function showNotice(message: string, kind: Notice["kind"] = ""): void {
  notice.value = { message, kind };
}

export function persist(): void {
  if (!storageAvailable.value) return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(exportState()));
  } catch {
    storageAvailable.value = false;
    showNotice(
      "Browser storage is unavailable; changes will disappear when this tab closes.",
      "error",
    );
  }
}

/** The most recent save on this origin, whichever schema version wrote it. */
function readStoredState(): { key: string; raw: string } | null {
  for (const key of [STORAGE_KEY, ...LEGACY_STORAGE_KEYS]) {
    const raw = localStorage.getItem(key);
    if (raw !== null) return { key, raw };
  }
  return null;
}

export function initializeState(): void {
  try {
    const stored = readStoredState();
    if (stored) {
      applyState(
        validateState(JSON.parse(stored.raw), validPokemon, validForms),
      );
      // An older save rewrites itself under the current key. The legacy entry is
      // deliberately left behind so an older build still finds its own data.
      if (stored.key !== STORAGE_KEY) persist();
    }
  } catch {
    applyState(defaultState());
    storageAvailable.value = false;
    showNotice(
      "Saved data could not be read; starting a fresh checklist that will not be saved.",
      "error",
    );
  }
}

export function cycleSpecies(id: number): void {
  const status = speciesSignal(id);
  status.value = cycleStatus(status.value);
  persist();
}

export function cycleForm(key: string): void {
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
  const pinned = isStarred(id);
  starred.value = pinned
    ? starred.value.filter((entry) => entry !== id)
    : [...starred.value, id].sort((a, b) => a - b);
  persist();
  showNotice(
    pinned ? "Unstarred." : "Starred. It stays at the top until you unstar it.",
    "good",
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

export function restoreState(state: SavedState): void {
  applyState(state);
  persist();
}

export function resetState(): void {
  applyState(defaultState());
  persist();
}

export function savedNotice(subject: "Status" | "Form status"): void {
  showNotice(
    storageAvailable.value
      ? `${subject} saved.`
      : `${subject} changed, but it will disappear when this tab closes.`,
    storageAvailable.value ? "good" : "error",
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
  if (event.key !== STORAGE_KEY) return;
  const synced = interpretStoredState(event.newValue);
  if (synced.kind === "ignore") return;
  if (synced.kind === "cleared") {
    applyState(defaultState());
    showNotice("Progress was cleared in another tab.");
    return;
  }
  applyState(synced.state);
  showNotice("Progress updated from another tab.", "good");
}

export function watchOtherTabs(): void {
  window.addEventListener("storage", syncFromStorage);
}
