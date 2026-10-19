import { formKey, formSlug, normalize, titleForm } from "./domain";
import { encounterRegionalForm } from "./regional";
import type { EncounterRow } from "./types";

type NamedEncounter = Pick<EncounterRow, "speciesId" | "speciesName" | "species" | "form" | "forms" | "ability">;

/** Ephemeral acquisition context: never a new collection target or save field. */
export interface EncounterViewContext { id: number; name: string; detailKey?: string }
export function encounterViewContext(row: NamedEncounter, canonicalName: string): EncounterViewContext | undefined {
  if (!row.speciesId) return undefined;
  const name = encounterName(row, canonicalName);
  if (!row.form && !row.ability && normalize(name) === normalize(canonicalName)) return undefined;
  const form = row.form ?? encounterRegionalForm(row.speciesId);
  const detailKey = form ? formKey(row.speciesId, "form", formSlug(form))
    : row.ability ? formKey(row.speciesId, "ability", formSlug(row.ability)) : undefined;
  return { id: row.speciesId, name, ...(detailKey ? { detailKey } : {}) };
}

/** Acquisition identity is not the collection-view preference. Never infer a
 * native form from legacy `forms`: those lists also include SOS-only variants. */
export function encounterName(row: NamedEncounter, canonicalName?: string): string {
  const name = row.speciesName || canonicalName || row.species || "Pokémon";
  const regional = row.speciesId ? encounterRegionalForm(row.speciesId, row.form ? formSlug(row.form) : undefined) : undefined;
  if (regional) {
    const label = regional === "alolan" ? "Alolan" : "Kanto";
    const base = canonicalName || name;
    return base.endsWith(` (${label})`) ? base : `${base} (${label})`;
  }
  const suffix = row.form ? ` (${titleForm(row.form)})` : row.ability ? ` (${row.ability})` : "";
  if (!suffix) return name;
  return name.endsWith(suffix) ? name : `${name}${suffix}`;
}
