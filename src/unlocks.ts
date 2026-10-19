import type { EncounterGroup, EncounterRow, Location } from "./types";
import { encounterRegionalForm, isRegional } from "./regional";

export function groupUnlock(group: EncounterGroup): string | null {
  if (/Weather.*SOS|Rain.*SOS/i.test(group.name)) return "weather-sos";
  if (/Surfing/i.test(group.name)) return "surfing";
  if (/Tauros/i.test(group.name)) return "tauros";
  if (/Fishing/i.test(group.name)) return "fishing";
  if (/SOS/i.test(group.name)) return "sos";
  return null;
}

/** A documented call edge; source conditions/notes remain on the original records. */
export interface SosEncounter {
  kind: "sos" | "weather-sos";
  group: EncounterGroup;
  sourceRow: EncounterRow;
  /** Exact wild row for an embedded rule; a reachable identity exemplar for a
   * location-wide caller table; null for a location-wide weather rule. */
  caller: EncounterRow | null;
  row: EncounterRow;
}
export interface EncounterProjection {
  wild: { group: EncounterGroup; row: EncounterRow; eligible: boolean }[];
  calls: SosEncounter[];
  /** Unreachable with THESE flags, not proof that the creator's source is wrong. */
  unavailableCallers: { group: EncounterGroup; row: EncounterRow }[];
}

function directAccess(group: EncounterGroup, flags: readonly string[]): boolean {
  const kind = groupUnlock(group);
  return group.category === "regular" || (kind !== null && kind !== "sos" && kind !== "weather-sos" && flags.includes(kind));
}

function encounterIdentity(row: EncounterRow): string {
  const form = row.speciesId && isRegional(row.speciesId)
    ? encounterRegionalForm(row.speciesId, row.form) ?? row.form : row.form;
  return JSON.stringify([row.speciesId, form || "", row.ability || ""]);
}

function sameCaller(source: EncounterRow, caller: EncounterRow): boolean {
  if (source.speciesId !== caller.speciesId || !source.speciesId || source.ability !== caller.ability) return false;
  if (isRegional(source.speciesId)) {
    const form = encounterRegionalForm(source.speciesId, source.form);
    return form !== undefined && form === encounterRegionalForm(source.speciesId, caller.form);
  }
  // Legacy `forms` lists mix wild/SOS variants; never infer native forms from them.
  return source.form === caller.form;
}

function allyRow(source: EncounterRow, ally: EncounterRow["allies"][number]): EncounterRow {
  return { id: source.id, speciesId: ally.speciesId, species: ally.species,
    speciesName: ally.name, form: ally.form, rates: null, allies: [] };
}

/** Pure caller graph. Full encounter identities drive traversal even in collapsed collection mode. */
export function projectEncounters(location: Location, flags: readonly string[]): EncounterProjection {
  const wild: EncounterProjection["wild"] = [];
  const sources: { group: EncounterGroup; row: EncounterRow }[] = [];
  for (const group of location.groups) {
    const kind = groupUnlock(group);
    if (kind === "sos") {
      sources.push(...group.encounters.map(row => ({ group, row })));
    } else if (kind !== "weather-sos") {
      for (const row of group.encounters) {
        const eligible = !!row.speciesId && directAccess(group, flags);
        wild.push({ group, row, eligible });
        if (eligible && row.allies.length) sources.push({ group, row });
      }
    }
  }
  const queue: EncounterRow[] = [];
  const reached = new Set<string>();
  const add = (row: EncounterRow) => {
    if (row.speciesId && !reached.has(encounterIdentity(row))) {
      reached.add(encounterIdentity(row));
      queue.push(row);
    }
  };
  for (const entry of wild) if (entry.eligible) add(entry.row);
  const native = new Set(reached);
  const calls: SosEncounter[] = [];
  const matched = new Set<EncounterRow>();
  if (flags.includes("sos")) {
    if (native.size && flags.includes("weather-sos")) {
      for (const group of location.groups) {
        if (groupUnlock(group) !== "weather-sos") continue;
        for (const sourceRow of group.encounters) {
          const targets: EncounterRow[] = sourceRow.speciesId ? [{ ...sourceRow, allies: [] }] : [];
          for (const ally of sourceRow.allies) targets.push(allyRow(sourceRow, ally));
          for (const row of targets) {
            calls.push({ kind: "weather-sos", group, sourceRow, caller: null, row });
            add(row);
          }
        }
      }
    }
    for (let index = 0; index < queue.length; index++) {
      const caller = queue[index];
      for (const source of sources) {
        const wildcard = !source.row.speciesId && source.row.speciesName === "All";
        // “All listed wild species” attaches to documented native callers; it cannot bootstrap itself.
        if (!(wildcard ? native.has(encounterIdentity(caller)) : sameCaller(source.row, caller))) continue;
        matched.add(source.row);
        const targets = new Set<string>();
        for (const ally of source.row.allies) {
          const row = allyRow(source.row, ally);
          const key = encounterIdentity(row);
          if (targets.has(key)) continue;
          targets.add(key);
          // An embedded rule belongs to that exact wild row/method. A standalone
          // caller table is location-wide and uses a reachable identity exemplar.
          const anchor = groupUnlock(source.group) === "sos" ? caller : source.row;
          calls.push({ kind: "sos", group: source.group, sourceRow: source.row, caller: anchor, row });
          add(row);
        }
      }
    }
  }
  return { wild, calls, unavailableCallers: sources.filter(source => groupUnlock(source.group) === "sos" && !matched.has(source.row)) };
}

/** Immutable species-level reachability; an owned Pokémon never grants access. */
export function eligibleRows(location: Location, unlocks: readonly string[], separateForms = false): EncounterRow[] {
  const projection = projectEncounters(location, unlocks);
  const rows = new Map<string, EncounterRow>();
  const add = (row: EncounterRow) => {
    if (!row.speciesId) return;
    const identity = separateForms && isRegional(row.speciesId)
      ? JSON.stringify([row.speciesId, encounterRegionalForm(row.speciesId, row.form) ?? row.form ?? ""]) : String(row.speciesId);
    if (!rows.has(identity)) rows.set(identity, row);
  };
  for (const entry of projection.wild) if (entry.eligible) add(entry.row);
  for (const call of projection.calls) add(call.row);
  return [...rows.values()];
}

export function occurrenceEligible(location: Location, group: EncounterGroup, row: EncounterRow, ally: boolean, flags: readonly string[]): boolean {
  const projection = projectEncounters(location, flags);
  const kind = groupUnlock(group);
  const sameSource = (entry: { group: EncounterGroup; sourceRow: EncounterRow }) =>
    entry.group.id === group.id && entry.sourceRow.id === row.id;
  if (kind === "sos" || kind === "weather-sos" || ally) {
    return projection.calls.some(sameSource);
  }
  return projection.wild.some(entry => entry.group.id === group.id && entry.row.id === row.id && entry.eligible);
}
