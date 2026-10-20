import { expect, test } from "@playwright/test";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
for (const close of ["Escape", "Close", "Backdrop"]) test(`phone drawer ${close} restores its opening toggle after inert cleanup`, async ({ browser }, info) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 900 }, isMobile: true, hasTouch: true, baseURL: info.project.use.baseURL as string | undefined });
  const page = await context.newPage();
  try {
    await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
    const fixture = { schemaVersion: 5, species: {}, forms: {}, starred: [], starredForms: [], settings: { forms: true, mode: "photonic-prismatic", unlocks: [] } };
    const key = "pokemon-checklist-state-v5";
    await page.evaluate(({ key, fixture }) => { localStorage.clear(); localStorage.setItem(key, JSON.stringify(fixture)); }, { key, fixture });
    await page.reload();
    await expect(page.locator("#mode-select")).toBeEnabled();
    await expect(page.locator("#forms-toggle")).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator("details.location[open] > summary").first()).toBeFocused();
    await page.locator("#sidebar-toggle").tap();
    await page.locator("#dex-search").fill("Meowth Kanto");
    const selected = page.locator('#dex-list [data-action="select"][data-species="52"]').filter({ hasText: "Kanto" });
    await expect(selected).toHaveCount(1);
    await selected.tap();
    await expect(page.locator("#dex-selection")).toBeFocused();
    if (close === "Escape") await page.keyboard.press("Escape");
    else if (close === "Close") await page.locator("#drawer-close").tap();
    else await page.locator("#backdrop").tap({ position: { x: 4, y: 400 } });
    await expect(page.locator("#pokedex")).toHaveAttribute("aria-hidden", "true");
    await expect(page.locator("#sidebar-toggle")).toBeFocused();
    expect(await page.evaluate(key => JSON.parse(localStorage.getItem(key)!), key)).toEqual(fixture);
  } finally { await context.close(); }
});
