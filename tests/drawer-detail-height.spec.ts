import { expect, test } from "@playwright/test";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
for (const width of [360, 412, 1440]) test.describe(`drawer detail space ${width}px`, () => {
  test.use({ viewport: { width, height: 915 }, isMobile: width < 1000, hasTouch: width < 1000 });
  test("phone uses one content scroll while preserving search, family access and records", async ({ page }, info) => {
    const errors: string[] = [];
    page.on("pageerror", e => errors.push(e.message));
    page.on("console", e => { if (e.type() === "error") errors.push(e.text()); });
    const fixture = { schemaVersion: 5, species: { "133": "seen" }, forms: {}, starred: [25], starredForms: [],
      settings: { forms: true, mode: "ultra-moon", unlocks: ["tauros", "surfing", "fishing", "sos", "weather-sos"] } };
    await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
    await page.evaluate(f => { localStorage.clear(); localStorage.setItem("pokemon-checklist-state-v5", JSON.stringify(f)); }, fixture);
    await page.reload();
    await expect(page.locator("#mode-select")).toHaveValue("ultra-moon");
    await expect(page.locator("#mode-select")).toBeEnabled();
    await expect(page.locator("#forms-toggle")).toHaveAttribute("aria-pressed", "true");
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem("pokemon-checklist-state-v5")!))).toEqual(fixture);
    if (width < 1000) await page.locator("#sidebar-toggle").click();
    await page.locator("#dex-search").fill("Eevee");
    await page.locator('#dex-list [data-action="select"][data-species="133"]').click();
    const panel = page.locator("#dex-selection");
    await expect(panel).toContainText("#133 Eevee");
    const dimensions = await panel.evaluate(e => ({ height: e.getBoundingClientRect().height, content: e.scrollHeight, viewport: e.clientHeight }));
    await info.attach("drawer-dimensions", { body: JSON.stringify(dimensions), contentType: "application/json" });
    if (width < 1000) {
      expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport + 1);
      const content = page.locator(".dex-content");
      const bounds = await content.boundingBox();expect(bounds).not.toBeNull();
      expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(916);
      const family = panel.locator(".evolution-controls > details");
      await family.locator(":scope > summary").click();
      await expect(family).toHaveAttribute("open", "");
      const lastStage = family.getByRole("button", { name: /Sylveon evolution stage status/ });
      await lastStage.scrollIntoViewIfNeeded();
      await expect(lastStage).toBeVisible();
      expect(await content.evaluate(e => e.scrollTop)).toBeGreaterThan(0);
      expect(await panel.evaluate(e => e.scrollTop)).toBe(0);
      await expect(page.locator("#dex-search")).toBeInViewport();
      await page.getByRole("button", { name: "Close these details and show what to catch next", exact: true }).click();
      await expect(page.locator(".dex-selection-empty")).toHaveCount(1);
      await expect(page.locator('#dex-list [data-action="select"][data-species="133"]')).toBeInViewport();
    } else {
      expect(dimensions.height).toBeLessThan(500);
    }
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem("pokemon-checklist-state-v5")!))).toEqual(fixture);
    expect(errors).toEqual([]);
  });
});
