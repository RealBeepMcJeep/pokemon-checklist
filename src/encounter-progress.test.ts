import { expect, it } from "vitest";
import { locationSummary } from "./encounter-progress";
import type { EncounterRow, Location, Status } from "./types";

const caller: EncounterRow = { id: "native", speciesId: 52, form: "alolan", rates: { single: 15 }, allies: [] };
const rule: EncounterRow = { id: "sos", speciesId: 52, form: "alolan", rates: null,
  allies: [{ speciesId: 52, species: "meowth", name: "Meowth", form: "kanto" }] };
const location: Location = { id: "fixture", name: "Fixture", order: 1, groups: [
  { id: "grass", name: "Grass", category: "regular", encounters: [caller, { id: "other", speciesId: 81, rates: { single: 85 }, allies: [] }] },
  { id: "sos", name: "SOS Calls", category: "return-later", encounters: [rule, { ...rule, id: "duplicate" }] },
] };
const species = (): Status => "caught";
const forms = (key: string): Status => key === "52:alolan" ? "caught" : "none";

it("uses one target scope for missing regional allies, locked totals and backtrack", () => {
  expect(locationSummary(location, species, [], forms)).toEqual({
    progress: { none: 0, seen: 0, caught: 2, total: 2 }, locked: 1, backtrack: false, complete: true,
  });
  expect(locationSummary(location, species, ["sos"], forms)).toEqual({
    progress: { none: 1, seen: 0, caught: 2, total: 3 }, locked: 0, backtrack: true, complete: false,
  });
  expect(locationSummary(location, species, ["sos"])).toEqual({
    progress: { none: 0, seen: 0, caught: 2, total: 2 }, locked: 0, backtrack: false, complete: true,
  });
  expect(locationSummary(location, species, ["sos"], () => "caught")).toEqual({
    progress: { none: 0, seen: 0, caught: 3, total: 3 }, locked: 0, backtrack: false, complete: true,
  });
});

it("keeps weather visibility and completion dependent on both SOS switches", () => {
  const data: Location = { ...location, groups: [...location.groups,
    { id: "weather", name: "Weather SOS", category: "return-later", encounters: [
      { id: "rain", speciesId: 351, rates: { single: 11 }, conditions: ["Rain"], allies: [] },
    ] },
  ] };
  const status = (id: number): Status => id === 351 ? "none" : "caught";
  for (const flags of [[], ["weather-sos"]]) {
    const summary = locationSummary(data, status, flags, forms);
    expect(summary.progress.total).toBe(2);
    expect(summary.locked).toBe(2);
    expect(summary.complete).toBe(true);
  }
  expect(locationSummary(data, status, ["sos"], forms).progress.total).toBe(3);
  const both = locationSummary(data, status, ["sos", "weather-sos"], forms);
  expect(both.progress).toEqual({ none: 2, seen: 0, caught: 2, total: 4 });
  expect(both.locked).toBe(0);
  expect(both.backtrack).toBe(true);
});

it("does not reinterpret an unknown explicit encounter form as Alolan in locked totals", () => {
  const data: Location = { ...location, groups: [{ ...location.groups[0], encounters: [
    caller, { ...caller, id: "unknown-form", form: "unresolved" },
  ] }] };
  const summary = locationSummary(data, species, [], forms);
  expect(summary.progress.total).toBe(2);
  expect(summary.locked).toBe(0);
});
