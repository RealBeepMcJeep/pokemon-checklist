import { expect, test } from "@playwright/test";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

for (const width of [360, 1440]) test.describe(`compact weather allies ${width}px`, () => {
  test.use({ viewport: { width, height: 915 }, isMobile: width < 1000, hasTouch: width < 1000 });
  test("one inline identity retains all three distinct Castform weather/rate rules", async ({ page }, info) => {
    const errors: string[] = [];
    page.on("pageerror", e => errors.push(e.message));
    page.on("console", e => { if (e.type() === "error") errors.push(e.text()); });
    const fixture = { schemaVersion: 5, species: { "19": "caught", "20": "seen", "25": "caught", "52": "caught", "133": "seen", "363": "caught" }, forms: { "19:alolan": "caught", "20:alolan": "seen", "52:alolan": "caught" }, starred: [25], starredForms: ["52:alolan"],
      settings: { forms: true, mode: "ultra-moon", unlocks: ["tauros", "surfing", "fishing", "sos", "weather-sos"] } };
    await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
    await page.evaluate(f => { localStorage.clear(); localStorage.setItem("pokemon-checklist-state-v5", JSON.stringify(f)); }, fixture);
    await page.reload();
    await expect(page.locator("#mode-select")).toHaveValue("ultra-moon");
    await expect(page.locator("#mode-select")).toBeEnabled();
    await expect(page.locator("#forms-toggle")).toHaveAttribute("aria-pressed", "true");
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem("pokemon-checklist-state-v5")!))).toEqual(fixture);
    const area = page.locator('[data-location-id="ulaula-island/route-17"]');
    await expect(area).toHaveCount(1);
    if (!await area.evaluate((e: HTMLDetailsElement) => e.open)) await area.locator(":scope > summary").click();
    const caller = area.locator("tbody > tr").filter({ has: page.locator(".species-name .guide-pokemon-link").filter({ hasText: "Graveler (Alolan)" }) }).first();
    await expect(caller).toHaveCount(1);
    await expect(caller.locator('.inline-sos .guide-pokemon-link').filter({ hasText: /^Castform$/ })).toHaveCount(1);
    const castform = caller.locator('.sos-entry[data-sos-kind="weather-sos"]').filter({ has: page.getByRole("button", { name: "Castform", exact: true }) });
    await expect(castform).toHaveCount(1);
    await expect(castform.locator('.sos-identity .status-button')).toHaveCount(1);
    const rules = castform.locator('.sos-rule');
    await expect(rules).toHaveCount(3);
    for (const [condition, rate] of [["During rain", "1%"], ["During hail", "11%"], ["During sandstorm", "11%"]]) {
      const rule = rules.filter({ has: page.getByText(condition, { exact: true }) });
      await expect(rule).toHaveCount(1);
      await expect(rule.locator('.sos-method')).toHaveText(`guide-reported rate: ${rate}`);
    }
    await expect(castform).toContainText("location-wide rule");
    await expect(castform).not.toContainText("Appears as an SOS ally; the caller depends on the encounter.");
    await expect(castform).not.toContainText("Weather-dependent SOS encounter.");
    const goomy = caller.locator('.sos-entry[data-sos-kind="weather-sos"]').filter({ has: page.getByRole("button", { name: "Goomy", exact: true }) });
    await expect(goomy).toHaveCount(1);
    await expect(goomy).toContainText("During rain");
    await expect(goomy).toContainText("guide-reported rate: 10%");
    await expect(goomy).not.toContainText("SOS encounter while it is raining.");
    await expect(area.locator('.group-heading strong').filter({ hasText: /^Weather SOS$/ })).toHaveCount(0);
    if (width < 1000) await page.locator('#header-settings-toggle').click(); else await page.locator('#header-settings-toggle').click();
    await page.getByLabel('Weather SOS', { exact: true }).uncheck();
    await page.getByRole('button', { name: 'Close settings', exact: true }).click();
    await expect(caller.locator('.sos-entry[data-sos-kind="weather-sos"]')).toHaveCount(0);
    await page.locator('#header-settings-toggle').click();
    await page.getByLabel('Weather SOS', { exact: true }).check();
    await page.getByRole('button', { name: 'Close settings', exact: true }).click();
    await expect(castform).toHaveCount(1);await expect(rules).toHaveCount(3);
    await expect(area.locator('summary')).toContainText('Not caught 11');
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem("pokemon-checklist-state-v5")!))).toEqual(fixture);
    expect(errors).toEqual([]);
  });
});
