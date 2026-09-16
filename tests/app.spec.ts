import { expect, test, type Page } from "@playwright/test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

const standaloneUrl = pathToFileURL(resolve("index.html")).href;

async function openApp(page: Page, project: string): Promise<string[]> {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  if (project === "standalone-file") {
    await page.route(/^https?:\/\//, (route) => route.abort("blockedbyclient"));
    await page.goto(standaloneUrl);
  } else {
    await page.goto("/");
  }
  await expect(page.locator("#overall-text")).toHaveText("0 / 807 Pokémon");
  return errors;
}

test("renders the complete responsive checklist", async ({
  page,
}, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);
  await expect(page.locator("details.location")).toHaveCount(60);
  await expect(page.locator("details.location[open]")).toHaveCount(1);
  await expect(page.locator(".dex-row")).toHaveCount(807);
  await expect(
    page.locator(".dex-row").first().locator(".type-mark"),
  ).toHaveCount(2);
  await expect(
    page.locator(".dex-row").first().locator(".grade-badge"),
  ).toHaveText("B");
  await expect(
    page.locator(".dex-row").first().locator(".grade-badge"),
  ).toHaveAttribute(
    "title",
    /Inherited from Venusaur.*tier RU.*Without evolution inheritance, Bulbasaur's tier is LC.*OU usage: 1\.62%/,
  );
  const guidePokemon = page.locator("tbody .guide-pokemon").first();
  await expect(
    guidePokemon.locator(".compact-status .status-symbol"),
  ).toHaveText("❌");
  await expect(guidePokemon.locator(".compact-status .icon")).toHaveCount(0);
  await expect(
    guidePokemon.locator(".guide-pokemon-identity .icon"),
  ).toHaveCount(1);
  await expect(guidePokemon.locator(".type-mark")).toHaveCount(2);
  await expect(guidePokemon.locator(".grade-badge")).toHaveText("F");
  await guidePokemon.locator(".guide-pokemon-link").click();
  await expect(page.locator("#dex-selection .selected-title")).toContainText(
    "Pikipek",
  );
  await expect(page.locator("#mode-select option")).toHaveCount(5);
  await expect(page.locator("tbody .icon").first()).toHaveCSS("width", "40px");
  await expect(page.getByAltText("Route 1 numbered grass map")).toBeVisible();
  await expect(page.getByAltText("Melemele Island overview map")).toBeVisible();
  expect(errors).toEqual([]);
});

test("updates matching controls and preserves progress across modes", async ({
  page,
}, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);
  const pikipek = page.locator('[data-action="species"][data-species="731"]');
  await pikipek.first().click();
  await expect(pikipek.locator(".status-text")).toHaveText([
    "Caught",
    "Caught",
  ]);
  await expect(pikipek.first().locator(".status-symbol")).toHaveText("✅");
  await expect(
    page.locator("details.location .location-progress").first(),
  ).toContainText("1 / 23");

  const expected = {
    sun: 57,
    moon: 57,
    "ultra-sun": 60,
    "ultra-moon": 60,
    "photonic-prismatic": 60,
  } as const;
  for (const [mode, locations] of Object.entries(expected)) {
    await page.locator("#mode-select").selectOption(mode);
    await expect(page.locator("details.location")).toHaveCount(locations);
    await expect(
      page.locator('[data-action="species"][data-species="731"]').first(),
    ).toContainText("Caught");
    await expect(page.locator("html")).toHaveAttribute("data-mode", mode);
  }
  await page.reload();
  await expect(
    page.locator('[data-action="species"][data-species="731"]').first(),
  ).toContainText("Caught");
  expect(errors).toEqual([]);
});

test("searches, selects, and navigates to known locations", async ({
  page,
}, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);
  await page.locator("#dex-search").fill("807");
  await expect(page.locator(".dex-row")).toHaveCount(1);
  await expect(page.locator(".dex-name")).toContainText("Zeraora");
  await page.locator("#dex-search").fill("6");
  await page.locator('[data-action="select"][data-species="6"]').click();
  await expect(page.locator("#dex-selection .location-links")).toContainText(
    "No direct wild location in this mode",
  );
  await expect(
    page.locator("#dex-selection .evolution-path .evolution-link"),
  ).toHaveText(["Charmander", "Charmeleon", "Charizard"]);
  await expect(
    page.locator("#dex-selection .evolution-path .evolution-method"),
  ).toHaveText(["Level 16 →", "Level 36 →"]);
  await page
    .locator("#dex-selection .evolution-path")
    .getByRole("button", { name: "Charmander", exact: true })
    .click();
  await expect(page.locator("#dex-selection .selected-title")).toContainText(
    "#004 Charmander",
  );

  await page.locator("#dex-search").fill("731");
  await page.locator('[data-action="select"][data-species="731"]').click();
  await expect(page.locator("#dex-selection")).toContainText("Pikipek");
  await expect(page.locator("#dex-selection .bulbapedia-link")).toHaveAttribute(
    "href",
    "https://bulbapedia.bulbagarden.net/wiki/Pikipek_(Pok%C3%A9mon)",
  );
  await expect(page.locator("#dex-selection .bulbapedia-link")).toHaveAttribute(
    "target",
    "_blank",
  );
  const link = page.locator("#dex-selection .location-links a").first();
  await expect(link).toContainText("Route 1");
  const targetId = (await link.getAttribute("href"))?.slice(1);
  if (!targetId) throw new Error("Location link has no target");
  await link.click();
  await expect(page.locator(`#${targetId}`)).toBeFocused();
  expect(new URL(page.url()).hash).toBe(`#${targetId}`);
  expect(errors).toEqual([]);
});

test("tracks forms and validates restore, migration, and reset", async ({
  page,
}, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);
  await page.locator("#forms-toggle").click();
  await page.locator("#dex-search").fill("37");
  await page.locator('[data-action="select"][data-species="37"]').click();
  const alolan = page.locator("#dex-selection .form-detail").filter({
    has: page.locator('[data-form="37:alolan"]'),
  });
  await expect(alolan.locator(".type-mark")).toHaveCount(1);
  await expect(alolan.locator(".grade-badge")).toHaveText("S");
  await expect(alolan.locator(".grade-badge")).toHaveAttribute(
    "title",
    /Ninetales-Alola.*UUBL/,
  );
  const form = page.locator('[data-action="form"]').first();
  const formKey = await form.getAttribute("data-form");
  await form.click();
  const promotedId = formKey!.split(":")[0];
  await expect(
    page
      .locator(`[data-action="species"][data-species="${promotedId}"]`)
      .first(),
  ).toContainText("Caught");

  page.once("dialog", (dialog) => dialog.accept());
  await page.locator("#import-file").setInputFiles({
    name: "save.json",
    mimeType: "application/json",
    buffer: Buffer.from(
      JSON.stringify({
        schemaVersion: 2,
        species: { 25: "caught" },
        forms: {},
        settings: { forms: false, mode: "ultra-moon" },
      }),
    ),
  });
  await expect(page.locator("#notice")).toHaveText("Backup restored.");
  await expect(page.locator("html")).toHaveAttribute("data-mode", "ultra-moon");
  await expect(
    page.locator('[data-action="species"][data-species="25"]').first(),
  ).toContainText("Caught");

  await page.locator("#import-file").setInputFiles({
    name: "bad.json",
    mimeType: "application/json",
    buffer: Buffer.from(
      '{"schemaVersion":2,"species":{"808":"caught"},"forms":{},"settings":{"forms":false,"mode":"sun"}}',
    ),
  });
  await expect(page.locator("#notice")).toContainText("Restore failed");
  await expect(
    page.locator('[data-action="species"][data-species="25"]').first(),
  ).toContainText("Caught");

  await page.evaluate(() => {
    localStorage.clear();
    localStorage.setItem(
      "pokemon-checklist-state-v1",
      JSON.stringify({
        schemaVersion: 1,
        species: { 25: "seen" },
        forms: {},
        settings: { forms: true },
      }),
    );
  });
  await page.reload();
  await expect(page.locator("#mode-select")).toHaveValue("photonic-prismatic");
  await expect(
    page.locator('[data-action="species"][data-species="25"]').first(),
  ).toContainText("Seen");

  page.once("dialog", (dialog) => dialog.accept());
  await page.locator("#reset-button").click();
  await expect(page.locator("#overall-text")).toHaveText("0 / 807 Pokémon");
  await expect(page.locator("#mode-select")).toHaveValue("photonic-prismatic");
  expect(errors).toEqual([]);
});

test("opens the Pokédex drawer without mobile overflow", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const errors = await openApp(page, testInfo.project.name);
  await page.locator("tbody .guide-pokemon-link").first().click();
  await expect(page.locator("#pokedex")).toHaveClass(/drawer-open/);
  await expect(page.locator("#dex-selection .selected-title")).toContainText(
    "Pikipek",
  );
  await expect(page.locator("#pokedex")).toHaveAttribute(
    "aria-hidden",
    "false",
  );
  const sizes = await page.evaluate(() => ({
    width: innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    rowDisplay: getComputedStyle(document.querySelector("tbody tr")!).display,
  }));
  expect(sizes.scrollWidth).toBeLessThanOrEqual(sizes.width);
  expect(sizes.rowDisplay).toBe("block");
  await page.keyboard.press("Escape");
  await expect(page.locator("#pokedex")).not.toHaveClass(/drawer-open/);
  expect(errors).toEqual([]);
});
