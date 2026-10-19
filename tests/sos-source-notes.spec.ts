import { expect, test } from "@playwright/test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

for (const width of [390, 1440]) {
  test.describe(`SOS source-note scope ${width}px`, () => {
    test.use({ viewport: { width, height: 950 }, isMobile: width === 390, hasTouch: width === 390 });
    test("canyon footnotes stay with their documented callers", async ({ page }, info) => {
      const errors: string[] = [];
      page.on("pageerror", error => errors.push(error.message));
      page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
      await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
      const fixture = { schemaVersion: 5, species: {}, forms: {}, starred: [], starredForms: [],
        settings: { forms: true, mode: "photonic-prismatic", unlocks: ["sos", "fishing"] } };
      await page.evaluate(value => { localStorage.clear(); localStorage.setItem("pokemon-checklist-state-v5", JSON.stringify(value)); }, fixture);
      await page.reload();
      const location = page.locator('[data-location-id="poni-island/vast-poni-canyon"]');
      if (!await location.evaluate(element => (element as HTMLDetailsElement).open)) await location.locator("summary").click();
      const row = (suffix: string) => location.locator(`[id="${("encounter-poni-island/vast-poni-canyon/" + suffix).replace(/[^a-zA-Z0-9]+/g, "-")}"]`);
      const torracat = location.locator("tbody tr").filter({ has: page.locator(".species-name .guide-pokemon-link").getByText("Torracat", { exact: true }) });
      await expect(torracat).toHaveCount(1);
      await expect(torracat.locator(".sos-note")).toHaveCount(0);
      for (const suffix of ["cave-3/5", "caves-with-water-4/2"]) {
        const carbink = row(suffix);
        await expect(carbink.locator(".sos-note")).toHaveCount(1);
        await expect(carbink.locator(".sos-note")).toContainText("only called by Carbink encountered in caves");
        await expect(carbink.locator(".inline-sos")).not.toContainText("Lycanroc");
        await expect(carbink.locator(".inline-sos")).not.toContainText("Dragonair");
      }
      const dragonair = location.locator("tbody tr").filter({ has: page.locator(".species-name .guide-pokemon-link").getByText("Dragonair", { exact: true }) });
      await expect(dragonair).toHaveCount(1);
      await expect(dragonair.locator(".sos-note")).toHaveCount(1);
      await expect(dragonair.locator(".sos-note")).toContainText("bubbling spot");
      await expect(dragonair.locator(".inline-sos")).not.toContainText("Carbink");
      await expect(dragonair.locator(".inline-sos")).not.toContainText("Lycanroc");
      await row("cave-3/5").evaluate(element => window.scrollBy(0, element.getBoundingClientRect().top - document.querySelector("header")!.getBoundingClientRect().bottom - 16));
      await page.screenshot({ path: info.outputPath(`notes-${width}.png`) });
      expect(await page.evaluate(() => JSON.parse(localStorage.getItem("pokemon-checklist-state-v5")!))).toEqual(fixture);
      expect(errors).toEqual([]);
    });
  });
}
