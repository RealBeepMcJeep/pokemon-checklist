import {test,expect,type Page} from "@playwright/test";
import {pathToFileURL} from "node:url";import {resolve} from "node:path";
async function open(page:Page,p:string){await page.goto(p==="standalone-file"?pathToFileURL(resolve("index.html")).href:"/");await page.locator("#tools-toggle").click();}
test("neighbors wrap, forms follow species and rail keyboard works",async({page},info)=>{
 await open(page,info.project.name);await page.locator("#catch-species-name").click();await page.locator("#catch-species").fill("Bulbasaur");await page.getByRole("option",{name:"Bulbasaur",exact:true}).click();
 await page.locator("#catch-species-rail button").first().click();await expect(page.locator("#catch-species-name")).toHaveText("Zeraora");
 await page.locator("#catch-species-rail button").last().click();await expect(page.locator("#catch-species-name")).toHaveText("Bulbasaur");
 await page.locator("#catch-species-name").click();await page.locator("#catch-species").fill("Minior");await page.getByRole("option",{name:"Minior",exact:true}).click();
 await page.locator("#catch-species-rail .selected").focus();await page.keyboard.press("ArrowRight");await expect(page.locator("#catch-species-name")).toHaveText("Minior — Form 7");await expect(page.locator(".catch-form-note")).toContainText("base-species icon");
 await page.locator("#catch-ball-rail button").first().click();await expect(page.locator("#catch-ball-name")).toHaveText("Beast Ball");await page.locator("#catch-ball-rail .selected").press("ArrowRight");await expect(page.locator("#catch-ball-name")).toHaveText("Poké Ball");
});
test("real horizontal touch swipes advance both bounded rails",async({browser},info)=>{
 const context=await browser.newContext({viewport:{width:390,height:844},hasTouch:true,isMobile:true});const page=await context.newPage();await open(page,info.project.name);const cdp=await context.newCDPSession(page);
 for(const kind of ["species","ball"]){const rail=page.locator("#catch-"+kind+"-rail");await rail.scrollIntoViewIfNeeded();const b=(await rail.boundingBox())!;const x=b.x+b.width*.8,y=b.y+b.height/2;const before=await page.locator("#catch-"+kind+"-name").textContent();await cdp.send("Input.dispatchTouchEvent",{type:"touchStart",touchPoints:[{x,y}]});for(let n=1;n<=6;n++){await cdp.send("Input.dispatchTouchEvent",{type:"touchMove",touchPoints:[{x:x-n*25,y}]});await page.waitForTimeout(20);}await cdp.send("Input.dispatchTouchEvent",{type:"touchEnd",touchPoints:[]});await expect(page.locator("#catch-"+kind+"-name")).not.toHaveText(before!);await expect(rail.locator("button")).toHaveCount(3);}
 await context.close();
});
test("compact status chips expose mutually exclusive multipliers and colored chance tiers",async({page},info)=>{
 await open(page,info.project.name);await page.getByRole("button",{name:"Asleep ×2.5",exact:true}).click();await page.getByRole("button",{name:"Paralyzed ×1.5",exact:true}).click();await expect(page.getByRole("button",{name:"Asleep ×2.5",exact:true})).toHaveAttribute("aria-pressed","false");await expect(page.locator("#catch-breakdown")).toContainText("Status ×1.5");await page.getByRole("button",{name:"Paralyzed ×1.5",exact:true}).click();await expect(page.locator("#catch-breakdown")).toContainText("Status ×1");await expect(page.locator("#catch-result")).toContainText("Moderate");await expect(page.locator(".catch-factors")).toContainText("HP 100/100");
 for(const b of await page.locator(".catch-status button").all()){expect(await b.evaluate(el=>el.getBoundingClientRect().height)).toBeGreaterThanOrEqual(44);}
});
