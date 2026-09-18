// Render a self-contained HTML card to PNG using the Chromium that ships in the image.
// Used by tools/moveline.py --png; kept separate because Python has no rasteriser here.
import { chromium } from "playwright-core";

const [htmlPath, pngPath, widthArg] = process.argv.slice(2);
if (!htmlPath || !pngPath) {
  console.error("usage: node tools/render-png.mjs <input.html> <output.png> [width]");
  process.exit(2);
}

const width = Number(widthArg) || 940;
const browser = await chromium.launch({ args: ["--no-sandbox"] });
try {
  const page = await browser.newPage({
    viewport: { width, height: 800 },
    deviceScaleFactor: 2, // crisp text and sprites in the delivered image
  });
  await page.goto(`file://${htmlPath}`);
  // The atlas is a data URL, so there is nothing to fetch; one frame is enough for layout,
  // but wait for fonts so the first paint is not measured short.
  await page.evaluate(() => document.fonts.ready);
  const height = await page.evaluate(() => document.body.scrollHeight);
  await page.setViewportSize({ width, height: Math.ceil(height) });
  await page.screenshot({ path: pngPath, fullPage: true });
  console.log(`wrote ${pngPath} (${width}×${Math.ceil(height)} css px)`);
} finally {
  await browser.close();
}
