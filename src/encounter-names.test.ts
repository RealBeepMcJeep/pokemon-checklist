import { describe, expect, it } from "vitest";
import * as Names from "./encounter-names";
import type { EncounterRow } from "./types";

function label(row: Partial<EncounterRow>, canonical?: string): string {
  const format = Reflect.get(Names, "encounterName");
  expect(typeof format).toBe("function");
  return format(row, canonical);
}

describe("source encounter names, independent of collection presentation", () => {
  it("names documented flower forms rather than leaving identical bare names", () => {
    expect(label({ speciesId: 670, speciesName: "Floette", form: "eternal-flower" })).toBe("Floette (Eternal Flower)");
  });
  it("uses native Alolan identity for an unmarked regional encounter", () => {
    expect(label({ speciesId: 52, speciesName: "Meowth" }, "Meowth")).toBe("Meowth (Alolan)");
    expect(label({ speciesId: 52, speciesName: "Meowth", form: "kanto" }, "Meowth")).toBe("Meowth (Kanto)");
  });
  it("keeps non-regional forms readable without enabling their tracking", () => {
    expect(label({ speciesId: 479, speciesName: "Rotom", form: "heat" })).toBe("Rotom (Heat)");
    expect(label({ speciesId: 745, speciesName: "Lycanroc", form: "midnight" })).toBe("Lycanroc (Midnight)");
    expect(label({ speciesId: 710, speciesName: "Pumpkaboo", form: "super-size" })).toBe("Pumpkaboo (Super Size)");
  });
  it("does not replay a known suffix or strip an explicit source qualifier", () => {
    expect(label({ speciesId: 479, speciesName: "Rotom (Heat)", form: "heat" })).toBe("Rotom (Heat)");
    expect(label({ speciesId: 658, speciesName: "Greninja (Battle Bond)" })).toBe("Greninja (Battle Bond)");
  });
  it("does not promote legacy mixed wild/SOS form lists into native identities", () => {
    const row = { speciesId: 585, speciesName: "Deerling", forms: ["spring", "summer", "autumn", "winter"] };
    expect(label(row)).toBe("Deerling");
    expect(row.forms).toEqual(["spring", "summer", "autumn", "winter"]);
  });
  it("retains source-only labels and safe fallbacks without making up a form", () => {
    expect(label({ speciesName: "All listed wild species" })).toBe("All listed wild species");
    expect(label({ speciesId: 25 }, "Pikachu")).toBe("Pikachu");
  });
});
