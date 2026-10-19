import { expect,test } from "@playwright/test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";
const KEY="pokemon-checklist-state-v5";
for(const width of [390,1440]) test.describe(`source pool audit ${width}px`,()=>{
  test.use({viewport:{width,height:950},isMobile:width===390,hasTouch:width===390});
  test("pooled native variants and documented SOS identities stay explicit without expanding records",async({page},info)=>{
    const errors:string[]=[];
    page.on("pageerror",e=>errors.push(e.message));page.on("console",e=>{if(e.type()==="error")errors.push(e.text());});
    await page.goto(info.project.name==="standalone-file"?pathToFileURL(resolve("index.html")).href:"/");
    await page.evaluate(key=>{localStorage.clear();localStorage.setItem(key,JSON.stringify({schemaVersion:5,species:{744:"caught",745:"caught"},forms:{"744:owntempo":"caught","745:midnight":"caught","710:small":"caught","710:supersize":"seen"},starred:[744,745],starredForms:[],settings:{forms:true,mode:"photonic-prismatic",unlocks:["sos"]}}));},KEY);
    await page.reload();
    const before=await page.evaluate(key=>JSON.parse(localStorage.getItem(key)!),KEY);
    const cases=[
      {area:"melemele-island/ten-carat-hill",name:"Rockruff (Normal / Own Tempo)",count:1,rate:"20%",allies:["Rockruff (Own Tempo)"]},
      {area:"akala-island/memorial-hill",name:"Pumpkaboo (Small / Average / Large / Super Size)",count:1,rate:"30%",allies:["Pumpkaboo (Super Size)"]},
      {area:"poni-island/vast-poni-canyon",name:"Lycanroc (Midday: Day / Midnight: Night)",count:2,rate:"20%",allies:["Lycanroc (Dusk)"]},
    ];
    for(const tracking of [true,false]){
      if(!tracking){if(width===390)await page.locator("#header-settings-toggle").click();await page.locator("#forms-toggle").click();if(width===390)await page.getByRole("button",{name:"Close settings",exact:true}).click();}
      for(const c of cases){
        const loc=page.locator(`[data-location-id="${c.area}"]`);if(!await loc.evaluate(e=>(e as HTMLDetailsElement).open))await loc.locator("summary").click();
        const rows=loc.locator("tr").filter({has:page.getByRole("button",{name:c.name,exact:true})});await expect(rows).toHaveCount(c.count);
        for(const row of await rows.all()){
          await expect(row.locator(".species-name .guide-pokemon-link").first()).toHaveText(c.name);
          // A pooled identity must not inherit one variant's competitive grade.
          await expect(row.locator(".species-name .pokemon-facts")).toHaveCount(0);
          if(c.allies.length)await expect(row.locator(".sos-identity .pokemon-facts")).toHaveCount(1);
          await expect(row.locator("td").first()).toHaveText(c.rate);
          await expect(row.locator(".sos-identity .guide-pokemon-link")).toHaveText(c.allies);
          if(c.name.startsWith("Rockruff")) await expect(row.locator(".inline-sos .condition")).toHaveText("Caller: Rockruff (Own Tempo) only");
          if(c.allies.length){await expect(row.locator(".sos-legend")).toContainText("not documented");expect(await row.locator(".inline-sos").innerText()).not.toContain("%");}
          if(!tracking){
            await expect(row.locator(".form-status")).toHaveCount(0);
            await row.evaluate(el=>{const h=document.querySelector("header")!.getBoundingClientRect();window.scrollBy(0,el.getBoundingClientRect().top-h.bottom-16);});
            await page.evaluate(()=>new Promise<void>(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>r()))));
            const label=row.locator(".species-name .guide-pokemon-link").first();await expect(label).toBeInViewport({ratio:0.98});expect(await label.evaluate(e=>e.clientWidth>0&&e.scrollWidth<=e.clientWidth+1)).toBe(true);
            await page.screenshot({path:info.outputPath(`${width}-${c.area.split("/").pop()}-source-pool.png`)});
          }
        }
      }
    }
    await page.locator("#header-settings-toggle").click();await page.getByLabel("SOS Calls",{exact:true}).uncheck();await page.getByRole("button",{name:"Close settings",exact:true}).click();
    for(const c of cases)await expect(page.locator(`[data-location-id="${c.area}"] .inline-sos`)).toHaveCount(0);
    const after=await page.evaluate(key=>JSON.parse(localStorage.getItem(key)!),KEY);
    for(const key of ["species","forms","starred","starredForms"])expect(after[key]).toEqual(before[key]);
    expect(Object.keys(after).sort()).toEqual(Object.keys(before).sort());expect(errors).toEqual([]);
  });
});
