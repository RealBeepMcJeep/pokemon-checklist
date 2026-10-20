import { expect, test, type Page } from "@playwright/test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";
import { writeFile } from "node:fs/promises";

async function open(page: Page, project: string) {
  if (project === "standalone-file") {
    await page.route(/^https?:\/\//, route => route.abort("blockedbyclient"));
    await page.goto(pathToFileURL(resolve("index.html")).href);
  } else await page.goto("/");
  await expect(page.locator("details.location")).toHaveCount(60);
}

test.afterEach(async ({ page }, info) => {
  if (info.status === info.expectedStatus) return;
  const geometry = await page.evaluate(() => ({
    scrollY, viewport: innerHeight, ready: document.readyState,
    header: document.querySelector(".app-header")?.getBoundingClientRect().toJSON(),
    active: document.activeElement?.textContent,
    locations: [...document.querySelectorAll("details.location[open]")].map(el => ({ id: el.getAttribute("data-location-id"), box: el.querySelector("summary")?.getBoundingClientRect().toJSON(), margin: getComputedStyle(el).scrollMarginTop })),
  }));
  await writeFile(info.outputPath("restoration-geometry.json"), JSON.stringify(geometry, null, 2));
  await info.attach("restoration-geometry", { body: JSON.stringify(geometry), contentType: "application/json" });
  await page.screenshot({ path: info.outputPath("restoration-failure.png") });
});

test("late native history restoration cannot override the remembered area", async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await open(page, info.project.name);
  await expect(page.locator("#mode-select")).toHaveValue("photonic-prismatic");
  await expect(page.locator("#mode-select")).toBeEnabled();
  const area = page.locator("details.location").nth(12);
  const id = await area.getAttribute("data-location-id");
  await area.locator("summary").click();
  await expect(area.locator(".location-body")).toBeVisible();
  // Hold a one-pixel load, not application scrolling: Chromium's real history
  // restoration will run after the app focuses its remembered section.
  let release: (() => Promise<void>) | undefined;
  await page.route("**/restore-load-gate.svg", route => {
    release = () => route.fulfill({ contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>' });
  });
  const imageURL = `http://127.0.0.1:${process.env.PW_PORT ?? 4173}/restore-load-gate.svg`;
  await page.addInitScript(url => document.addEventListener("DOMContentLoaded", () => {
    const image = document.createElement("img"); image.src = url;
    image.style.cssText = "position:fixed;width:1px;height:1px;opacity:0";
    document.body.append(image);
  }), imageURL);
  await page.reload({ waitUntil: "domcontentloaded" });
  const summary = page.locator(`[data-location-id="${id}"] > summary`);
  await expect(summary).toBeFocused();
  await expect.poll(() => typeof release).toBe("function");
  await release!(); await page.waitForLoadState("load");
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  await expect.poll(async () => {
    const box = await summary.boundingBox();
    const header = await page.locator(".app-header").boundingBox();
    return box !== null && header !== null && box.y >= header.y + header.height - 1 && box.y < 400;
  }).toBe(true);
  await expect(summary).toBeFocused();
});

for (const [device, width] of [["desktop", 1440], ["phone", 390]] as const) {
  test(`remembers the last manually opened area on reload: ${device}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 900 });
    await open(page, info.project.name);
    const area = page.locator("details.location").nth(12);
    const id = await area.getAttribute("data-location-id");
    await area.locator("summary").click();
    await expect(area.locator(".location-body")).toBeVisible();
    await page.reload();
    const restored = page.locator(`[data-location-id="${id}"]`);
    await expect(restored).toHaveJSProperty("open", true, { timeout: 3000 });
    await expect(restored.locator("summary")).toBeFocused();
    await expect.poll(async () => {
      const box = await restored.locator("summary").boundingBox();
      return box !== null && box.y >= 0 && box.y < 400;
    }).toBe(true);
    await page.screenshot({ path: info.outputPath(`restored-${device}.png`) });
  });
}

test("manual opening supersedes an earlier location URL", async ({ page }, info) => {
  await open(page, info.project.name);
  const linked = page.locator("details.location").nth(8);
  await page.evaluate(id => { location.hash = id!; }, await linked.getAttribute("id"));
  await page.reload();
  await expect(linked).toHaveJSProperty("open", true);
  const manual = page.locator("details.location").nth(12);
  await manual.locator("summary").click();
  await expect(manual.locator(".location-body")).toBeVisible();
  await page.reload();
  await expect(manual).toHaveJSProperty("open", true, { timeout: 3000 });
});

test("keeps separate last areas per game mode and leaves background browsing alone", async ({ page }, info) => {
  await open(page, info.project.name);
  const first = page.locator("details.location").nth(12);
  const firstId = await first.getAttribute("data-location-id");
  await first.locator("summary").click();
  await expect(first.locator(".location-body")).toBeVisible();
  await page.locator("#mode-select").selectOption("sun");
  const second = page.locator("details.location").nth(18);
  const secondId = await second.getAttribute("data-location-id");
  await second.locator("summary").click();
  await expect(second.locator(".location-body")).toBeVisible();
  await page.locator("#mode-select").selectOption("photonic-prismatic");
  await expect(page.locator(`[data-location-id="${firstId}"]`)).toHaveJSProperty("open", true);
  await page.locator("#mode-select").selectOption("sun");
  await expect(page.locator(`[data-location-id="${secondId}"]`)).toHaveJSProperty("open", true);
  await expect(page.locator(`[data-location-id="${secondId}"] summary`)).toBeFocused();
  await page.evaluate(() => { scrollTo({ top: 0, behavior: "instant" }); document.dispatchEvent(new Event("visibilitychange")); window.dispatchEvent(new Event("pageshow")); });
  expect(await page.evaluate(() => scrollY)).toBe(0);
  await page.reload();
  await expect(page.locator(`[data-location-id="${secondId}"]`)).toHaveJSProperty("open", true);
});

test("explicit encounter links beat remembered areas on launch", async ({ page }, info) => {
  await open(page, info.project.name);
  const rowId = await page.locator("tr[id^='encounter-']").first().getAttribute("id");
  const other = page.locator("details.location").nth(12);
  await other.locator("summary").click();
  await expect(other.locator(".location-body")).toBeVisible();
  await page.evaluate(id => { location.hash = id!; }, rowId);
  await page.reload();
  await expect(page.locator(`[id="${rowId}"]`)).toBeFocused();
});

test("corrupt preference falls back without losing collection progress", async ({ page }, info) => {
  await open(page, info.project.name);
  await page.locator('[data-action="species"][data-species="731"]').first().click();
  await page.evaluate(() => {
    for (const key of Object.keys(localStorage)) if (key.startsWith("pokemon-checklist-last-area-v1:")) localStorage.setItem(key, "removed/location");
  });
  await page.reload();
  await expect(page.locator("details.location").first()).toHaveJSProperty("open", true);
  await expect(page.locator("#overall-text")).toContainText("1 / 807");
});

test("switching local account namespaces restores only that account's area", async ({ page }, info) => {
  test.skip(info.project.name === "standalone-file", "Vite module fixture; offline behavior covered separately");
  await open(page, info.project.name);
  const offline = page.locator("details.location").nth(12);
  await offline.locator("summary").click();
  await expect(offline.locator(".location-body")).toBeVisible();
  await page.evaluate(async () => { const path = "/state.ts"; (await import(path)).setSyncAccount("area-memory-fixture", { adopt: false }); });
  const account = page.locator("details.location").nth(18);
  await account.locator("summary").click();
  await expect(account.locator(".location-body")).toBeVisible();
  await page.evaluate(async () => { const path = "/state.ts"; (await import(path)).setSyncAccount(null); });
  await expect(offline).toHaveJSProperty("open", true);
  await expect(offline.locator("summary")).toBeFocused();
  await page.evaluate(async () => { const path = "/state.ts"; (await import(path)).setSyncAccount("area-memory-fixture"); });
  await expect(account).toHaveJSProperty("open", true);
  await expect(account.locator("summary")).toBeFocused();
});

test("reopens the remembered area in a new page session", async ({ page, context }, info) => {
  await open(page, info.project.name);
  const area = page.locator("details.location").nth(12);
  const id = await area.getAttribute("data-location-id");
  await area.locator("summary").click();
  await expect(area.locator(".location-body")).toBeVisible();
  await page.close();
  const reopened = await context.newPage();
  await open(reopened, info.project.name);
  await expect(reopened.locator(`[data-location-id="${id}"]`)).toHaveJSProperty("open", true);
  await expect(reopened.locator(`[data-location-id="${id}"] summary`)).toBeFocused();
});

test("unavailable area storage leaves browsing and player saves working", async ({ page }, info) => {
  await page.addInitScript(() => {
    const set = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key, value) {
      if (key.startsWith("pokemon-checklist-last-area-v1:")) throw new DOMException("fixture quota", "QuotaExceededError");
      return set.call(this, key, value);
    };
  });
  await open(page, info.project.name);
  const area = page.locator("details.location").nth(12);
  await area.locator("summary").click();
  await expect(area.locator(".location-body")).toBeVisible();
  await expect(page.locator("#notice")).toContainText("Last area could not be remembered");
  await area.locator('[data-action="species"]').first().click();
  await page.reload();
  await expect(page.locator("#overall-text")).toContainText("1 / 807");
});
