import { describe, expect, it } from "vitest";
const modules = import.meta.glob<typeof import("./collection")>("./collection.ts");
import type { Pokemon } from "./types";

const pokemon: Pokemon[] = [{ id: 25, name: "Pikachu", slug: "pikachu" }, { id: 52, name: "Meowth", slug: "meowth" }];
describe("collection targets", () => {
  it("splits regional identities only while tracking and searches explicit form names", async () => {
    expect(typeof modules["./collection.ts"]).toBe("function");
    const Collection = await modules["./collection.ts"]();
    const targets = Collection.collectionTargets(pokemon, true);
    expect(targets.map(Collection.targetKey)).toEqual(["25", "52:alolan", "52:kanto"]);
    expect(Collection.collectionTargets(pokemon, false).map(Collection.targetKey)).toEqual(["25", "52"]);
    expect(Collection.targetName(pokemon[1], "alolan")).toBe("Meowth (Alolan)");
    expect(Collection.matchesTarget(pokemon[1], targets[1], "Alolan Meowth")).toBe(true);
    expect(Collection.matchesTarget(pokemon[1], targets[2], "Meowth Kanto")).toBe(true);
    expect(Collection.matchesTarget(pokemon[1], targets[2], "Alolan")).toBe(false);
    expect(Collection.matchesTarget(pokemon[1], targets[1], "052")).toBe(true);
  });
});
