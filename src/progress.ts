import { collectionTargets } from "./collection";
import { isRegional, projectRegionalSpeciesStatus } from "./regional";
import type { Pokemon, Status, StatusMap } from "./types";

export type ProgressMetric = "registered" | "owned" | "living";
export const PROGRESS_PREFERENCE_KEY = "pokemon-checklist-progress-v1";
type PreferenceStorage = Pick<Storage, "getItem" | "setItem">;
const browserStorage = () => globalThis.localStorage;
export const isProgressMetric = (value: unknown): value is ProgressMetric =>
  value === "registered" || value === "owned" || value === "living";
export const defaultProgressMetric = (tracking: boolean): ProgressMetric => tracking ? "living" : "owned";

export interface ProgressCount { value: number; max: number }
export type ProgressCounts = Record<ProgressMetric, ProgressCount>;

/** Count current evidence without changing records or assigning unknown legacy forms. */
export function countProgress(pokemon: readonly Pokemon[], species: StatusMap, forms: StatusMap, tracking: boolean): ProgressCounts {
  const unique = [...new Map(pokemon.map(row => [row.id, row])).values()];
  const status = (id: number): Status => isRegional(id)
    ? projectRegionalSpeciesStatus(species[String(id)] || "none", [forms[`${id}:alolan`] || "none", forms[`${id}:kanto`] || "none"])
    : species[String(id)] || "none";
  const owned = unique.filter(row => status(row.id) === "caught").length;
  const targets = collectionTargets(unique, tracking);
  return {
    registered: { value: unique.filter(row => status(row.id) !== "none").length, max: unique.length },
    owned: { value: owned, max: unique.length },
    living: { value: targets.filter(target => target.form ? forms[`${target.id}:${target.form}`] === "caught" : status(target.id) === "caught").length, max: targets.length },
  };
}

/** Null means no explicit choice: the UI default follows the active tracking scope. */
export function readProgressPreference(getStorage: () => PreferenceStorage = browserStorage): ProgressMetric | null {
  try {
    const value = getStorage().getItem(PROGRESS_PREFERENCE_KEY);
    return isProgressMetric(value) ? value : null;
  } catch {
    return null;
  }
}

/** UI preference only: never write a player namespace, backup or sync setting. */
export function writeProgressPreference(metric: unknown, getStorage: () => PreferenceStorage = browserStorage): boolean {
  if (!isProgressMetric(metric)) return false;
  try {
    getStorage().setItem(PROGRESS_PREFERENCE_KEY, metric);
    return true;
  } catch {
    return false;
  }
}
