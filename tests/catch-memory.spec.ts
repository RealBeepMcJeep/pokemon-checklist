import {test,expect,type Page} from "@playwright/test";
import {pathToFileURL} from "node:url";
import {resolve} from "node:path";
const key="pokemon-checklist-catch-selection-v1";
async function open(page:Page,project:string) {await page.goto(project === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/"); await page.locator("#tools-toggle").click();}
test("selection memory excludes drafts and battle fields",async({page},info)=>{
 await open(page,info.project.name);
 await expect(page.locator("#catch-result")).toContainText("35.19%");
 await page.locator("#catch-species-name").click(); await page.locator("#catch-species").fill("Bulbasaur"); await page.getByRole("option",{name:"Bulbasaur",exact:true}).click();
 await expect.poll(()=>page.evaluate(k=>JSON.parse(localStorage.getItem(k)!),key)).toEqual({id:1,form:0,ball:"Poké Ball"});
 await page.getByLabel("HP remaining (approximate %)").fill("10");
 await page.locator("#catch-species-name").click(); await page.locator("#catch-species").fill("nonsense");
 await expect(page.locator("#catch-result")).toBeVisible();
 await expect.poll(()=>page.evaluate(k=>JSON.parse(localStorage.getItem(k)!),key)).toEqual({id:1,form:0,ball:"Poké Ball"});
 await page.reload();await page.locator("#tools-toggle").click();
 await expect(page.locator("#catch-species-name")).toHaveText("Bulbasaur"); await expect(page.getByLabel("HP remaining (approximate %)")).toHaveValue("100");
});
test("invalid selection and blocked storage give notices without breaking math",async({page},info)=>{
 await open(page,info.project.name); await page.evaluate(k=>localStorage.setItem(k,JSON.stringify({id:9999,form:0,ball:"invented"})),key); await page.reload();await page.locator("#tools-toggle").click();
 await expect(page.locator("#catch-species-name")).toHaveText("Pikachu");await expect(page.locator("#catch-memory-notice")).toContainText("default");
 await page.addInitScript(()=>{Storage.prototype.getItem=function(){throw new Error("blocked")};Storage.prototype.setItem=function(){throw new Error("blocked")}});await page.reload();await page.locator("#tools-toggle").click();await expect(page.locator("#catch-result")).toContainText("35.19%");await expect(page.locator("#catch-memory-notice")).toBeVisible();
});
