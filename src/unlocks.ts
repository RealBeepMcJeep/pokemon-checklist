import type { EncounterGroup, EncounterRow, Location } from "./types";
import { isRegional } from "./regional";

export function groupUnlock(group: EncounterGroup): string | null {
  if (/Weather.*SOS|Rain.*SOS/i.test(group.name)) return "weather-sos";
  if (/Surfing/i.test(group.name)) return "surfing";
  if (/Tauros/i.test(group.name)) return "tauros";
  if (/Fishing/i.test(group.name)) return "fishing";
  if (/SOS/i.test(group.name)) return "sos";
  return null;
}

/** Immutable species-level reachability; an owned Pokémon never grants access. */
export function eligibleRows(location: Location, unlocks: readonly string[], separateForms = false): EncounterRow[] {
  const identity = (row: EncounterRow): string => separateForms && row.speciesId && isRegional(row.speciesId)
    ? `${row.speciesId}:${row.form || "alolan"}` : String(row.speciesId);
  const rows = new Map<string, EncounterRow>();
  const add = (row: EncounterRow) => {
    if (row.speciesId && !rows.has(identity(row))) rows.set(identity(row), row);
  };
  for (const group of location.groups) {
    const kind = groupUnlock(group);
    if (group.category === "regular" || (kind !== null && kind !== "sos" && kind !== "weather-sos" && unlocks.includes(kind))) {
      group.encounters.forEach(add);
    }
  }
  if (unlocks.includes("sos")) {
    let changed = true;
    while (changed) {
      const size = rows.size;
  if (rows.size && unlocks.includes("sos") && unlocks.includes("weather-sos")) {
    for (const group of location.groups.filter(group => groupUnlock(group) === "weather-sos")) {
      for (const row of group.encounters) {
        add(row);
        for (const ally of row.allies || []) add({id:row.id,speciesId:ally.speciesId,
          species:ally.species,speciesName:ally.name,form:ally.form,rates:null,allies:[]});
      }
    }
  }

      for (const group of location.groups) {
        const kind = groupUnlock(group);
        const direct = group.category === "regular" || (kind !== null && kind !== "sos" && kind !== "weather-sos" && unlocks.includes(kind));
        if (!direct && kind !== "sos") continue;
        for (const caller of group.encounters) {
          if (!caller.speciesId || !rows.has(identity(caller))) continue;
          for (const ally of caller.allies || []) {
            add({id:caller.id,speciesId:ally.speciesId,
              species:ally.species,speciesName:ally.name,form:ally.form,rates:null,allies:[]});
          }
        }
      }
      changed = size !== rows.size;
    }
  }
  return [...rows.values()];
}

export function occurrenceEligible(location: Location, group: EncounterGroup, row: EncounterRow, ally: boolean, flags: readonly string[]): boolean {
  const kind = groupUnlock(group);
  const ids = new Set(eligibleRows(location,flags).map(r=>r.speciesId));
  if (kind === "weather-sos") return flags.includes("sos") && flags.includes("weather-sos") && ids.size > 0 && (row.speciesId ? ids.has(row.speciesId) : row.allies.some(a=>ids.has(a.speciesId)));
  const accessible = group.category === "regular" || (kind !== null && kind !== "sos" && flags.includes(kind));
  if (ally || kind === "sos") return flags.includes("sos") && (accessible || kind === "sos") && !!row.speciesId && ids.has(row.speciesId);
  return accessible;
}
