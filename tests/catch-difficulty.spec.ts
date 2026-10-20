import { expect, test } from "@playwright/test";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { readFile } from "node:fs/promises";
const key = "pokemon-checklist-state-v5";
const calcKey = "pokemon-checklist-catch-selection-v1";
for (const width of [390, 1440]) test(`Catch next and pooled source identity ${width}px`, async ({ page }, info) => {
  await page.setViewportSize({ width, height: 950 });
  const fixture = { schemaVersion: 5, species: {}, forms: {}, starred: [], starredForms: [], settings: { forms: true, mode: "photonic-prismatic", unlocks: ["tauros", "surfing", "fishing", "sos", "weather-sos"] } };
  await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
  await page.evaluate(({ key, fixture }) => { localStorage.clear(); localStorage.setItem(key, JSON.stringify(fixture)); }, { key, fixture });
  await page.reload();
  await expect(page.locator("#mode-select")).toHaveValue("photonic-prismatic");
  await expect(page.locator("#mode-select")).toBeEnabled();
  await expect(page.locator("#forms-toggle")).toHaveAttribute("aria-pressed", "true");
  const saved = () => page.evaluate(key => JSON.parse(localStorage.getItem(key)!), key);
  expect(await saved()).toEqual(fixture);
  if (width < 1000) await page.locator("#sidebar-toggle").click();
  const next = page.locator(".catch-next");
  await expect(next).toHaveCount(1);
  if (!await next.evaluate((el: HTMLDetailsElement) => el.open)) await next.locator("summary").click();
  const badge = next.locator(".catch-badge-action").first();
  const rate = await badge.locator(".catch-badge").getAttribute("data-catch-rate");
  await badge.click();
  await expect(page.locator(".catch-info")).toContainText(`Stock base catch rate: ${rate}`);
  expect(await saved()).toEqual(fixture);
  if (width < 1000) await page.keyboard.press("Escape");
  const data = JSON.parse(await readFile(resolve("data/encounters.json"), "utf8"));
  const location = data.islands.flatMap((i: any) => i.locations).find((l: any) => l.groups.some((g: any) => g.encounters.some((r: any) => r.speciesId === 585)));
  expect(location).toBeTruthy();
  const area = page.locator(`[data-location-id="${location.id}"]`);
  await expect(area).toHaveCount(1);
  if (!await area.evaluate((el: HTMLDetailsElement) => el.open)) await area.locator(":scope > summary").click();
  const pooled = area.locator(".guide-pokemon").filter({ has: page.getByRole("button", { name: /Deerling.*Spring.*Summer/ }) }).first();
  await expect(pooled).toBeVisible();
  await expect(pooled.locator(".catch-badge")).toHaveText("Catch —");
  await pooled.locator(".catch-badge-action").click();
  await expect(page.locator(".catch-info")).toContainText("unavailable for this exact form/profile");
  expect(await saved()).toEqual(fixture);
});
for (const width of [360, 390, 412, 1440]) test(`intrinsic catch facts and accessible help ${width}px`, async ({ page }, info) => {
  await page.setViewportSize({ width, height: 950 });
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  const fixture = { schemaVersion: 5, species: { "25": "seen" }, forms: {}, starred: [], starredForms: [], settings: { forms: true, mode: "photonic-prismatic", unlocks: [] } };
  const calculator = JSON.stringify({ id: 25, form: 0, ball: "Poké Ball" });
  await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
  await page.evaluate(({ key, calcKey, fixture, calculator }) => { localStorage.clear(); localStorage.setItem(key, JSON.stringify(fixture)); localStorage.setItem(calcKey, calculator); }, { key, calcKey, fixture, calculator });
  await page.reload();
  await expect(page.locator("#mode-select")).toHaveValue("photonic-prismatic");
  await expect(page.locator("#mode-select")).toBeEnabled();
  await expect(page.locator("#forms-toggle")).toHaveAttribute("aria-pressed", "true");
  const saved = () => page.evaluate(key => JSON.parse(localStorage.getItem(key)!), key);
  expect(await saved()).toEqual(fixture);
  const guide = page.locator(".guide-pokemon").first();
  await expect(guide).toBeVisible();
  await expect(guide.locator(".catch-badge")).toHaveCount(1);
  if (width < 1000) await page.locator("#sidebar-toggle").click();
  await page.locator("#dex-search").fill("");
  {
    const ordinaryName = page.locator('#dex-list [data-action="select"][data-species="1"] .dex-name');
    await ordinaryName.scrollIntoViewIfNeeded();
    expect(await ordinaryName.evaluate(el => el.clientWidth > 0 && el.scrollWidth <= el.clientWidth + 1)).toBe(true);
  }
  await page.locator("#dex-search").fill("Meowth");
  const alola = page.locator('#dex-list [data-action="select"][data-species="52"]').filter({ hasText: "Alolan" });
  const kanto = page.locator('#dex-list [data-action="select"][data-species="52"]').filter({ hasText: "Kanto" });
  await expect(alola).toBeVisible(); await expect(kanto).toBeVisible();
  for (const row of [alola, kanto]) {
    await expect(row.locator(".catch-badge")).toHaveText("Catch F");
    await expect(row.locator(".catch-badge")).toHaveAttribute("data-catch-rate", "255");
    await expect(row.locator(".grade-badge")).toHaveCount(1);
  }
  await kanto.click();
  await expect(page.locator(".catch-info")).toContainText("Stock base catch rate: 255");
  await page.locator(".catch-legend > summary").focus(); await page.keyboard.press("Enter");
  await expect(page.locator(".catch-legend")).toHaveJSProperty("open", true);
  await expect(page.locator(".catch-legend")).toContainText("F easiest");
  await expect(page.locator(".catch-legend")).toContainText("S hardest");
  await expect(page.locator(".catch-legend")).toContainText("Ultra Beasts");
  await expect(page.locator(".catch-legend")).toContainText("not a percentage");
  await expect(page.locator(".catch-info")).toContainText("Prismatic");
  expect(await saved()).toEqual(fixture);
  expect(await page.evaluate(key => localStorage.getItem(key), calcKey)).toBe(calculator);
  await page.screenshot({ path: info.outputPath("catch-help.png") });
  await page.locator("#dex-search").fill("Exeggutor");
  const longLabels = page.locator('#dex-list [data-species="103"] .dex-name');
  await expect(longLabels).toHaveCount(2);
  for (const label of await longLabels.all()) {
    expect(await label.evaluate(el => el.clientWidth > 0 && el.scrollWidth <= el.clientWidth + 1)).toBe(true);
  }
  const bystander = page.locator('#dex-list [data-action="select"][data-species="500"]');
  await expect(bystander).toHaveCount(1);
  const renders = await bystander.getAttribute("data-renders");
  for (const [mode, rate, tier] of [["moon", 3, "S"], ["ultra-moon", 255, "F"]] as const) {
    if (width < 1000) { await page.keyboard.press("Escape"); await page.locator("#header-settings-toggle").click(); }
    await page.locator("#mode-select").selectOption(mode);
    if (width < 1000) { await page.keyboard.press("Escape"); await page.locator("#sidebar-toggle").click(); }
    await page.locator("#dex-search").fill("Necrozma");
    await page.locator('#dex-list [data-action="select"][data-species="800"]').click();
    await expect(page.locator(".dex-selection .catch-badge")).toHaveText(`Catch ${tier}`);
    await expect(page.locator(".catch-info")).toContainText(`Stock base catch rate: ${rate}`);
    if (mode === "moon") {
      await page.locator("#dex-search").fill("Poipole");
      await page.locator('#dex-list [data-action="select"][data-species="803"]').click();
      await expect(page.locator(".dex-selection .catch-badge")).toHaveText("Catch —");
      await expect(page.locator(".catch-info")).toContainText("unavailable for this exact form/profile");
    }
    expect(await saved()).toEqual({ ...fixture, settings: { ...fixture.settings, mode } });
    expect(await page.evaluate(key => localStorage.getItem(key), calcKey)).toBe(calculator);
    await expect(bystander).toHaveAttribute("data-renders", renders!);
  }
  if (width < 1000) { await page.keyboard.press("Escape"); await page.locator("#header-settings-toggle").click(); }
  await page.locator("#forms-toggle").click();
  if (width < 1000) { await page.keyboard.press("Escape"); await page.locator("#sidebar-toggle").click(); }
  await page.locator("#dex-search").fill("");
  {
    const ordinaryName = page.locator('#dex-list [data-action="select"][data-species="1"] .dex-name');
    await ordinaryName.scrollIntoViewIfNeeded();
    expect(await ordinaryName.evaluate(el => el.clientWidth > 0 && el.scrollWidth <= el.clientWidth + 1)).toBe(true);
  }
  await page.locator("#dex-search").fill("Meowth");
  const collapsed = page.locator('#dex-list [data-action="select"][data-species="52"]');
  await expect(collapsed).toHaveCount(1); await collapsed.click();
  await expect(page.locator(".catch-info")).toContainText("Meowth — Alolan");
  expect(await saved()).toEqual({ ...fixture, settings: { ...fixture.settings, forms: false, mode: "ultra-moon" } });
  if (width < 1000) await page.keyboard.press("Escape");
  await page.locator(".guide-pokemon .catch-badge-action").first().click();
  await expect(page.locator(".catch-info")).toBeVisible();
  expect(await saved()).toEqual({ ...fixture, settings: { ...fixture.settings, forms: false, mode: "ultra-moon" } });
  await expect(page.locator("button button")).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});
