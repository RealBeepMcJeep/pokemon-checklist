import { expect,test } from "@playwright/test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";
const KEY="pokemon-checklist-state-v5";
const fixture={schemaVersion:5,species:{703:"caught",719:"seen"},forms:{"745:dusk":"caught"},starred:[703],starredForms:[],settings:{forms:true,mode:"photonic-prismatic",unlocks:["sos"]}};
for(const width of [390,1440])test.describe(`canyon caller method ${width}px`,()=>{
 test.use({viewport:{width,height:950},isMobile:width===390,hasTouch:width===390});
 test("only documented cave Carbink rows show their SOS allies",async({page},info)=>{
  const errors:string[]=[];page.on("pageerror",e=>errors.push(e.message));page.on("console",e=>{if(e.type()==="error")errors.push(e.text());});
  await page.goto(info.project.name==="standalone-file"?pathToFileURL(resolve("index.html")).href:"/");
  await page.evaluate(v=>{localStorage.clear();localStorage.setItem("pokemon-checklist-state-v5",JSON.stringify(v));},fixture);await page.reload();
  const loc=page.locator('[data-location-id="poni-island/vast-poni-canyon"]');if(!await loc.evaluate(e=>(e as HTMLDetailsElement).open))await loc.locator("summary").click();
  for(const tracking of [true,false]){
   if(!tracking){if(width===390)await page.locator("#header-settings-toggle").click();await page.locator("#forms-toggle").click();if(width===390)await page.getByRole("button",{name:"Close settings",exact:true}).click();}
   for(const [suffix,rate,cave] of [["grass-1-1/6","10%",false],["grass-2-2/6","10%",false],["cave-3/5","20%",true],["caves-with-water-4/2","20%",true]] as const){
    const id=("encounter-poni-island/vast-poni-canyon/"+suffix).replace(/[^a-zA-Z0-9]+/g,"-");const row=loc.locator(`[id="${id}"]`);
    await expect(row.locator(".species-name .guide-pokemon-link").first()).toHaveText("Carbink");await expect(row.locator("td").first()).toHaveText(cave ? `Carbink · ${rate}` : rate);
    await expect(row.locator(".sos-identity .guide-pokemon-link")).toHaveText(cave?["Diancie","Sableye"]:[]);
    if(cave){expect(await row.locator(".inline-sos").innerText()).not.toContain("%");await expect(row.locator(".sos-legend")).toContainText("not documented");}
    if(!tracking){await row.evaluate(e=>{const h=document.querySelector("header")!.getBoundingClientRect();window.scrollBy(0,e.getBoundingClientRect().top-h.bottom-16);});await page.evaluate(()=>new Promise<void>(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>r()))));await expect(row.locator(".species-name .guide-pokemon-link").first()).toBeInViewport({ratio:0.98});await page.screenshot({path:info.outputPath(`${width}-${suffix.replaceAll("/","-")}.png`)});}
   }
   expect(await page.evaluate(key=>JSON.parse(localStorage.getItem(key)!),KEY)).toEqual({...fixture,settings:{...fixture.settings,forms:tracking}});
  }
  if(width===390)await page.locator("#header-settings-toggle").click();else await page.locator("#header-settings-toggle").click();await page.getByLabel("SOS Calls",{exact:true}).uncheck();await page.getByRole("button",{name:"Close settings",exact:true}).click();
  await expect(loc.locator(".inline-sos")).toHaveCount(0);
  const after=await page.evaluate(key=>JSON.parse(localStorage.getItem(key)!),KEY);for(const key of ["species","forms","starred","starredForms"] as const)expect(after[key]).toEqual(fixture[key]);expect(errors).toEqual([]);
 });
});
