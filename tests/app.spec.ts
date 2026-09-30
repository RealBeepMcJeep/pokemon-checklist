import { expect, test, devices, type Page } from "@playwright/test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

const standaloneUrl = pathToFileURL(resolve("index.html")).href;
// A search hides non-matching rows rather than unmounting them.
const VISIBLE_ROW = "#dex-list .dex-row:not([hidden])";

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
  await expect(page.locator(VISIBLE_ROW)).toHaveCount(1);
  await expect(page.locator(`${VISIBLE_ROW} .dex-name`)).toContainText("Zeraora");
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

test("keeps Pokédex rows mounted through a search", async ({
  page,
}, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);
  await expect(page.locator(".dex-row")).toHaveCount(807);
  // Clearing a search used to rebuild every row, which blocked a phone for about a
  // second. Rows must survive a search and its clearing as the same DOM nodes.
  await page.evaluate(() => {
    document.querySelector<HTMLElement>(
      '.dex-row:has([data-species="500"])',
    )!.dataset.probe = "kept";
  });
  await page.locator("#dex-search").fill("pikachu");
  await expect(page.locator(VISIBLE_ROW)).toHaveCount(1);
  await expect(page.locator("#dex-count")).toContainText("1 of 807");
  await page.locator("#dex-search").fill("");
  await expect(page.locator(VISIBLE_ROW)).toHaveCount(807);
  await expect(page.locator('.dex-row[data-probe="kept"]')).toHaveCount(1);
  expect(errors).toEqual([]);
});

test("shows popular moves for a species and its final evolutions", async ({
  page,
}, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);
  await page.locator("#dex-search").fill("ralts");
  await page.locator('[data-action="select"][data-species="280"]').click();
  const moves = page.locator("#dex-selection .popular-moves");
  await expect(moves.locator("summary")).toHaveText(
    "Popular moves of its 2 final evolutions",
  );
  await moves.locator("summary").click();
  await expect(moves.locator(".final-moves h3")).toHaveText([
    "Gardevoir · RU",
    /^Gallade · /,
  ]);
  const moonblast = moves.locator(".final-moves li").first();
  await expect(moonblast).toContainText("Moonblast");
  await expect(moonblast.locator(".move-routes")).toHaveText(
    "Level 62 · Move Reminder",
  );

  // A final evolution shows its own list, and the panel stays open between selections.
  await page.locator("#dex-search").fill("gardevoir");
  await page.locator('[data-action="select"][data-species="282"]').click();
  await expect(moves.locator("summary")).toHaveText("Popular moves (RU)");
  await expect(moves.locator(".final-moves li").first()).toContainText("Moonblast");
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

  // Act in the first tab; the second (view-only: one tab edits) must follow
  // without any user action.
  await page.locator(pikipek).first().click();
  await expect(page.locator("#overall-text")).toHaveText("1 / 807 Pokémon");
  await expect(other.locator("#overall-text")).toHaveText("1 / 807 Pokémon");
  await expect(other.locator(pikipek).first()).toContainText("Caught");

  // Take editing to the second tab; the first must follow in the other direction.
  // Cycling continues Caught → Seen, so Caught stops counting toward progress.
  await other.locator("#use-this-tab").click();
  await other.locator(pikipek).first().click();
  await expect(other.locator("#overall-text")).toHaveText("0 / 807 Pokémon");
  await expect(page.locator("#overall-text")).toHaveText("0 / 807 Pokémon");
  await expect(page.locator(pikipek).first()).toContainText("Seen");

  // Stars travel between tabs the same way statuses do.
  await other.locator('[data-action="star"][data-species="807"]').click();
  await expect(
    page.locator(`${VISIBLE_ROW} .dex-name`).first(),
  ).toContainText("807");

  expect(errors).toEqual([]);
});

test("pins starred Pokémon to the top of the Pokédex list", async ({
  page,
}, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);
  const firstRow = page.locator(`${VISIBLE_ROW} .dex-name`).first();
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
    page.locator(`${VISIBLE_ROW} .dex-name`).nth(1),
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
    page.locator(`${VISIBLE_ROW} .dex-name`).first(),
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

test("gives sign-in a whole row on a small phone", async ({ page }, testInfo) => {
  // The phone header is a three-column button grid; sign-in once got one cell of it and
  // spilled out of its own frame at 320px.
  await page.setViewportSize({ width: 320, height: 700 });
  const errors = await openApp(page, testInfo.project.name);
  const actions = await page.locator(".actions").boundingBox();
  const panel = await page.locator("#sync-panel").boundingBox();
  const button = await page.locator("#sync-signin").boundingBox();
  expect(panel!.width).toBeGreaterThan(actions!.width * 0.9);
  expect(button!.x + button!.width).toBeLessThanOrEqual(panel!.x + panel!.width + 1);
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBe(true);
  expect(errors).toEqual([]);
});

test("offers sign-in without ever prompting for it", async ({
  page,
}, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);

  const signIn = page.locator("#sync-signin");
  await expect(signIn).toBeVisible();
  await expect(signIn).toBeEnabled();
  await expect(signIn).toHaveText("Sign in to sync");
  // Signed out there is no account line and no sign-out control, and nothing has
  // opened a provider dialog behind the player's back.
  await expect(page.locator("#sync-status")).toHaveText("");
  // There is exactly one sign-in control; a blocked popup relabels it rather than
  // adding a second one.
  await expect(page.locator("#sync-panel button")).toHaveCount(1);
  await expect(page.locator("#sync-signout")).toHaveCount(0);
  await expect(page.locator("iframe")).toHaveCount(0);

  expect(errors).toEqual([]);
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
  await expect(page.locator(VISIBLE_ROW)).toHaveCount(1);
  const mewtwo = await page.evaluate((row) => {
    const image = document.querySelector<HTMLImageElement>(`${row} .icon-sprite`)!;
    return getComputedStyle(image).transform;
  }, VISIBLE_ROW);
  expect(mewtwo).toBe("matrix(1, 0, 0, 1, -840, -120)");
  expect(errors).toEqual([]);
});

test("shows a live catch-next card as the Pokédex's empty-selection state", async ({
  page,
}, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);
  const catchNext = page.locator("#dex-selection .catch-next");
  await expect(catchNext.locator("strong")).toHaveText("Catch next in Route 1");
  const pikipekRow = catchNext.locator("li").filter({ hasText: "Pikipek" });
  await expect(pikipekRow).toHaveCount(1);

  // A status change made from the card itself must update the still-open card live,
  // with no selection and no navigation.
  await pikipekRow.locator('[data-species="731"]').click();
  await expect(
    catchNext.locator("li").filter({ hasText: "Pikipek" }),
  ).toHaveCount(0);
  await expect(
    page.locator('[data-action="species"][data-species="731"]').first(),
  ).toContainText("Caught");
  await expect(page.locator("#dex-selection .selected-title")).toHaveCount(0);

  // The jump button opens the same location the card is about, reusing the same
  // focusedLocation mechanism as every other in-app jump.
  await catchNext.locator(".catch-next-jump").click();
  await expect(
    page.locator('[data-location-id="melemele-island/route-1"][open]'),
  ).toHaveCount(1);

  // Selecting a Pokémon replaces the card; the details header brings it back.
  await page.locator('[data-action="select"][data-species="1"]').click();
  await expect(catchNext).toHaveCount(0);
  await page.locator("#dex-selection .deselect-button").click();
  await expect(catchNext.locator("strong")).toHaveText("Catch next in Route 1");
  expect(errors).toEqual([]);
});

test("lists where a species is caught in other game modes", async ({
  page,
}, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);
  await page.locator("#dex-search").fill("pichu");
  await page.locator('[data-action="select"][data-species="172"]').click();
  const also = page.locator("#dex-selection .also-catchable");
  await expect(also.locator("summary")).toHaveText(
    "Also catchable in 4 other modes",
  );
  await also.locator("summary").click();
  await expect(also.locator("li").first()).toContainText(
    "Pokémon Sun: Route 1",
  );
  // Switching into a mode Pichu is already listed under swaps it out for the mode
  // just left, rather than double-counting or keeping the current mode listed.
  await page.locator("#mode-select").selectOption("sun");
  const alsoAfterSwitch = page.locator("#dex-selection .also-catchable");
  await expect(alsoAfterSwitch.locator("summary")).toHaveText(
    "Also catchable in 4 other modes",
  );
  await alsoAfterSwitch.locator("summary").click();
  await expect(alsoAfterSwitch).not.toContainText("Pokémon Sun:");
  await expect(alsoAfterSwitch).toContainText("Prismatic Moon:");

  // A species with no encounter at all in the current mode still says where else
  // it can be caught, instead of going blank.
  await page.locator("#mode-select").selectOption("photonic-prismatic");
  await page.locator("#dex-search").fill("chansey");
  await page.locator('[data-action="select"][data-species="113"]').click();
  await expect(page.locator("#dex-selection .location-links")).toContainText(
    "No direct wild location in this mode",
  );
  await expect(
    page.locator("#dex-selection .also-catchable summary"),
  ).toHaveText("Also catchable in 4 other modes");
  expect(errors).toEqual([]);
});

test("always shows the evolution path, even next to a direct wild location", async ({
  page,
}, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);
  await page.locator("#dex-search").fill("pikachu");
  await page.locator('[data-action="select"][data-species="25"]').click();
  await expect(
    page.locator("#dex-selection .location-links > strong"),
  ).toContainText("Known places in this mode");
  await expect(
    page.locator("#dex-selection .evolution-path .evolution-link"),
  ).toHaveText(["Pichu", "Pikachu"]);
  expect(errors).toEqual([]);
});

test("opens a Pokémon's own location from the Pokédex even when it isn't the open one", async ({
  page,
}, testInfo) => {
  // "Known places in this mode" links used to do nothing unless the target
  // location happened to already be open; Bulbasaur's only location (Melemele
  // Meadow) is never the location auto-opened at the start of a save (Route 1).
  const errors = await openApp(page, testInfo.project.name);
  await page.locator("#dex-search").fill("bulbasaur");
  await page.locator('[data-action="select"][data-species="1"]').click();
  const link = page.locator("#dex-selection .location-links a").first();
  await expect(link).toContainText("Melemele Meadow");
  const targetId = (await link.getAttribute("href"))?.slice(1);
  if (!targetId) throw new Error("Location link has no target");
  await link.click();
  await expect(page.locator(`#${targetId}`)).toBeFocused();
  await expect(
    page.locator('[data-location-id="melemele-island/melemele-meadow"]'),
  ).toHaveAttribute("open", "");
  expect(errors).toEqual([]);
});

test("keeps the pokedex interactive after crossing the breakpoint via resize", async ({
  page,
}, testInfo) => {
  // aria-hidden/inert used to be computed once from window.innerWidth during
  // render and never revisited, so a resize or rotation across the 1000px
  // breakpoint left the drawer either visible-but-inert or hidden-but-live.
  await page.setViewportSize({ width: 1280, height: 900 });
  const errors = await openApp(page, testInfo.project.name);
  await expect(page.locator("#pokedex")).toHaveAttribute("aria-hidden", "false");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("#pokedex")).toHaveAttribute("aria-hidden", "true");
  await page.setViewportSize({ width: 1280, height: 900 });
  await expect(page.locator("#pokedex")).toHaveAttribute("aria-hidden", "false");
  // Not just the attribute: the panel must actually respond to input again.
  await page.locator("#dex-search").fill("bulbasaur");
  await expect(page.locator(VISIBLE_ROW)).toHaveCount(1);

  // A drawer left open on a phone must not keep the desktop page locked or inert.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator("#sidebar-toggle").click();
  await expect(page.locator("#pokedex")).toHaveClass(/drawer-open/);
  await page.setViewportSize({ width: 1280, height: 900 });
  await expect(page.locator("#pokedex")).not.toHaveClass(/drawer-open/);
  expect(await page.evaluate(() => document.body.style.overflow)).not.toBe("hidden");
  await expect(page.locator(".app-header")).not.toHaveAttribute("inert", /.*/);
  expect(errors).toEqual([]);
});

test("does not re-render every mounted dex row when only the selection changes", async ({
  page,
}, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);
  await expect(page.locator(".dex-row")).toHaveCount(807);
  const bystander = page.locator('[data-action="select"][data-species="2"]');
  const first = page.locator('[data-action="select"][data-species="1"]');
  const second = page.locator('[data-action="select"][data-species="4"]');
  const bystanderRenders = await bystander.getAttribute("data-renders");

  await first.click();
  await expect(first).toHaveAttribute("aria-current", "true");
  await expect(bystander).toHaveAttribute("data-renders", bystanderRenders!);

  await second.click();
  await expect(second).toHaveAttribute("aria-current", "true");
  await expect(first).toHaveAttribute("aria-current", "false");
  // Only the previously and newly selected rows should have re-rendered; a row
  // that was never involved must show the same render count throughout.
  await expect(bystander).toHaveAttribute("data-renders", bystanderRenders!);
  expect(errors).toEqual([]);
});

test("does not re-render every already-open location when only the focus moves", async ({
  page,
}, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);
  // Open a location that finishing Route 1 will not make the new focus, so any
  // change to it can only be an unnecessary re-render.
  const bystander = page.locator("details.location").nth(2);
  await bystander.locator("summary").click();
  await expect(bystander).toHaveAttribute("open", "");
  const before = await bystander.getAttribute("data-renders");

  const first = page.locator("details.location").first();
  const speciesIds = await first
    .locator('[data-action="species"]')
    .evaluateAll((nodes) => [
      ...new Set(nodes.map((node) => node.getAttribute("data-species"))),
    ]);
  for (const id of speciesIds) {
    await first
      .locator(`[data-action="species"][data-species="${id}"]`)
      .first()
      .click();
  }
  await expect(first.locator(".location-progress")).toContainText("Complete");

  await expect(bystander).toHaveAttribute("data-renders", before!);
  expect(errors).toEqual([]);
});

test("counts forms caught against the active mode's own obtainable forms", async ({
  page,
}, testInfo) => {
  // The denominator used to be the 54-form union of all five modes in every mode,
  // so Sun/Moon (14 forms) and the Ultra games (17) could never reach completion.
  const errors = await openApp(page, testInfo.project.name);
  await page.locator("#forms-toggle").click();
  await page.locator("#mode-select").selectOption("sun");
  await expect(page.locator("#form-progress")).toHaveText("Forms caught: 0 / 14");
  await page.locator("#mode-select").selectOption("photonic-prismatic");
  await expect(page.locator("#form-progress")).toHaveText("Forms caught: 0 / 48");
  expect(errors).toEqual([]);
});

test("gives phone tap targets at least 44px without changing desktop", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const errors = await openApp(page, testInfo.project.name);
  const compact = await page.locator("tbody .compact-status").first().boundingBox();
  expect(compact!.width).toBeGreaterThanOrEqual(44);
  expect(compact!.height).toBeGreaterThanOrEqual(44);

  await page.locator("tbody .guide-pokemon-link").first().click();
  const star = await page.locator(".dex-row .star-button").first().boundingBox();
  const status = await page
    .locator('.dex-row [data-action="species"]')
    .first()
    .boundingBox();
  expect(star!.width).toBeGreaterThanOrEqual(44);
  expect(star!.height).toBeGreaterThanOrEqual(44);
  expect(status!.height).toBeGreaterThanOrEqual(44);

  await page.setViewportSize({ width: 1280, height: 900 });
  const desktopCompact = await page
    .locator("tbody .compact-status")
    .first()
    .boundingBox();
  expect(desktopCompact!.width).toBeLessThan(44);
  expect(errors).toEqual([]);
});

test("keeps the mode select at 16px on phones to avoid iOS auto-zoom", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const errors = await openApp(page, testInfo.project.name);
  const fontSize = await page
    .locator("#mode-select")
    .evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
  expect(fontSize).toBeGreaterThanOrEqual(16);
  expect(errors).toEqual([]);
});

test("uses dvh with a vh fallback for pokedex height calculations", async ({
  page,
}, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);
  const hasDvh = await page.evaluate(() => {
    const text = [...document.styleSheets]
      .flatMap((sheet) => {
        try {
          return [...sheet.cssRules].map((rule) => rule.cssText);
        } catch {
          return [];
        }
      })
      .join("\n");
    return /dvh/.test(text);
  });
  expect(hasDvh).toBe(true);
  expect(errors).toEqual([]);
});

test("locks page scroll behind the mobile pokedex drawer", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const errors = await openApp(page, testInfo.project.name);
  await expect
    .poll(() => page.evaluate(() => getComputedStyle(document.body).overflow))
    .not.toBe("hidden");
  await page.locator("tbody .guide-pokemon-link").first().click();
  await expect
    .poll(() => page.evaluate(() => getComputedStyle(document.body).overflow))
    .toBe("hidden");
  await page.keyboard.press("Escape");
  await expect
    .poll(() => page.evaluate(() => getComputedStyle(document.body).overflow))
    .not.toBe("hidden");
  expect(errors).toEqual([]);
});

test("focuses the selection panel, not search, when opened from a location link", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const errors = await openApp(page, testInfo.project.name);
  await page.locator("tbody .guide-pokemon-link").first().click();
  await expect(page.locator("#dex-selection")).toBeFocused();
  expect(errors).toEqual([]);
});

test("traps focus inside the drawer and keeps the page behind it inert", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const errors = await openApp(page, testInfo.project.name);
  await page.locator("tbody .guide-pokemon-link").first().click();
  await expect(page.locator("#pokedex")).toHaveAttribute("role", "dialog");
  await expect(page.locator("#pokedex")).toHaveAttribute("aria-modal", "true");
  expect(
    await page.locator(".app-header").evaluate((el) => el.hasAttribute("inert")),
  ).toBe(true);
  expect(
    await page.locator("#main-view").evaluate((el) => el.hasAttribute("inert")),
  ).toBe(true);
  await page.keyboard.press("Escape");
  expect(
    await page.locator(".app-header").evaluate((el) => el.hasAttribute("inert")),
  ).toBe(false);
  expect(errors).toEqual([]);
});

test("keeps the sticky pokedex offset in sync with the header's real height", async ({
  page,
}, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);
  const { headerHeight, varValue, pokedexTop } = await page.evaluate(() => {
    const header = document.querySelector(".app-header")!;
    return {
      headerHeight: header.getBoundingClientRect().height,
      varValue: parseFloat(
        getComputedStyle(document.documentElement).getPropertyValue("--header-h"),
      ),
      pokedexTop: parseFloat(
        getComputedStyle(document.querySelector("#pokedex")!).top,
      ),
    };
  });
  expect(varValue).toBeGreaterThan(0);
  expect(Math.abs(varValue - headerHeight)).toBeLessThan(2);
  expect(Math.abs(pokedexTop - headerHeight)).toBeLessThan(2);
  expect(errors).toEqual([]);
});

test("names the resulting status in the status button's label", async ({
  page,
}, testInfo) => {
  // The label used to say only the current status and "Activate to cycle status",
  // never what pressing the button would actually change it to.
  const errors = await openApp(page, testInfo.project.name);
  const button = page.locator('[data-action="species"][data-species="1"]').first();
  await expect(button).toHaveAttribute(
    "aria-label",
    /status: None\. Activate to mark as Caught\./,
  );
  await button.click();
  await expect(button).toHaveAttribute(
    "aria-label",
    /status: Caught\. Activate to mark as Seen\./,
  );
  expect(errors).toEqual([]);
});

test("keeps grade badge colors at WCAG AA contrast against their white text", async ({
  page,
}, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);
  const css = await page.evaluate(() =>
    [...document.styleSheets]
      .flatMap((sheet) => {
        try {
          return [...sheet.cssRules].map((rule) => rule.cssText);
        } catch {
          return [];
        }
      })
      .join("\n"),
  );

  function luminance([r, g, b]: number[]): number {
    const channel = [r, g, b].map((value) => {
      const v = value / 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * channel[0] + 0.7152 * channel[1] + 0.0722 * channel[2];
  }
  function contrast(a: number[], b: number[]): number {
    const [lighter, darker] = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return (lighter + 0.05) / (darker + 0.05);
  }
  function rgbStopsFor(selector: string): number[][] {
    const rule = css.match(new RegExp(`${selector}\\s*\\{([^}]*)\\}`));
    if (!rule) throw new Error(`${selector} rule not found in the built stylesheet`);
    return [...rule[1].matchAll(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/g)].map((match) => [
      Number(match[1]),
      Number(match[2]),
      Number(match[3]),
    ]);
  }

  const white = [255, 255, 255];
  for (const selector of ["\\.grade-a", "\\.grade-b"]) {
    const [color] = rgbStopsFor(selector);
    expect(contrast(color, white)).toBeGreaterThanOrEqual(4.5);
  }
  const gradientStops = rgbStopsFor("\\.grade-sss");
  expect(gradientStops.length).toBeGreaterThanOrEqual(2);
  for (const stop of gradientStops) {
    expect(contrast(stop, white)).toBeGreaterThanOrEqual(4.5);
  }
  expect(errors).toEqual([]);
});

test("undoes a status change, a star, and a Reset in one tap", async ({
  page,
}, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);
  const pikipek = page.locator('[data-action="species"][data-species="731"]').first();
  const undo = page.locator("#notice-action");

  await pikipek.click();
  await expect(page.locator("#notice")).toHaveText("Status saved.");
  await undo.click();
  await expect(page.locator("#notice")).toHaveText("Undone.");
  await expect(undo).toHaveCount(0);
  await expect(pikipek).toContainText("None");

  await page.locator('[data-action="star"][data-species="807"]').click();
  await undo.click();
  await expect(
    page.locator('[data-action="star"][data-species="807"]'),
  ).toHaveAttribute("aria-pressed", "false");

  await pikipek.click();
  page.once("dialog", (dialog) => dialog.accept());
  await page.locator("#reset-button").click();
  await expect(page.locator("#overall-text")).toHaveText("0 / 807 Pokémon");
  await expect(undo).toHaveText("Undo");
  await undo.click();
  await expect(page.locator("#overall-text")).toHaveText("1 / 807 Pokémon");

  // The undo was saved like any other change.
  await page.reload();
  await expect(page.locator("#overall-text")).toHaveText("1 / 807 Pokémon");
  expect(errors).toEqual([]);
});

test("shows the last good copy when the save cannot be read", async ({
  page,
}, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);
  await page.locator('[data-action="species"][data-species="731"]').first().click();
  await expect(page.locator("#overall-text")).toHaveText("1 / 807 Pokémon");
  await page.evaluate(() =>
    localStorage.setItem("pokemon-checklist-state-v3", "{half a save"),
  );

  await page.reload();

  await expect(page.locator("#overall-text")).toHaveText("1 / 807 Pokémon");
  await expect(page.locator("#notice")).toContainText("could not be read");
  await expect(page.locator("#notice-action")).toHaveText("Download unreadable copy");
  expect(
    await page.evaluate(() =>
      localStorage.getItem("pokemon-checklist-state-v3:unreadable"),
    ),
  ).toBe("{half a save");
  expect(errors).toEqual([]);
});

test("offers Undo above the phone Pokédex drawer, where the tap happened", async ({
  page,
}, testInfo) => {
  // The header's notice line sits behind the drawer and scrolls away on a phone,
  // so the action floats where a player tapping inside the drawer can reach it.
  await page.setViewportSize({ width: 390, height: 844 });
  const errors = await openApp(page, testInfo.project.name);
  await page.locator("#sidebar-toggle").click();
  await page.locator("#dex-search").fill("bulbasaur");
  const status = page.locator('#dex-list [data-action="species"][data-species="1"]');
  await status.click();
  await expect(status).toContainText("Caught");
  const undo = page.locator("#notice-action");
  await expect(undo).toBeVisible();
  await expect(page.locator("#pokedex")).toHaveClass(/drawer-open/);
  await undo.click();
  await expect(status).toContainText("None");
  await expect(undo).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("fills the phone screen with the Pokédex drawer even for a short list", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const errors = await openApp(page, testInfo.project.name);
  await page.locator("#sidebar-toggle").click();
  await page.locator("#dex-search").fill("bulbasaur");
  const height = await page.evaluate(
    () => document.querySelector("#pokedex")!.getBoundingClientRect().height,
  );
  expect(height).toBeGreaterThanOrEqual(840);
  expect(errors).toEqual([]);
});

test("lets one tab edit, shows the other view-only, and hands editing over", async ({
  page,
  context,
}, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);
  const other = await context.newPage();
  await openApp(other, testInfo.project.name);
  const pikipek = '[data-action="species"][data-species="731"]';

  // The first tab edits; the second says so and cannot change anything.
  await expect(page.locator("#view-only")).toHaveCount(0);
  await expect(other.locator("#view-only")).toContainText(
    "This checklist is being edited in another tab.",
  );
  await expect(other.locator(pikipek).first()).toBeDisabled();
  await expect(other.locator("#reset-button")).toBeDisabled();
  await expect(other.locator('[data-action="star"][data-species="25"]')).toBeDisabled();
  await other.locator(pikipek).first().click({ force: true });
  await expect(other.locator("#overall-text")).toHaveText("0 / 807 Pokémon");
  await expect(page.locator("#overall-text")).toHaveText("0 / 807 Pokémon");

  // "Use this tab" moves editing: the first tab turns view-only at once.
  await other.locator("#use-this-tab").click();
  await expect(other.locator("#view-only")).toHaveCount(0);
  await expect(page.locator("#view-only")).toBeVisible();
  await expect(page.locator(pikipek).first()).toBeDisabled();
  await other.locator(pikipek).first().click();
  await expect(page.locator("#overall-text")).toHaveText("1 / 807 Pokémon");

  // Closing the editing tab lets the other one edit again.
  await other.close();
  await expect(page.locator("#view-only")).toHaveCount(0);
  await expect(page.locator(pikipek).first()).toBeEnabled();
  expect(errors).toEqual([]);
});

test("keeps the view-only banner readable on small phones", async ({
  page,
  context,
}, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);
  const other = await context.newPage();
  await openApp(other, testInfo.project.name);
  for (const width of [320, 390]) {
    await other.setViewportSize({ width, height: 700 });
    const banner = await other.locator("#view-only").boundingBox();
    const button = await other.locator("#use-this-tab").boundingBox();
    // The button gets a row of its own, inside the banner, and a real target.
    expect(button!.x + button!.width).toBeLessThanOrEqual(banner!.x + banner!.width + 1);
    expect(button!.width).toBeGreaterThan(banner!.width * 0.8);
    expect(button!.height).toBeGreaterThanOrEqual(30);
    expect(
      await other.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBe(true);
  }
  expect(errors).toEqual([]);
});

test("keeps the view-only banner on screen on a phone, scrolled or under the drawer", async ({
  page,
  context,
}, testInfo) => {
  const errors = await openApp(page, testInfo.project.name);
  const other = await context.newPage();
  await other.setViewportSize({ width: 390, height: 844 });
  await openApp(other, testInfo.project.name);
  // On screen, and the topmost thing where it is drawn (not behind the drawer).
  const bannerShown = () =>
    other.evaluate(() => {
      const banner = document.querySelector("#view-only");
      if (!banner) return false;
      const box = banner.getBoundingClientRect();
      const top = document.elementFromPoint(
        box.left + box.width / 2,
        box.top + box.height / 2,
      );
      return box.top >= 0 && box.bottom <= innerHeight && banner.contains(top);
    });

  // Jump to a location far down the page, as the location links do.
  await other.locator("tbody .guide-pokemon-link").last().click();
  await other.locator("#dex-selection .location-links a").last().click();
  await expect(other.locator("#pokedex")).not.toHaveClass(/drawer-open/);
  expect(await other.evaluate(() => scrollY)).toBeGreaterThan(500);
  expect(await bannerShown()).toBe(true);

  // With the Pokédex drawer open, the banner and its button still work.
  await other.locator("#sidebar-toggle").click();
  await expect(other.locator("#pokedex")).toHaveClass(/drawer-open/);
  expect(await bannerShown()).toBe(true);
  await other.locator("#use-this-tab").click();
  await expect(other.locator("#view-only")).toHaveCount(0);
  await expect(page.locator("#view-only")).toBeVisible();
  expect(errors).toEqual([]);
});
