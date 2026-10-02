import { expect, test, type Page } from "@playwright/test";
import { createServer, type Server } from "node:http";
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

const galleryFile = pathToFileURL(resolve("qr.html")).href;
let httpServer: Server;
let httpGalleryUrl = "";

test.beforeAll(async () => {
  httpServer = createServer((request, response) => {
    if (request.url !== "/qr.html") {
      response.writeHead(404).end("not found");
      return;
    }
    response.writeHead(200, { "content-type": "text/html; charset=utf-8" });
    response.end(readFileSync(resolve("qr.html")));
  });
  await new Promise<void>((resolveListen, reject) => {
    httpServer.once("error", reject);
    httpServer.listen(0, "127.0.0.1", () => {
      const address = httpServer.address();
      if (!address || typeof address === "string") {
        reject(new Error("Could not resolve the temporary gallery HTTP address"));
        return;
      }
      httpGalleryUrl = `http://127.0.0.1:${address.port}/qr.html`;
      resolveListen();
    });
  });
});

test.afterAll(async () => {
  if (httpServer?.listening) await new Promise<void>((resolveClose) => httpServer.close(() => resolveClose()));
});

async function openGallery(page: Page, project: string): Promise<string[]> {
  const errors: string[] = [];
  const externalRequests: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    if (/^https?:\/\//.test(request.url())) {
      const local = project === "vite-dev" && request.url().startsWith(httpGalleryUrl);
      if (!local) externalRequests.push(request.url());
    }
  });
  if (project === "standalone-file") {
    await page.route(/^https?:\/\//, (route) => route.abort("blockedbyclient"));
    await page.goto(galleryFile);
  } else {
    await page.route(/^https?:\/\//, (route) => route.request().url().startsWith(httpGalleryUrl)
      ? route.continue()
      : route.abort("blockedbyclient"));
    await page.goto(httpGalleryUrl);
  }
  await expect(page.locator("#ordinary-gallery .qr-card")).toHaveCount(244);
  await expect(page.locator("#result-count")).toHaveText("Showing 244 of 244 ordinary QR records");
  expect(externalRequests).toEqual([]);
  return errors;
}

test("gift cards use the shared mobile viewer with separate navigation and accessible close/back", async ({ page }, testInfo) => {
  const errors = await openGallery(page, testInfo.project.name);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator("#search").fill("not a Pokémon");
  const gifts = page.locator("#promotional-gifts .gift-card");
  await expect(gifts).toHaveCount(2);
  for (const width of [360, 390, 1440]) {
    await page.setViewportSize({ width, height: 844 });
    const sourceVisibility = await gifts.evaluateAll(cards => cards.map(card => {
      const outer = card.getBoundingClientRect();
      const sources = card.querySelector(".gift-sources")!.getBoundingClientRect();
      return card.querySelectorAll(".gift-sources a").length > 0 && sources.top >= outer.top && sources.bottom <= outer.bottom;
    }));
    expect(sourceVisibility).toEqual([true, true]);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  const opener = gifts.first().locator(".card-open");
  await gifts.first().locator(".qr-original").click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.locator("#scan-title")).toHaveText("Magearna · Event gift");
  await expect(page.locator("#scan-details")).toContainText("US/American-region");
  await expect(page.locator("#scan-image")).toHaveJSProperty("naturalWidth", 147);
  await expect(page.locator("#scan-close")).toBeFocused();
  await expect(page.locator("html")).toHaveCSS("overflow", "hidden");
  await page.keyboard.press("Shift+Tab");
  await expect(page.locator("#scan-source-link")).toBeFocused();
  await page.locator("#scan-next").click();
  await expect(page.locator("#scan-title")).toHaveText("Partner Cap Pikachu · Event gift");
  await expect(page.locator("#scan-details")).toContainText("Pikachu Valley");
  await page.keyboard.press("ArrowLeft");
  await expect(page.locator("#scan-title")).toHaveText("Magearna · Event gift");
  await page.locator("#scan-close").click();
  await expect(page.getByRole("dialog")).toBeHidden();
  await expect(opener).toBeFocused();
  await expect(page.locator("html")).not.toHaveCSS("overflow", "hidden");
  await opener.click();
  await page.goBack();
  await expect(page.getByRole("dialog")).toBeHidden();
  await expect(opener).toBeFocused();
  expect(errors).toEqual([]);
});

test("renders the complete offline source archive and composes search/type/library filters", async ({ page }, testInfo) => {
  const errors = await openGallery(page, testInfo.project.name);
  await expect(page.locator("#ordinary-gallery .qr-original")).toHaveCount(244);
  await expect(page.locator(".sprite-atlas").first()).toHaveJSProperty("naturalWidth", 1280);
  await expect(page.locator("#promotional-gifts .gift-card")).toHaveCount(2);
  await expect(page.locator("#ordinary-gallery")).toContainText("Rowlet");

  for (const width of [360, 390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    const overflow = await page.evaluate(() => ({
      page: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      grid: document.querySelector<HTMLElement>("#cards")!.scrollWidth - document.querySelector<HTMLElement>("#cards")!.clientWidth,
    }));
    expect(overflow, `horizontal overflow at ${width}px`).toEqual({ page: 0, grid: 0 });
  }

  await page.locator("#search").fill("Ampharos Mega");
  await page.locator("#type-filter").selectOption("Electric");
  await page.locator("#library-filter").selectOption("ultra-sun-ultra-moon");
  const match = page.locator('.qr-card:not([hidden])[data-name="Ampharos"]');
  await expect(match).toHaveCount(1);
  await expect(match).toHaveAttribute("data-form-label", "Mega");
  await expect(page.locator("#result-count")).toHaveText("Showing 1 of 244 ordinary QR records");
  await page.locator("#search").fill("not a Pokémon");
  await expect(page.locator("#ordinary-gallery .qr-card:not([hidden])")).toHaveCount(0);
  await expect(page.locator("#empty-state")).toBeVisible();
  expect(errors).toEqual([]);
});

test("opens the original QR in a white full-viewport scan viewer and supports keyboard, focus, scroll lock, close and back", async ({ page }, testInfo) => {
  const errors = await openGallery(page, testInfo.project.name);
  await page.setViewportSize({ width: 390, height: 844 });
  const rowlet = page.locator('.qr-card[data-name="Rowlet"][data-form="0"]');
  const opener = rowlet.locator(".card-open");
  await rowlet.locator(".qr-original").click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(page.locator("#scan-title")).toHaveText("Rowlet · Standard");
  await expect.poll(() => page.locator("#scan-image").evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true);
  await expect(page.locator(".scan-sheet")).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await expect(page.locator("#scan-source-link")).toBeVisible();
  await expect(page.locator("#scan-source-link")).toHaveAttribute("href", /^https:\/\/archives\.bulbagarden\.net\//);
  await expect(page.locator("#scan-close")).toBeFocused();
  await expect(page.locator("html")).toHaveCSS("overflow", "hidden");
  await expect(page.locator("body")).toHaveCSS("overflow", "hidden");
  const viewportLock = await page.evaluate(() => {
    const before = window.scrollY;
    return { before, html: document.documentElement.style.overflow, body: document.body.style.overflow };
  });
  expect(viewportLock.html).toBe("hidden");
  expect(viewportLock.body).toBe("hidden");
  const beforeWheel = await page.evaluate(() => window.scrollY);
  await page.mouse.move(6, 600);
  await page.mouse.wheel(0, 450);
  await page.waitForTimeout(100);
  expect(await page.evaluate(() => window.scrollY)).toBe(beforeWheel);
  const box = await dialog.boundingBox();
  expect(box?.width).toBe(390);
  expect(box?.height).toBe(844);

  await page.keyboard.press("Shift+Tab");
  await expect(page.locator("#scan-source-link")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.locator("#scan-close")).toBeFocused();
  await page.keyboard.press("ArrowRight");
  await expect(page.locator("#scan-title")).not.toHaveText("Rowlet · Standard");
  await page.keyboard.press("ArrowLeft");
  await expect(page.locator("#scan-title")).toHaveText("Rowlet · Standard");
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(opener).toBeFocused();
  await expect(page.locator("html")).not.toHaveCSS("overflow", "hidden");

  await rowlet.locator(".card-open").click();
  await expect(dialog).toBeVisible();
  await page.goBack();
  await expect(dialog).toBeHidden();
  await expect(opener).toBeFocused();
  expect(errors).toEqual([]);
});
