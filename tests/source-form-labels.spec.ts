import { expect, test, type Page } from "@playwright/test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";
import { readFile } from "node:fs/promises";

const fixture = {
  schemaVersion: 4, species: { 52: "caught", 479: "caught", 585: "caught", 670: "caught", 710: "seen", 744: "caught", 745: "caught" },
  forms: { "585:autumn": "caught", "585:winter": "seen", "479:heat": "caught", "670:orangeflower": "seen", "744:normal": "seen", "744:owntempo": "caught", "745:dusk": "caught", "745:midnight": "seen", "710:supersize": "seen" },
  starred: [479, 585, 670], settings: { forms: false, mode: "photonic-prismatic", unlocks: ["sos"] },
};
const examples: { area: string; row: string; name: string; rate: string; allies: string[]; pooled?: boolean }[] = [
  { area: "akala-island/route-6", row: "grass-1-1/4", name: "Deerling (Spring / Summer)", rate: "15%", allies: [], pooled: true },
  { area: "akala-island/route-6", row: "grass-2-2/5", name: "Deerling (Spring / Summer)", rate: "15%", allies: [], pooled: true },
  { area: "akala-island/route-6", row: "sos-calls-3/1", name: "Deerling (Spring / Summer)", rate: "—", allies: ["Deerling (Autumn)", "Deerling (Winter)"], pooled: true },
  { area: "ulaula-island/thrifty-megamart", row: "building-1/5", name: "Rotom (Base)", rate: "15%", allies: ["Rotom (Frost)", "Rotom (Heat)"] },
  { area: "ulaula-island/ulaula-meadow", row: "grass-1/2", name: "Floette (Red Flower)", rate: "20%", allies: ["Floette (Orange Flower)", "Floette (White Flower)"] },
  { area: "melemele-island/ten-carat-hill", row: "grass-2/1", name: "Rockruff (Normal / Own Tempo)", rate: "20%", allies: [], pooled: true },
  { area: "akala-island/memorial-hill", row: "all-grass-1/1", name: "Pumpkaboo (Small / Average / Large / Super Size)", rate: "30%", allies: ["Pumpkaboo (Super Size)"], pooled: true },
  { area: "poni-island/vast-poni-canyon", row: "grass-1-1/2", name: "Lycanroc (Midday: Day / Midnight: Night)", rate: "20%", allies: ["Lycanroc (Dusk)"], pooled: true },
  { area: "poni-island/vast-poni-canyon", row: "grass-2-2/2", name: "Lycanroc (Midday: Day / Midnight: Night)", rate: "20%", allies: ["Lycanroc (Dusk)"], pooled: true },
];
const read = (page: Page) => page.evaluate(() => JSON.parse(localStorage.getItem("pokemon-checklist-state-v4")!));
async function area(page: Page, id: string) {
  const loc = page.locator(`[data-location-id="${id}"]`);
  if (!await loc.evaluate(el => (el as HTMLDetailsElement).open)) await loc.locator("summary").click();
  return loc;
}
for (const width of [390, 1440]) test.describe(`source form labels at ${width}px`, () => {
  test.use({ viewport: { width, height: 950 }, isMobile: width === 390, hasTouch: width === 390 });
  test("documented identities remain visible without changing v4 saves or legacy controls", async ({ page }, info) => {
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    await page.goto(process.env.POKEMON_LIVE_URL || (info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "./"));
    // Local-only synthetic state in an isolated signed-out browser context.
    await page.evaluate(value => { localStorage.clear(); localStorage.setItem("pokemon-checklist-state-v4", JSON.stringify(value)); }, fixture);
    await page.reload();
    for (const tracked of [false, true, false]) {
      if (tracked !== (await read(page)).settings.forms) {
        if (!await page.locator("#forms-toggle").isVisible()) await page.locator("#header-settings-toggle").click();
        await page.locator("#forms-toggle").click();
        if (width === 390) await page.getByRole("button", { name: "Close settings", exact: true }).click();
      }
      for (const example of examples) {
        const loc = await area(page, example.area);
        const id = `encounter-${example.area}/${example.row}`.replace(/[^a-zA-Z0-9]+/g, "-");
        const row = loc.locator(`[id="${id}"]`);
        await expect(row).toBeVisible();
        const caller = row.locator("th .guide-pokemon-link").first();
        await expect(caller).toHaveText(example.name);
        await expect(caller).toBeVisible();
        expect(await caller.evaluate(el => el.clientWidth > 0 && el.scrollWidth <= el.clientWidth + 1)).toBe(true);
        await expect(row.locator("th .pokemon-facts")).toHaveCount(example.pooled ? 0 : 1);
        await expect(row.locator(".ally-list .pokemon-facts")).toHaveCount(example.allies.length);
        await expect(row.locator("td").nth(0)).toHaveText(example.rate);
        await expect(row.locator(".ally-list .guide-pokemon-link")).toHaveText(example.allies);
        expect(await row.locator("td").last().innerText()).not.toContain("%");
        if (!tracked) await expect(row.locator(".form-status")).toHaveCount(0);
        if (!tracked && (example.allies.length || example.pooled)) {
          await row.evaluate(el => { const h = document.querySelector("header")!.getBoundingClientRect(); window.scrollBy(0, el.getBoundingClientRect().top - h.bottom - 16); });
          await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
          await expect(caller).toBeInViewport({ ratio: 0.98 });
          expect(await caller.evaluate(el => el.getBoundingClientRect().top >= document.querySelector("header")!.getBoundingClientRect().bottom)).toBe(true);
          for (const ally of await row.locator(".ally-list .guide-pokemon-link").all()) expect(await ally.evaluate(el => el.clientWidth > 0 && el.scrollWidth <= el.clientWidth + 1)).toBe(true);
          await page.screenshot({ path: info.outputPath(`${width}-${example.area.split("/").pop()}-${example.row.replaceAll("/", "-")}-forms-off.png`) });
        }
      }
      const school = await area(page, "melemele-island/trainers-school");
      const kanto = school.locator(".ally-list .guide-pokemon").filter({ has: page.getByRole("button", { name: "Meowth", exact: true }) });
      await expect(kanto.locator(".type-marks")).toHaveAttribute("aria-label", "Types: Normal");
      await expect(kanto.locator(".grade-badge")).toHaveCount(1);
      const firstRoute = await area(page, "melemele-island/route-1");
      const ordinary = firstRoute.locator(".species-name .guide-pokemon").filter({ has: page.getByRole("button", { name: "Pikipek", exact: true }) }).first();
      await expect(ordinary.locator(".type-marks")).toHaveAttribute("aria-label", "Types: Normal and Flying");
      await expect(ordinary.locator(".grade-badge")).toHaveCount(1);
      expect(await read(page)).toEqual({ ...fixture, settings: { ...fixture.settings, forms: tracked } });
      if (tracked) {
        const loc = await area(page, "akala-island/route-6");
        const winter = loc.locator('[data-form="585:winter"]');
        await expect(winter).toHaveCount(1);
        await expect(winter).toContainText("Seen");
        // Exercise the existing exact legacy key through a complete cycle.
        for (const label of ["None", "Caught", "Seen"]) { await winter.click(); await expect(winter).toContainText(label); }
        const canyon = await area(page, "poni-island/vast-poni-canyon");
        const dusk = canyon.locator('[data-form="745:dusk"]');
        await expect(dusk).toHaveCount(2);
        for (const label of ["Seen", "None", "Caught"]) { await dusk.first().click(); for (const control of await dusk.all()) await expect(control).toContainText(label); }
        expect(await read(page)).toEqual({ ...fixture, settings: { ...fixture.settings, forms: true } });
      }
    }
    await page.reload();
    expect(await read(page)).toEqual(fixture);
    expect(await page.evaluate(() => localStorage.getItem("pokemon-checklist-state-v5"))).toBeNull();
    if (!await page.getByRole("button", { name: "Backup", exact: true }).isVisible()) await page.locator("#header-settings-toggle").click();
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Backup", exact: true }).click();
    const download = await downloadPromise;
    const file = await download.path();
    expect(file).not.toBeNull();
    expect(JSON.parse(await readFile(file!, "utf8"))).toEqual(fixture);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    expect(errors).toEqual([]);
  });
});
