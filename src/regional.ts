import regionalJson from "../data/regional-forms.json";
import type { Status } from "./types";

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

/** Native unmarked regional encounters default to Alolan; unknown tokens stay unknown. */
export function encounterRegionalForm(id: number, form?: string): RegionalForm | undefined {
  if (!isRegional(id)) return undefined;
  if (form === undefined || form === "alolan") return "alolan";
  return form === "kanto" ? "kanto" : undefined;
}

/** One aggregate rule for every regional species: Caught wins, then Seen. */
export function aggregateRegionalStatus(statuses: readonly Status[]): Status {
  return statuses.includes("caught") ? "caught" : statuses.includes("seen") ? "seen" : "none";
}

/** Generic progress stronger than the known forms still needs an explicit decision. */
export const hasUnresolvedRegionalOwnership = (species: Status, forms: readonly Status[]): boolean =>
  species === "caught" ? aggregateRegionalStatus(forms) !== "caught"
    : species === "seen" && aggregateRegionalStatus(forms) === "none";

/**
 * Project merged records without losing explicit form evidence or attributing
 * stronger legacy progress to a form. Explicit user edits set their aggregate
 * with aggregateRegionalStatus; reading a snapshot is not such a decision.
 */
export function projectRegionalSpeciesStatus(current: Status, forms: readonly Status[]): Status {
  return hasUnresolvedRegionalOwnership(current, forms) ? current : aggregateRegionalStatus(forms);
}
