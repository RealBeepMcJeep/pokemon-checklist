import { formSlug, titleForm } from "./domain";
import { encounterRegionalForm } from "./regional";
import type { EncounterRow } from "./types";

type NamedEncounter = Pick<EncounterRow, "speciesId" | "speciesName" | "species" | "form" | "forms">;

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
  if (!row.form) return name;
  const suffix = ` (${titleForm(row.form)})`;
  return name.endsWith(suffix) ? name : `${name}${suffix}`;
}
