import { describe, expect, it } from "vitest";
import { ENCOUNTERS_BY_MODE } from "./data";
import * as eligibility from "./unlocks";
import type { EncounterGroup, EncounterRow, Location } from "./types";

const row = (id: string, speciesId: number | null, allies: number[] = []): EncounterRow => ({
  id, speciesId, speciesName: speciesId ? String(speciesId) : "All",
  rates: speciesId ? { single: 15 } : null,
  allies: allies.map(speciesId => ({ speciesId, species: String(speciesId), name: String(speciesId) })),
});
const group = (id: string, name: string, encounters: EncounterRow[], regular = false): EncounterGroup => ({
  id, name, encounters, category: regular ? "regular" : "return-later",
});
const location = (...groups: EncounterGroup[]): Location => ({ id: "fixture", name: "Fixture", order: 1, groups });

const project = eligibility.projectEncounters;

describe("source-preserving SOS projection", () => {
  it("keeps row-inline allies anchored to their documented wild method", () => {
    const grass = row("grass-caller", 10);
    const water = row("water-caller", 10, [20]);
    const loc = location(group("grass", "Grass", [grass], true), group("water", "Surfing", [water]));
    expect(project(loc, ["sos"]).calls).toEqual([]);
    expect(project(loc, ["sos", "surfing"]).calls.map(call => [call.caller?.id, call.group.id])).toEqual([["water-caller", "water"]]);
  });
  it("does not bootstrap disconnected cycles, wildcard rules or weather without wild access", () => {
    const calls = group("calls", "SOS Calls", [row("first", 10, [20]), row("second", 20, [10]), row("all", null, [30])]);
    const loc = location(calls, group("weather", "Weather SOS", [row("weather-only", 40)]));
    const result = project(loc, ["sos", "weather-sos"]);
    expect(result.calls).toEqual([]);
    expect(result.unavailableCallers.map(source => source.row.id)).toEqual(["first", "second", "all"]);
    expect(eligibility.eligibleRows(loc, ["sos", "weather-sos"])).toEqual([]);
  });
  it("retains distinct explicit seasonal allies without promoting legacy form lists to wild targets", () => {
    const caller = { ...row("native", 585), forms: ["spring", "summer", "autumn", "winter"] };
    const rule = row("rule", 585);
    rule.allies = ["autumn", "winter"].map(form => ({ speciesId: 585, species: "deerling", name: "Deerling", form }));
    const loc = location(group("grass", "Grass", [caller], true), group("calls", "SOS Calls", [rule]));
    const result = project(loc, ["sos"]);
    expect(result.wild.map(entry => entry.row.form)).toEqual([undefined]);
    expect(result.calls.map(call => call.row.form)).toEqual(["autumn", "winter"]);
    expect(result.calls.every(call => call.caller?.id === "native")).toBe(true);
  });
  it("never borrows a native Alolan rule for an unknown explicit regional token", () => {
    const caller = { ...row("native", 52), form: "unverified-form" };
    const loc = location(group("grass", "Grass", [caller], true), group("calls", "SOS Calls", [row("rule", 52, [25])]));
    expect(project(loc, ["sos"]).calls).toEqual([]);
    expect(eligibility.eligibleRows(loc, ["sos"]).map(r => r.speciesId)).toEqual([52]);
  });
  it("keeps an unresolved creator caller as unavailable source evidence, not a fabricated encounter", () => {
    const loc = ENCOUNTERS_BY_MODE["photonic-prismatic"].islands.flatMap(i => i.locations).find(l => l.id === "ulaula-island/route-15-16")!;
    const result = project(loc, ["tauros", "surfing", "fishing", "sos", "weather-sos"]);
    const missing = result.unavailableCallers.find(source => source.row.speciesId === 739);
    expect(missing?.row.note).toContain("Caller availability is unverified");
    expect(result.calls.some(call => call.row.speciesId === 740)).toBe(false);
    expect(result.wild.some(entry => entry.row.speciesId === 739)).toBe(false);
  });
  it("keeps ability-scoped callers distinct without creating extra regional collection targets", () => {
    const first = { ...row("first", 52), ability: "first-ability" };
    const second = { ...row("second", 52), ability: "second-ability" };
    const rule = { ...row("rule", 52, [25]), ability: "second-ability" };
    const calls = group("calls", "SOS Calls", [rule]);
    expect(project(location(group("grass", "Grass", [first], true), calls), ["sos"]).calls).toEqual([]);
    const loc = location(group("grass", "Grass", [first, second], true), calls);
    expect(project(loc, ["sos"]).calls.map(call => call.caller?.id)).toEqual(["second"]);
    expect(eligibility.eligibleRows(loc, ["sos"], true).filter(r => r.speciesId === 52)).toHaveLength(1);
  });
  it("uses the same caller graph for occurrence availability, not species-only reachability", () => {
    const native = row("native", 52);
    const kanto = row("kanto-rule", 52, [25]);
    kanto.form = "kanto";
    const wildcard = row("all", null, [20]);
    const calls = group("calls", "SOS Calls", [kanto, wildcard]);
    const loc = location(group("grass", "Grass", [native], true), calls);
    expect(eligibility.occurrenceEligible(loc, calls, kanto, false, ["sos"])).toBe(false);
    expect(eligibility.occurrenceEligible(loc, calls, wildcard, false, ["sos"])).toBe(true);
    expect(eligibility.occurrenceEligible(loc, calls, wildcard, true, [])).toBe(false);
  });
  it("makes Haina's documented ordinary wildcard targets eligible without enabling weather SOS", () => {
    const haina = ENCOUNTERS_BY_MODE["photonic-prismatic"].islands.flatMap(i => i.locations).find(l => l.id === "ulaula-island/haina-desert")!;
    expect(haina).toBeDefined();
    const off = eligibility.eligibleRows(haina, []).map(r => r.speciesId);
    expect(off).not.toContain(344);
    expect(off).not.toContain(623);
    const on = eligibility.eligibleRows(haina, ["sos"]);
    expect(on.map(r => r.speciesId)).toEqual(expect.arrayContaining([344, 623]));
    expect(on.filter(r => r.speciesId === 344 || r.speciesId === 623).map(r => r.rates)).toEqual([null, null]);
    expect(on.map(r => r.speciesId)).not.toContain(351);
  });
  it("traverses exact regional callers before collapsing collection targets", () => {
    const native = row("native", 52);
    const alolan = row("alolan-rule", 52);
    alolan.allies = [{ speciesId: 52, species: "meowth", name: "Meowth", form: "kanto" }];
    const kanto = row("kanto-rule", 52, [25]);
    kanto.form = "kanto";
    // Explicit reverse edge exercises cycle termination without suppressing other targets.
    kanto.allies.push({ speciesId: 52, species: "meowth", name: "Meowth", form: "alolan" });
    const unreachable = location(group("grass", "Grass", [native], true), group("calls", "SOS Calls", [kanto]));
    expect(eligibility.eligibleRows(unreachable, ["sos"]).map(r => r.speciesId)).toEqual([52]);
    const loc = location(group("grass", "Grass", [native], true), group("calls", "SOS Calls", [alolan, kanto]));
    expect(eligibility.eligibleRows(loc, ["sos"]).map(r => r.speciesId)).toEqual([52, 25]);
    expect(eligibility.eligibleRows(loc, ["sos"], true).map(r => [r.speciesId, r.form])).toEqual([
      [52, undefined], [52, "kanto"], [25, undefined],
    ]);
    expect(project(loc, ["sos"]).calls).toHaveLength(3);
  });
  it("preserves documented weather rates and unlocks their ordinary call chains only with real wild access", () => {
    const weather = row("weather-target", 20);
    weather.rates = { single: 11 };
    weather.conditions = ["Rain"];
    weather.note = "Guide-reported SOS encounter rate";
    const loc = location(
      group("water", "Surfing", [row("surf", 10)]),
      group("weather", "Weather SOS", [weather]),
      group("chain", "SOS Calls", [row("chain-caller", 20, [21])]),
    );
    for (const flags of [["sos", "weather-sos"], ["surfing", "weather-sos"], ["surfing", "sos"]]) {
      expect(project(loc, flags).calls).toEqual([]);
    }
    expect(project(loc, ["surfing", "sos", "weather-sos"]).calls.map(call => [
      call.kind, call.row.speciesId, call.row.rates, call.caller?.speciesId ?? null, call.sourceRow.conditions,
    ])).toEqual([
      ["weather-sos", 20, { single: 11 }, null, ["Rain"]],
      ["sos", 21, null, 20, undefined],
    ]);
    expect(weather.note).toBe("Guide-reported SOS encounter rate");
  });
  it("anchors an ordinary wildcard ally to a real caller without borrowing its wild rate", () => {
    const caller = row("wild", 10);
    const rule = row("all", null, [20]);
    rule.conditions = ["Documented caller condition"];
    const calls = group("calls", "SOS Calls", [rule]);
    calls.notes = ["Retained source note"];
    const loc = location(group("grass", "Grass", [caller], true), calls);
    const before = structuredClone(loc);
    const result = project(loc, ["sos"]);
    expect(result.calls.map(call => [
      call.caller?.id, call.row.speciesId, call.row.rates, call.sourceRow.id,
      call.sourceRow.conditions, call.group.notes,
    ])).toEqual([["wild", 20, null, "all", ["Documented caller condition"], ["Retained source note"]]]);
    expect(loc).toEqual(before);
  });
});
