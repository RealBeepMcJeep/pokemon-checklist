// Gen VII regional species at the pinned Showdown revision. Pikachu's Alola cap
// is deliberately excluded: it is not the Kanto/Alolan regional pair feature.
export const REGIONAL_IDS: readonly number[] = [
  19, 20, 26, 27, 28, 37, 38, 50, 51, 52, 53, 74, 75, 76, 88, 89, 103, 105,
];
export type RegionalForm = "alolan" | "kanto";
export const isRegional = (id: number): boolean => REGIONAL_IDS.includes(id);
