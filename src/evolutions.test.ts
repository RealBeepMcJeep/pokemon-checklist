import { describe, expect, it } from "vitest";
import type { CollectionTarget } from "./collection";
import type { GameMode } from "./types";

interface Stage extends CollectionTarget { key: string; name: string; methods: string[] }
const modules = import.meta.glob<{ evolutionFamily: (target: CollectionTarget, mode: GameMode, tracking: boolean) => Stage[] }>("./evolutions.ts", { eager: true });
const family = (target: CollectionTarget, mode: GameMode = "photonic-prismatic", tracking = true): Stage[] => modules["./evolutions.ts"]?.evolutionFamily(target, mode, tracking) ?? [];

describe("evolution family projection", () => {
  it("includes complete linear and branched nonregional families from an intermediate selection", () => {
    expect(family({ id: 364 }).map(x => x.id)).toEqual([363, 364, 365]);
    expect(family({ id: 134 }).map(x => x.id)).toEqual([133, 134, 135, 136, 196, 197, 470, 471, 700]);
    expect(family({ id: 9999 })).toEqual([]);
  });
  it("keeps game-specific location restrictions and honest undocumented hack conditions", () => {
    const target = { id: 26, form: "kanto" } as const;
    expect(family(target, "sun").at(-1)?.methods.join(" ")).toContain("cannot be evolved locally in Sun/Moon");
    expect(family(target, "ultra-moon").at(-1)?.methods.join(" ")).toContain("Ultra Space");
    expect(family(target).at(-1)?.methods.join(" ")).toContain("hack-specific location behavior unverified");
  });
  it("collapses regional stages to generic native-Alolan identities when tracking is off", () => {
    const stages = family({ id: 26, form: "kanto" }, "photonic-prismatic", false);
    expect(stages.map(x => x.key)).toEqual(["172", "25", "26"]);
    expect(stages.map(x => x.form)).toEqual([undefined, undefined, undefined]);
    expect(stages.map(x => x.name)).toEqual(["Pichu", "Pikachu", "Raichu"]);
  });
  it("orders shared predecessors before the selected regional evolution without merging its sibling", () => {
    expect(family({ id: 26, form: "alolan" }).map(x => x.key)).toEqual(["172", "25", "26:alolan"]);
    expect(family({ id: 26, form: "kanto" }).map(x => x.key)).toEqual(["172", "25", "26:kanto"]);
    expect(family({ id: 25 }).map(x => x.key)).toEqual(["172", "25", "26:alolan", "26:kanto"]);
  });
  it("uses creator methods only in Prismatic mode", () => {
    expect(family({ id: 737 }).find(x => x.id === 738)?.methods).toEqual(["Thunder Stone"]);
    for (const mode of ["sun", "moon", "ultra-sun", "ultra-moon"] as const) {
      expect(family({ id: 737 }, mode).find(x => x.id === 738)?.methods).toEqual(["Level up near a special magnetic field"]);
    }
  });
  it("keeps each selected regional branch separate and includes earlier and later stages", () => {
    expect(family({ id: 52, form: "alolan" }).map(x => x.key)).toEqual(["52:alolan", "53:alolan"]);
    expect(family({ id: 53, form: "kanto" }).map(x => x.key)).toEqual(["52:kanto", "53:kanto"]);
  });
});
