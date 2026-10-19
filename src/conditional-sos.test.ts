import { expect, it } from "vitest";
import { guideCalls, guideEncounters, projectEncounters } from "./unlocks";
import type { Location } from "./types";

it("keeps an Own Tempo-only ally conditional instead of sharing it with regular callers", () => {
  for (const form of [undefined, "normal", "own-tempo"]) {
    const caller = {
      id: "native", speciesId: 744, species: "rockruff", speciesName: "Rockruff",
      ...(form ? { form } : { forms: ["normal", "own-tempo"] }),
      rates: { single: 20 }, allies: [],
      conditionalAllies: [{ speciesId: 744, species: "rockruff", name: "Rockruff", form: "own-tempo", callerForm: "own-tempo" }],
    };
    const location: Location = { id: "fixture", name: "Fixture", order: 1,
      groups: [{ id: "grass", name: "Grass", category: "regular", encounters: [caller] }] };
    const before = structuredClone(location);
    const calls = projectEncounters(location, ["sos"]).calls;
    expect(calls).toHaveLength(form === "normal" ? 0 : 1);
    if (form !== "normal") {
      expect(calls[0]).toMatchObject({ callerForm: "own-tempo", row: { form: "own-tempo", rates: null } });
      expect(guideCalls(guideEncounters(location, ["sos"])[0].sos)).toHaveLength(1);
    }
    expect(projectEncounters(location, []).calls).toEqual([]);
    expect(location).toEqual(before);
    expect(caller.allies).toEqual([]);
  }
});
