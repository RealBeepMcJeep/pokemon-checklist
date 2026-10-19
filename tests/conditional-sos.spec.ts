import { expect, test } from "@playwright/test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

for (const width of [390, 1440]) test.describe(`conditional SOS ${width}px`, () => {
  test.use({ viewport: { width, height: 950 }, isMobile: width === 390, hasTouch: width === 390 });
  test("pooled Rockruff names Own Tempo as the required SOS caller", async ({ page }, info) => {
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
    const fixture = { schemaVersion: 5, species: { 744: "seen" }, forms: { "744:owntempo": "seen" },
      starred: [744], starredForms: [], settings: { forms: true, mode: "photonic-prismatic", unlocks: ["sos"] } };
    await page.evaluate(value => { localStorage.clear(); localStorage.setItem("pokemon-checklist-state-v5", JSON.stringify(value)); }, fixture);
    await page.reload();
    // Legacy formSlug strips hyphens: source own-tempo is stored as 744:owntempo.
    await expect(page.getByText("Your saved checklist could not be read", { exact: false })).toHaveCount(0);
    const location = page.locator('[data-location-id="melemele-island/ten-carat-hill"]');
    if (!await location.evaluate(element => (element as HTMLDetailsElement).open)) await location.locator("summary").click();
    const row = location.locator("#encounter-melemele-island-ten-carat-hill-grass-2-1");
    await expect(row.locator(".species-name .guide-pokemon-link").first()).toHaveText("Rockruff (Normal / Own Tempo)");
    await expect(row.locator("td").first()).toHaveText("20%");
    await expect(row.locator(".sos-identity .guide-pokemon-link")).toHaveText(["Rockruff (Own Tempo)"]);
    await expect(row.locator(".inline-sos .condition")).toHaveText("Caller: Rockruff (Own Tempo) only");
    expect(await row.locator(".inline-sos").innerText()).not.toContain("%");
    await row.evaluate(element => window.scrollBy(0, element.getBoundingClientRect().top - document.querySelector("header")!.getBoundingClientRect().bottom - 16));
    await page.screenshot({ path: info.outputPath(`own-tempo-${width}.png`) });
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem("pokemon-checklist-state-v5")!))).toEqual(fixture);
    if (width === 390) await page.locator("#header-settings-toggle").click();
    await page.locator("#forms-toggle").click();
    if (width === 390) await page.getByRole("button", { name: "Close settings", exact: true }).click();
    await expect(row.locator(".sos-identity .guide-pokemon-link")).toHaveText(["Rockruff (Own Tempo)"]);
    await expect(row.locator(".inline-sos .condition")).toHaveText("Caller: Rockruff (Own Tempo) only");
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem("pokemon-checklist-state-v5")!)))
      .toEqual({ ...fixture, settings: { ...fixture.settings, forms: false } });
    await page.locator("#header-settings-toggle").click();
    await page.getByLabel("SOS Calls", { exact: true }).uncheck();
    await page.getByRole("button", { name: "Close settings", exact: true }).click();
    await expect(row.locator(".inline-sos")).toHaveCount(0);
    const after = await page.evaluate(() => JSON.parse(localStorage.getItem("pokemon-checklist-state-v5")!));
    for (const key of ["species", "forms", "starred", "starredForms"] as const) expect(after[key]).toEqual(fixture[key]);
    expect(errors).toEqual([]);
  });
});
