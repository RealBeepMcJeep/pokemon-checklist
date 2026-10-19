import { describe, expect, it } from "vitest";
import { MOVES } from "./data";
import {
  describeRoute,
  moveInfo,
  moveTargetName,
  routesForMode,
  movesFinals,
  shownRoutes,
  statsTier,
} from "./moves";

describe("popular moves", () => {
  it("selects only the requested regional move family and defaults collapsed entries to Alolan", () => {
    expect(movesFinals(52, "alolan")).toEqual(["53:alolan"]);
    expect(movesFinals(52, "kanto")).toEqual(["53:kanto"]);
    expect(movesFinals(52)).toEqual(["53:alolan"]);
    expect(movesFinals(25, undefined, true)).toEqual(["26:alolan", "26:kanto"]);
    expect(movesFinals(25, undefined, false)).toEqual(["26:alolan"]);
  });
  it("keeps native mode routes separate and uses verified Standard evolution moves", () => {
    const entry = MOVES.finals["53:alolan"];
    const knock = entry.moves.find(row => row.move === "knockoff")!;
    for (const mode of ["sun", "moon"] as const) expect(routesForMode(knock, mode)).toEqual([]);
    for (const mode of ["ultra-sun", "ultra-moon"] as const) {
      expect(routesForMode(knock, mode)).toContainEqual({ via: "tutor", form: "53:alolan" });
    }
    const parting = entry.moves.find(row => row.move === "partingshot")!;
    expect(routesForMode(parting, "photonic-prismatic")).toContainEqual({ via: "evolution", form: "53:alolan" });
    expect(routesForMode(parting, "moon").some(route => route.via === "evolution")).toBe(false);
    expect(routesForMode({ move: "fixture", usage: 1, how: [{ via: "tutor" }] }, "sun")).toEqual([]);
  });

  it("names the exact teaching form while collapsed details stay generic", () => {
    expect(moveTargetName("52:alolan")).toBe("Meowth (Alolan)");
    expect(moveTargetName("52:kanto")).toBe("Meowth (Kanto)");
    expect(moveTargetName("52:alolan", false)).toBe("Meowth");
    const route = { via: "level", level: 25, form: "52:alolan", beforeEvolving: true } as const;
    const info = { name: "Fixture", type: "Normal" };
    expect(describeRoute(route, info, "53:alolan", "moon")).toBe("Before evolving: Meowth (Alolan) at level 25");
    expect(describeRoute(route, info, "53:alolan", "moon", false)).toBe("Before evolving: Meowth at level 25");
    expect(describeRoute({ via: "TM", tm: 3 }, { ...info, tm: 3, tmAt: "Legacy placement" }, 282, "sun")).toBe("TM03");
  });

  it("points each species at its own final evolutions", () => {
    expect(movesFinals(282)).toEqual([282]); // Gardevoir is final
    expect(movesFinals(280)).toEqual([282, 475]); // Ralts branches
    expect(movesFinals(133)).toHaveLength(8); // Eevee
    expect(movesFinals(150)).toEqual([150]); // Ubers are covered too
  });

  it("covers every final evolution in the dex", () => {
    expect(Object.keys(MOVES.finals).filter(key => !key.includes(":"))).toHaveLength(439);
    expect(MOVES.finals["53:alolan"]).toBeDefined();
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
      "Egg move on Ralts (breed for it)",
    );
    expect(
      describeRoute({ via: "tutor", form: 280, beforeEvolving: true }, { ...plain, tutorAt: "Ula'ula Beach", tutorBp: 8 }, 282, "sun"),
    ).toBe("Before evolving: Tutor · Ula'ula Beach · 8 BP (Ralts)");
  });

  it("keeps the existing level-before-reminder presentation with native CSV ordering", () => {
    const level = { via: "level", level: 62, form: 282 } as const;
    const reminder = { via: "reminder", form: 282 } as const;
    expect(shownRoutes([reminder, level], 282)).toEqual([level, reminder]);
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
