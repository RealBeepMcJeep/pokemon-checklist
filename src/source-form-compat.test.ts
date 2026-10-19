import { expect, it } from "vitest";
import { ENCOUNTERS_BY_MODE, POKEMON } from "./data";
import { buildFormDefinitions, STATE_VERSION, STORAGE_KEY, validateState } from "./domain";

it("source-label normalization preserves form definitions and imports v4 records into v5", () => {
  const legacy = structuredClone(ENCOUNTERS_BY_MODE);
  for (const island of legacy["photonic-prismatic"].islands) for (const loc of island.locations) for (const group of loc.groups) for (const row of group.encounters) {
    if (row.id === "akala-island/route-6/grass-1-1/4") row.forms = ["spring", "summer", "autumn", "winter"];
    if (row.id === "akala-island/route-6/grass-2-2/5") delete row.forms;
    if (row.id === "akala-island/route-6/sos-calls-3/1") for (const ally of row.allies) delete ally.form;
    if (row.id === "ulaula-island/thrifty-megamart/building-1/5") {
      delete row.form;
      row.forms = ["base", "heat", "frost"];
      row.allies = [{ species: "rotom", name: "Rotom", speciesId: 479 }];
    }
    if (row.id === "ulaula-island/ulaula-meadow/grass-1/2") {
      delete row.form;
      row.forms = ["red-flower", "orange-flower", "white-flower"];
      row.allies = [];
    }
  }
  const before = buildFormDefinitions(legacy);
  const after = buildFormDefinitions(ENCOUNTERS_BY_MODE);
  const entries = (value: typeof before) => [...value.entries()].sort(([a], [b]) => a.localeCompare(b));
  expect(entries(after)).toEqual(entries(before));
  expect(STATE_VERSION).toBe(5);
  expect(STORAGE_KEY).toBe("pokemon-checklist-state-v5");
  // Synthetic exhaustive old-key backup, not an account snapshot.
  const backup = {
    schemaVersion: 4, species: { 479: "caught", 585: "seen", 670: "caught" },
    forms: Object.fromEntries([...before.keys()].map(key => [key, "caught"])),
    starred: [479, 585, 670], settings: { forms: false, mode: "photonic-prismatic", unlocks: ["sos"] },
  };
  expect(validateState(backup, new Set(POKEMON.map(p => p.id)), new Set(after.keys()))).toEqual({ ...backup, schemaVersion: 5, starredForms: [] });
});
