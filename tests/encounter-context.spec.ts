import { expect, test, type Page } from "@playwright/test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";
const KEY = "pokemon-checklist-state-v5";
async function setup(page: Page, project: string) {
  const errors: string[] = [];
  page.on("pageerror", e => errors.push(e.message));
  page.on("console", e => { if (e.type() === "error") errors.push(e.text()); });
  await page.goto(project === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
  await page.evaluate(key => {
    localStorage.clear();
    localStorage.setItem(key, JSON.stringify({schemaVersion:5, species:{52:"caught",479:"caught"}, forms:{"52:alolan":"caught"}, starred:[479], starredForms:["52:alolan"], settings:{forms:false,mode:"photonic-prismatic",unlocks:["sos"]}}));
  }, KEY);
  await page.reload();
  return errors;
}
const records = (page: Page) => page.evaluate(key => {
  const {species,forms,starred,starredForms} = JSON.parse(localStorage.getItem(key)!);
  return {species,forms,starred,starredForms};
}, KEY);
async function stablePanel(page: Page) {
  // A visible drawer can still be half offscreen during its opening transition.
  await expect.poll(async () => {
    const box = await page.locator("#pokedex").boundingBox();
    return !!box && box.x >= -1 && box.x + box.width <= page.viewportSize()!.width + 1;
  }).toBe(true);
  await expect(page.locator("#dex-selection")).toBeFocused();
}
async function openArea(page: Page,id: string) {
  const loc = page.locator(`[data-location-id="${id}"]`);
  if (!await loc.evaluate(e => (e as HTMLDetailsElement).open)) await loc.locator("summary").click();
  return loc;
}
for (const width of [390,1440]) test.describe(`encounter detail context ${width}px`, () => {
  test.use({viewport:{width,height:950},isMobile:width===390,hasTouch:width===390});
  test("cosmetic encounter details keep exact facts and explicitly scope species information", async ({page},info) => {
    const errors = await setup(page,info.project.name);
    const before = await records(page);
    const loc = await openArea(page,"ulaula-island/thrifty-megamart");
    await loc.getByRole("button",{name:"Rotom (Frost)",exact:true}).click();
    const panel = page.locator("#dex-selection");
    await expect(panel.locator(".selected-title")).toContainText("Rotom (Frost)");
    await expect(panel.locator(".encounter-facts").getByLabel("Types: Electric and Ice",{exact:true})).toBeVisible();
    await expect(panel.locator(".encounter-facts").getByLabel("Types: Electric and Ghost",{exact:true})).toHaveCount(0);
    await expect(panel.locator(".selected-title")).toContainText("Species status");
    await expect(panel.locator(".encounter-context-note")).toContainText("species-wide");
    await expect(panel.getByText("Popular moves",{exact:true})).toHaveCount(0);
    await expect(panel.locator(".location-links > strong")).toContainText("Species locations (all forms)");
    await stablePanel(page);
    await page.screenshot({path:info.outputPath(`${width}-rotom-frost-context.png`)});
    for (const mode of ["sun","photonic-prismatic"]) {
      if (width===390) await page.locator("#drawer-close").click();
      if (!await page.locator("#mode-select").isVisible()) await page.locator("#header-settings-toggle").click();
      await page.locator("#mode-select").selectOption(mode);
      if (width===390) {
        await page.getByRole("button",{name:"Close settings",exact:true}).click();
        await page.locator("#sidebar-toggle").click();
      }
      await expect(panel.locator(".selected-title")).toContainText("Rotom (Frost)");
      await expect(panel.locator(".location-links > strong")).toContainText("Species locations (all forms)");
    }
    await panel.getByRole("button",{name:"Show species information",exact:true}).click();
    await expect(panel.locator(".selected-title")).not.toContainText("Frost");
    await expect(panel.getByLabel("Types: Electric and Ghost",{exact:true}).first()).toBeVisible();
    if (width===390) await page.locator("#drawer-close").click();
    await page.locator("#header-settings-toggle").click();
    await page.getByLabel("Weather SOS",{exact:true}).check();
    await page.getByRole("button",{name:"Close settings",exact:true}).click();
    const garden = await openArea(page,"ulaula-island/malie-garden");
    await garden.getByRole("button",{name:"Greninja (Battle Bond)",exact:true}).first().click();
    await expect(panel.locator(".selected-title")).toContainText("Greninja (Battle Bond)");
    await expect(panel.locator(".encounter-context-note")).toContainText("species-wide");
    if (width===390) await page.locator("#drawer-close").click();
    await page.locator("#header-settings-toggle").click();
    await page.getByLabel("Weather SOS",{exact:true}).uncheck();
    await page.getByRole("button",{name:"Close settings",exact:true}).click();
    const deer = await openArea(page,"akala-island/route-6");
    await deer.getByRole("button",{name:"Deerling (Spring / Summer)",exact:true}).first().click();
    await expect(panel.locator(".selected-title")).toContainText("Deerling (Spring / Summer)");
    await expect(panel.locator(".encounter-facts-missing")).toBeVisible();
    await expect(panel.getByText("Popular moves",{exact:true})).toHaveCount(0);
    await expect(panel.locator(".encounter-facts .pokemon-facts")).toHaveCount(0);
    await expect(panel.locator(".evolution-controls")).toHaveCount(0);
    await stablePanel(page);
    await page.screenshot({path:info.outputPath(`${width}-deerling-pool-context.png`)});
    await panel.getByRole("button",{name:"Show species information",exact:true}).click();
    await expect(panel.locator(".evolution-controls")).toBeVisible();
    expect(await records(page)).toEqual(before);
    expect(errors).toEqual([]);
  });
  test("explicit Kanto guide selection survives tracking off without changing generic Pokédex defaults", async ({page},info) => {
    const errors = await setup(page,info.project.name);
    const before = await records(page);
    const loc = await openArea(page,"melemele-island/trainers-school");
    await loc.getByRole("button",{name:"Meowth (Kanto)",exact:true}).click();
    const panel = page.locator("#dex-selection");
    await expect(panel.locator(".selected-title")).toContainText("Meowth (Kanto)");
    await expect(panel.getByLabel("Types: Normal",{exact:true}).first()).toBeVisible();
    await expect(panel.locator(".selected-title .status-button")).toHaveAttribute("aria-label",/Kanto.*Not caught/);
    const kantoStage = panel.locator('.evolution-stage[data-target="52:kanto"]');
    await expect(kantoStage).toHaveCount(1);
    await expect(kantoStage.locator(".status-button")).toHaveAttribute("aria-label",/Kanto.*Not caught/);
    await expect(panel.locator('.evolution-stage[data-target="53:kanto"]')).toHaveCount(1);
    await panel.locator('.evolution-stage[data-target="53:kanto"] .evolution-name').click();
    await expect(panel.locator(".selected-title")).toContainText("Persian (Kanto)");
    await panel.locator('.evolution-stage[data-target="52:kanto"] .evolution-name').click();
    await expect(panel.locator(".selected-title")).toContainText("Meowth (Kanto)");
    await stablePanel(page);
    await page.screenshot({path:info.outputPath(`${width}-kanto-context-tracking-off.png`)});
    for (const tracked of [true,false]) {
      if (width===390) await page.locator("#drawer-close").click();
      if (!await page.locator("#forms-toggle").isVisible()) await page.locator("#header-settings-toggle").click();
      await page.locator("#forms-toggle").click();
      if (width===390) {
        await page.getByRole("button",{name:"Close settings",exact:true}).click();
        await page.locator("#sidebar-toggle").click();
      }
      await expect(panel.locator(".selected-title")).toContainText("Meowth (Kanto)");
      expect(await page.evaluate(key => JSON.parse(localStorage.getItem(key)!).settings.forms,KEY)).toBe(tracked);
      expect(await records(page)).toEqual(before);
    }
    const generic = page.locator('.dex-select[data-species="52"]');
    await expect(generic).toHaveCount(1);
    await generic.click();
    await expect(panel.locator(".selected-title")).not.toContainText("Kanto");
    await expect(panel.locator(".selected-title")).not.toContainText("Alolan");
    await expect(panel.getByLabel("Types: Dark",{exact:true}).first()).toBeVisible();
    expect(await records(page)).toEqual(before);
    expect(errors).toEqual([]);
  });
});
