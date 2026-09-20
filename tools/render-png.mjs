import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright-core";

const [htmlPathArg, pngPathArg, widthArg, ...flags] = process.argv.slice(2);
if (!htmlPathArg || !pngPathArg) {
  console.error("usage: node tools/render-png.mjs <input.html> <output.png> [width] [--assert-no-overflow]");
  process.exit(2);
}

const htmlPath = resolve(htmlPathArg);
const pngPath = resolve(pngPathArg);
const width = Number(widthArg) || 940;
const assertNoOverflow = flags.includes("--assert-no-overflow");
const browser = await chromium.launch();
const context = await browser.newContext({
  javaScriptEnabled: false,
  viewport: { width, height: 800 },
  deviceScaleFactor: 2, // crisp text and sprites in the delivered image
});
await context.route("**/*", (route) => {
  const protocol = new URL(route.request().url()).protocol;
  if (protocol === "file:" || protocol === "data:") return route.continue();
  return route.abort();
});
try {
  const page = await context.newPage();
  await page.goto(pathToFileURL(htmlPath).href);
  // The atlas is a data URL, so there is nothing to fetch; one frame is enough for layout,
  // but wait for fonts so the first paint is not measured short.
  await page.evaluate(() => document.fonts.ready);
  const layout = await page.evaluate(() => ({
    height: document.body.scrollHeight,
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  if (assertNoOverflow && layout.scrollWidth > layout.clientWidth) {
    const offenders = await page.evaluate(() => [...document.querySelectorAll("*")]
      .map((element) => ({
        tag: element.tagName,
        className: element.className,
        width: Math.ceil(element.getBoundingClientRect().width),
        right: Math.ceil(element.getBoundingClientRect().right),
        text: (element.textContent || "").trim().slice(0, 80),
      }))
      .filter((item) => item.right > document.documentElement.clientWidth)
      .slice(0, 3));
    throw new Error(`horizontal overflow at ${width}px: ${layout.scrollWidth} > ${layout.clientWidth}; ${JSON.stringify(offenders)}`);
  }
  const height = Math.ceil(layout.height);
  await page.setViewportSize({ width, height });
  await mkdir(dirname(pngPath), { recursive: true });
  await page.screenshot({ path: pngPath, fullPage: true });
  console.log(`wrote ${pngPath} (${width}×${height} css px)`);
} finally {
  await context.close();
  await browser.close();
}
