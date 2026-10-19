import { expect, it } from "vitest";
import { ENCOUNTERS_BY_MODE } from "./data";
import { buildFormDefinitions } from "./domain";
import { eligibleRows, projectEncounters } from "./unlocks";
it("source size and time identities preserve existing form keys without promoting SOS forms to wild", () => {
  const data = structuredClone(ENCOUNTERS_BY_MODE);
  const locations = data["photonic-prismatic"].islands.flatMap(i => i.locations);
  const find = (id: string) => locations.find(l => l.id === id)!;
  for (const [area,id,form] of [["akala-island/memorial-hill",710,"super-size"],["poni-island/vast-poni-canyon",745,"dusk"]] as const) {
    const loc = find(area);
    const calls = projectEncounters(loc,["sos"]).calls.filter(c => c.row.speciesId===id);
    expect(calls.length).toBeGreaterThan(0);
    expect(calls.every(c => c.row.form===form && c.row.rates===null)).toBe(true);
    expect(eligibleRows(loc,["sos"],true).filter(r=>r.speciesId===id)).toHaveLength(1);
    expect(projectEncounters(loc,[]).calls).toEqual([]);
  }
  const after = [...buildFormDefinitions(data).keys()].sort();
  for (const loc of locations) for (const g of loc.groups) for (const r of g.encounters) {
    if (r.id==="akala-island/memorial-hill/all-grass-1/1") r.allies=[{species:"pumpkaboo",name:"Pumpkaboo",speciesId:710}];
    if (r.id==="poni-island/vast-poni-canyon/grass-1-1/2") {r.forms=["midday","midnight","dusk"];r.allies=[];}
    if (r.id==="poni-island/vast-poni-canyon/grass-2-2/2") {delete r.forms;r.allies=[];}
  }
  expect([...buildFormDefinitions(data).keys()].sort()).toEqual(after);
});
