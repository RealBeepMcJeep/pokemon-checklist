import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

async function openSourceFixture(page: Page, info: TestInfo) {
  const errors: string[] = [];
  // Capture the first render, not only interactions after the fixture reload.
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "./");
  // Deliberately synthetic, signed-out collection; no account/auth fixtures.
  const species = Object.fromEntries(Array.from({ length: 807 }, (_, index) => index + 1)
    .filter(id => id !== 25 && id !== 440).map(id => [String(id), "caught"]));
  await page.evaluate(species => {
    localStorage.clear();
    localStorage.setItem("pokemon-checklist-state-v4", JSON.stringify({
      schemaVersion: 4, species, forms: {}, starred: [],
      settings: { forms: false, mode: "photonic-prismatic", unlocks: ["sos", "weather-sos"] },
    }));
  }, species);
  await page.reload();
  return { errors, species };
}

async function openArea(page: Page, id: string) {
  const area = page.locator(`[data-location-id="${id}"]`);
  if (!await area.evaluate(el => (el as HTMLDetailsElement).open)) await area.locator("summary").click();
  return area;
}

for (const width of [390, 1440]) test.describe(`SOS source corrections at ${width}px`, () => {
  test.use({ viewport: { width, height: 950 }, isMobile: width === 390, hasTouch: width === 390 });

  test("Route 1 callers and distinct Catch-next targets render without duplicate keys", async ({ page }, info) => {
    const { errors, species } = await openSourceFixture(page, info);
    const route = await openArea(page, "melemele-island/route-1");
    const pichu = route.locator("tr").filter({ has: page.getByRole("button", { name: "Pichu", exact: true }) });
    const calls = pichu.locator(".inline-sos");
    await expect(calls).toHaveCount(1);
    await expect(calls).toContainText("these callers occur in the Route 1 grass");
    await expect(route.locator(".group-heading strong").filter({ hasText: /^SOS Calls$/ })).toHaveCount(0);
    await expect(calls.getByRole("button", { name: "Pikachu", exact: true })).toBeVisible();
    await expect(calls.getByRole("button", { name: "Happiny", exact: true })).toBeVisible();
    await expect(calls.locator(".sos-legend")).toContainText("share not documented");
    await expect(calls.locator(".sos-legend")).not.toContainText("%");
    const outskirts = await openArea(page, "melemele-island/hauoli-outskirts");
    await expect(outskirts.getByRole("button", { name: "Rattata (Kanto)", exact: true })).toHaveCount(0);
    await expect(outskirts.getByRole("button", { name: "Pichu", exact: true })).toHaveCount(0);

    if (width === 390) await page.locator("#sidebar-toggle").click();
    const next = page.locator(".catch-next");
    await expect(next.locator("summary")).toHaveText("Catch next in Route 1");
    if (!await next.evaluate(el => (el as HTMLDetailsElement).open)) await next.locator("summary").click();
    await expect(next.locator(".catch-next-name")).toHaveText(["Pikachu", "Happiny"]);
    await expect(next.locator(".catch-next-name").first()).toBeVisible();
    await expect(next.locator(".catch-next-name").last()).toBeVisible();
    await page.screenshot({ path: info.outputPath("route-one-catch-next.png") });
    const saved = await page.evaluate(() => ({
      state: JSON.parse(localStorage.getItem("pokemon-checklist-state-v5")!),
      legacy: JSON.parse(localStorage.getItem("pokemon-checklist-state-v4")!),
    }));
    expect(saved.state.species).toEqual(species);
    expect(saved.state.forms).toEqual({});
    expect(saved.state.starred).toEqual([]);
    expect(saved.state.schemaVersion).toBe(5);
    expect(saved.state.starredForms).toEqual([]);
    // Keep the old input and assert real migration, rather than merely reseeding v5.
    expect(saved.legacy.schemaVersion).toBe(4);
    expect(saved.legacy.species).toEqual(species);
    expect(errors).toEqual([]);
  });

  test("distinct weather rates and unverified caller warning survive migration into the inline guide", async ({ page }, info) => {
    const { errors } = await openSourceFixture(page, info);
    const haina = await openArea(page, "ulaula-island/haina-desert");
    const caller = haina.locator("#encounter-ulaula-island-haina-desert-sand-1-1");
    const weather = caller.locator('.sos-entry[data-sos-kind="weather-sos"]');
    const castform = weather.filter({ has: page.getByRole("button", { name: "Castform", exact: true }) });
    await expect(haina.locator(".group-heading strong").filter({ hasText: /^Weather SOS$/ })).toHaveCount(0);
    await expect(castform).toHaveCount(1);
    await expect(castform.locator(".sos-rule")).toHaveCount(2);
    const sand = castform.locator(".sos-rule").filter({ hasText: "Sandstorm" });
    const rain = castform.locator(".sos-rule").filter({ hasText: "Rain, Hail" });
    await expect(sand.locator(".sos-method")).toContainText("guide-reported rate: 1%");
    await expect(rain.locator(".sos-method")).toContainText("guide-reported rate: 11%");
    await expect(caller.locator(".species-name .guide-pokemon-link").first()).toHaveText("Krokorok");
    await expect(caller.locator("td").first()).toHaveText("Krokorok · 20%");
    await expect(sand).toContainText("not a per-turn or call-success probability");
    await expect(sand).toContainText("Guide-reported SOS encounter rate");
    await weather.locator("img").evaluateAll(imgs => Promise.all(imgs.map(img => (img as HTMLImageElement).decode().catch(() => {}))));
    await sand.scrollIntoViewIfNeeded();
    await page.screenshot({ path: info.outputPath("haina-sandstorm-rate.png") });
    const route = await openArea(page, "ulaula-island/route-15-16");
    const crab = route.locator(".sos-source-warning").filter({ hasText: "Crabrawler" });
    await expect(crab).toContainText(/caller availability is unverified/i);
    await expect(crab).toContainText("do not assume Shuckle calls Crabominable");
    // Missing source evidence stays a warning, not a fabricated wild caller/control.
    await expect(route.getByRole("button", { name: "Crabrawler", exact: true })).toHaveCount(0);
    await expect(route.locator('[data-action="species"][data-species="739"]')).toHaveCount(0);
    await crab.scrollIntoViewIfNeeded();
    await page.screenshot({ path: info.outputPath("unverified-caller.png") });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    expect(errors).toEqual([]);
  });
});
