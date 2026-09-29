// Renders the home-screen app icon (a flat Poké Ball on the app's dark background)
// from an inline SVG, at every size src/index.html embeds as a data: URL. No network
// request and no second committed asset format: Chromium just rasterizes text we
// already have. Re-run after changing the SVG below, then re-embed the PNGs as
// base64 in src/index.html's <head> (apple-touch-icon + manifest icons).
import { writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { chromium } from "playwright-core";

const ROOT = resolve(import.meta.dirname, "..");
const SIZES = [180, 512];
// iOS renders transparent pixels in an apple-touch-icon as black, so the square is
// fully opaque (the app's dark "paper" background) rather than a transparent PNG.
const SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <rect width="100" height="100" fill="#0d0814"/>
  <circle cx="50" cy="50" r="34" fill="#fff"/>
  <path d="M 16 50 A 34 34 0 0 1 84 50 Z" fill="#ef4136"/>
  <rect x="16" y="46" width="68" height="8" fill="#150e20"/>
  <circle cx="50" cy="50" r="10" fill="#150e20"/>
  <circle cx="50" cy="50" r="6" fill="#fff"/>
</svg>`;

const browser = await chromium.launch();
try {
  for (const size of SIZES) {
    const page = await browser.newPage({
      viewport: { width: size, height: size },
      deviceScaleFactor: 1,
    });
    await page.setContent(
      `<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0}</style></head>` +
        `<body>${SVG.replace("<svg ", `<svg width="${size}" height="${size}" `)}</body></html>`,
    );
    const png = await page.screenshot();
    const out = resolve(ROOT, "assets", `app-icon-${size}.png`);
    writeFileSync(out, png);
    console.log(`Wrote ${out.replace(ROOT + "\\", "").replace(ROOT + "/", "")} (${size}x${size})`);
    await page.close();
  }
} finally {
  await browser.close();
}
