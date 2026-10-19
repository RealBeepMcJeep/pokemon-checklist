import regionalJson from "../data/regional-forms.json";

export type RegionalForm = "alolan" | "kanto";
export interface RegionalFacts {
  id: number;
  form: RegionalForm;
  name: string;
  showdownKey: string;
  types: readonly string[];
  baseStats: Readonly<Record<"hp" | "atk" | "def" | "spa" | "spd" | "spe", number>>;
  abilities: Readonly<Record<string, string>>;
}

// One generated identity catalogue is shared with the Python tools. Cosmetic
// Alola-cap Pikachu is deliberately excluded by its source-backed generator.
export const REGIONAL_DETAILS = regionalJson.forms as Readonly<Record<string, RegionalFacts>>;
export const REGIONAL_IDS: readonly number[] = [...new Set(Object.values(REGIONAL_DETAILS).map(row => row.id))].sort((a, b) => a - b);
const regionalIds = new Set(REGIONAL_IDS);
export const isRegional = (id: number): boolean => regionalIds.has(id);
export const regionalDetails = (id: number, form: RegionalForm): RegionalFacts | undefined => REGIONAL_DETAILS[`${id}:${form}`];
