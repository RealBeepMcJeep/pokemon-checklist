import {expect,test} from "@playwright/test";
import {pathToFileURL} from "node:url";
import {resolve} from "node:path";
import {readFileSync} from "node:fs";
import type {EncounterData} from "../src/types";
const data = JSON.parse(readFileSync(resolve("data/encounters.json"),"utf8")) as EncounterData;

for (const width of [360,1440]) test(`saved Tauros unlock reveals backtracking at ${width}px`,async({page},info)=>{
  await page.setViewportSize({width,height:900});
  const loc=data.islands[0].locations.find(l=>l.groups.some(g=>/Tauros/i.test(g.name)))!;
  const species=Object.fromEntries(loc.groups.filter(g=>g.category==="regular").flatMap(g=>g.encounters).filter(r=>r.speciesId).map(r=>[String(r.speciesId),"caught"]));
  const errors:string[]=[];page.on("pageerror",e=>errors.push(e.message));
  await page.goto(info.project.name==="standalone-file"?pathToFileURL(resolve("index.html")).href:"/");
  // Seed once after origin initialization. An early file:// init hook can open
  // transient Chromium storage; replaying that hook also confounds reload tests.
  await page.evaluate(({species})=>{
    localStorage.setItem("pokemon-checklist-state-v3",JSON.stringify({schemaVersion:3,species,forms:{},starred:[],settings:{forms:false,mode:"photonic-prismatic"}}));
  },{species});
  await page.reload();
  const summary=page.locator(`[data-location-progress="${loc.id}"]`);
  await expect(summary).toContainText("Complete");
  await page.locator("#header-settings-toggle").click();
  const settings=page.locator("#header-settings-panel");
  await expect(settings.getByRole("checkbox")).toHaveCount(5);
  await settings.getByLabel("Tauros Charge",{exact:true}).check();
  await settings.getByRole("button",{name:"Close settings"}).click();
  await expect(summary.locator("[data-backtrack]")).toBeVisible();
  const area=page.locator(`[data-location-id="${loc.id}"]`);
  if (!(await area.evaluate(el=>(el as HTMLDetailsElement).open))) await area.locator("summary").click();
  await expect(area.locator(".encounter-group").filter({hasText:"Tauros"}).locator(".group-tag")).toHaveText("Catch now");
  const saved=await page.evaluate(()=>JSON.parse(localStorage.getItem("pokemon-checklist-state-v4")!));
  expect(saved.species).toEqual(species);expect(saved.settings.unlocks).toEqual(["tauros"]);
  for (let reload=0; reload<3; reload++) {
    await page.reload();
    await expect.poll(()=>page.evaluate(()=>JSON.parse(localStorage.getItem("pokemon-checklist-state-v4")!).settings.unlocks)).toEqual(["tauros"]);
    expect(await page.evaluate(()=>JSON.parse(localStorage.getItem("pokemon-checklist-state-v4")!).species)).toEqual(species);
    await page.locator("#header-settings-toggle").click();
    await expect(settings.getByLabel("Tauros Charge",{exact:true})).toBeChecked();
    if (reload<2) await settings.getByRole("button",{name:"Close settings"}).click();
  }
  await settings.getByLabel("Tauros Charge",{exact:true}).uncheck();
  await settings.getByRole("button",{name:"Close settings"}).click();
  await expect(summary.locator("[data-backtrack]")).toHaveCount(0);
  expect(errors).toEqual([]);
});
