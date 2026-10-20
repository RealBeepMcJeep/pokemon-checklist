import type { GameMode } from "./types";
import { LEGACY_STORAGE_KEYS, STORAGE_KEY } from "./domain";

/** UI preference only: never part of player saves, backups or sync records. */
export const LOCATION_MEMORY_KEY = "pokemon-checklist-last-area-v1";
export function locationMemoryKey(mode: GameMode, namespace: string): string {
  return `${LOCATION_MEMORY_KEY}:${namespace}:${mode}`;
}
export function readLastLocation(mode: GameMode, namespace: string, validIds: readonly string[]): string | null {
  try {
    const id = localStorage.getItem(locationMemoryKey(mode, namespace));
    if (id !== null) return validIds.includes(id) ? id : null;
    if (namespace !== STORAGE_KEY && !namespace.startsWith(`${STORAGE_KEY}:`)) return null;
    const suffix = namespace.slice(STORAGE_KEY.length);
    for (const legacy of LEGACY_STORAGE_KEYS) {
      const previous = localStorage.getItem(locationMemoryKey(mode, `${legacy}${suffix}`));
      if (!previous || !validIds.includes(previous)) continue;
      // Copy only this namespace/mode's valid UI preference; retain older keys.
      // A failed copy does not prevent using a readable preference this session.
      try { localStorage.setItem(locationMemoryKey(mode, namespace), previous); } catch { /* optional UI memory */ }
      return previous;
    }
    return null;
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
