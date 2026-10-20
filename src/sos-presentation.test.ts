import { describe, expect, it } from "vitest";
import { groupWeatherNodes, sosConditions } from "./sos-presentation";
import type { GuideSosNode } from "./unlocks";
const node = (id: string): GuideSosNode => {
  const row = { id, speciesId: 351, speciesName: "Castform", rates: { single: 1 }, allies: [], conditions: ["During rain"] };
  return { call: { kind: "weather-sos", group: { id: "weather", name: "Weather SOS", category: "return-later", encounters: [row] }, sourceRow: row, row, caller: null }, eligible: true, children: [] };
};
describe("lossless caller-local weather presentation", () => {
  it("groups one exact identity but retains every source/rate rule without modifying nodes", () => {
    const nodes = [node("rain"), node("hail"), node("sand")];
    nodes[1].call.row.conditions = ["During hail"]; nodes[1].call.row.rates = { single: 11 };
    nodes[2].call.row.conditions = ["During sandstorm"]; nodes[2].call.row.rates = { single: 11 };
    const before = structuredClone(nodes), grouped = groupWeatherNodes(nodes);
    expect(grouped).toHaveLength(1); expect(grouped[0]).toEqual(nodes);
    expect(grouped.flat()).toEqual(nodes); expect(nodes).toEqual(before);
  });
  it("does not merge different forms, abilities or pooled display identities", () => {
    for (const key of ["form", "ability", "speciesName"] as const) {
      const a = node("a"), b = node("b"); b.call.row[key] = "Distinct acquisition identity";
      expect(groupWeatherNodes([a,b])).toHaveLength(2);
    }
  });
  it("does not collapse ordinary calls or different access states", () => {
    const a=node("a"), b=node("b"); a.call.kind="sos"; b.call.kind="sos";
    expect(groupWeatherNodes([a,b])).toHaveLength(2);
    a.call.kind="weather-sos"; b.call.kind="weather-sos"; b.eligible=false;
    expect(groupWeatherNodes([a,b])).toHaveLength(2);
  });
  it("keeps descendant call trees separate", () => {
    const a=node("a"), b=node("b"); a.children=[node("child")];
    expect(groupWeatherNodes([a,b])).toEqual([[a],[b]]);
  });
  it("removes only redundant weather prose and duplicate exact conditions", () => {
    const n=node("rain"); n.call.group.conditions=["Appears as an SOS ally; the caller depends on the encounter.","Weather-dependent SOS encounter.","SOS encounter while it is raining.","During rain","Keep this caller restriction"];
    expect(sosConditions(n)).toEqual(["During rain","Keep this caller restriction"]);
  });
  it("retains raining prose without an explicit replacement and preserves ordinary conditions", () => {
    const n=node("rain");n.call.sourceRow.conditions=["SOS encounter while it is raining."];
    expect(sosConditions(n)).toEqual(["SOS encounter while it is raining."]);
    n.call.kind="sos";n.call.group.conditions=["Weather-dependent SOS encounter."];
    expect(sosConditions(n)).toEqual(["Weather-dependent SOS encounter.","SOS encounter while it is raining."]);
  });
});
