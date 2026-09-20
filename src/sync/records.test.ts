import { describe, expect, it } from "vitest";
import type { SavedState } from "../types";
import {
  SETTING_FORMS,
  SETTING_MODE,
  STAR_OFF,
  STAR_ON,
  TOMBSTONE,
  clearedByReset,
  diffEntries,
  entriesFromState,
  formKey,
  inverseOfSet,
  mergeDocument,
  mergeEntry,
  speciesKey,
  starKey,
  stateFromDocument,
  undoableFrom,
  type LogEntry,
  type RecordEntry,
  type SyncDocument,
} from "./records";

const POKEMON = new Set([1, 2, 25, 150]);
const FORMS = new Set(["25:alola"]);

const entry = (s: string, at: number, by = "uid-a"): RecordEntry => ({
  s,
  at,
  by,
});

const document = (
  records: Record<string, RecordEntry>,
  updatedAt = 0,
): SyncDocument => ({ schema: 1, records, updatedAt });

const save = (overrides: Partial<SavedState> = {}): SavedState => ({
  schemaVersion: 3,
  species: {},
  forms: {},
  starred: [],
  settings: { forms: false, mode: "moon" },
  ...overrides,
});

describe("mergeEntry", () => {
  it("takes the later write", () => {
    expect(mergeEntry(entry("seen", 10), entry("caught", 20))).toEqual(
      entry("caught", 20),
    );
    expect(mergeEntry(entry("caught", 20), entry("seen", 10))).toEqual(
      entry("caught", 20),
    );
  });

  it("breaks an exact tie the same way whichever order they arrive in", () => {
    const a = entry("caught", 10, "uid-a");
    const b = entry("seen", 10, "uid-b");
    expect(mergeEntry(a, b)).toEqual(mergeEntry(b, a));
    expect(mergeEntry(a, b)!.s).toBe("seen");
  });

  it("keeps a tombstone: clearing is a fact, not an absence", () => {
    const merged = mergeEntry(entry("caught", 10), entry(TOMBSTONE, 20));
    expect(merged!.s).toBe(TOMBSTONE);
  });

  it("lets a clear win an exact provisional stamp tie", () => {
    const merged = mergeEntry(
      entry("caught", 10, "uid-z"),
      entry(TOMBSTONE, 10, "uid-a"),
    );
    expect(merged!.s).toBe(TOMBSTONE);
  });

  it("returns whichever side exists", () => {
    expect(mergeEntry(undefined, entry("seen", 5))).toEqual(entry("seen", 5));
    expect(mergeEntry(entry("seen", 5), undefined)).toEqual(entry("seen", 5));
    expect(mergeEntry(undefined, undefined)).toBeUndefined();
  });
});

describe("mergeDocument", () => {
  it("converges to the same document from either direction", () => {
    const left = document({
      [speciesKey(25)]: entry("caught", 10, "kid"),
      [starKey(150)]: entry(STAR_ON, 30, "dad"),
    });
    const right = document({
      [speciesKey(25)]: entry("seen", 20, "dad"),
      [speciesKey(1)]: entry("caught", 15, "kid"),
    });
    const forward = mergeDocument(left, right);
    const backward = mergeDocument(right, left);
    expect(forward.records).toEqual(backward.records);
    expect(forward.records[speciesKey(25)].s).toBe("seen");
    expect(forward.records[speciesKey(1)].s).toBe("caught");
    expect(forward.records[starKey(150)].s).toBe(STAR_ON);
  });

  it("is idempotent, so replaying the same remote state is harmless", () => {
    const left = document({ [speciesKey(1)]: entry("caught", 10) });
    const right = document({ [speciesKey(1)]: entry("caught", 20) });
    const once = mergeDocument(left, right);
    expect(mergeDocument(once, right).records).toEqual(once.records);
  });
});

describe("entriesFromState", () => {
  it("records progress, stars and settings, and skips absent species", () => {
    const records = entriesFromState(
      save({
        species: { "25": "caught", "150": "seen" },
        forms: { "25:alola": "caught" },
        starred: [25],
        settings: { forms: true, mode: "ultra-moon" },
      }),
      1_000,
      "uid-a",
    );
    expect(records[speciesKey(25)]).toEqual(entry("caught", 1_000));
    expect(records[speciesKey(150)]).toEqual(entry("seen", 1_000));
    expect(records[formKey("25:alola")]).toEqual(entry("caught", 1_000));
    expect(records[starKey(25)]).toEqual(entry(STAR_ON, 1_000));
    expect(records[SETTING_MODE]).toEqual(entry("ultra-moon", 1_000));
    expect(records[SETTING_FORMS]).toEqual(entry(STAR_ON, 1_000));
    expect(records[speciesKey(1)]).toBeUndefined();
  });
});

describe("diffEntries", () => {
  it("publishes only what changed, with a tombstone when a value is cleared", () => {
    const before = entriesFromState(
      save({ species: { "1": "caught", "25": "caught" }, starred: [25] }),
      100,
      "uid-a",
    );
    const after = entriesFromState(
      save({ species: { "25": "seen" } }),
      200,
      "uid-a",
    );
    const changed = diffEntries(before, after);
    expect(Object.keys(changed).sort()).toEqual(
      [speciesKey(1), speciesKey(25), starKey(25)].sort(),
    );
    // #001 was dropped from the save, so it is cleared rather than forgotten.
    expect(changed[speciesKey(1)].s).toBe(TOMBSTONE);
    expect(changed[starKey(25)].s).toBe(STAR_OFF);
    expect(changed[speciesKey(25)].s).toBe("seen");
  });

  it("publishes nothing when nothing changed", () => {
    const before = entriesFromState(save({ species: { "1": "caught" } }), 1, "a");
    expect(diffEntries(before, { ...before })).toEqual({});
  });
});

describe("stateFromDocument", () => {
  it("rebuilds the save, sorted and deduplicated", () => {
    const doc = document({
      [speciesKey(25)]: entry("caught", 10),
      [speciesKey(150)]: entry("seen", 10),
      [formKey("25:alola")]: entry("caught", 10),
      [starKey(150)]: entry(STAR_ON, 10),
      [starKey(2)]: entry(STAR_ON, 10),
      [SETTING_MODE]: entry("ultra-sun", 10),
      [SETTING_FORMS]: entry(STAR_ON, 10),
    });
    expect(stateFromDocument(doc, POKEMON, FORMS)).toEqual({
      schemaVersion: 3,
      species: { "25": "caught", "150": "seen" },
      forms: { "25:alola": "caught" },
      starred: [2, 150],
      settings: { forms: true, mode: "ultra-sun" },
    });
  });

  it("skips records this build does not know, instead of failing", () => {
    const doc = document({
      [speciesKey(999)]: entry("caught", 10),
      [formKey("999:future")]: entry("caught", 10),
      [speciesKey(1)]: entry("shiny", 10),
      "setting:unknown": entry("whatever", 10),
      "future:thing": entry("on", 10),
      [SETTING_MODE]: entry("pokemon-go", 10),
    });
    expect(stateFromDocument(doc, POKEMON, FORMS)).toEqual({
      schemaVersion: 3,
      species: {},
      forms: {},
      starred: [],
      settings: { forms: false, mode: "photonic-prismatic" },
    });
  });

  it("ignores cleared records", () => {
    const doc = document({
      [speciesKey(1)]: entry(TOMBSTONE, 30),
      [starKey(1)]: entry(STAR_OFF, 30),
    });
    expect(stateFromDocument(doc, POKEMON, FORMS).species).toEqual({});
    expect(stateFromDocument(doc, POKEMON, FORMS).starred).toEqual([]);
  });
});

describe("reset and undo", () => {
  const beforeReset = save({
    species: { "1": "caught", "25": "caught" },
    starred: [25],
  });

  it("captures a before-image of everything a reset clears", () => {
    expect(clearedByReset(beforeReset).sort()).toEqual(
      [
        [speciesKey(1), "caught"],
        [speciesKey(25), "caught"],
        [starKey(25), STAR_ON],
      ].sort(),
    );
  });

  it("restores the records the reset still owns", () => {
    const reset: LogEntry = {
      op: "reset",
      at: 500,
      by: "uid-a",
      cleared: clearedByReset(beforeReset),
    };
    const doc = document({
      [speciesKey(1)]: entry(TOMBSTONE, 500, "uid-a"),
      [speciesKey(25)]: entry(TOMBSTONE, 500, "uid-a"),
      [starKey(25)]: entry(STAR_OFF, 500, "uid-a"),
    });
    expect(undoableFrom(doc, reset).sort()).toEqual(
      [
        [speciesKey(1), "caught"],
        [speciesKey(25), "caught"],
        [starKey(25), STAR_ON],
      ].sort(),
    );
  });

  it("leaves a catch made after the reset alone", () => {
    const reset: LogEntry = {
      op: "reset",
      at: 500,
      by: "uid-a",
      cleared: clearedByReset(beforeReset),
    };
    // The kid caught #001 on another device after the reset: newer than 500.
    const doc = document({
      [speciesKey(1)]: entry("caught", 900, "uid-b"),
      [speciesKey(25)]: entry(TOMBSTONE, 500, "uid-a"),
      [starKey(25)]: entry(STAR_OFF, 500, "uid-a"),
    });
    const restorable = undoableFrom(doc, reset);
    expect(restorable).toContainEqual([speciesKey(25), "caught"]);
    expect(restorable).not.toContainEqual([speciesKey(1), "caught"]);
  });

  it("does not re-restore a record another device re-created identically", () => {
    const reset: LogEntry = {
      op: "reset",
      at: 500,
      by: "uid-a",
      cleared: [[speciesKey(1), "caught"]],
    };
    const doc = document({ [speciesKey(1)]: entry("caught", 700, "uid-b") });
    expect(undoableFrom(doc, reset)).toEqual([]);
  });

  it("inverts a single set back to its previous value", () => {
    const set: LogEntry = {
      op: "set",
      at: 10,
      by: "uid-a",
      key: speciesKey(25),
      from: "seen",
      to: "caught",
    };
    expect(inverseOfSet(set)).toEqual([speciesKey(25), "seen"]);
  });

  it("inverts a set that had no previous value back to a tombstone", () => {
    const set: LogEntry = {
      op: "set",
      at: 10,
      by: "uid-a",
      key: speciesKey(25),
      to: "caught",
    };
    expect(inverseOfSet(set)).toEqual([speciesKey(25), TOMBSTONE]);
  });

  it("has no inverse for a reset, which is undone through its before-image", () => {
    expect(inverseOfSet({ op: "reset", at: 10, by: "uid-a" })).toBeNull();
  });
});
