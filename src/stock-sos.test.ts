import { expect, it } from "vitest";
import { guideEncounters, projectEncounters } from "./unlocks";
import { getOccurrences } from "./domain";
import type { EncounterData, GameMode } from "./types";
import type { EncounterGroup, EncounterRow, Location } from "./types";

const row = (id: string, speciesId: number): EncounterRow => ({
  id, speciesId, speciesName: String(speciesId), rates: { single: 15 }, allies: [],
});
const group = (id: string, name: string, encounters: EncounterRow[], regular = false): EncounterGroup => ({
  id, name, encounters, category: regular ? "regular" : "return-later",
});
const location = (...groups: EncounterGroup[]): Location => ({ id: "fixture", name: "Fixture", order: 1, groups });

it("uses stock method provenance for bubbling fishing versus Poni rustling access", () => {
  const fishing = Object.assign(group("bubbles", "Bubbling / rustling spots", [row("dratini", 147)]),
    { encounterType: "wild", sourceArea: { location: "poni-meadow", area: "main", method: "bubbling-spots" } });
  const bushes = Object.assign(group("bushes", "Bubbling / rustling spots", [row("chansey", 113)]),
    { encounterType: "wild", sourceArea: { location: "poni-plains", area: "center-rustling-bush", method: "bubbling-spots" } });
  const target = Object.assign(row("blissey", 242), { sosRules: [{ kind: "sos" as const, callerIds: ["chansey"] }] });
  const grass = Object.assign(group("rustling-grass", "Bubbling / rustling spots", [row("tauros", 128)]),
    { encounterType: "wild", sourceArea: { location: "poni-plains", area: "center-grass", method: "bubbling-spots" } });
  const place = location(fishing, bushes, grass, group("sos", "SOS allies", [target]));
  const before = structuredClone(place);
  expect(projectEncounters(place, ["sos"]).wild.filter(entry => entry.eligible).map(entry => entry.row.id)).toEqual(["chansey", "tauros"]);
  expect(projectEncounters(place, ["sos"]).calls.map(call => call.row.id)).toEqual(["blissey"]);
  expect(projectEncounters(place, ["sos", "fishing"]).wild.every(entry => entry.eligible)).toBe(true);
  expect(place).toEqual(before);
});

it.each(["sun", "moon", "ultra-sun", "ultra-moon"] as GameMode[])("uses the same exact caller and unresolved-source navigation for %s details", mode => {
  const native = row("native-metapod", 11);
  const target = Object.assign(row("leaf-caterpie", 10), { sosRules: [{ kind: "sos" as const, callerIds: [native.id] }] });
  const unknown = Object.assign(row("unverified-sableye", 302), { sosRules: [] });
  const place = location(group("grass", "Grass", [native], true), group("sos", "SOS allies", [target, unknown]));
  const data: EncounterData = { schemaVersion: 1, assets: [], mode, islands: [{ id: "island", name: "Island", locations: [place] }] };
  const before = structuredClone(data);
  for (const flags of [[], ["sos"]]) {
    const occurrences = getOccurrences(data, 10, flags);
    expect(occurrences).toHaveLength(1);
    expect(occurrences[0].row.id).toBe(native.id);
    expect(occurrences[0].row.rates).toEqual({ single: 15 });
    expect(occurrences[0].ally).toBe(true);
    expect(occurrences[0].eligible).toBe(flags.includes("sos"));
    const unavailable = getOccurrences(data, 302, flags);
    expect(unavailable).toHaveLength(1);
    expect(unavailable[0].row.id).toBe(unknown.id);
    expect(unavailable[0].eligible).toBe(false);
  }
  expect(data).toEqual(before);
});

it("retains native method scope through explicit chained leaves and terminates cycles", () => {
  const mid = Object.assign(row("mid", 20), { sosRules: [{ kind: "sos" as const, callerIds: ["grass", "cave", "last"] }] });
  const last = Object.assign(row("last", 30), { callerGroups: ["cave-method"],
    sosRules: [{ kind: "sos" as const, callerIds: ["mid"] }] });
  const data = location(group("grass-method", "Grass", [row("grass", 10)], true),
    group("cave-method", "Surfing", [row("cave", 10)]), group("sos", "SOS allies", [mid, last]));
  expect(projectEncounters(data, ["sos"]).calls.filter(call => call.row.speciesId === 30)).toEqual([]);
  const calls = projectEncounters(data, ["sos", "surfing"]).calls.filter(call => call.row.speciesId === 30);
  expect(calls).toHaveLength(1);
  expect(calls[0].originGroupId).toBe("cave-method");
  expect(guideEncounters(data, ["sos", "surfing"])[0].sos[0].children).toEqual([]);
});

it("does not collapse exact stock callers that share species across different native methods", () => {
  const target = Object.assign(row("caterpie", 10), { sosRules: [{ kind: "sos" as const, callerIds: ["cave-metapod"] }] });
  const data = location(group("grass", "Grass", [row("grass-metapod", 11)], true),
    group("cave", "Cave", [row("cave-metapod", 11)], true), group("sos", "SOS allies", [target]));
  const calls = projectEncounters(data, ["sos"]).calls;
  expect(calls.map(call => [call.caller?.id, call.originGroupId])).toEqual([["cave-metapod", "cave"]]);
  const guide = guideEncounters(data, ["sos"]);
  expect(guide[0].sos).toEqual([]);
  expect(guide[1].sos).toHaveLength(1);
});

it.each(["SOS allies", "Weather SOS"])("keeps explicit weather callers/rates conditional in %s", name => {
  const target = Object.assign(row("castform", 351), { sosRules: [{
    kind: "weather-sos" as const, callerIds: ["caller"], conditions: ["During hail"], rates: { single: 11 },
  }] });
  const data = location(group("native", "Grass", [row("caller", 11)], true),
    group("other", "Grass", [row("not-a-caller", 10)], true), group("sos", name, [target]));
  expect(projectEncounters(data, ["sos"]).calls).toEqual([]);
  expect(projectEncounters(data, ["weather-sos"]).calls).toEqual([]);
  const calls = projectEncounters(data, ["sos", "weather-sos"]).calls;
  expect(calls).toHaveLength(1);
  expect(calls[0].caller?.id).toBe("caller");
  expect(calls[0].kind).toBe("weather-sos");
  expect(calls[0].row.rates).toEqual({ single: 11 });
  const guide = guideEncounters(data, ["sos", "weather-sos"]);
  expect(guide[0].sos).toHaveLength(1);
  expect(guide[1].sos).toEqual([]);
});

it("projects a stock ally leaf from its explicit caller ID, retaining the original source ID and wild rate", () => {
  // Stock SM Route 1 exception: Metapod calls Caterpie, not an inferred reverse edge.
  const target = Object.assign(row("stock-caterpie", 10), { sosRules: [{
    kind: "sos" as const, callerIds: ["metapod"], conditions: ["Only on Route 1"],
  }] });
  const data = location(group("grass", "Grass", [row("metapod", 11), row("other-method", 11)], true),
    group("sos", "SOS allies", [target]));
  const before = structuredClone(data);
  const calls = projectEncounters(data, ["sos"]).calls;
  expect(calls).toHaveLength(1);
  expect(calls[0].caller?.id).toBe("metapod");
  expect(calls[0].row.id).toBe("stock-caterpie");
  expect(calls[0].row.speciesId).toBe(10);
  expect(calls[0].row.rates).toBeNull();
  expect(calls[0].sourceRow.conditions).toContain("Only on Route 1");
  expect(projectEncounters(data, []).calls).toEqual([]);
  expect(data).toEqual(before);
  const guide = guideEncounters(data, ["sos"]);
  expect(guide[0].sos.map(node => node.call.row.speciesId)).toEqual([10]);
  expect(guide[1].sos).toEqual([]);
});
