import { expect, test } from "@playwright/test";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

for (const width of [360, 412, 1440]) test.describe(`all-on caller facts ${width}px`, () => {
  test.use({ viewport: { width, height: 915 }, isMobile: width < 1000, hasTouch: width < 1000 });
  test("caller rate precedes allies and genuinely empty phone facts disappear", async ({ page }, info) => {
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    const key = "pokemon-checklist-state-v5";
    const fixture = { schemaVersion: 5, species: { "19": "caught", "20": "seen", "25": "caught" },
      forms: { "19:alolan": "caught", "20:alolan": "seen" }, starred: [25], starredForms: [],
      settings: { forms: true, mode: "ultra-moon", unlocks: ["tauros", "surfing", "fishing", "sos", "weather-sos"] } };
    await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
    await page.evaluate(({ key, fixture }) => { localStorage.clear(); localStorage.setItem(key, JSON.stringify(fixture)); }, { key, fixture });
    await page.reload();
    await expect(page.locator("#mode-select")).toHaveValue("ultra-moon");
    await expect(page.locator("#mode-select")).toBeEnabled();
    await expect(page.locator("#forms-toggle")).toHaveAttribute("aria-pressed", "true");
    expect(await page.evaluate(key => JSON.parse(localStorage.getItem(key)!), key)).toEqual(fixture);
    await expect(page.getByText("Your saved checklist could not be read", { exact: false })).toHaveCount(0);
    const area = page.locator('[data-location-id="ulaula-island/route-17"]');
    await expect(area).toHaveCount(1);
    if (!await area.evaluate((el: HTMLDetailsElement) => el.open)) await area.locator(":scope > summary").click();
    const row = area.locator("tbody > tr").filter({ has: page.locator(".species-name > .guide-pokemon .guide-pokemon-link").filter({ hasText: "Graveler (Alolan)" }) }).first();
    await expect(row).toHaveCount(1);
    await expect(row.locator(":scope > th > .inline-sos")).toContainText("Castform");
    const rate = row.locator(":scope > td").nth(0);
    await expect(rate).toHaveText("Graveler (Alolan) · 20%");
    const geometry = await row.evaluate(el => {
      const identity = el.querySelector(".species-name")!.getBoundingClientRect();
      const rate = el.querySelector("td")!.getBoundingClientRect();
      const allies = el.querySelector(".inline-sos")!.getBoundingClientRect();
      return { identity: identity.toJSON(), rate: rate.toJSON(), allies: allies.toJSON() };
    });
    await info.attach("caller-geometry", { body: JSON.stringify(geometry), contentType: "application/json" });
    if (width < 680) {
      expect(geometry.rate.top - geometry.identity.bottom).toBeLessThan(24);
      expect(geometry.rate.bottom).toBeLessThanOrEqual(geometry.allies.top);
      for (const cell of [row.locator(":scope > td").nth(1), row.locator(":scope > td").nth(2)]) {
        await expect(cell).toHaveText("—");
        await expect(cell).not.toBeVisible();
      }
    } else {
      expect(Math.abs(geometry.rate.top - geometry.identity.top)).toBeLessThan(32);
      await expect(row.locator(":scope > td").nth(1)).toBeVisible();
      await expect(row.locator(":scope > td").nth(2)).toBeVisible();
    }
    const rows = area.locator("tbody > tr");
    expect(await rows.count()).toBeGreaterThan(0);
    for (const nativeRow of await rows.all()) {
      for (const cell of await nativeRow.locator(":scope > td").all()) {
        if ((await cell.innerText()).trim() !== "—") await expect(cell).toBeVisible();
      }
    }
    expect(await page.evaluate(key => JSON.parse(localStorage.getItem(key)!), key)).toEqual(fixture);
    expect(errors).toEqual([]);
  });
});
