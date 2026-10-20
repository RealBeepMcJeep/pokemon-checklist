import { expect, test, devices } from "@playwright/test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";
for (const width of [360,412]) {
 test(`C lifecycle and labeled compact counters at ${width}px`, async ({page}, info) => {
  await page.setViewportSize({width,height:844});
  await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
  await expect(page.locator("details.location[open] > summary").first()).toBeFocused();
  await page.evaluate(()=>scrollTo(0,0));
  await expect(page.locator(".app-header")).not.toHaveClass(/is-scrolled/);
  await expect(page.locator(".mobile-identity")).toHaveCSS("opacity","1");
  // One layout snapshot: separate protocol calls can straddle a scroll update.
  const { topCounts, topCommands } = await page.evaluate(() => ({
    topCounts: document.querySelector("#overall-text")!.getBoundingClientRect().toJSON(),
    topCommands: document.querySelector("#tools-toggle")!.getBoundingClientRect().toJSON(),
  }));
  expect(topCounts!.y).toBeGreaterThanOrEqual(topCommands!.y + topCommands!.height);
  await page.screenshot({path:info.outputPath(`C-${width}-top.png`)});
  await page.evaluate(()=>scrollTo(0,500));
  await expect(page.locator(".app-header")).toHaveClass(/is-scrolled/);
  await expect(page.locator(".mobile-identity")).toHaveCSS("opacity","0");
  await expect(page.locator("#overall-text")).toHaveText("0 / 807");
  await expect(page.locator(".app-header progress")).toHaveCount(1);
  for (const selector of [".mobile-mode","#sidebar-toggle","#tools-toggle","#header-settings-toggle"]) {
   const box = await page.locator(selector).boundingBox(); expect(box!.width).toBeGreaterThanOrEqual(44); expect(box!.height).toBeGreaterThanOrEqual(44);
  }
  await page.screenshot({path:info.outputPath(`C-${width}-scrolled.png`)});
  await page.locator("#header-settings-toggle").click();
  await expect(page.locator("#header-settings-panel")).toBeVisible();
  await expect(page.locator("body")).toHaveCSS("overflow","hidden");
  await page.screenshot({path:info.outputPath(`C-${width}-settings.png`)});
  await page.locator("#build-version").scrollIntoViewIfNeeded();
  await page.screenshot({path:info.outputPath(`C-${width}-footer.png`)});
  await page.keyboard.press("Escape");
  await expect(page.locator("#header-settings-toggle")).toBeFocused();
  await page.locator("#tools-toggle").click();
  await expect(page.locator("dialog[open]")).toHaveCount(1);
  await expect(page.locator("#tools-panel")).toBeVisible();
  await page.keyboard.press("Escape");
  await page.locator("#sidebar-toggle").click();
  await expect(page.locator("#pokedex")).toHaveClass(/drawer-open/);
  await page.keyboard.press("Escape");
  await page.locator("#header-settings-toggle").click();
  await page.setViewportSize({width:1440,height:900});
  await expect(page.locator("#header-settings-panel")).not.toBeVisible();
  await expect(page.locator("body")).not.toHaveCSS("overflow","hidden");
  await expect(page.locator("#mode-select")).toBeVisible();
  await expect(page.locator(".brand #build-version")).toBeVisible();
  await page.screenshot({path:info.outputPath("C-desktop-1440.png")});
  await page.setViewportSize({width,height:844});
  await page.evaluate(()=>scrollTo(0,0));
  await expect(page.locator(".app-header")).not.toHaveClass(/is-scrolled/);
  await expect(page.locator(".mobile-identity")).toHaveCSS("opacity","1");
 });
}
test("opening mobile Settings is network silent with a mobile user agent", async ({browser}, info)=>{
 const context = await browser.newContext({...devices["Pixel 7"],baseURL:info.project.use.baseURL as string|undefined});
 const page = await context.newPage(); const requests:string[]=[];
 page.on("request",r=>{if (/^https?:/.test(r.url())&&!/^https?:\/\/(localhost|127\.0\.0\.1)(:|\/)/.test(r.url()))requests.push(r.url());});
 await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
 await page.locator("#header-settings-toggle").click(); await expect(page.locator("#sync-signin")).toBeVisible();
 await page.waitForTimeout(1200); expect(requests).toEqual([]); await context.close();
});
