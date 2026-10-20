import { expect, test } from "@playwright/test";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
for (const width of [360, 1440]) test(`compact status labels remain readable without emoji fonts ${width}px`, async ({ page }, info) => {
  await page.setViewportSize({ width, height: 950 });
  await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
  const controls = page.locator(".guide-pokemon > .status-button");
  await expect(controls.first()).toBeVisible();
  const ids = await controls.evaluateAll(elements => [...new Set(elements.map(el => Number((el as HTMLElement).dataset.species)).filter(Boolean))].slice(0, 3));
  expect(ids).toHaveLength(3);
  const key = "pokemon-checklist-state-v5";
  const fixture = { schemaVersion: 5, species: { [ids[1]]: "seen", [ids[2]]: "caught" }, forms: {}, starred: [], starredForms: [], settings: { forms: false, mode: "photonic-prismatic", unlocks: [] } };
  await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
  await page.evaluate(({ key, fixture }) => { localStorage.clear(); localStorage.setItem(key, JSON.stringify(fixture)); }, { key, fixture });
  await page.reload();
  await expect(page.locator("#mode-select")).toHaveValue("photonic-prismatic");
  await expect(page.locator("#mode-select")).toBeEnabled();
  await expect(page.locator("#forms-toggle")).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByText("Your saved checklist could not be read", { exact: false })).toHaveCount(0);
  await expect(page.locator("details.location[open] > summary").first()).toBeFocused();
  for (const [index, text] of ["None", "Seen", "Caught"].entries()) {
    const button = page.locator(`.guide-pokemon > .status-button[data-species="${ids[index]}"]`).first();
    await expect(button).toHaveCount(1);
    const label = button.locator(".status-text");
    await expect(label).toHaveText(text);
    const box = await label.boundingBox();
    expect(box!.width).toBeGreaterThanOrEqual(20);
    expect(box!.height).toBeGreaterThanOrEqual(12);
    const bounds = await button.boundingBox();
    expect(bounds!.height).toBeGreaterThanOrEqual(width < 1000 ? 44 : 32);
    expect(await label.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
  }
  const first = page.locator(`.guide-pokemon > .status-button[data-species="${ids[0]}"]`).first();
  await first.evaluate(el => scrollBy(0, el.getBoundingClientRect().top - document.querySelector(".app-header")!.getBoundingClientRect().bottom - 16));
  await page.screenshot({ path: info.outputPath("compact-status-labels.png") });
  expect(await page.evaluate(key => JSON.parse(localStorage.getItem(key)!), key)).toEqual(fixture);
});
