import { formKey, normalize } from "./domain";
import { isRegional, type RegionalForm } from "./regional";
import type { Pokemon } from "./types";

export interface CollectionTarget { id: number; form?: RegionalForm }
export const targetKey = (target: CollectionTarget): string => target.form ? formKey(target.id, "form", target.form) : String(target.id);
export const targetName = (pokemon: Pokemon, form?: RegionalForm): string => form ? `${pokemon.name} (${form === "alolan" ? "Alolan" : "Kanto"})` : pokemon.name;

export function collectionTargets(pokemon: readonly Pokemon[], tracking: boolean): CollectionTarget[] {
  return pokemon.flatMap(({ id }) => tracking && isRegional(id)
    ? [{ id, form: "alolan" as const }, { id, form: "kanto" as const }]
    : [{ id }]);
}

export function matchesTarget(pokemon: Pokemon, target: CollectionTarget, query: string): boolean {
  const needle = normalize(query);
  return !needle || normalize(targetName(pokemon, target.form)).includes(needle)
    || (target.form !== undefined && normalize(`${target.form === "alolan" ? "Alolan" : "Kanto"} ${pokemon.name}`).includes(needle))
    || String(pokemon.id).padStart(3, "0").includes(needle);
}
