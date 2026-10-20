import { expect, test } from "@playwright/test";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { readFile } from "node:fs/promises";
const saveKey = "pokemon-checklist-state-v5";
const preferenceKey = "pokemon-checklist-progress-v1";
test("denied preference storage reports failure without changing a player save", async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => {
    const set = Storage.prototype.setItem;
    Storage.prototype.setItem = function(key, value) {
      if (key === "pokemon-checklist-progress-v1") throw new DOMException("blocked preference", "SecurityError");
      return set.call(this, key, value);
    };
  });
  await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
  const before = await page.evaluate(key => localStorage.getItem(key), saveKey);
  await page.locator("#header-settings-toggle").click();
  await page.locator("#progress-metric").selectOption("registered");
  await expect(page.locator("#header-settings-panel .preference-error[role=status]")).toContainText("could not be remembered");
  await expect(page.locator(".collection-headline")).toHaveAttribute("data-progress-metric", "registered");
  expect(await page.evaluate(key => localStorage.getItem(key), saveKey)).toBe(before);
  expect(await page.evaluate(key => localStorage.getItem(key), preferenceKey)).toBeNull();
  await page.reload();
  await expect(page.locator(".collection-headline")).toHaveAttribute("data-progress-metric", "owned");
});
for (const width of [360, 390, 412, 1440]) for (const tracking of [false, true]) {
  test(`device-local headline ${width}px tracking=${tracking}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 950 });
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    const regional = JSON.parse(await readFile(resolve("data/regional-forms.json"), "utf8"));
    const livingMax = 807 + new Set(Object.values(regional.forms).map((r: any) => r.id)).size;
    const fixture = { schemaVersion: 5, species: { "25": "seen", "52": "caught" }, forms: { "52:alolan": "caught", "52:kanto": "caught" }, starred: [], starredForms: ["52:alolan"], settings: { forms: tracking, mode: "photonic-prismatic", unlocks: [] } };
    await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
    await page.evaluate(({ saveKey, fixture }) => { localStorage.clear(); localStorage.setItem(saveKey, JSON.stringify(fixture)); }, { saveKey, fixture });
    await page.reload();
    const read = () => page.evaluate(key => JSON.parse(localStorage.getItem(key)!), saveKey);
    await expect(page.locator("#mode-select")).toHaveValue("photonic-prismatic");
    await expect(page.locator("#mode-select")).toBeEnabled();
    await expect(page.locator("#forms-toggle")).toHaveAttribute("aria-pressed", String(tracking));
    expect(await read()).toEqual(fixture);
    await expect(page.locator(".collection-headline")).toHaveAttribute("data-progress-metric", tracking ? "living" : "owned");
    await expect(page.locator("#overall-progress")).toHaveJSProperty("value", tracking ? 2 : 1);
    await expect(page.locator("#overall-progress")).toHaveJSProperty("max", tracking ? livingMax : 807);
    expect(await page.evaluate(key => localStorage.getItem(key), preferenceKey)).toBeNull();
    await expect(page.locator(".app-header progress")).toHaveCount(1);
    await expect(page.locator(".mobile-progress-rail")).toHaveCount(0);
    const bystander = page.locator('#dex-list [data-action="select"][data-species="500"]');
    // Closed phone drawers deliberately defer row mounting. Metric changes must not mount them.
    await expect(bystander).toHaveCount(width < 1000 ? 0 : 1);
    const renders = width < 1000 ? null : await bystander.getAttribute("data-renders");
    await page.locator("#header-settings-toggle").click();
    for (const metric of ["living", "owned", "registered"]) {
      await page.locator("#progress-metric").selectOption(metric);
      await expect(page.locator(".collection-headline")).toHaveAttribute("data-progress-metric", metric);
      await expect(page.locator("#overall-progress")).toHaveJSProperty("value", metric === "registered" ? 2 : metric === "living" && tracking ? 2 : 1);
      expect(await read()).toEqual(fixture);
      if (width < 1000) await expect(bystander).toHaveCount(0);
      else await expect(bystander).toHaveAttribute("data-renders", renders!);
    }
    await expect(page.locator("#header-settings-panel progress")).toHaveCount(0);
    await expect(page.locator('[data-progress-stat="registered"]')).toContainText("2 / 807");
    await expect(page.locator('[data-progress-stat="owned"]')).toContainText("1 / 807");
    await page.getByRole("button", { name: "Close settings", exact: true }).click();
    await page.reload();
    await expect(page.locator(".collection-headline")).toHaveAttribute("data-progress-metric", "registered");
    expect(await read()).toEqual(fixture);
    if (width < 1000) await page.locator("#header-settings-toggle").click();
    await page.locator("#forms-toggle").click();
    await page.locator("#mode-select").selectOption("sun");
    if (width < 1000) await page.getByRole("button", { name: "Close settings", exact: true }).click();
    await expect(page.locator(".collection-headline")).toHaveAttribute("data-progress-metric", "registered");
    expect(await read()).toEqual({ ...fixture, settings: { ...fixture.settings, forms: !tracking, mode: "sun" } });
    await page.evaluate(() => scrollTo(0, 500));
    const headline = page.locator(".collection-headline");
    await expect(headline).toBeVisible();
    const box = await headline.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(width);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const label = page.locator("#progress-label");
    expect(await label.evaluate(el => el.clientWidth > 0 && el.scrollWidth <= el.clientWidth + 1)).toBe(true);
    await page.screenshot({ path: info.outputPath("progress-headline.png") });
    await page.locator("#header-settings-toggle").click();
    await expect(page.locator("#progress-metric")).toHaveValue("registered");
    await page.screenshot({ path: info.outputPath("progress-settings.png") });
    expect(errors).toEqual([]);
  });
}
