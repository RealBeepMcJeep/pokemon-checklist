export const GAME_MODES = [
  "photonic-prismatic",
  "sun",
  "moon",
  "ultra-sun",
  "ultra-moon",
] as const;

export type GameMode = (typeof GAME_MODES)[number];
export type Status = "none" | "caught" | "seen";
export type StatusMap = Record<string, Status>;

export interface Pokemon {
  id: number;
  name: string;
  slug: string;
}

export type Grade = "SSS" | "S" | "A" | "B" | "C" | "D" | "F";

interface EvolutionStep {
  name: string;
  method?: string;
}

export interface PokemonDetails {
  types: string[];
  grade: Grade;
  source: string;
  tier: string;
  ownTier: string;
  usage?: number;
  evolution?: EvolutionStep[];
}

export interface PokedexDetailsData {
  schemaVersion: 1;
  source: { showdownCommit: string; usage: string };
  species: (PokemonDetails & { id: number })[];
  forms: Record<string, PokemonDetails>;
}

/** How the game teaches a move; see tools/build_moves.py. */
export interface MoveRoute {
  via: "level" | "reminder" | "TM" | "tutor" | "egg" | "event";
  level?: number;
  /** Dex number of the form that learns it; set for level-up, egg and pre-evolution routes. */
  form?: number;
  beforeEvolving?: boolean;
}

export interface MoveInfo {
  name: string;
  type: string;
  power?: number;
  tm?: number;
  tmAt?: string;
  tutorAt?: string;
  tutorBp?: number;
}

export interface PopularMove {
  move: string;
  /** Percent of that species' competitive sets running the move. */
  usage: number;
  /** Set-specific overrides, e.g. "Hidden Power Fire". */
  name?: string;
  type?: string;
  /** Empty when the game cannot teach the move at all. */
  how: MoveRoute[];
}

export interface MovesData {
  schemaVersion: 1;
  source: { showdownCommit: string; usage: string; profile: string; top: number };
  moves: Record<string, MoveInfo>;
  /** Keyed by dex number; `stats` names the Smogon file, or null when none lists it. */
  finals: Record<string, { stats: string | null; moves: PopularMove[] }>;
  /** Unevolved species -> the final evolutions whose moves apply. */
  lines: Record<string, number[]>;
}

export interface Rates {
  single?: number;
  day?: number;
  night?: number;
  bubbling?: number;
}

export interface Ally {
  name: string;
  species: string;
  speciesId: number;
  form?: string;
}

export interface EncounterRow {
  id: string;
  speciesName?: string;
  species?: string | null;
  speciesId?: number | null;
  form?: string;
  forms?: string[];
  ability?: string;
  rates?: Rates | null;
  conditions?: string[];
  note?: string;
  allies: Ally[];
}

export interface EncounterGroup {
  id: string;
  name: string;
  category: "regular" | "return-later";
  levels?: { min: number; max: number } | null;
  conditions?: string[];
  notes?: string[];
  encounterType?: string;
  encounters: EncounterRow[];
}

export interface Location {
  id: string;
  name: string;
  order: number;
  assets?: string[];
  notes?: string[];
  groups: EncounterGroup[];
}

export interface Island {
  id: string;
  name: string;
  assets?: string[];
  locations: Location[];
}

export interface EncounterData {
  schemaVersion: 1;
  mode?: GameMode;
  assets: string[];
  islands: Island[];
}

export interface FormDefinition {
  key: string;
  speciesId: number;
  label: string;
  kind: string;
}

export interface Settings {
  forms: boolean;
  mode: GameMode;
}

export interface SavedState {
  schemaVersion: 3;
  species: StatusMap;
  forms: StatusMap;
  /** Dex numbers pinned to the top of the Pokédex list, ascending and unique. */
  starred: number[];
  settings: Settings;
}

export interface Occurrence {
  row: EncounterRow;
  group: EncounterGroup;
  location: Location;
  island: Island;
  ally: boolean;
}
