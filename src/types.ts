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
  schemaVersion: 2;
  species: StatusMap;
  forms: StatusMap;
  settings: Settings;
}

export interface LegacyState {
  schemaVersion: 1;
  species: StatusMap;
  forms: StatusMap;
  settings: { forms: boolean };
}

export interface Occurrence {
  row: EncounterRow;
  group: EncounterGroup;
  location: Location;
  island: Island;
  ally: boolean;
}
