import type {
  EncounterData,
  EncounterRow,
  FormDefinition,
  GameMode,
  Location,
  Occurrence,
  SavedState,
  SavedStateV5,
  Status,
  StatusMap,
} from "./types";
import { GAME_MODES, UNLOCKS } from "./types";
import { eligibleRows, occurrenceEligible, guideEncounters, guideCalls, groupUnlock } from "./unlocks";
import { REGIONAL_IDS, encounterRegionalForm, isRegional, type RegionalForm } from "./regional";

export const DEFAULT_MODE: GameMode = "photonic-prismatic";
export const STATE_VERSION = 5;
export const STORAGE_KEY = "pokemon-checklist-state-v5";
/**
 * Checked in order when the current key holds nothing. Each is migrated on read
 * and rewritten under `STORAGE_KEY`, so an older save upgrades itself and an
 * older build of the app still finds its own key untouched.
 */
export const LEGACY_STORAGE_KEYS = [
  "pokemon-checklist-state-v4",
  "pokemon-checklist-state-v3",
  "pokemon-checklist-state-v2",
  "pokemon-checklist-state-v1",
] as const;
export const STATUS_ORDER: readonly Status[] = ["none", "caught", "seen"];
export const STATUS_LABEL = {
  none: "None",
  caught: "Caught",
  seen: "Seen",
} satisfies Record<Status, string>;
export const MODE_LABELS = {
  "photonic-prismatic": "Prismatic Moon",
  sun: "Pokémon Sun",
  moon: "Pokémon Moon",
  "ultra-sun": "Pokémon Ultra Sun",
  "ultra-moon": "Pokémon Ultra Moon",
} satisfies Record<GameMode, string>;

export const normalize = (value: unknown): string =>
  String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");

export const formSlug = (value: unknown): string => normalize(value);

const titleForm = (value: unknown): string =>
  String(value)
    .split("-")
    .map((part) => (part ? part[0].toUpperCase() + part.slice(1) : part))
    .join(" ");

/** The one place the `species:slug` / `species:kind-slug` form-key format is
 * spelled out; StatusControls.tsx and Locations.tsx build the same keys through
 * this rather than re-typing the format. */
export const formKey = (
  speciesId: number,
  kind: string,
  slug: string,
): string => `${speciesId}:${kind === "form" ? slug : `${kind}-${slug}`}`;

export const safeId = (value: unknown): string =>
  String(value)
    .replace(/[^a-zA-Z0-9]+/g, "-")
    .replace(/^-|-$/g, "");

export function forEachEncounter(
  encounters: EncounterData,
  callback: (
    row: EncounterRow,
    group: EncounterData["islands"][number]["locations"][number]["groups"][number],
    location: Location,
    island: EncounterData["islands"][number],
  ) => void,
): void {
  for (const island of encounters.islands) {
    for (const location of island.locations) {
      for (const group of location.groups) {
        for (const row of group.encounters)
          callback(row, group, location, island);
      }
    }
  }
}

function addFormsFrom(
  encounters: EncounterData,
  forms: Map<string, FormDefinition>,
): void {
  const add = (
    speciesId: number | null | undefined,
    rawName: string | undefined,
    kind = "form",
    displayName?: string,
  ): void => {
    if (!speciesId || !rawName) return;
    const slug = formSlug(rawName);
    if (!slug) return;
    const key = formKey(speciesId, kind, slug);
    if (!forms.has(key)) {
      forms.set(key, {
        key,
        speciesId,
        label: displayName || titleForm(rawName),
        kind,
      });
    }
  };

  forEachEncounter(encounters, (row) => {
    if (row.speciesId) {
      add(row.speciesId, row.form);
      for (const form of row.forms || []) add(row.speciesId, form);
      if (row.ability) {
        add(row.speciesId, row.ability, "ability", `${row.ability} ability`);
      }
    }
    for (const ally of row.allies || []) add(ally.speciesId, ally.form);
  });
}

/** Every form obtainable across all five modes; used to validate a save's form
 * keys regardless of which mode it was written under. */
export function buildFormDefinitions(
  encountersByMode: Record<GameMode, EncounterData>,
): Map<string, FormDefinition> {
  const forms = new Map<string, FormDefinition>();
  for (const speciesId of REGIONAL_IDS) {
    for (const [slug, label] of [["alolan", "Alolan"], ["kanto", "Kanto"]]) {
      const key = formKey(speciesId, "form", slug);
      forms.set(key, { key, speciesId, label, kind: "form" });
    }
  }
  for (const encounters of Object.values(encountersByMode)) {
    addFormsFrom(encounters, forms);
  }
  return forms;
}

/** Only the forms reachable in one mode's own encounters, e.g. for a "forms
 * caught" count that shouldn't count forms the active mode can't offer. */
export function formsForMode(encounters: EncounterData): Map<string, FormDefinition> {
  const forms = new Map<string, FormDefinition>();
  addFormsFrom(encounters, forms);
  return forms;
}

export function cycleStatus(status: Status): Status {
  return STATUS_ORDER[(STATUS_ORDER.indexOf(status) + 1) % STATUS_ORDER.length];
}

const catchNowRowsCache = new WeakMap<Location, EncounterRow[]>();

export function catchNowRows(location: Location, unlocks: readonly string[] = [], separateForms = false): EncounterRow[] {
  const cached = unlocks.length === 0 && !separateForms ? catchNowRowsCache.get(location) : undefined;
  if (cached) return cached;

  const rows = eligibleRows(location, unlocks, separateForms);
  if (unlocks.length === 0 && !separateForms) catchNowRowsCache.set(location, rows);
  return rows;
}

export function encounterStatus(row: EncounterRow, statusOf: (id: number) => Status, formStatusOf?: (key: string) => Status): Status {
  return row.speciesId && formStatusOf && isRegional(row.speciesId)
    ? formStatusOf(formKey(row.speciesId, "form", row.form || "alolan"))
    : statusOf(row.speciesId!);
}

export function locationProgress(
  location: Location,
  statusOf: (id: number) => Status,
  unlocks: readonly string[] = [],
  formStatusOf?: (key: string) => Status,
): { none: number; seen: number; caught: number; total: number } {
  const counts = { none: 0, seen: 0, caught: 0, total: 0 };
  for (const row of catchNowRows(location, unlocks, !!formStatusOf)) {
    counts[encounterStatus(row, statusOf, formStatusOf)]++;
    counts.total++;
  }
  return counts;
}

export function firstIncompleteLocation(
  encounters: EncounterData,
  statusOf: (id: number) => Status,
  unlocks: readonly string[] = [],
  formStatusOf?: (key: string) => Status,
): Location | null {
  for (const island of encounters.islands) {
    for (const location of island.locations) {
      const progress = locationProgress(location, statusOf, unlocks, formStatusOf);
      if (progress.caught !== progress.total) return location;
    }
  }
  return null;
}

export function getOccurrences(
  encounters: EncounterData,
  speciesId: number,
  unlocks?: readonly string[],
  form?: RegionalForm,
): Occurrence[] {
  const found: Occurrence[] = [];
  if (!encounters.mode || encounters.mode === "photonic-prismatic") {
    for (const island of encounters.islands) for (const location of island.locations) {
      const source = guideEncounters(location, unlocks || [], true);
      const mapped = new Set<string>();
      const routes = new Map<string, Occurrence>();
      for (const entry of source) {
        if (entry.row.speciesId === speciesId && (!form || encounterRegionalForm(speciesId, entry.row.form) === form)) {
          found.push({ row: entry.row, group: entry.group, location, island, ally: false, eligible: entry.eligible });
        }
        for (const node of guideCalls(entry.sos)) {
          const call = node.call;
          mapped.add(call.sourceRow.id);
          if (call.row.speciesId !== speciesId || (form && encounterRegionalForm(speciesId, call.row.form) !== form)) continue;
          const key = JSON.stringify([call.group.id, call.sourceRow.id, call.row.form || ""]);
          const conditions = [...(call.group.conditions || []), ...(call.sourceRow.conditions || [])];
          const group = { ...call.group, name: [call.group.name, ...conditions].join(" · ") };
          const item = { row: entry.row, group, location, island, ally: true, eligible: node.eligible };
          if (!routes.has(key) || node.eligible) routes.set(key, item);
        }
      }
      found.push(...routes.values());
      // Preserve unresolved source evidence at its warning, never as a fake wild caller.
      for (const group of location.groups) {
        const kind = groupUnlock(group);
        if (kind !== "sos" && kind !== "weather-sos") continue;
        for (const row of group.encounters) if (!mapped.has(row.id)) {
          const match = kind === "weather-sos" && row.speciesId === speciesId
            && (!form || encounterRegionalForm(speciesId, row.form) === form);
          if (match || row.allies.some(ally => ally.speciesId === speciesId && (!form || encounterRegionalForm(speciesId, ally.form) === form))) {
            found.push({ row, group, location, island, ally: true, eligible: false });
          }
        }
      }
    }
    return found;
  }
  forEachEncounter(encounters, (row, group, location, island) => {
    if (row.speciesId === speciesId && (!form || encounterRegionalForm(speciesId, row.form) === form)) {
      found.push({
        row,
        group,
        location,
        island,
        ally: group.encounterType === "sos",
      });
    }
    for (const ally of row.allies || []) {
      if (ally.speciesId === speciesId && (!form || encounterRegionalForm(speciesId, ally.form) === form)) {
        found.push({ row, group, location, island, ally: true });
      }
    }
  });
  if (unlocks) for (const item of found) item.eligible = occurrenceEligible(item.location,item.group,item.row,item.ally,unlocks);
  return found;
}

export function rateText(rates: EncounterRow["rates"]): string {
  if (!rates) return "—";
  const parts: string[] = [];
  if (rates.single !== undefined) parts.push(`${rates.single}%`);
  if (rates.day !== undefined) parts.push(`Day ${rates.day}%`);
  if (rates.night !== undefined) parts.push(`Night ${rates.night}%`);
  if (rates.bubbling !== undefined) parts.push(`Bubbling ${rates.bubbling}%`);
  return parts.join(" · ");
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

function validateStatusMap(
  value: unknown,
  validPokemon: ReadonlySet<number>,
  validForms: ReadonlySet<string>,
  label: string,
  numeric = false,
): StatusMap {
  if (!isRecord(value)) throw new Error(`${label} must be an object`);
  const result: StatusMap = {};
  for (const [key, rawStatus] of Object.entries(value)) {
    if (
      numeric &&
      (!/^(?:[1-9]|[1-9][0-9]|[1-9][0-9]{2})$/.test(key) ||
        !validPokemon.has(Number(key)))
    ) {
      throw new Error(`Unknown Pokémon number in ${label}`);
    }
    if (!numeric && !validForms.has(key))
      throw new Error(`Unknown form in ${label}`);
    if (!STATUS_ORDER.includes(rawStatus as Status)) {
      throw new Error(`Unknown status in ${label}`);
    }
    if (rawStatus !== "none") result[key] = rawStatus as Status;
  }
  return result;
}

/** Every shipped schema version is still readable and migrates up on load. */
const isSupportedVersion = (value: unknown): value is number =>
  typeof value === "number" &&
  Number.isInteger(value) &&
  value >= 1 &&
  value <= STATE_VERSION;

/**
 * Starred Pokédex numbers: real species, no duplicates. Order is normalized
 * rather than rejected so a hand-edited backup loads in a canonical shape.
 */
function validateStarred(
  value: unknown,
  validPokemon: ReadonlySet<number>,
): number[] {
  if (!Array.isArray(value))
    throw new Error("Starred Pokémon must be a list");
  const seen = new Set<number>();
  for (const entry of value) {
    if (
      typeof entry !== "number" ||
      !Number.isInteger(entry) ||
      !validPokemon.has(entry)
    ) {
      throw new Error("Unknown Pokémon number in starred Pokémon");
    }
    if (seen.has(entry))
      throw new Error("Starred Pokémon must not repeat a number");
    seen.add(entry);
  }
  return [...seen].sort((a, b) => a - b);
}

export function validateState(
  value: unknown,
  validPokemon: ReadonlySet<number>,
  validForms: ReadonlySet<string>,
): SavedStateV5 {
  if (!isRecord(value) || !isSupportedVersion(value.schemaVersion)) {
    throw new Error("This backup format is not supported");
  }
  const { schemaVersion } = value;
  // v3 introduced `starred`; each version keeps its own exact key set.
  const expectedKeys =
    schemaVersion === 5
      ? "forms,schemaVersion,settings,species,starred,starredForms"
      : schemaVersion >= 3
      ? "forms,schemaVersion,settings,species,starred"
      : "forms,schemaVersion,settings,species";
  if (
    Object.keys(value)
      .sort((a, b) => a.localeCompare(b))
      .join(",") !== expectedKeys
  ) {
    throw new Error("This backup contains unexpected information");
  }
  if (!isRecord(value.settings))
    throw new Error("This backup has invalid settings");
  const expectedSettings = schemaVersion === 1 ? "forms" : schemaVersion >= 4 ? "forms,mode,unlocks" : "forms,mode";
  if (
    typeof value.settings.forms !== "boolean" ||
    Object.keys(value.settings)
      .sort((a, b) => a.localeCompare(b))
      .join(",") !== expectedSettings
  ) {
    throw new Error("This backup has invalid settings");
  }
  const rawMode =
    schemaVersion === 1 ? DEFAULT_MODE : value.settings.mode;
  if (!GAME_MODES.includes(rawMode as GameMode)) {
    throw new Error("This backup has an unknown game mode");
  }
  const unlocks = schemaVersion >= 4 ? value.settings.unlocks : [];
  if (!Array.isArray(unlocks) || unlocks.some(flag => !UNLOCKS.includes(flag)) || new Set(unlocks).size !== unlocks.length)
    throw new Error("This backup has invalid encounter unlocks");
  const starredForms: string[] = [];
  if (schemaVersion === 5) {
    if (!Array.isArray(value.starredForms) || value.starredForms.some(key => typeof key !== "string" || !validForms.has(key)) || new Set(value.starredForms).size !== value.starredForms.length)
      throw new Error("This backup has invalid form favorites");
    starredForms.push(...value.starredForms);
  }
  return canonicalState({
    schemaVersion: STATE_VERSION,
    species: validateStatusMap(
      value.species,
      validPokemon,
      validForms,
      "Pokémon statuses",
      true,
    ),
    forms: validateStatusMap(
      value.forms,
      validPokemon,
      validForms,
      "form statuses",
    ),
    starred:
      schemaVersion >= 3 ? validateStarred(value.starred, validPokemon) : [],
    starredForms,
    settings: { forms: value.settings.forms, mode: rawMode as GameMode, unlocks: [...unlocks] },
  });
}

export function canonicalState(state: SavedState): SavedStateV5 {
  const species: StatusMap = {};
  for (const key of Object.keys(state.species).sort(
    (a, b) => Number(a) - Number(b),
  )) {
    if (state.species[key] !== "none") species[key] = state.species[key];
  }
  const forms: StatusMap = {};
  for (const key of Object.keys(state.forms).sort((a, b) =>
    a.localeCompare(b),
  )) {
    if (state.forms[key] !== "none") forms[key] = state.forms[key];
  }
  const starredForms = new Set("starredForms" in state ? state.starredForms : []);
  const starred = [...new Set(state.starred)].filter(id => {
    if (!isRegional(id)) return true;
    if ([...starredForms].some(key => Number(key.split(":")[0]) === id)) return false;
    const owned = ["alolan", "kanto"].map(form => formKey(id, "form", form)).filter(key => forms[key] === "caught");
    if (owned.length !== 1) return true;
    starredForms.add(owned[0]);
    return false;
  });
  return {
    schemaVersion: STATE_VERSION,
    species,
    forms,
    starred: starred.sort((a, b) => a - b),
    starredForms: [...starredForms].sort((a, b) => a.localeCompare(b)),
    settings: { forms: state.settings.forms, mode: state.settings.mode, unlocks: UNLOCKS.filter(flag => state.settings.unlocks.includes(flag)) },
  };
}

/** The catch-now species at a location that are not yet caught, in "Catch next". */
export function uncaughtCatchNowRows(
  location: Location,
  statusOf: (id: number) => Status,
  unlocks: readonly string[] = [],
  formStatusOf?: (key: string) => Status,
): EncounterRow[] {
  return catchNowRows(location, unlocks, !!formStatusOf)
    .filter((row) => row.speciesId && encounterStatus(row, statusOf, formStatusOf) !== "caught")
    .sort((a, b) =>
      Number(encounterStatus(a, statusOf, formStatusOf) === "seen") -
      Number(encounterStatus(b, statusOf, formStatusOf) === "seen"),
    );
}

/**
 * Where a species turns up in every OTHER game mode, for the Pokédex's "Also
 * catchable in" section. All five modes' data already sit in memory together
 * (src/data.ts), so this is one more loop over it, not a new fetch.
 */
export function crossModeOccurrences(
  encountersByMode: Record<GameMode, EncounterData>,
  currentMode: GameMode,
  speciesId: number,
  form?: RegionalForm,
): { mode: GameMode; occurrences: Occurrence[] }[] {
  return GAME_MODES.filter((candidate) => candidate !== currentMode)
    .map((candidate) => ({
      mode: candidate,
      occurrences: getOccurrences(encountersByMode[candidate], speciesId, undefined, form),
    }))
    .filter((entry) => entry.occurrences.length > 0);
}
