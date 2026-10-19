import { expect, test, type Page } from "@playwright/test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";
import { readFile } from "node:fs/promises";

const fixture = {
  schemaVersion: 4, species: { 52: "caught", 479: "caught", 585: "caught", 670: "caught" },
  forms: { "585:autumn": "caught", "585:winter": "seen", "479:heat": "caught", "670:orangeflower": "seen" },
  starred: [479, 585, 670], settings: { forms: false, mode: "photonic-prismatic", unlocks: ["sos"] },
};
const examples = [
  { area: "akala-island/route-6", row: "grass-1-1/4", name: "Deerling (Spring / Summer)", rate: "15%", allies: [] },
  { area: "akala-island/route-6", row: "grass-2-2/5", name: "Deerling (Spring / Summer)", rate: "15%", allies: [] },
  { area: "akala-island/route-6", row: "sos-calls-3/1", name: "Deerling (Spring / Summer)", rate: "—", allies: ["Deerling (Autumn)", "Deerling (Winter)"] },
  { area: "ulaula-island/thrifty-megamart", row: "building-1/5", name: "Rotom (Base)", rate: "15%", allies: ["Rotom (Frost)", "Rotom (Heat)"] },
  { area: "ulaula-island/ulaula-meadow", row: "grass-1/2", name: "Floette (Red Flower)", rate: "20%", allies: ["Floette (Orange Flower)", "Floette (White Flower)"] },
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
        expect(await caller.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
        await expect(row.locator("td").nth(0)).toHaveText(example.rate);
        await expect(row.locator(".ally-list .guide-pokemon-link")).toHaveText(example.allies);
        expect(await row.locator("td").last().innerText()).not.toContain("%");
        if (!tracked) await expect(row.locator(".form-status")).toHaveCount(0);
        if (!tracked && example.allies.length) await row.screenshot({ path: info.outputPath(`${width}-${example.area.split("/").pop()}-forms-off.png`) });
      }
      expect(await read(page)).toEqual({ ...fixture, settings: { ...fixture.settings, forms: tracked } });
      if (tracked) {
        const loc = await area(page, "akala-island/route-6");
        const winter = loc.locator('[data-form="585:winter"]');
        await expect(winter).toHaveCount(1);
        await expect(winter).toContainText("Seen");
        // Exercise the existing exact legacy key through a complete cycle.
        for (const label of ["None", "Caught", "Seen"]) { await winter.click(); await expect(winter).toContainText(label); }
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
