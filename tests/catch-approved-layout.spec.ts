import { test, expect } from "@playwright/test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

for (const width of [360, 412, 1440]) {
  test(`approved compact selectors and parameter factors at ${width}px`, async ({page}, info) => {
    await page.setViewportSize({width,height:900});
    await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
    await page.locator("#tools-toggle").click();
    await expect(page.locator("#tools-panel")).toBeVisible();
    await expect(page.locator("#catch-species-rail")).toBeVisible();
    for (const kind of ["species", "ball"]) {
      const rail = page.locator(`#catch-${kind}-rail`);
      const r = (await rail.boundingBox())!;
      const name = (await page.locator(`#catch-${kind}-name`).boundingBox())!;
      expect(name.x, "Name belongs beside the sprite strip inside the compact row").toBeGreaterThanOrEqual(r.x+r.width-1);
      const card = await rail.evaluate(el => el.closest("section")!.getBoundingClientRect().height);
      expect(card, "Approved selector row must stay compact").toBeLessThanOrEqual(125);
    }
    await expect(page.locator('.catch-selector[aria-label="Ball selector"]')).toContainText("×1.00");
    await expect(page.locator('.catch-parameters .catch-factors')).toBeVisible();
    const selectors = (await page.locator('.catch-selectors').boundingBox())!;
    const parameters = (await page.locator('.catch-parameters').boundingBox())!;
    if (width > 680) expect(parameters.x).toBeGreaterThan(selectors.x+selectors.width-1);
    else expect(parameters.y).toBeGreaterThanOrEqual(selectors.y+selectors.height-1);
  });
}
