import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import * as model from "./capture";
const worker = vm.createContext({ console: { log() {} }, onmessage: null });
vm.runInContext(
  readFileSync("tools/tests/fixtures/dragonfly-worker.js", "utf8"),
  worker,
);
const base = {
  catchRate: 45,
  ballBonus: 1,
  currentHP: 100,
  maxHP: 100,
  status: "none",
  roto: false,
  caught: 0,
};
describe("documented staged Q12 model", () => {
  it("applies documented conditional Gen VII ball modifiers and boundaries", () => {
    expect(model).toHaveProperty("ballModifiers");
    const p = {
      id: 25,
      catchRate: 45,
      speed: 90,
      weight: 600,
      types: [12],
      gender: 127,
    };
    const c = {
      turn: 1,
      level: 10,
      yourLevel: 10,
      night: false,
      cave: false,
      fishing: false,
      surfing: false,
      registered: false,
      sameSpecies: false,
      oppositeGender: false,
    };
    const cases: [string, Partial<typeof c>, number][] = [
      ["Great Ball", {}, 1.5],
      ["Ultra Ball", {}, 2],
      ["Quick Ball", {}, 5],
      ["Quick Ball", { turn: 2 }, 1],
      ["Timer Ball", { turn: 2 }, 1 + 1229 / 4096],
      ["Timer Ball", { turn: 11 }, 4],
      ["Nest Ball", { level: 1 }, 4],
      ["Nest Ball", { level: 29 }, 1.2],
      ["Nest Ball", { level: 30 }, 1],
      ["Dusk Ball", { night: true }, 3],
      ["Dusk Ball", { cave: true }, 3],
      ["Dive Ball", { surfing: true }, 3.5],
      ["Dive Ball", { fishing: true }, 3.5],
      ["Lure Ball", { surfing: true }, 1],
      ["Lure Ball", { fishing: true }, 5],
      ["Repeat Ball", { registered: true }, 3.5],
      ["Level Ball", { yourLevel: 11 }, 2],
      ["Level Ball", { yourLevel: 20 }, 4],
      ["Level Ball", { yourLevel: 40 }, 8],
      ["Love Ball", { sameSpecies: true, oppositeGender: true }, 8],
      ["Love Ball", { sameSpecies: false, oppositeGender: true }, 1],
      ["Beast Ball", {}, 410 / 4096],
    ];
    for (const [ball, context, bonus] of cases)
      expect(
        model.ballModifiers(ball, p, { ...c, ...context }, "usum").bonus,
      ).toBe(bonus);
    expect(
      model.ballModifiers("Fast Ball", { ...p, speed: 100 }, c, "usum").bonus,
    ).toBe(4);
    expect(
      model.ballModifiers("Net Ball", { ...p, types: [10] }, c, "usum").bonus,
    ).toBe(3.5);
    expect(
      model.ballModifiers("Heavy Ball", { ...p, catchRate: 3 }, c, "sm").rate,
    ).toBe(0);
    expect(
      model.ballModifiers("Heavy Ball", { ...p, catchRate: 3 }, c, "usum").rate,
    ).toBe(1);
    for (const [weight, delta] of [
      [999, -20],
      [1000, 0],
      [1999, 0],
      [2000, 20],
      [2999, 20],
      [3000, 30],
    ])
      expect(
        model.ballModifiers("Heavy Ball", { ...p, weight }, c, "usum").rate,
      ).toBe(45 + delta);
    expect(
      model.ballModifiers("Ultra Ball", { ...p, id: 793 }, c, "usum").bonus,
    ).toBe(410 / 4096);
    expect(
      model.ballModifiers("Beast Ball", { ...p, id: 803 }, c, "usum").bonus,
    ).toBe(5);
    expect(
      model.ballModifiers(
        "Love Ball",
        { ...p, gender: 255 },
        { ...c, sameSpecies: true, oppositeGender: true },
        "usum",
      ).bonus,
    ).toBe(1);
    for (const id of [30, 33, 35, 39, 300, 517])
      expect(
        model.ballModifiers("Moon Ball", { ...p, id }, c, "usum").bonus,
      ).toBe(4);
    for (const id of [29, 31, 32, 34, 36, 173, 40, 174, 301, 518])
      expect(
        model.ballModifiers("Moon Ball", { ...p, id }, c, "usum").bonus,
      ).toBe(1);
    expect(() => model.ballModifiers("invalid", p, c, "usum")).toThrow();
  });
  it("ignores inactive ball conditions but rejects malformed source rates", () => {
    const p = {
      id: 25,
      catchRate: 45,
      speed: 90,
      weight: 600,
      types: [12],
      gender: 127,
    };
    const c = {
      turn: NaN,
      level: NaN,
      yourLevel: NaN,
      night: false,
      cave: false,
      fishing: false,
      surfing: false,
      registered: false,
      sameSpecies: false,
      oppositeGender: false,
    };
    expect(model.ballModifiers("Ultra Ball", p, c, "usum").bonus).toBe(2);
    expect(() =>
      model.ballModifiers(
        "Heavy Ball",
        { ...p, catchRate: -1 },
        { ...c, turn: 1, level: 10, yourLevel: 10 },
        "usum",
      ),
    ).toThrow();
  });
  it("rejects illegal inputs before a Master Ball can guarantee a catch", () => {
    for (const bad of [
      { currentHP: 0 },
      { currentHP: 101 },
      { currentHP: 1.5 },
      { maxHP: 0 },
      { catchRate: 256 },
      { catchRate: -1 },
      { caught: -1 },
      { caught: 808 },
      { ballBonus: NaN },
      { status: "invalid" },
    ]) {
      expect(() =>
        model.probability({ ...base, ...bad, master: true }),
      ).toThrow();
    }
    expect(model.probability({ ...base, catchRate: 0 }).probability).toBe(0);
    expect(model.probability({ ...base, master: true }).probability).toBe(1);
  });
  it("matches the retained real worker across HP, status, Roto and critical boundaries", () => {
    expect(model).toHaveProperty("probability");
    for (const rate of [1, 3, 45, 190, 255])
      for (const hp of [1, 17, 100])
        for (const status of ["none", "slp", "par"])
          for (const caught of [
            0, 30, 31, 150, 151, 300, 301, 450, 451, 600, 601, 807,
          ])
            for (const roto of [false, true]) {
              const input = {
                ...base,
                catchRate: rate,
                currentHP: hp,
                status,
                caught,
                roto,
              };
              const e = {
                pokemon: { catch_rate: rate },
                ball: "poke-ball",
                status,
                cur_hp: hp,
                max_hp: 100,
                entralink: roto ? 250 : 100,
                pokedex: caught,
                version_group: 17,
              };
              worker.event = e;
              const ref = vm.runInContext("calculateResults(event)", worker);
              const result = model.probability(input);
              const critical = ref.critical ?? 0,
                q = ref.crit_success ?? 1;
              expect(result.probability).toBeCloseTo(
                critical * q + (1 - critical) * ref.success,
                14,
              );
              expect(result.x).toBe(vm.runInContext("calcX(event)", worker));
            }
  });
});
