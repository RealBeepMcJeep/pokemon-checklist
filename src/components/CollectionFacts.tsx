import { byDex, detailsByDex, formDetails } from "../data";
import { isRegional, regionalDetails, type RegionalForm } from "../regional";
import { PokemonFacts, TypeMarks } from "./PokemonFacts";

/** Never substitute the opposite region's competitive facts for a missing form. */
export function CollectionFacts({ id, form, labels = false }: { id: number; form?: RegionalForm; labels?: boolean }) {
  const actualForm = form ?? (isRegional(id) ? "alolan" : undefined);
  const native = actualForm ? regionalDetails(id, actualForm) : undefined;
  const competitive = actualForm ? formDetails.get(`${id}:${actualForm}`) ?? (actualForm === "kanto" ? detailsByDex.get(id) : undefined) : detailsByDex.get(id);
  const baseName = byDex.get(id)?.name ?? "Pokémon";
  const name = actualForm === "alolan" ? `${baseName}-Alola` : baseName;
  if (competitive) return <PokemonFacts details={{ ...competitive, types: native ? [...native.types] : competitive.types }} name={name} labels={labels} />;
  return native ? <TypeMarks types={[...native.types]} labels={labels} /> : null;
}
