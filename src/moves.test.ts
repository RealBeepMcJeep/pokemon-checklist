import { describe, expect, it } from "vitest";
import { MOVES } from "./data";
import {
  describeRoute,
  moveInfo,
  movesFinals,
  shownRoutes,
  statsTier,
} from "./moves";

describe("popular moves", () => {
  it("points each species at its own final evolutions", () => {
    expect(movesFinals(282)).toEqual([282]); // Gardevoir is final
    expect(movesFinals(280)).toEqual([282, 475]); // Ralts branches
    expect(movesFinals(133)).toHaveLength(8); // Eevee
    expect(movesFinals(150)).toEqual([150]); // Ubers are covered too
  });

  it("covers every final evolution in the dex", () => {
    expect(Object.keys(MOVES.finals)).toHaveLength(439);
    for (const targets of Object.values(MOVES.lines)) {
      for (const target of targets) expect(MOVES.finals[target]).toBeDefined();
    }
  });

  it("keeps a Hidden Power set's own type", () => {
    const row = Object.values(MOVES.finals)
      .flatMap((entry) => entry.moves)
      .find((move) => move.name?.startsWith("Hidden Power "));
    expect(row).toBeDefined();
    expect(moveInfo(row!).type).toBe(row!.type);
    expect(moveInfo(row!).tm).toBe(10);
  });

  it("words routes plainly and per mode", () => {
    const tm = { name: "Psyshock", type: "Psychic", tm: 3, tmAt: "Lake of the Moone" };
    expect(describeRoute({ via: "TM" }, tm, 282, "sun")).toBe(
      "TM03 · Lake of the Moone",
    );
    const plain = { name: "Psychic", type: "Psychic" };
    expect(describeRoute({ via: "level", level: 31, form: 282 }, plain, 282, "sun")).toBe(
      "Level 31",
    );
    expect(describeRoute({ via: "level", level: 27, form: 280 }, plain, 282, "sun")).toBe(
      "Ralts at level 27",
    );
    const egg = { via: "egg", form: 280, beforeEvolving: true } as const;
    expect(describeRoute(egg, plain, 475, "sun")).toBe("Egg move on Ralts (breed for it)");
    expect(describeRoute(egg, plain, 475, "photonic-prismatic")).toBe(
      "Egg move on Ralts; this hack teaches it by level-up",
    );
    expect(
      describeRoute({ via: "tutor", form: 280, beforeEvolving: true }, { ...plain, tutorAt: "Ula'ula Beach", tutorBp: 8 }, 282, "sun"),
    ).toBe("Before evolving: Tutor · Ula'ula Beach · 8 BP (Ralts)");
  });

  it("shows the useful routes only", () => {
    const flamethrower = [
      { via: "TM" },
      { via: "level", level: 40, form: 757 },
      { via: "level", level: 44, form: 758 },
      { via: "event" },
    ] as const;
    expect(shownRoutes([...flamethrower], 758)).toEqual([
      { via: "TM" },
      { via: "level", level: 44, form: 758 },
    ]);
    const preEvolutionOnly = [
      { via: "level", level: 30, form: 281, beforeEvolving: true },
      { via: "level", level: 27, form: 280, beforeEvolving: true },
    ] as const;
    expect(shownRoutes([...preEvolutionOnly], 282)).toEqual([preEvolutionOnly[1]]);
    expect(shownRoutes([{ via: "event" }], 282)).toEqual([{ via: "event" }]);
  });

  it("names the tier file", () => {
    expect(statsTier("gen7ru-1630")).toBe("RU");
    expect(statsTier("gen7ubers-1630")).toBe("Ubers");
  });

  it("degrades to a labeled entry instead of throwing when a move is unknown", () => {
    const row = { move: "not-a-real-move", usage: 1, how: [] };
    expect(moveInfo(row)).toEqual({ name: "not-a-real-move", type: "?" });
    const overridden = { move: "not-a-real-move", usage: 1, how: [], name: "Hidden Power Fire", type: "Fire" };
    expect(moveInfo(overridden)).toEqual({ name: "Hidden Power Fire", type: "Fire" });
  });
});
