import { expect, it } from "vitest";
import capture from "../data/capture.json";
import { POKEMON } from "./data";
import { REGIONAL_DETAILS } from "./regional";
type Tier = "F" | "D" | "C" | "B" | "A" | "S";
type Result = { profile: "sm" | "usum" | null; sourceForm: number | null; rate: number | null; tier: Tier | null; reason: string | null; stockFallback: boolean };
type API = { encounterCatchForm(row: { speciesId?: number; speciesName?: string; form?: string; ability?: string }, canonical: string): string; catchTier(rate: unknown): Tier | null; resolveCatchDifficulty(id: number, mode: string, form?: string | number): Result };
const modules = import.meta.glob("./catch-difficulty.ts", { eager: true }) as Record<string, API>;
function api() { const result = modules["./catch-difficulty.ts"]; expect(result).toBeDefined(); return result; }
it("resolves every collection identity from its admitted game field including equal-rate regional forms", () => {
  const m = api(); expect(m.resolveCatchDifficulty).toBeTypeOf("function");
  for (const mode of ["sun", "moon", "ultra-sun", "ultra-moon", "photonic-prismatic"]) {
    const profile = mode === "sun" || mode === "moon" ? "sm" : "usum";
    for (const p of POKEMON) {
      const genericForm = REGIONAL_DETAILS[`${p.id}:alolan`] ? 1 : 0;
      const raw = capture.pokemon.find(row => row.id === p.id && row.form === genericForm)!;
      const rate = raw[profile]?.catchRate ?? null;
      expect(m.resolveCatchDifficulty(p.id, mode)).toMatchObject({ profile, sourceForm: genericForm, rate, tier: m.catchTier(rate), stockFallback: mode === "photonic-prismatic" });
    }
    for (const row of Object.values(REGIONAL_DETAILS)) {
      const sourceForm = row.form === "alolan" ? 1 : 0;
      const raw = capture.pokemon.find(p => p.id === row.id && p.form === sourceForm)!;
      if (sourceForm === 1) expect(raw.name).toMatch(/ — Alolan$/);
      expect(m.resolveCatchDifficulty(row.id, mode, row.form)).toMatchObject({ profile, sourceForm, rate: raw[profile]!.catchRate, tier: m.catchTier(raw[profile]!.catchRate), reason: null });
    }
  }
  expect(m.resolveCatchDifficulty(52, "moon", "alolan").tier).toBe(m.resolveCatchDifficulty(52, "moon", "kanto").tier);
  expect(m.resolveCatchDifficulty(745, "ultra-moon", "dusk").sourceForm).toBe(2);
  expect(m.resolveCatchDifficulty(803, "sun")).toMatchObject({ rate: null, tier: null, reason: "missing-profile" });
  expect(m.resolveCatchDifficulty(803, "ultra-sun").rate).toBe(capture.pokemon.find(p => p.id === 803 && p.form === 0)!.usum!.catchRate);
  expect(m.resolveCatchDifficulty(745, "moon", 2)).toMatchObject({ rate: null, tier: null, reason: "missing-profile" });
  for (const form of ["Spring / Summer", "own-tempo", "unverified", -1, 1.5, 999]) expect(m.resolveCatchDifficulty(585, "moon", form)).toMatchObject({ rate: null, tier: null });
  expect(m.resolveCatchDifficulty(20, "moon", "form-2")).toMatchObject({ rate: null, tier: null, reason: "unsupported-form" });
  expect(m.resolveCatchDifficulty(0, "moon").tier).toBeNull();
  expect(m.resolveCatchDifficulty(52, "unverified-profile")).toMatchObject({ profile: null, rate: null, tier: null });
});

it("shares exact encounter identity without treating pooled names or abilities as base", () => {
  const m = api(); expect(m.encounterCatchForm).toBeTypeOf("function");
  expect(m.encounterCatchForm({ speciesId: 52, speciesName: "Meowth", form: "Alolan" }, "Meowth")).toBe("alolan");
  expect(m.encounterCatchForm({ speciesId: 52, speciesName: "Meowth", form: "Kanto" }, "Meowth")).toBe("kanto");
  expect(m.encounterCatchForm({ speciesId: 479, speciesName: "Rotom", form: "Base" }, "Rotom")).toBe("base");
  expect(m.encounterCatchForm({ speciesId: 585, speciesName: "Deerling (Spring / Summer)" }, "Deerling")).toBe("unsupported");
  expect(m.resolveCatchDifficulty(585, "moon", m.encounterCatchForm({ speciesId: 585, speciesName: "Deerling (Spring / Summer)" }, "Deerling")).tier).toBeNull();
  expect(m.resolveCatchDifficulty(744, "moon", m.encounterCatchForm({ speciesId: 744, speciesName: "Rockruff", ability: "Own Tempo" }, "Rockruff")).tier).toBeNull();
  expect(m.encounterCatchForm({ speciesId: 351, speciesName: "Castform" }, "Castform")).toBe("base");
});

it("maps every positive base constant monotonically through fixed F-easiest to S-hardest boundaries", () => {
  const m = api();
  for (const [rate, tier] of [[1,"S"],[15,"S"],[16,"A"],[44,"A"],[45,"B"],[74,"B"],[75,"C"],[119,"C"],[120,"D"],[199,"D"],[200,"F"],[255,"F"]] as const) expect(m.catchTier(rate)).toBe(tier);
  const order = ["F", "D", "C", "B", "A", "S"];
  for (let rate = 2; rate <= 255; rate++) expect(order.indexOf(m.catchTier(rate)!)).toBeLessThanOrEqual(order.indexOf(m.catchTier(rate - 1)!));
  for (const bad of [0, -1, 256, 1.5, NaN, Infinity, "255", null, undefined, {}]) expect(m.catchTier(bad)).toBeNull();
});
