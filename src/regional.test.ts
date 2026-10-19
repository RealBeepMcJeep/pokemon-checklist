import { describe, expect, it } from "vitest";
import { buildFormDefinitions, locationProgress, uncaughtCatchNowRows, validateState } from "./domain";
import { GAME_MODES, type EncounterData, type GameMode, type Location } from "./types";
import { entriesFromState, stateFromDocument } from "./sync/records";

describe("regional collection catalogue", () => {
  it("includes regular and Alolan evolution-only targets even without any wild encounter", () => {
    const empty: EncounterData = { schemaVersion: 1, assets: [], islands: [] };
    const modes = Object.fromEntries(GAME_MODES.map(mode => [mode, empty])) as Record<GameMode, EncounterData>;
    const forms = buildFormDefinitions(modes);
    expect(forms.get("53:kanto")).toMatchObject({ speciesId: 53, label: "Kanto" });
    expect(forms.get("53:alolan")).toMatchObject({ speciesId: 53, label: "Alolan" });
    expect(forms.has("103:kanto")).toBe(true);
    expect(forms.has("25:alolan")).toBe(false);
  });
});

describe("regional encounter progress", () => {
  const school: Location = { id: "school", name: "School", order: 1, groups: [{
    id: "grass", name: "Grass", category: "regular", encounters: [{
      id: "meowth", speciesId: 52, speciesName: "Meowth", form: "alolan", rates: { single: 15 },
      allies: [{ speciesId: 52, species: "meowth", name: "Meowth", form: "kanto" }],
    }],
  }] };
  it("keeps the missing regular SOS form eligible after its Alolan caller is caught", () => {
    const species = () => "caught" as const;
    const forms = (key: string) => key === "52:alolan" ? "caught" as const : "none" as const;
    expect(locationProgress(school, species, ["sos"], forms)).toEqual({ none: 1, seen: 0, caught: 1, total: 2 });
    expect(uncaughtCatchNowRows(school, species, ["sos"], forms).map(row => row.form)).toEqual(["kanto"]);
    expect(locationProgress(school, species, [], forms).total).toBe(1);
    expect(locationProgress(school, species, ["sos"]).total).toBe(1);
  });
});

describe("regional favorite migration", () => {
  it("migrates a legacy species favorite to its sole owned regional form without favoriting its counterpart", () => {
    const result = validateState({ schemaVersion: 4, species: { "52": "caught" },
      forms: { "52:alolan": "caught" }, starred: [52],
      settings: { forms: true, mode: "photonic-prismatic", unlocks: [] },
    }, new Set([52]), new Set(["52:alolan", "52:kanto"]));
    expect(result).toMatchObject({ schemaVersion: 5, starred: [], starredForms: ["52:alolan"] });
    expect(result.forms).toEqual({ "52:alolan": "caught" });
  });
  it("round-trips an independent favorite and does not revive it from its stale species bridge after clearing", () => {
    const ids = new Set([52]);
    const forms = new Set(["52:alolan", "52:kanto"]);
    const save = validateState({ schemaVersion: 4, species: { "52": "caught" },
      forms: { "52:alolan": "caught" }, starred: [52],
      settings: { forms: true, mode: "photonic-prismatic", unlocks: [] },
    }, ids, forms);
    const records = entriesFromState(save, 1, "test");
    expect(records["starform:52:alolan"]?.s).toBe("on");
    expect(records["star:52"]?.s).toBe("on"); // Compatibility for existing species-only readers.
    expect(stateFromDocument({ schema: 1, records, updatedAt: 1 }, ids, forms)).toEqual(save);
    records["starform:52:alolan"] = { s: "off", at: 2, by: "test" };
    expect(stateFromDocument({ schema: 1, records, updatedAt: 2 }, ids, forms)).toMatchObject({ starred: [], starredForms: [] });
  });
});
