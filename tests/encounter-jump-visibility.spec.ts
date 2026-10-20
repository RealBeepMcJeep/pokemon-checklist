import { expect, test } from "@playwright/test";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { writeFile } from "node:fs/promises";

const KEY = "pokemon-checklist-state-v5";
const fixture = {
  schemaVersion: 5,
  species: { "19": "caught", "20": "seen", "25": "caught", "52": "caught", "133": "seen", "363": "caught" },
  forms: { "19:alolan": "caught", "20:alolan": "seen", "52:alolan": "caught" },
  starred: [25], starredForms: ["52:alolan"],
  settings: { forms: true, mode: "ultra-moon", unlocks: ["tauros", "surfing", "fishing", "sos", "weather-sos"] },
};
const destinations = [
  { hash: "#encounter-ulaula-island-malie-garden-ultra-moon-malie-garden-main-super-rod-10-28-4", area: "ulaula-island/malie-garden", caller: "Gyarados" },
  { hash: "#encounter-ulaula-island-route-17-ultra-moon-alola-route-17-west-walk-33-36-6", area: "ulaula-island/route-17", caller: "Raticate (Alolan)" },
];
for (const width of [360, 412, 1440]) test.describe(`encounter jump ${width}px`, () => {
  const phone = width < 768;
  test.use({ viewport: { width, height: 915 }, isMobile: phone, hasTouch: phone });
  test("tall encounter-link destinations keep their caller below the header after focus", async ({ page }, info) => {
    const errors: string[] = [];
    page.on("pageerror", e => errors.push(e.message));
    page.on("console", e => { if (e.type() === "error") errors.push(e.text()); });
    await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
    await page.evaluate(({ key, fixture }) => { localStorage.clear(); localStorage.setItem(key, JSON.stringify(fixture)); }, { key: KEY, fixture });
    await page.reload();
    await expect(page.locator("#mode-select")).toHaveValue("ultra-moon");
    await expect(page.locator("#mode-select")).toBeEnabled();
    await expect(page.locator("#forms-toggle")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByLabel("SOS Calls", { exact: true })).toBeChecked();
    await expect(page.getByLabel("Weather SOS", { exact: true })).toBeChecked();
    await expect(page.locator("details.location[open] > summary").first()).toBeFocused();
    const before = await page.evaluate(key => JSON.parse(localStorage.getItem(key)!), KEY);
    expect(before).toEqual(fixture);
    const route = page.locator('[data-location-id="ulaula-island/route-17"]');
    const act = async (target: ReturnType<typeof page.locator>) => phone ? target.tap() : target.click();
    await act(route.locator(":scope > summary"));
    for (const destination of destinations) {
      const ally = page.locator('details.location[open] .sos-entry[data-sos-kind="weather-sos"]').getByRole("button", { name: "Castform", exact: true }).first();
      await expect(ally).toBeVisible();
      await act(ally);
      await expect(page.locator("#dex-selection")).toBeFocused();
      await expect(page.locator("#dex-selection .selected-title")).toContainText("Castform");
      if (phone) await expect.poll(async () => {
        const box = await page.locator("#pokedex").boundingBox();
        return !!box && box.x >= -1 && box.x + box.width <= width + 1;
      }).toBe(true);
      const link = page.locator(`#dex-selection .location-links > ul a[href="${destination.hash}"]`);
      await expect(link).toHaveCount(1);
      await act(link);
      const row = page.locator(`[id="${destination.hash.slice(1)}"]`);
      await expect(row).toBeFocused();
      await expect(page.locator(`[data-location-id="${destination.area}"]`)).toHaveJSProperty("open", true);
      if (phone) await expect(page.locator("#pokedex")).toHaveAttribute("aria-hidden", "true");
      await expect(row.locator(".species-name .guide-pokemon-link").first()).toHaveText(destination.caller);
      let geometry: unknown;
      try {
        await expect.poll(async () => {
          const result = await row.evaluate(target => {
            const header = document.querySelector(".app-header")!.getBoundingClientRect();
            const row = target.getBoundingClientRect();
            const caller = target.querySelector(".species-name")!.getBoundingClientRect();
            return { activeId: document.activeElement?.id, targetId: target.id, headerBottom: header.bottom, rowTop: row.top, rowHeight: row.height, callerTop: caller.top, callerBottom: caller.bottom, height: innerHeight, inert: !!target.closest("[inert]") };
          });
          geometry = result;
          return !result.inert && result.activeId === result.targetId && result.rowTop >= result.headerBottom && result.callerTop >= result.headerBottom && result.callerBottom <= result.height;
        }).toBe(true);
      } finally {
        const tag = `${width}-${destination.area.split("/").at(-1)}`;
        await writeFile(info.outputPath(`${tag}-geometry.json`), JSON.stringify(geometry, null, 2));
        await page.screenshot({ path: info.outputPath(`${tag}-jump.png`) });
      }
      expect(await page.evaluate(() => location.hash)).toBe(destination.hash);
      expect(await page.evaluate(key => JSON.parse(localStorage.getItem(key)!), KEY)).toEqual(before);
    }
    expect(errors).toEqual([]);
  });
});
