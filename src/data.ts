import pokemonJson from "../data/pokemon.json";
import prismaticJson from "../data/encounters.json";
import sunJson from "../data/encounters-sun.json";
import moonJson from "../data/encounters-moon.json";
import ultraSunJson from "../data/encounters-ultra-sun.json";
import ultraMoonJson from "../data/encounters-ultra-moon.json";
import atlasUrl from "../assets/gen7-icons.png?url";
import type { EncounterData, GameMode, Pokemon } from "./types";

export const POKEMON = pokemonJson as Pokemon[];
export const ENCOUNTERS_BY_MODE = {
  "photonic-prismatic": prismaticJson as EncounterData,
  sun: sunJson as EncounterData,
  moon: moonJson as EncounterData,
  "ultra-sun": ultraSunJson as EncounterData,
  "ultra-moon": ultraMoonJson as EncounterData,
} satisfies Record<GameMode, EncounterData>;

const imageModules = import.meta.glob<string>(
  "../assets/locations/*.{png,jpg,jpeg}",
  { eager: true, query: "?url", import: "default" },
);

export const ASSETS = Object.fromEntries(
  Object.entries(imageModules).map(([path, url]) => [path.slice(3), url]),
) as Record<string, string>;

export const ATLAS = {
  url: atlasUrl,
  width: 1280,
  height: 780,
  columns: 32,
  frameWidth: 40,
  frameHeight: 30,
} as const;

export const byDex = new Map(POKEMON.map((pokemon) => [pokemon.id, pokemon]));
