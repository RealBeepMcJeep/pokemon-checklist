import { byDex, detailsByDex, formDetails } from "../data";
import { isRegional, regionalDetails, type RegionalForm } from "../regional";
import { PokemonFacts, TypeMarks } from "./PokemonFacts";
import { CatchBadge } from "./CatchDifficulty";

/** Never substitute the opposite region's competitive facts for a missing form. */
export function CollectionFacts({ id, form, labels = false, onCatchInspect }: { id: number; form?: RegionalForm; labels?: boolean; onCatchInspect?: () => void }) {
  const actualForm = form ?? (isRegional(id) ? "alolan" : undefined);
  const native = actualForm ? regionalDetails(id, actualForm) : undefined;
  const competitive = actualForm ? formDetails.get(`${id}:${actualForm}`) ?? (actualForm === "kanto" ? detailsByDex.get(id) : undefined) : detailsByDex.get(id);
  const baseName = byDex.get(id)?.name ?? "Pokémon";
  const name = actualForm === "alolan" ? `${baseName}-Alola` : baseName;
  const facts = competitive ? <PokemonFacts details={{ ...competitive, types: native ? [...native.types] : competitive.types }} name={name} labels={labels} /> : native ? <TypeMarks types={[...native.types]} labels={labels} /> : null;
  return <span class="collection-facts">{facts}<CatchBadge id={id} form={actualForm} onInspect={onCatchInspect} /></span>;
}
