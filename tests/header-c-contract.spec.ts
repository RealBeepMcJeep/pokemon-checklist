import { expect, test } from "@playwright/test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

for (const width of [360, 412]) {
  test(`C mobile header keeps compact commands and original information at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 844 });
    const errors: string[] = [];
    const remote: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("request", request => {
      if (/^https?:/.test(request.url()) && !/^https?:\/\/(localhost|127\.0\.0\.1)(:|\/)/.test(request.url())) remote.push(request.url());
    });
    await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
    await page.evaluate(() => scrollTo(0, 500));
    await expect(page.locator("#header-settings-toggle")).toBeVisible();
    await expect.poll(() => page.locator(".app-header").evaluate(el => el.getBoundingClientRect().height)).toBeLessThanOrEqual(64);
    await expect.poll(() => page.locator(".app-header").evaluate(el => Math.abs(el.getBoundingClientRect().top))).toBeLessThanOrEqual(1);
    await expect(page.locator("#sidebar-toggle")).toBeVisible();
    await expect(page.locator("#tools-toggle")).toBeVisible();
    await expect(page.locator("#overall-text [data-status]")).toHaveText(["Not caught 807", "Seen 0", "Caught 0"]);
    await page.locator("#header-settings-toggle").click();
    const settings = page.locator("#header-settings-panel");
    await expect(settings).toBeVisible();
    await expect(settings.locator("#build-version")).toBeVisible();
    await expect(settings.locator("#build-version")).toHaveText(/^v\d+\.\d+\.\d+ - [a-f0-9]{7,40}$/);
    await expect(settings).toContainText("Alola locations in story order");
    await expect(settings).toContainText("National Pokédex 001–807");
    await expect(settings.locator("#mode-select")).toBeVisible();
    await expect(settings.locator("#forms-toggle")).toBeVisible();
    for (const id of ["export-button", "import-button", "reset-button"]) await expect(settings.locator(`#${id}`)).toBeVisible();
    await expect(settings.getByRole("button", { name: /Sign in to sync/i })).toBeVisible();
    await settings.locator("#forms-toggle").click();
    await expect(settings.locator("#form-progress [data-status]")).toHaveText(["Not caught 48", "Seen 0", "Caught 0"]);
    await page.keyboard.press("Escape");
    await expect(settings).not.toBeVisible();
    await expect(page.locator("#header-settings-toggle")).toBeFocused();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(remote).toEqual([]);
    expect(errors).toEqual([]);
  });
}
