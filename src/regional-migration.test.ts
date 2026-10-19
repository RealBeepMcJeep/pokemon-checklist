import { describe, expect, it } from "vitest";
import { STATE_VERSION, validateState } from "./domain";

const ids = new Set([52, 150]);
const forms = new Set(["52:alolan", "52:kanto"]);
const legacy = () => ({ schemaVersion: 4, species: { "52": "caught" }, forms: {} as Record<string, string>, starred: [52, 150], settings: { forms: true, mode: "photonic-prismatic", unlocks: [] } });
const current = () => ({ ...legacy(), schemaVersion: 5, starredForms: [] as unknown[] });

describe("strict regional save migration", () => {
  it("preserves ambiguous and unidentified legacy favorite intent instead of duplicating or dropping it", () => {
    for (const statuses of [{}, { "52:alolan": "caught", "52:kanto": "caught" }]) {
      const save = validateState({ ...legacy(), forms: statuses }, ids, forms);
      expect(save.starred).toEqual([52, 150]);
      expect(save.starredForms).toEqual([]);
    }
  });
  it.each([null, ["52:future"], [52], ["52:alolan", "52:alolan"]])("rejects invalid v5 form favorite list %j", value => {
    expect(() => validateState({ ...current(), starredForms: value }, ids, forms)).toThrow();
  });
  it("requires the new field only on v5 and rejects unrecognized fields on every version", () => {
    expect(() => validateState({ ...legacy(), starredForms: [] }, ids, forms)).toThrow();
    expect(() => validateState({ ...legacy(), schemaVersion: 5 }, ids, forms)).toThrow();
    expect(() => validateState({ ...current(), opaque: true }, ids, forms)).toThrow();
    expect(() => validateState({ ...current(), settings: { ...current().settings, progress: "living" } }, ids, forms)).toThrow();
    expect(() => validateState({ ...current(), schemaVersion: STATE_VERSION + 1 }, ids, forms)).toThrow();
  });
  it("round-trips every supported old version without changing species ownership", () => {
    for (const version of [1, 2, 3, 4]) {
      const input: Record<string, unknown> = { schemaVersion: version, species: { "150": "seen" }, forms: {}, settings: version === 1 ? { forms: false } : version < 4 ? { forms: false, mode: "moon" } : { forms: false, mode: "moon", unlocks: [] } };
      if (version >= 3) input.starred = [150];
      const migrated = validateState(input, ids, forms);
      expect(migrated.species).toEqual({ "150": "seen" });
      expect(validateState(JSON.parse(JSON.stringify(migrated)), ids, forms)).toEqual(migrated);
    }
  });
});
