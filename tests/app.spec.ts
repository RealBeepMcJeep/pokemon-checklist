import { expect, test, devices, type Page } from "@playwright/test";
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

test("mirrors progress between two tabs of the same site", async ({
  page,
  context,
}, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);
  const other = await context.newPage();
  await openApp(other, testInfo.project.name);

  const pikipek = '[data-action="species"][data-species="731"]';

  // Act in the first tab; the second tab must follow without any user action.
  await page.locator(pikipek).first().click();
  await expect(page.locator("#overall-text")).toHaveText("1 / 807 Pokémon");
  await expect(other.locator("#overall-text")).toHaveText("1 / 807 Pokémon");
  await expect(other.locator(pikipek).first()).toContainText("Caught");

  // Act in the second tab; the first must follow in the other direction.
  // Cycling continues Caught → Seen, so Caught stops counting toward progress.
  await other.locator(pikipek).first().click();
  await expect(other.locator("#overall-text")).toHaveText("0 / 807 Pokémon");
  await expect(page.locator("#overall-text")).toHaveText("0 / 807 Pokémon");
  await expect(page.locator(pikipek).first()).toContainText("Seen");

  // Stars travel between tabs the same way statuses do.
  await page.locator('[data-action="star"][data-species="807"]').click();
  await expect(
    other.locator("#dex-list .dex-row .dex-name").first(),
  ).toContainText("807");

  expect(errors).toEqual([]);
});

test("pins starred Pokémon to the top of the Pokédex list", async ({
  page,
}, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);
  const firstRow = page.locator("#dex-list .dex-row .dex-name").first();
  const starFor = (id: number) =>
    page.locator(`[data-action="star"][data-species="${id}"]`);

  await expect(firstRow).toContainText("001");
  await expect(starFor(807)).toHaveAttribute("aria-pressed", "false");

  // Starring the last entry lifts it above everything else.
  await starFor(807).click();
  await expect(firstRow).toContainText("807");
  await expect(starFor(807)).toHaveAttribute("aria-pressed", "true");

  // Starring must not act as row selection.
  await expect(page.locator("#dex-selection")).toContainText(
    "Select a Pokémon",
  );

  // Several starred entries keep National Dex order among themselves.
  await starFor(25).click();
  await expect(firstRow).toContainText("025");
  await expect(
    page.locator("#dex-list .dex-row .dex-name").nth(1),
  ).toContainText("807");

  // A starred match still floats above lower-numbered matches in a search.
  await starFor(6).click();
  await page.locator("#dex-search").fill("char");
  await expect(firstRow).toContainText("006");

  // Unstarring everything restores plain National Dex order.
  await page.locator("#dex-search").fill("");
  await starFor(6).click();
  await starFor(25).click();
  await starFor(807).click();
  await expect(firstRow).toContainText("001");
  await expect(starFor(807)).toHaveAttribute("aria-pressed", "false");

  expect(errors).toEqual([]);
});

test("keeps starred Pokémon across a reload", async ({ page }, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);
  await page.locator('[data-action="star"][data-species="807"]').click();
  await page.reload();

  await expect(
    page.locator("#dex-list .dex-row .dex-name").first(),
  ).toContainText("807");
  await expect(
    page.locator('[data-action="star"][data-species="807"]'),
  ).toHaveAttribute("aria-pressed", "true");
  expect(errors).toEqual([]);
});

test("attempts no network requests while signed out", async ({
  page,
  browser,
}, testInfo) => {
  // This test is the offline guarantee, not a formality. The artifact bundles a
  // database SDK whose network code is reachable only after signing in, so the
  // publisher can no longer assert "no network API exists" — it asserts nothing is
  // even ATTEMPTED until a player chooses to sign in. If that ever regresses, the
  // offline-only app starts talking to the network behind the player's back, and
  // this is the only check that would notice.
  const external = (urls: string[]) =>
    urls.filter(
      (url) =>
        !url.startsWith("data:") &&
        !url.startsWith("file:") &&
        !url.startsWith("blob:") &&
        !/^https?:\/\/(?:127\.0\.0\.1|localhost)\b/.test(url),
    );

  const desktopAttempts: string[] = [];
  page.on("request", (request) => desktopAttempts.push(request.url()));
  const errors = await openApp(page, testInfo.project.name);
  await page.click('[data-action="species"][data-species="25"]');
  await page.waitForTimeout(1500);
  expect(external(desktopAttempts)).toEqual([]);
  expect(errors).toEqual([]);

  // A mobile profile has to be covered separately. Firebase Auth eagerly loads its
  // sign-in iframe and GAPI helper for MOBILE user agents even when nobody is
  // signed in — exactly how this promise was broken once — and desktop-only
  // coverage passes happily while that happens.
  const standalone = testInfo.project.name === "standalone-file";
  const mobile = await browser.newContext({
    ...devices["Pixel 7"],
    baseURL: testInfo.project.use.baseURL as string | undefined,
  });
  const mobilePage = await mobile.newPage();
  const mobileAttempts: string[] = [];
  mobilePage.on("request", (request) => mobileAttempts.push(request.url()));
  if (standalone) {
    await mobilePage.route(/^https?:\/\//, (route) => route.abort("blockedbyclient"));
  }
  await mobilePage.goto(standalone ? standaloneUrl : "/");
  await expect(mobilePage.locator("#overall-text")).toHaveText("0 / 807 Pokémon");
  await mobilePage.waitForTimeout(2500);
  expect(external(mobileAttempts)).toEqual([]);
  await mobile.close();
});

test("keeps the atlas out of computed styles and crops the right frame", async ({
  page,
}, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);
  await expect(page.locator(".dex-row")).toHaveCount(807);

  // Guard for a measured bug, not a cosmetic detail: while the icons referenced the
  // ~900 KB atlas as a CSS background, every icon carried that data URL in its
  // computed style and a full style recalculation over the list blocked the main
  // thread for about a second when the drawer closed. The sprites must therefore
  // come from an <img>; a background-image here reintroduces the stall.
  const backgrounds = await page.evaluate(() =>
    [...document.querySelectorAll(".dex-row .icon")].map(
      (icon) => getComputedStyle(icon).backgroundImage,
    ),
  );
  expect(new Set(backgrounds)).toEqual(new Set(["none"]));

  const sprite = await page.evaluate(() => {
    const image = document.querySelector<HTMLImageElement>(
      ".dex-row .icon .icon-sprite",
    );
    const box = image?.closest(".icon");
    const boxRect = box?.getBoundingClientRect();
    const imageRect = image?.getBoundingClientRect();
    return image && boxRect && imageRect
      ? {
          src: image.getAttribute("src"),
          alt: image.getAttribute("alt"),
          naturalWidth: image.naturalWidth,
          box: [boxRect.width, boxRect.height],
          offset: [
            boxRect.left - imageRect.left,
            boxRect.top - imageRect.top,
          ],
        }
      : null;
  });
  expect(sprite).not.toBeNull();
  // In the shipped artifact the atlas is inlined; the dev server serves it as a file.
  expect(sprite!.src).toMatch(/^(data:image\/|.*gen7-icons)/);
  expect(sprite!.alt).toBe("");
  expect(sprite!.box).toEqual([40, 30]);
  // #001 Bulbasaur is the first frame, so nothing is shifted.
  expect(sprite!.offset).toEqual([0, 0]);
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          document.querySelector<HTMLImageElement>(".dex-row .icon-sprite")
            ?.naturalWidth,
      ),
    )
    .toBe(1280);

  // A species outside the atlas's first row has to be shifted on both axes.
  await page.fill("#dex-search", "Mewtwo");
  await expect(page.locator(".dex-row")).toHaveCount(1);
  const mewtwo = await page.evaluate(() => {
    const image = document.querySelector<HTMLImageElement>(".dex-row .icon-sprite")!;
    return getComputedStyle(image).transform;
  });
  expect(mewtwo).toBe("matrix(1, 0, 0, 1, -840, -120)");
  expect(errors).toEqual([]);
});
