import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const key = "pokemon-checklist-state-v5";
const flags = ["tauros", "surfing", "fishing", "sos", "weather-sos"];
const safe = (value: string) => value.replace(/[^a-zA-Z0-9]+/g, "-").replace(/^-|-$/g, "");
for (const width of [390, 1440]) for (const mode of ["sun", "moon", "ultra-sun", "ultra-moon"]) {
  test(`stock inline SOS ${mode} ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 950 });
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    const data = JSON.parse(await readFile(resolve(`data/encounters-${mode}.json`), "utf8"));
    const area = data.islands.flatMap((i: any) => i.locations).find((l: any) => l.name === "Route 1");
    const actor = mode.startsWith("ultra") ? 172 : 11;
    const ally = mode.startsWith("ultra") ? "Pikachu" : "Caterpie";
    const native = area.groups.filter((g: any) => g.encounterType === "wild").flatMap((g: any) => g.encounters).find((r: any) => r.speciesId === actor);
    expect(native).toBeTruthy();
    const fixture = { schemaVersion: 5, species: {}, forms: {}, starred: [], starredForms: [], settings: { forms: true, mode, unlocks: flags } };
    await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
    await page.evaluate(({ key, fixture }) => { localStorage.clear(); localStorage.setItem(key, JSON.stringify(fixture)); }, { key, fixture });
    await page.reload();
    await expect(page.locator("#mode-select")).toHaveValue(mode);
    await expect(page.getByText("Your saved checklist could not be read", { exact: false })).toHaveCount(0);
    const details = page.locator(`[data-location-id="${area.id}"]`);
    await expect(details).toHaveCount(1);
    if (!await details.evaluate((element: HTMLDetailsElement) => element.open)) await details.locator(":scope > summary").click();
    const caller = page.locator(`#encounter-${safe(native.id)}`);
    await expect(caller).toHaveCount(1);
    await expect(caller.locator(".inline-sos").getByText(ally, { exact: true })).toBeVisible();
    await expect(details.locator(".group-heading strong").filter({ hasText: /SOS allies|Weather SOS/i })).toHaveCount(0);
    const toggle = page.getByLabel("SOS Calls", { exact: true });
    if (!await toggle.isVisible()) {
      if (width === 390) await page.locator("#header-settings-toggle").click();
      else await page.getByRole("button", { name: "Settings", exact: true }).click();
    }
    await expect(toggle).toBeChecked();
    await toggle.uncheck();
    await expect(caller.locator(".inline-sos")).toHaveCount(0);
    await toggle.check();
    await expect(caller.locator(".inline-sos").getByText(ally, { exact: true })).toHaveCount(1);
    await page.getByRole("button", { name: "Close settings", exact: true }).click();
    await expect(caller.locator(".inline-sos")).toBeVisible();
    await caller.locator(".inline-sos").getByRole("button", { name: ally, exact: true }).click();
    const links = page.locator(".location-links > ul > li > a").filter({ hasText: /Route 1 ›.*SOS ally/ });
    await expect(links.first()).toBeVisible();
    const possible = new Set(area.groups.flatMap((g: any) => g.encounters).filter((r: any) => r.speciesName === ally && r.sosRules?.length)
      .flatMap((r: any) => r.sosRules.flatMap((rule: any) => rule.callerIds)).map((id: string) => `#encounter-${safe(id)}`));
    expect(possible.size).toBeGreaterThan(0);
    const hrefs = await links.evaluateAll(elements => elements.map(element => element.getAttribute("href")));
    expect(hrefs.every(href => possible.has(href))).toBe(true);
    const destination = await links.first().getAttribute("href");
    await links.first().click();
    await expect(page.locator(destination!)).toBeFocused();
    await caller.evaluate(element => {
      const header = document.querySelector(".app-header")!.getBoundingClientRect();
      window.scrollBy(0, element.getBoundingClientRect().top - header.bottom - 16);
    });
    await expect.poll(async () => caller.evaluate(element => element.getBoundingClientRect().top >= document.querySelector(".app-header")!.getBoundingClientRect().bottom)).toBe(true);
    if ((width === 390 && mode === "moon") || (width === 1440 && mode === "ultra-moon")) await page.screenshot({ path: info.outputPath("stock-inline-source.png") });
    const stored = await page.evaluate(key => JSON.parse(localStorage.getItem(key)!), key);
    expect(stored).toEqual(fixture);
    expect(errors).toEqual([]);
  });
}

for (const width of [390, 1440]) test(`stock weather and unavailable-source acceptance ${width}px`, async ({ page }, info) => {
  await page.setViewportSize({ width, height: 950 });
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  const data = JSON.parse(await readFile(resolve("data/encounters-ultra-moon.json"), "utf8"));
  const route = data.islands.flatMap((i: any) => i.locations).find((l: any) => l.id === "ulaula-island/route-17");
  const leaf = route.groups.flatMap((g: any) => g.encounters).find((r: any) => r.speciesId === 351 && r.sosRules?.some((rule: any) => rule.kind === "weather-sos"));
  expect(leaf).toBeTruthy();
  const rule = leaf.sosRules.find((rule: any) => rule.kind === "weather-sos");
  expect(rule.conditions).toContain("During rain");
  expect(rule.rates).toEqual({ single: 1 }); // Stock UM, NOT Prismatic's 11%.
  const fixture = { schemaVersion: 5, species: { "25": "caught" }, forms: {}, starred: [25], starredForms: [], settings: { forms: true, mode: "ultra-moon", unlocks: ["sos"] } };
  await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
  await page.evaluate(({ key, fixture }) => { localStorage.clear(); localStorage.setItem(key, JSON.stringify(fixture)); }, { key, fixture });
  await page.reload();
  await expect(page.locator("#mode-select")).toHaveValue("ultra-moon");
  await expect(page.locator("#mode-select")).toBeEnabled();
  const details = page.locator(`[data-location-id="${route.id}"]`);
  if (!await details.evaluate((element: HTMLDetailsElement) => element.open)) await details.locator(":scope > summary").click();
  const caller = page.locator(`#encounter-${safe(rule.callerIds[0])}`);
  await expect(caller).toHaveCount(1);
  const weather = caller.locator(".sos-entry[data-sos-kind=weather-sos]").filter({ has: page.getByRole("button", { name: "Castform", exact: true }) }).filter({ hasText: "During rain" });
  await expect(weather).toHaveCount(0);
  await page.locator("#header-settings-toggle").click();
  await expect(page.getByLabel("SOS Calls", { exact: true })).toBeChecked();
  await page.getByLabel("Weather SOS", { exact: true }).check();
  await expect(weather).toHaveCount(1);
  await expect(weather.locator(".sos-method")).toContainText("guide-reported rate: 1%");
  await expect(weather).toContainText("During rain");
  await page.getByLabel("SOS Calls", { exact: true }).uncheck();
  await expect(caller.locator(".inline-sos")).toHaveCount(0);
  await page.getByLabel("Weather SOS", { exact: true }).uncheck();
  await page.getByLabel("SOS Calls", { exact: true }).check();
  await page.getByRole("button", { name: "Close settings", exact: true }).click();
  await expect(weather).toHaveCount(0);
  const cave = data.islands.flatMap((i: any) => i.locations).find((l: any) => l.id === "melemele-island/ten-carat-hill");
  const unknown = cave.groups.flatMap((g: any) => g.encounters).find((r: any) => Array.isArray(r.sosRules) && !r.sosRules.length);
  expect(unknown.speciesId).toBe(302);
  const area = page.locator(`[data-location-id="${cave.id}"]`);
  if (!await area.evaluate((element: HTMLDetailsElement) => element.open)) await area.locator(":scope > summary").click();
  const warning = page.locator(`#encounter-${safe(unknown.id)}`);
  await expect(warning).toContainText("Caller mapping unavailable");
  await expect(warning).toContainText("Sableye");
  expect(await warning.evaluate(element => element.tagName)).toBe("P");
  await expect(warning.getByRole("button")).toHaveCount(0);
  expect(await page.evaluate(key => JSON.parse(localStorage.getItem(key)!), key)).toEqual(fixture);
  expect(errors).toEqual([]);
});
