import { normalize } from "../domain";
import type { PokemonDetails } from "../types";

export const TYPES = [
  "Normal",
  "Fire",
  "Water",
  "Electric",
  "Grass",
  "Ice",
  "Fighting",
  "Poison",
  "Ground",
  "Flying",
  "Psychic",
  "Bug",
  "Rock",
  "Ghost",
  "Dragon",
  "Dark",
  "Steel",
  "Fairy",
];

export function TypeMarks({
  types,
  labels = false,
}: {
  types: string[];
  labels?: boolean;
}) {
  return (
    <span
      class={`type-marks ${labels ? "type-labels" : ""}`}
      aria-label={`Types: ${types.join(" and ")}`}
    >
      {types.map((type) => (
        <span
          key={type}
          class={`type-mark type-${type.toLowerCase()}`}
          title={`${type} type`}
          aria-hidden="true"
        >
          {labels && type}
        </span>
      ))}
    </span>
  );
}

function GradeBadge({
  details,
  name,
}: {
  details: PokemonDetails;
  name: string;
}) {
  const inherited = !normalize(details.source).startsWith(normalize(name));
  const ownTier = inherited
    ? ` Without evolution inheritance, ${name}'s tier is ${details.ownTier}.`
    : "";
  const usage =
    details.usage === undefined
      ? ""
      : ` ${details.source} OU usage: ${details.usage < 0.01 ? details.usage.toFixed(5) : details.usage.toFixed(2)}% (November 2019, 1695 weighted).`;
  const title = `${details.grade} grade. ${inherited ? `Inherited from ${details.source}, ` : ""}based on Smogon Gen VII tier ${details.tier}.${ownTier}${usage}`;
  return (
    <span
      class={`grade-badge grade-${details.grade.toLowerCase()}`}
      title={title}
      aria-label={title}
    >
      {details.grade}
    </span>
  );
}

export function PokemonFacts({
  details,
  name,
  labels = false,
}: {
  details: PokemonDetails;
  name: string;
  labels?: boolean;
}) {
  return (
    <span class={`pokemon-facts ${labels ? "pokemon-facts-expanded" : ""}`}>
      <TypeMarks types={details.types} labels={labels} />
      <GradeBadge details={details} name={name} />
    </span>
  );
}
