import type {
  EncounterData,
  EncounterRow,
  FormDefinition,
  GameMode,
  Location,
  Occurrence,
  SavedState,
  Status,
  StatusMap,
} from "./types";
import { GAME_MODES } from "./types";

export const DEFAULT_MODE: GameMode = "photonic-prismatic";
export const STATE_VERSION = 3;
export const STORAGE_KEY = "pokemon-checklist-state-v3";
/**
 * Checked in order when the current key holds nothing. Each is migrated on read
 * and rewritten under `STORAGE_KEY`, so an older save upgrades itself and an
 * older build of the app still finds its own key untouched.
 */
export const LEGACY_STORAGE_KEYS = [
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

export const titleForm = (value: unknown): string =>
  String(value)
    .split("-")
    .map((part) => (part ? part[0].toUpperCase() + part.slice(1) : part))
    .join(" ");

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

export function buildFormDefinitions(
  encountersByMode: Record<GameMode, EncounterData>,
): Map<string, FormDefinition> {
  const forms = new Map<string, FormDefinition>();
  const add = (
    speciesId: number | null | undefined,
    rawName: string | undefined,
    kind = "form",
    displayName?: string,
  ): void => {
    if (!speciesId || !rawName) return;
    const slug = formSlug(rawName);
    if (!slug) return;
    const key = `${speciesId}:${kind === "form" ? slug : `${kind}-${slug}`}`;
    if (!forms.has(key)) {
      forms.set(key, {
        key,
        speciesId,
        label: displayName || titleForm(rawName),
        kind,
      });
    }
  };

  for (const encounters of Object.values(encountersByMode)) {
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
  return forms;
}

export function cycleStatus(status: Status): Status {
  return STATUS_ORDER[(STATUS_ORDER.indexOf(status) + 1) % STATUS_ORDER.length];
}

const catchNowRowsCache = new WeakMap<Location, EncounterRow[]>();

export function catchNowRows(location: Location): EncounterRow[] {
  const cached = catchNowRowsCache.get(location);
  if (cached) return cached;

  const unique = new Map<number, EncounterRow>();
  for (const group of location.groups) {
    if (group.category !== "regular") continue;
    for (const row of group.encounters) {
      if (row.speciesId) unique.set(row.speciesId, row);
    }
  }
  const rows = [...unique.values()];
  catchNowRowsCache.set(location, rows);
  return rows;
}

export function locationProgress(
  location: Location,
  statusOf: (id: number) => Status,
): { caught: number; total: number } {
  const rows = catchNowRows(location);
  return {
    caught: rows.filter(
      (row) => row.speciesId && statusOf(row.speciesId) === "caught",
    ).length,
    total: rows.length,
  };
}

export function firstIncompleteLocation(
  encounters: EncounterData,
  statusOf: (id: number) => Status,
): Location | null {
  for (const island of encounters.islands) {
    for (const location of island.locations) {
      const progress = locationProgress(location, statusOf);
      if (progress.caught !== progress.total) return location;
    }
  }
  return null;
}

export function getOccurrences(
  encounters: EncounterData,
  speciesId: number,
): Occurrence[] {
  const found: Occurrence[] = [];
  forEachEncounter(encounters, (row, group, location, island) => {
    if (row.speciesId === speciesId) {
      found.push({
        row,
        group,
        location,
        island,
        ally: group.encounterType === "sos",
      });
    }
    for (const ally of row.allies || []) {
      if (ally.speciesId === speciesId) {
        found.push({ row, group, location, island, ally: true });
      }
    }
  });
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
): SavedState {
  if (!isRecord(value) || !isSupportedVersion(value.schemaVersion)) {
    throw new Error("This backup format is not supported");
  }
  const { schemaVersion } = value;
  // v3 introduced `starred`; each version keeps its own exact key set.
  const expectedKeys =
    schemaVersion >= 3
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
  const expectedSettings = schemaVersion === 1 ? "forms" : "forms,mode";
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
  return {
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
    settings: { forms: value.settings.forms, mode: rawMode as GameMode },
  };
}

export function canonicalState(state: SavedState): SavedState {
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
  return {
    schemaVersion: STATE_VERSION,
    species,
    forms,
    starred: [...new Set(state.starred)].sort((a, b) => a - b),
    settings: { forms: state.settings.forms, mode: state.settings.mode },
  };
}
