import { describe, expect, it } from "vitest";
import { ENCOUNTERS_BY_MODE, POKEMON, detailsByDex, formDetails } from "./data";
import {
  DEFAULT_MODE,
  buildFormDefinitions,
  canonicalState,
  catchNowRows,
  cycleStatus,
  firstIncompleteLocation,
  getOccurrences,
  validateState,
} from "./domain";
import type { Status } from "./types";

const forms = buildFormDefinitions(ENCOUNTERS_BY_MODE);
const pokemonIds = new Set(POKEMON.map(({ id }) => id));
const formKeys = new Set(forms.keys());

describe("checklist domain", () => {
  it("cycles statuses in the documented order", () => {
    expect(cycleStatus("none")).toBe("caught");
    expect(cycleStatus("caught")).toBe("seen");
    expect(cycleStatus("seen")).toBe("none");
  });

  it("migrates v1 saves without changing progress", () => {
    expect(
      validateState(
        {
          schemaVersion: 1,
          species: { 25: "seen" },
          forms: {},
          settings: { forms: true },
        },
        pokemonIds,
        formKeys,
      ),
    ).toEqual({
      schemaVersion: 2,
      species: { 25: "seen" },
      forms: {},
      settings: { forms: true, mode: DEFAULT_MODE },
    });
  });

  it("rejects unknown Pokémon before mutating state", () => {
    expect(() =>
      validateState(
        {
          schemaVersion: 2,
          species: { 808: "caught" },
          forms: {},
          settings: { forms: false, mode: DEFAULT_MODE },
        },
        pokemonIds,
        formKeys,
      ),
    ).toThrow("Unknown Pokémon number");
  });

  it("exports statuses deterministically", () => {
    expect(
      canonicalState({
        schemaVersion: 2,
        species: { 807: "seen", 1: "caught", 25: "none" },
        forms: { "20:alolan": "seen", "19:alolan": "caught" },
        settings: { forms: false, mode: "ultra-moon" },
      }),
    ).toEqual({
      schemaVersion: 2,
      species: { 1: "caught", 807: "seen" },
      forms: { "19:alolan": "caught", "20:alolan": "seen" },
      settings: { forms: false, mode: "ultra-moon" },
    });
  });

  it("advances after every unique regular encounter is caught", () => {
    const encounters = ENCOUNTERS_BY_MODE[DEFAULT_MODE];
    const first = firstIncompleteLocation(encounters, () => "none");
    expect(first?.id).toBe("melemele-island/route-1");
    expect(catchNowRows(first!).length).toBe(23);
    const caught = new Set(
      catchNowRows(first!).map(({ speciesId }) => speciesId),
    );
    const status = (id: number): Status => (caught.has(id) ? "caught" : "none");
    expect(firstIncompleteLocation(encounters, status)?.id).not.toBe(first?.id);
  });

  it("classifies direct and SOS occurrence links", () => {
    const encounters = ENCOUNTERS_BY_MODE[DEFAULT_MODE];
    expect(getOccurrences(encounters, 731).some(({ ally }) => !ally)).toBe(
      true,
    );
    expect(getOccurrences(encounters, 440).some(({ ally }) => ally)).toBe(true);
  });

  it("uses final evolutions for grades and keeps form details separate", () => {
    expect(detailsByDex.get(1)).toMatchObject({
      types: ["Grass", "Poison"],
      grade: "B",
      source: "Venusaur",
      tier: "RU",
      ownTier: "LC",
    });
    expect(formDetails.get("37:alolan")).toMatchObject({
      types: ["Ice"],
      grade: "S",
      source: "Ninetales-Alola",
    });
  });

  it("indexes forms once across all five modes", () => {
    expect(forms.get("19:alolan")?.label).toBe("Alolan");
    expect(forms.size).toBeGreaterThan(20);
  });
});
