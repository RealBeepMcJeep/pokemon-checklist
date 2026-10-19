import { expect,it } from "vitest";
import { ENCOUNTERS_BY_MODE } from "./data";
import { projectEncounters,guideEncounters,guideCalls,eligibleRows } from "./unlocks";
import type { EncounterRow,EncounterGroup,Location } from "./types";
const row=(id:string,speciesId:number,allies:number[]=[]):EncounterRow=>({id,speciesId,speciesName:String(speciesId),rates:{single:20},allies:allies.map(speciesId=>({speciesId,species:String(speciesId),name:String(speciesId)}))});
const group=(id:string,name:string,encounters:EncounterRow[],regular=false):EncounterGroup=>({id,name,encounters,category:regular?"regular":"return-later"});
const loc=(...groups:EncounterGroup[]):Location=>({id:"fixture",name:"Fixture",order:1,groups});
it("never borrows an accessible grass caller for a cave-only SOS rule",()=>{
 const rule=Object.assign(row("rule",703,[719,302]),{callerGroups:["cave"]});
 const data=loc(group("grass","Grass",[row("grass-caller",703)],true),group("cave","Surfing",[row("cave-caller",703)]),group("sos","SOS Calls",[rule]));
 expect(projectEncounters(data,["sos"]).calls).toEqual([]);
 expect(eligibleRows(data,["sos"]).map(r=>r.speciesId)).toEqual([703]);
});

it("keeps active and documented method-scoped roots consistent",()=>{
 const rule={...row("rule",703,[719,302]),callerGroups:["cave"]};
 const data=loc(group("grass","Grass",[row("grass-caller",703)],true),group("cave","Surfing",[row("cave-caller",703)]),group("sos","SOS Calls",[rule]));
 for(const flags of [[],["sos"],["sos","surfing"]]){
  const shown=guideEncounters(data,flags,true);
  expect(shown[0].sos).toEqual([]);
  expect(shown[1].sos.map(n=>n.call.row.speciesId)).toEqual([719,302]);
  expect(shown[1].sos.every(n=>n.eligible)).toBe(flags.includes("sos")&&flags.includes("surfing"));
 }
 expect(projectEncounters(data,["sos","surfing"]).calls.every(c=>c.originGroupId==="cave"&&c.row.rates===null)).toBe(true);
});
it("retains original method through chained callers and terminates cycles",()=>{
 const rule={...row("restricted",703,[719]),callerGroups:["cave"]};
 const data=loc(group("grass","Grass",[row("grass",10)],true),group("cave","Surfing",[row("cave",10)]),group("sos","SOS Calls",[row("first",10,[703]),rule,row("cycle",719,[703])]));
 expect(eligibleRows(data,["sos"]).map(r=>r.speciesId)).not.toContain(719);
 const shown=guideEncounters(data,["sos","surfing"]);
 expect(guideCalls(shown[0].sos).map(n=>n.call.row.speciesId)).toEqual([703]);
 expect(guideCalls(shown[1].sos).map(n=>n.call.row.speciesId)).toEqual([703,719,703]);
 expect(projectEncounters(data,["sos","surfing"]).calls).toHaveLength(4);
});
it("does not let location-wide weather arrivals erase native method restrictions",()=>{
 const rule={...row("restricted",703,[719]),callerGroups:["cave"]};
 const data=loc(group("grass","Grass",[row("grass",10)],true),group("cave","Surfing",[row("cave",10)]),group("weather","Weather SOS",[row("rain",703)]),group("sos","SOS Calls",[rule]));
 expect(eligibleRows(data,["sos","weather-sos"]).map(r=>r.speciesId)).not.toContain(719);
 const shown=guideEncounters(data,["sos","weather-sos","surfing"]);
 expect(guideCalls(shown[0].sos).map(n=>n.call.row.speciesId)).toEqual([703]);
 expect(guideCalls(shown[1].sos).map(n=>n.call.row.speciesId)).toEqual([703,719]);
});

it("restricts actual canyon Diancie and Sableye to both documented cave methods",()=>{
 const data=ENCOUNTERS_BY_MODE["photonic-prismatic"].islands.flatMap(i=>i.locations).find(l=>l.id==="poni-island/vast-poni-canyon")!;
 const roots=guideEncounters(data,["sos"]).filter(e=>e.row.speciesId===703);
 expect(roots).toHaveLength(4);
 for(const entry of roots)expect(guideCalls(entry.sos).filter(n=>[719,302].includes(n.call.row.speciesId!)).map(n=>n.call.row.speciesId)).toEqual(entry.group.name.startsWith("Cave")?[719,302]:[]);
});


it("does not let a locked embedded scope disable unrelated documented active calls",()=>{
 const locked={...row("locked",703,[719]),callerGroups:["cave"]};
 const data=loc(group("grass","Grass",[row("grass",10)],true),group("cave","Surfing",[locked]),group("sos","SOS Calls",[row("ordinary",10,[20])]));
 const root=guideEncounters(data,["sos"],true)[0];expect(root.sos[0].eligible).toBe(true);
});

it("fails closed for empty and unknown explicit scopes without mutating sources",()=>{
 for(const callerGroups of [[],["unknown"]]){
  const rule={...row("restricted",703,[719]),callerGroups};const data=loc(group("grass","Grass",[row("native",703)],true),group("sos","SOS Calls",[rule]));const before=structuredClone(data);
  expect(projectEncounters(data,["sos"]).calls).toEqual([]);expect(data).toEqual(before);
 }
});
