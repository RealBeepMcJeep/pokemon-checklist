import { expect, test } from "@playwright/test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

for (const width of [360, 412]) {
  test(`C action notices reserve space above the first section at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
    await page.evaluate(() => scrollTo(0, 0));
    await page.locator("#header-settings-toggle").click();
    await Promise.all([page.waitForEvent("download"), page.locator("#export-button").click()]);
    await page.getByRole("button", { name: "Close settings", exact: true }).click();
    await page.evaluate(() => scrollTo(0, 0));
    await expect(page.locator("#notice")).toHaveText("Backup downloaded.");
    await expect.poll(async () => {
      const header = await page.locator(".app-header").boundingBox();
      const first = await page.locator(".island > h2").first().boundingBox();
      return first!.y - (header!.y + header!.height);
    }).toBeGreaterThanOrEqual(0);
  });
}

test("C closes Settings after Reset so its timed Undo is immediately reachable", async ({ page }, info) => {
  await page.setViewportSize({ width: 360, height: 844 });
  await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
  await page.locator("#sidebar-toggle").click();
  await page.locator("#dex-search").fill("Pikipek");
  await page.locator('#dex-list [data-action="species"][data-species="731"]').click();
  await page.keyboard.press("Escape");
  await expect(page.locator('#overall-text [data-status="caught"]')).toHaveText("Caught 1");
  await page.locator("#header-settings-toggle").click();
  page.once("dialog", dialog => dialog.accept());
  await page.locator("#reset-button").click();
  await expect(page.locator("#header-settings-panel")).not.toBeVisible();
  await expect(page.locator("#notice-action")).toHaveText("Undo");
  await page.locator("#notice-action").click();
  await expect(page.locator('#overall-text [data-status="caught"]')).toHaveText("Caught 1");
});
