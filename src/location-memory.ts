import type { GameMode } from "./types";

/** UI preference only: never part of player saves, backups or sync records. */
export const LOCATION_MEMORY_KEY = "pokemon-checklist-last-area-v1";
export function locationMemoryKey(mode: GameMode, namespace: string): string {
  return `${LOCATION_MEMORY_KEY}:${namespace}:${mode}`;
}
export function readLastLocation(mode: GameMode, namespace: string, validIds: readonly string[]): string | null {
  try {
    const id = localStorage.getItem(locationMemoryKey(mode, namespace));
    return id && validIds.includes(id) ? id : null;
  } catch {
    return null;
  }
}
export function writeLastLocation(mode: GameMode, namespace: string, id: string): boolean {
  try {
    localStorage.setItem(locationMemoryKey(mode, namespace), id);
    return true;
  } catch {
    return false;
  }
}
