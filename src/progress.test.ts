import { expect, it } from "vitest";
import { POKEMON } from "./data";
import { REGIONAL_DETAILS } from "./regional";
import type { Pokemon, StatusMap } from "./types";

type Metric = "registered" | "owned" | "living";
type Store = { getItem(key: string): string | null; setItem(key: string, value: string): void };
type API = { countProgress(pokemon: readonly Pokemon[], species: StatusMap, forms: StatusMap, tracking: boolean): Record<Metric, { value: number; max: number }>; PROGRESS_PREFERENCE_KEY: string; readProgressPreference(getStore: () => Store): Metric | null; writeProgressPreference(metric: unknown, getStore: () => Store): boolean; defaultProgressMetric(tracking: boolean): Metric };
const modules = import.meta.glob("./progress.ts", { eager: true }) as Record<string, API>;
const api = () => { const result = modules["./progress.ts"]; expect(result).toBeDefined(); return result; };

it("counts registered species, owned species and enabled living targets without a third regional target", () => {
  const m = api();
  const pokemon = POKEMON.filter(row => [25, 52, 53].includes(row.id));
  const species: StatusMap = { "25": "seen", "52": "caught", "53": "seen" };
  const forms: StatusMap = { "52:alolan": "caught", "52:kanto": "caught", "53:alolan": "seen" };
  const before = JSON.stringify({ species, forms });
  expect(m.countProgress(pokemon, species, forms, true)).toEqual({ registered: { value: 3, max: 3 }, owned: { value: 1, max: 3 }, living: { value: 2, max: 5 } });
  expect(m.countProgress(pokemon, species, forms, false)).toEqual({ registered: { value: 3, max: 3 }, owned: { value: 1, max: 3 }, living: { value: 1, max: 3 } });
  expect(JSON.stringify({ species, forms })).toBe(before);
  expect(m.countProgress([...pokemon, pokemon[0]], species, forms, true)).toEqual(m.countProgress(pokemon, species, forms, true));
});

it("does not attribute legacy ownership to an assumed form and accepts stronger exact-form evidence", () => {
  const m = api(), pokemon = POKEMON.filter(row => row.id === 52);
  expect(m.countProgress(pokemon, { "52": "caught" }, {}, true)).toEqual({ registered: { value: 1, max: 1 }, owned: { value: 1, max: 1 }, living: { value: 0, max: 2 } });
  expect(m.countProgress(pokemon, {}, { "52:kanto": "caught" }, true)).toEqual({ registered: { value: 1, max: 1 }, owned: { value: 1, max: 1 }, living: { value: 1, max: 2 } });
  expect(m.countProgress(pokemon, { "52": "seen" }, {}, true).registered.value).toBe(1);
  for (const tracking of [false, true]) {
    const all = m.countProgress(pokemon, { "52": "caught" }, { "52:alolan": "caught", "52:kanto": "caught" }, tracking);
    expect(all.living.value).toBe(all.living.max);
    expect(m.countProgress(pokemon, { "52": "seen" }, {}, tracking).owned.value).toBe(0);
  }
  expect(m.countProgress([], {}, {}, true)).toEqual({ registered: { value: 0, max: 0 }, owned: { value: 0, max: 0 }, living: { value: 0, max: 0 } });
});

it("reaches exactly the full owned scope and counts all-seen as registered but not owned", () => {
  const m = api();
  const all = (value: "seen" | "caught"): StatusMap => Object.fromEntries(POKEMON.map(row => [String(row.id), value]));
  const forms = (value: "seen" | "caught"): StatusMap => Object.fromEntries(Object.keys(REGIONAL_DETAILS).map(key => [key, value]));
  const max = POKEMON.length + new Set(Object.values(REGIONAL_DETAILS).map(row => row.id)).size;
  for (const tracking of [false, true]) {
    const owned = m.countProgress(POKEMON, all("caught"), forms("caught"), tracking);
    const seen = m.countProgress(POKEMON, all("seen"), forms("seen"), tracking);
    expect(owned).toEqual({ registered: { value: POKEMON.length, max: POKEMON.length }, owned: { value: POKEMON.length, max: POKEMON.length }, living: { value: tracking ? max : POKEMON.length, max: tracking ? max : POKEMON.length } });
    expect(seen).toEqual({ registered: { value: POKEMON.length, max: POKEMON.length }, owned: { value: 0, max: POKEMON.length }, living: { value: 0, max: tracking ? max : POKEMON.length } });
  }
});

it("stores only an explicit device-global metric without touching player namespaces", () => {
  const m = api();
  const values = new Map([["pokemon-checklist-state-v5", "unchanged player save"], ["pokemon-checklist-state-v5:account-a", "unchanged account save"]]);
  const store: Store = { getItem: key => values.get(key) ?? null, setItem: (key, value) => { values.set(key, value); } };
  expect(m.readProgressPreference(() => store)).toBeNull();
  expect(values.size).toBe(2);
  expect(m.defaultProgressMetric(true)).toBe("living");
  expect(m.defaultProgressMetric(false)).toBe("owned");
  for (const metric of ["registered", "living", "owned"] as const) {
    expect(m.writeProgressPreference(metric, () => store)).toBe(true);
    expect(m.readProgressPreference(() => store)).toBe(metric);
  }
  expect([...values]).toEqual([["pokemon-checklist-state-v5", "unchanged player save"], ["pokemon-checklist-state-v5:account-a", "unchanged account save"], [m.PROGRESS_PREFERENCE_KEY, "owned"]]);
});

it("handles invalid stored data and denied storage without a player-save mutation", () => {
  const m = api();
  for (const raw of [null, "", "wrong", "\"owned\"", "REGISTERED", "{broken"]) {
    expect(m.readProgressPreference(() => ({ getItem: () => raw, setItem: () => { throw Error("must not write while reading"); } }))).toBeNull();
  }
  const denied = () => { throw Error("storage denied"); };
  expect(m.readProgressPreference(denied)).toBeNull();
  expect(m.writeProgressPreference("owned", denied)).toBe(false);
  const writes: string[] = [];
  const store: Store = { getItem: () => null, setItem: (key, value) => { writes.push(`${key}:${value}`); } };
  for (const bad of [null, {}, 0, "wrong"]) expect(m.writeProgressPreference(bad, () => store)).toBe(false);
  expect(writes).toEqual([]);
});
