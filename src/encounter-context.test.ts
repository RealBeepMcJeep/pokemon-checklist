import { expect, it } from "vitest";
import * as naming from "./encounter-names";
it("retains an explicitly documented ability identity without inventing a battle form", () => {
  const row = {speciesId:658,speciesName:"Greninja",ability:"Battle Bond"};
  expect(naming.encounterName(row,"Greninja")).toBe("Greninja (Battle Bond)");
  expect(naming.encounterViewContext(row,"Greninja"))
    .toEqual({id:658,name:"Greninja (Battle Bond)",detailKey:"658:ability-battlebond"});
});
it("never infers an exact form from pooled lists or changes source metadata", () => {
  const row = Object.freeze({speciesId:585,speciesName:"Deerling (Spring / Summer)",forms:["spring","summer"]});
  const before = JSON.stringify(row);
  expect(naming.encounterViewContext(row,"Deerling")).toEqual({id:585,name:"Deerling (Spring / Summer)"});
  expect(JSON.stringify(row)).toBe(before);
  expect(naming.encounterViewContext({speciesId:25,speciesName:"Pikachu"},"Pikachu")).toBeUndefined();
  expect(naming.encounterViewContext({speciesId:null,speciesName:"All"},"All")).toBeUndefined();
});
it("creates a read-only exact encounter view independently of collection tracking", () => {
  expect(typeof naming.encounterViewContext).toBe("function");
  expect(naming.encounterViewContext({speciesId:479,speciesName:"Rotom (Frost)",form:"frost"},"Rotom"))
    .toEqual({id:479,name:"Rotom (Frost)",detailKey:"479:frost"});
});
