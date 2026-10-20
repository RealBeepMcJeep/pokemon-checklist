import { expect, test } from "@playwright/test";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { writeFile } from "node:fs/promises";

test.use({ isMobile: true, hasTouch: true, deviceScaleFactor: 2.75 });

for (const surface of ["guide", "drawer"] as const) test(`status changes keep ${surface} background scroll stable through sync feedback`, async ({ page }, info) => {
  test.skip(info.project.name === "standalone-file", "Presentation-only sync signal fixture requires Vite; offline production reproduction retained separately.");
  await page.setViewportSize({ width: 393, height: 851 });
  const errors: string[] = [], blocked: string[] = [];
  page.on("pageerror", e => errors.push(e.message));
  page.on("console", e => { if (e.type() === "error") errors.push(e.text()); });
  await page.route("**/*", route => {
    const url = new URL(route.request().url());
    if (url.origin === new URL(info.project.use.baseURL as string).origin || ["data:", "blob:"].includes(url.protocol)) return route.continue();
    blocked.push(url.origin); return route.abort();
  });
  await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
  const fixture = { schemaVersion: 5, species: {}, forms: {}, starred: [], starredForms: [], settings: { forms: true, mode: "ultra-moon", unlocks: [] } };
  await page.evaluate(f => { localStorage.clear(); localStorage.setItem("pokemon-checklist-state-v5", JSON.stringify(f)); }, fixture);
  await page.reload();
  await expect(page.locator("#mode-select")).toHaveValue("ultra-moon");
  await expect(page.locator("#mode-select")).toBeEnabled();
  await expect(page.locator("#forms-toggle")).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("details.location[open] > summary").first()).toBeFocused();
  // Only change exported presentation signals. Never initialize Firebase/auth or switch save namespace.
  await page.evaluate(async () => { const path = "/sync/engine.ts"; const s = await import(path); s.syncAccount.value = { uid: "synthetic-scroll-presentation", email: "scroll@example.invalid" }; s.syncOnline.value = true; s.syncPhase.value = "ready"; });
  const row = page.locator('[data-location-id="melemele-island/route-1"] tbody tr').filter({ has: page.locator('.species-name .guide-pokemon-link').filter({ hasText: /^Pikipek$/ }) }).first();
  await expect(row).toHaveCount(1);
  await row.locator('.species-name').evaluate(e => e.scrollIntoView({ block: "center" }));
  await page.waitForTimeout(250);
  if (surface === "drawer") { await page.locator("#sidebar-toggle").click(); await page.locator("#dex-search").fill("Pikipek"); }
  const button = surface === "guide" ? row.locator('.species-name .status-button') : page.locator('#dex-list [data-action="species"][data-species="731"]');
  await expect(button).toHaveCount(1);
  const measure = async () => ({ scroll: await page.evaluate(() => scrollY), rowTop: (await row.boundingBox())!.y, header: await page.locator('.app-header').boundingBox(), spacer: await page.locator('.mobile-header-space').boundingBox() });
  const initial = await measure(), observations = [];
  for (const id of [731, 10]) {
    if (surface === "drawer") await page.locator('#dex-search').fill(id === 731 ? 'Pikipek' : 'Caterpie');
    const targetButton = surface === "guide"
      ? page.locator(`[data-location-id="melemele-island/route-1"] .species-name .status-button[data-species="${id}"]`).first()
      : page.locator(`#dex-list [data-action="species"][data-species="${id}"]`);
    await expect(targetButton).toHaveCount(1);
    for (const status of ["caught", "seen", "none"]) {
    await targetButton.tap();
    await expect.poll(() => page.evaluate(id => JSON.parse(localStorage.getItem("pokemon-checklist-state-v5")!).species[String(id)] || "none", id)).toBe(status);
    await page.evaluate(async () => { const path = "/sync/engine.ts"; const s = await import(path); s.syncPending.value = 1; s.syncPhase.value = "pending"; });
    await expect(page.locator('.mobile-sync-warning')).toContainText('1 to send');
    await page.waitForTimeout(100);const pending = await measure();
    await page.evaluate(async () => { const path = "/sync/engine.ts"; const s = await import(path); s.syncPending.value = 0; s.syncPhase.value = "ready"; });
    await expect(page.locator('.mobile-sync-healthy')).toHaveAttribute('aria-label', 'Synced');
    await page.waitForTimeout(100);const ready = await measure();observations.push({ id, status, pending, ready });
    }
  }
  const diagnostics = info.outputPath('scroll-observations.json');
  await writeFile(diagnostics, JSON.stringify({ initial, observations }, null, 2));
  await info.attach('scroll-observations', { path: diagnostics, contentType: 'application/json' });
  await page.screenshot({ path: info.outputPath(`status-${surface}.png`) });
  for (const observation of observations) for (const sample of [observation.pending, observation.ready]) {
    expect(Math.abs(sample.scroll - initial.scroll), JSON.stringify({ initial, observations })).toBeLessThanOrEqual(1);
    expect(Math.abs(sample.rowTop - initial.rowTop)).toBeLessThanOrEqual(1);
  }
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("pokemon-checklist-state-v5")!))).toEqual(fixture);
  expect(errors).toEqual([]);expect(blocked).toEqual([]);
});

for (const width of [360, 412]) for (const surface of ["guide", "drawer"] as const) test(`unsigned ${surface} status cycles preserve page position ${width}px`, async ({ page }, info) => {
  await page.setViewportSize({ width, height: 915 });
  const errors: string[] = [];
  page.on("pageerror", e => errors.push(e.message));
  page.on("console", e => { if (e.type() === "error") errors.push(e.text()); });
  await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
  const fixture = { schemaVersion: 5, species: {}, forms: {}, starred: [], starredForms: [], settings: { forms: true, mode: "ultra-moon", unlocks: [] } };
  await page.evaluate(f => { localStorage.clear(); localStorage.setItem("pokemon-checklist-state-v5", JSON.stringify(f)); }, fixture);
  await page.reload();
  await expect(page.locator("#mode-select")).toHaveValue("ultra-moon");await expect(page.locator("#mode-select")).toBeEnabled();
  await expect(page.locator('details.location[open] > summary').first()).toBeFocused();
  const row = page.locator('[data-location-id="melemele-island/route-1"] tbody tr').filter({ has: page.locator('.species-name .guide-pokemon-link').filter({ hasText: /^Pikipek$/ }) }).first();
  await expect(row).toHaveCount(1);await row.locator('.species-name').evaluate(e => e.scrollIntoView({ block: "center" }));
  if (surface === "drawer") { await page.locator('#sidebar-toggle').tap();await page.locator('#dex-search').fill('Pikipek'); }
  const button = surface === "guide" ? row.locator('.species-name .status-button') : page.locator('#dex-list [data-action="species"][data-species="731"]');
  await expect(button).toHaveCount(1);
  const initial = await page.evaluate(() => scrollY), top = (await row.boundingBox())!.y;
  for (const status of ['caught', 'seen', 'none']) {
    await button.tap();await expect.poll(() => page.evaluate(() => JSON.parse(localStorage.getItem('pokemon-checklist-state-v5')!).species['731'] || 'none')).toBe(status);
    await expect(page.locator('#notice-action')).toHaveText('Undo');
    await expect.poll(() => page.evaluate(() => scrollY)).toBe(initial);
    await expect.poll(async () => (await row.boundingBox())!.y).toBe(top);
  }
  if (surface === 'drawer') {
    await page.keyboard.press('Escape');await expect(page.locator('#sidebar-toggle')).toBeFocused();
    expect(await page.evaluate(() => scrollY)).toBe(initial);
  }
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('pokemon-checklist-state-v5')!))).toEqual(fixture);
  expect(errors).toEqual([]);
});

test('returning to top reserves long sync/error feedback without hiding the first section', async ({ page }, info) => {
  test.skip(info.project.name === 'standalone-file', 'Source-module presentation fixture; actual backup-at-top is covered for both protocols.');
  await page.setViewportSize({ width: 393, height: 851 });
  const errors: string[] = [], blocked: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', e => { if (e.type() === 'error') errors.push(e.text()); });
  await page.route('**/*', route => { const u=new URL(route.request().url()); if (['localhost','127.0.0.1'].includes(u.hostname) || ['data:','blob:'].includes(u.protocol)) return route.continue(); blocked.push(u.href); return route.abort(); });
  await page.goto('/');await expect(page.locator('details.location[open] > summary').first()).toBeFocused();
  await page.evaluate(() => scrollTo(0, 600));
  const before = await page.evaluate(() => scrollY);
  await page.evaluate(async () => { const path='/sync/engine.ts';const s=await import(path);s.syncAccount.value={uid:'synthetic-error-presentation',email:'error@example.invalid'};s.syncOnline.value=false;s.syncMessage.value='Sync is temporarily unavailable. Your progress is saved on this device; reconnect to send the pending changes to your other devices.';s.syncPhase.value='error'; });
  await expect(page.locator('.mobile-sync-warning')).toContainText('Sync is temporarily unavailable');
  expect(await page.evaluate(() => scrollY)).toBe(before);
  await page.evaluate(() => scrollTo(0, 0));
  await expect.poll(async () => {
    const header=await page.locator('.app-header').boundingBox(),first=await page.locator('.island > h2').first().boundingBox();
    return first!.y-(header!.y+header!.height);
  }).toBeGreaterThanOrEqual(0);
  await expect(page.locator('.mobile-sync-warning')).toContainText('reconnect');
  expect(errors).toEqual([]);expect(blocked).toEqual([]);
});
