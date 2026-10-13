import { describe, expect, it } from "vitest";
import { ENCOUNTERS_BY_MODE } from "./data";
import { catchNowRows, validateState, STATE_VERSION } from "./domain";
import { entriesFromState, stateFromDocument, diffEntries } from "./sync/records";
import * as state from "./state";
import { pendingEntries } from "./sync/outbox";

describe("encounter unlock eligibility", () => {
  it("Tauros adds its gated species once without changing the baseline rows", () => {
    const location = ENCOUNTERS_BY_MODE["photonic-prismatic"].islands[0].locations.find(
      location => location.groups.some(group => /Tauros/i.test(group.name)),
    )!;
    const original = catchNowRows(location);
    const expected = new Set(original.map(row => row.speciesId));
    for (const group of location.groups.filter(group => /Tauros/i.test(group.name))) {
      for (const row of group.encounters) if (row.speciesId) expected.add(row.speciesId);
    }
    const unlocked = Reflect.apply(catchNowRows, undefined, [location, ["tauros"]]);
    expect(unlocked.map(row => row.speciesId).sort()).toEqual([...expected].sort());
    expect(catchNowRows(location)).toBe(original);
  });
  it("SOS allies require an accessible caller, including fishing access", () => {
    const row = (id: number, allies: number[] = []) => ({id: String(id), speciesId: id, allies: allies.map(id => ({speciesId:id,name:String(id),species:String(id)}))});
    const location = {id:"fixture",name:"Fixture",order:1,groups:[
      {id:"grass",name:"Grass",category:"regular" as const,encounters:[row(1)]},
      {id:"fish",name:"Fishing",category:"return-later" as const,encounters:[row(10,[12])]},
      {id:"sos",name:"SOS Calls",category:"return-later" as const,encounters:[row(10,[11])]},
    ]};
    expect(catchNowRows(location,["sos"]).map(r=>r.speciesId)).toEqual([1]);
    expect(catchNowRows(location,["fishing","sos"]).map(r=>r.speciesId).sort()).toEqual([1,10,11,12]);
  });
  it("weather SOS needs both switches and a reachable wild encounter; surfing supplies access", () => {
    const row = (id:number) => ({id:String(id),speciesId:id,allies:[]});
    const location = {id:"weather",name:"Weather",order:1,groups:[
      {id:"surf",name:"Surfing",category:"return-later" as const,encounters:[row(10)]},
      {id:"weather",name:"Weather SOS",category:"return-later" as const,encounters:[row(20)]},
      {id:"chain",name:"SOS Calls",category:"return-later" as const,encounters:[{...row(20),allies:[{speciesId:21,name:"Ally",species:"ally"}]}]},
    ]};
    expect(catchNowRows(location,["sos","weather-sos"])).toEqual([]);
    expect(catchNowRows(location,["surfing","weather-sos"]).map(r=>r.speciesId)).toEqual([10]);
    expect(catchNowRows(location,["surfing","sos","weather-sos"]).map(r=>r.speciesId)).toEqual([10,20,21]);
  });
  it("v4 persists exact unlocks and migrates v3 without altering catches", () => {
    const old = {schemaVersion:3,species:{"25":"caught"},forms:{},starred:[25],settings:{forms:false,mode:"photonic-prismatic"}};
    const migrated = validateState(old,new Set([25]),new Set());
    expect(STATE_VERSION).toBe(4);
    expect(migrated.settings).toEqual({forms:false,mode:"photonic-prismatic",unlocks:[]});
    expect(migrated.species).toEqual(old.species);
    const current = {...migrated,settings:{...migrated.settings,unlocks:["tauros","sos"]}};
    expect(validateState(current,new Set([25]),new Set()).settings).toEqual(current.settings);
    expect(()=>validateState({...old,settings:current.settings},new Set([25]),new Set())).toThrow();
    expect(()=>validateState({...current,settings:{...current.settings,unlocks:["tauros","tauros"]}},new Set([25]),new Set())).toThrow();
  });
  it("sync round-trips unlocks and disabling emits off, without changing species", () => {
    const state = validateState({schemaVersion:4,species:{"25":"caught"},forms:{},starred:[],settings:{forms:false,mode:"photonic-prismatic",unlocks:["tauros"]}},new Set([25]),new Set());
    const records = entriesFromState(state,100,"fixture");
    expect(records["setting:unlock:tauros"]?.s).toBe("on");
    const restored = stateFromDocument({schema:1,records,updatedAt:100},new Set([25]),new Set());
    expect(restored).toEqual(state);
    const off = {...state,settings:{...state.settings,unlocks:[]}};
    expect(diffEntries(records,entriesFromState(off,101,"fixture"))["setting:unlock:tauros"].s).toBe("off");
  });
  it("state exports unlocks and setting one preserves species and read-only safety", () => {
    expect(state.defaultState().settings).toHaveProperty("unlocks",[]);
    state.applyState(state.defaultState());
    state.applyState({...state.defaultState(),species:{"25":"caught"}});
    Reflect.get(state,"setUnlock")("tauros",true);
    expect(state.exportState().settings.unlocks).toEqual(["tauros"]);
    expect(state.exportState().species["25"]).toBe("caught");
    state.readOnly.value = "outdated";
    Reflect.get(state,"setUnlock")("tauros",false);
    expect(state.exportState().settings.unlocks).toEqual(["tauros"]);
    state.readOnly.value = null;
    state.applyState(state.defaultState());
  });
  it("migration does not invent an unlock-clear against a forward-compatible server base", () => {
    const old = validateState({schemaVersion:3,species:{},forms:{},starred:[],settings:{forms:false,mode:"photonic-prismatic"}},new Set(),new Set());
    const base = {schema:1 as const,records:{"setting:unlock:tauros":{s:"on",at:10,by:"fixture"}},updatedAt:10};
    const pending = Reflect.apply(pendingEntries,undefined,[base,old,20,"fixture",true]);
    expect(pending).not.toHaveProperty("setting:unlock:tauros");
    expect(pendingEntries(base,old,20,"fixture")["setting:unlock:tauros"].s).toBe("off");
  });
  it("upgrades a legacy v3 last-good copy even when its primary save is corrupt", () => {
    const values = new Map<string,string>();
    const old = {schemaVersion:3,species:{"25":"caught"},forms:{},starred:[],settings:{forms:false,mode:"photonic-prismatic"}};
    values.set("pokemon-checklist-state-v3","corrupt legacy JSON");
    values.set("pokemon-checklist-state-v3:last-good",JSON.stringify(old));
    const previous = Object.getOwnPropertyDescriptor(globalThis,"localStorage");
    Object.defineProperty(globalThis,"localStorage",{configurable:true,value:{getItem:(k:string)=>values.get(k)??null,setItem:(k:string,v:string)=>values.set(k,v),removeItem:(k:string)=>values.delete(k)}});
    try {
      state.applyState(state.defaultState());state.initializeState();
      expect(state.exportState().species["25"]).toBe("caught");
      expect(values.get("pokemon-checklist-state-v3")).toBe("corrupt legacy JSON");
      expect(JSON.parse(values.get("pokemon-checklist-state-v4")!).species["25"]).toBe("caught");
    } finally {
      if(previous) Object.defineProperty(globalThis,"localStorage",previous);
      else Reflect.deleteProperty(globalThis,"localStorage");
      state.applyState(state.defaultState());
    }
  });
});
