import { describe, expect, it } from "vitest";
import { heldSummary, isWholeAccountClear, pendingEntries, localIntentChanges } from "./sync/outbox";
import { entriesFromState, mergeDocument, rebaseState, stateFromDocument, type SyncDocument } from "./sync/records";
import { validateState } from "./domain";
import type { SavedState } from "./types";

const entry = (s: string) => ({ s, at: 1, by: "fixture" });
describe("regional sync safety", () => {
  it("preserves an explicitly restored unresolved favorite through actual wire reload", () => {
    const ids = new Set([52]), forms = new Set(["52:alolan", "52:kanto"]);
    const legacy = validateState({ schemaVersion: 5, species: { "52": "caught" }, forms: { "52:alolan": "caught", "52:kanto": "caught" }, starred: [52], starredForms: [], settings: { forms: true, mode: "moon", unlocks: [] } }, ids, forms);
    const resolved = { ...legacy, starred: [], starredForms: ["52:kanto"] };
    const before = entriesFromState(legacy, 1, "fixture");
    const after = entriesFromState(resolved, 2, "fixture");
    const assigned = { ...before, ...localIntentChanges(legacy, resolved, 2, "fixture") };
    expect(stateFromDocument({ schema: 1, updatedAt: 2, records: assigned }, ids, forms)).toEqual(resolved);
    const undone = { ...assigned, ...localIntentChanges(resolved, legacy, 3, "fixture") };
    expect(stateFromDocument({ schema: 1, updatedAt: 3, records: undone }, ids, forms)).toEqual(legacy);
    expect(before["star:52"].s).toBe(after["star:52"].s);
  });
  it("does not revive unresolved intent older than an explicit form-favorite clear", () => {
    const records = { "star:52": entry("on"), "starlegacy:52": { s: "on", at: 2, by: "old" }, "starform:52:kanto": { s: "off", at: 3, by: "new" } };
    const read = stateFromDocument({ schema: 1, updatedAt: 3, records }, new Set([52]), new Set(["52:alolan", "52:kanto"]));
    expect(read).toMatchObject({ starred: [], starredForms: [] });
  });
  it("projects an owned sibling over a stale aggregate downgrade without inventing missing forms", () => {
    const ids = new Set([52, 150]), forms = new Set(["52:alolan", "52:kanto"]);
    const remote: SyncDocument = { schema: 1, updatedAt: 4, records: {
      "species:52": { s: "seen", at: 4, by: "first" },
      "form:52:alolan": { s: "seen", at: 4, by: "first" },
      "form:52:kanto": { s: "caught", at: 3, by: "second" },
      "species:150": entry("caught"),
    } };
    const projected = stateFromDocument(remote, ids, forms);
    expect(projected.species).toEqual({ "52": "caught", "150": "caught" });
    expect(projected.forms).toEqual({ "52:alolan": "seen", "52:kanto": "caught" });
    const unknown = stateFromDocument({ schema: 1, updatedAt: 1, records: { "species:52": entry("caught") } }, ids, forms);
    expect(unknown.species["52"]).toBe("caught");
    expect(unknown.forms).toEqual({});
  });
  it("undoes a catch without clearing a later sibling catch or its aggregate", () => {
    const ids = new Set([52, 150]), forms = new Set(["52:alolan", "52:kanto"]);
    const before = validateState({ schemaVersion: 5, species: {}, forms: {}, starred: [], starredForms: [], settings: { forms: true, mode: "moon", unlocks: [] } }, ids, forms);
    const after = { ...before, species: { "52": "caught" as const }, forms: { "52:alolan": "caught" as const } };
    const later = { ...after, species: { "52": "caught" as const, "150": "seen" as const },
      forms: { ...after.forms, "52:kanto": "caught" as const } };
    const undone = rebaseState(later, after, before, ids, forms, true);
    expect(undone.forms).toEqual({ "52:kanto": "caught" });
    expect(undone.species).toEqual({ "52": "caught", "150": "seen" });
  });
  it("keeps the aggregate star while either form is favored and clears it with the last form", () => {
    const initial = validateState({ schemaVersion: 4, species: { "52": "caught" }, forms: { "52:alolan": "caught" }, starred: [52], settings: { forms: true, mode: "moon", unlocks: [] } }, new Set([52]), new Set(["52:alolan", "52:kanto"]));
    const both = { ...initial, starredForms: ["52:alolan", "52:kanto"] };
    expect(localIntentChanges(initial, both, 2, "fixture")).toEqual({ "starform:52:kanto": { s: "on", at: 2, by: "fixture" } });
    const kanto = { ...both, starredForms: ["52:kanto"] };
    expect(localIntentChanges(both, kanto, 3, "fixture")).toEqual({ "starform:52:alolan": { s: "off", at: 3, by: "fixture" } });
    expect(entriesFromState(kanto, 3, "fixture")["star:52"].s).toBe("on");
    expect(localIntentChanges(kanto, { ...kanto, starredForms: [] }, 4, "fixture")).toEqual({ "star:52": { s: "off", at: 4, by: "fixture" }, "starform:52:kanto": { s: "off", at: 4, by: "fixture" } });
  });
  it("undoes one form favorite without deleting a later opposite-form favorite or catch", () => {
    const ids = new Set([52, 150]), forms = new Set(["52:alolan", "52:kanto"]);
    const before = validateState({ schemaVersion: 5, species: {}, forms: {}, starred: [], starredForms: [], settings: { forms: true, mode: "moon", unlocks: [] } }, ids, forms);
    const after = { ...before, starredForms: ["52:alolan"] };
    const later = { ...after, species: { "150": "caught" as const }, starredForms: ["52:alolan", "52:kanto"] };
    const undone = rebaseState(later, after, before, ids, forms, true);
    expect(undone).toMatchObject({ species: { "150": "caught" }, starredForms: ["52:kanto"] });
    expect(entriesFromState(undone, 4, "fixture")["star:52"].s).toBe("on");
  });
  it("converges simultaneous opposite-form favorite edits in either merge order", () => {
    const empty = { schema: 1 as const, updatedAt: 0, records: {} };
    const a: SyncDocument = { schema: 1, updatedAt: 2, records: { "starform:52:alolan": entry("on"), "star:52": entry("on") } };
    const b: SyncDocument = { schema: 1, updatedAt: 3, records: { "starform:52:kanto": { s: "on", at: 2, by: "other" }, "star:52": { s: "on", at: 2, by: "other" } } };
    const first = mergeDocument(mergeDocument(empty, a), b), second = mergeDocument(mergeDocument(empty, b), a);
    expect(first.records).toEqual(second.records);
    expect(stateFromDocument(first, new Set([52]), new Set(["52:alolan", "52:kanto"]))).toMatchObject({ starred: [], starredForms: ["52:alolan", "52:kanto"] });
  });

  it("does not turn a legacy snapshot lacking form favorites into a server clear", () => {
    const legacy: SavedState = { schemaVersion: 4, species: { "52": "caught" }, forms: { "52:alolan": "caught" }, starred: [52], settings: { forms: true, mode: "moon", unlocks: [] } };
    const base: SyncDocument = { schema: 1, updatedAt: 1, records: { ...entriesFromState(legacy, 1, "fixture"), "starform:52:kanto": entry("on") } };
    const migrated = validateState(legacy, new Set([52]), new Set(["52:alolan", "52:kanto"]));
    for (const [save, hint] of [[legacy, false], [migrated, true]] as const) {
      const pending = pendingEntries(base, save, 2, "fixture", false, hint);
      expect(pending["starform:52:kanto"]).toBeUndefined();
    }
  });

  it("does not invent or clear new unresolved-intent flags from a legacy migration", () => {
    const legacy: SavedState = { schemaVersion: 4, species: { "52": "caught" }, forms: { "52:alolan": "caught", "52:kanto": "caught" }, starred: [52], settings: { forms: true, mode: "moon", unlocks: [] } };
    const migrated = validateState(legacy, new Set([52]), new Set(["52:alolan", "52:kanto"]));
    const base: SyncDocument = { schema: 1, updatedAt: 1, records: entriesFromState(legacy, 1, "fixture") };
    expect(pendingEntries(base, migrated, 2, "fixture", false, true)["starlegacy:52"]).toBeUndefined();
    const current = { ...base, records: { ...base.records, "starlegacy:52": entry("on") } };
    expect(pendingEntries(current, { ...migrated, starred: [] }, 2, "fixture", false, true)["starlegacy:52"]).toBeUndefined();
  });
  it("counts unresolved favorite clears as protected favorites", () => {
    const base: SyncDocument = { schema: 1, updatedAt: 1, records: { "starlegacy:52": entry("on"), "starlegacy:26": entry("on") } };
    expect(isWholeAccountClear(base, { "starlegacy:52": entry("off"), "starlegacy:26": entry("off") })).toBe(true);
    expect(heldSummary(["starlegacy:52"])).toBe("1 favourite");
  });
  it("names held regional favorites as favorites, not zero Pokémon", () => {
    expect(heldSummary(["starform:52:alolan", "starform:52:kanto"])).toBe("2 favourites");
  });
  it("holds a whole-collection form-favorite clear just like species favorites", () => {
    const base: SyncDocument = { schema: 1, updatedAt: 1, records: { "starform:52:alolan": entry("on"), "starform:52:kanto": entry("on") } };
    expect(isWholeAccountClear(base, { "starform:52:alolan": entry("off"), "starform:52:kanto": entry("off") })).toBe(true);
  });
});
