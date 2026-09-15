import { batch, computed, signal, type Signal } from "@preact/signals";
import { ENCOUNTERS_BY_MODE, POKEMON } from "./data";
import {
  DEFAULT_MODE,
  LEGACY_STORAGE_KEY,
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

export function initializeState(): void {
  try {
    const current = localStorage.getItem(STORAGE_KEY);
    const legacy = current ? null : localStorage.getItem(LEGACY_STORAGE_KEY);
    const saved = current || legacy;
    if (saved) {
      applyState(validateState(JSON.parse(saved), validPokemon, validForms));
    }
    if (!current && legacy) persist();
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
