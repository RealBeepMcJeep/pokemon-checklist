import { describe, expect, it } from "vitest";
import { interpretStoredState } from "./state";

const current = JSON.stringify({
  schemaVersion: 2,
  species: { "731": "caught" },
  forms: {},
  settings: { forms: false, mode: "photonic-prismatic" },
});

describe("cross-tab state", () => {
  it("applies a state another tab saved", () => {
    const synced = interpretStoredState(current);
    expect(synced.kind).toBe("apply");
    if (synced.kind !== "apply") return;
    expect(synced.state.species["731"]).toBe("caught");
  });

  it("treats a removed save as cleared rather than unreadable", () => {
    expect(interpretStoredState(null).kind).toBe("cleared");
  });

  it("ignores unparseable payloads instead of wiping progress", () => {
    expect(interpretStoredState("{not json").kind).toBe("ignore");
  });

  it("ignores parseable payloads that are not a valid state", () => {
    expect(interpretStoredState(JSON.stringify({ species: {} })).kind).toBe(
      "ignore",
    );
  });

  it("ignores a state naming a Pokémon outside the National Dex", () => {
    const invalid = JSON.stringify({
      schemaVersion: 2,
      species: { "808": "caught" },
      forms: {},
      settings: { forms: false, mode: "photonic-prismatic" },
    });
    expect(interpretStoredState(invalid).kind).toBe("ignore");
  });

  it("migrates a v1 payload written by an older tab", () => {
    const legacy = JSON.stringify({
      schemaVersion: 1,
      species: { "25": "seen" },
      forms: {},
      settings: { forms: false },
    });
    const synced = interpretStoredState(legacy);
    expect(synced.kind).toBe("apply");
    if (synced.kind !== "apply") return;
    expect(synced.state.species["25"]).toBe("seen");
    expect(synced.state.settings.mode).toBe("photonic-prismatic");
  });
});
