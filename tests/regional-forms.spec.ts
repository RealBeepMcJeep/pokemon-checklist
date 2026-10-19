import { expect, test, type Page } from "@playwright/test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";
// Deliberate versioned fixtures; do not import Vite JSON modules into the Node test loader.
const STORAGE_KEY = "pokemon-checklist-state-v5";

async function openRegionalFixture(page: Page, project: string) {
  if (project === "standalone-file") {
    await page.route(/^https?:\/\//, route => route.abort("blockedbyclient"));
    await page.goto(pathToFileURL(resolve("index.html")).href);
  } else await page.goto("/");
  await expect(page.locator("#dex-search")).toBeAttached();
  await page.evaluate(key => {
    const legacy = { schemaVersion: 4, species: { "52": "caught" }, forms: { "52:alolan": "caught" }, starred: [52], settings: { forms: true, mode: "photonic-prismatic", unlocks: ["sos"] } };
    localStorage.clear();
    // Seed the old artifact as well: its RED must be the missing split UI, not
    // simply inability to read a save version it predates.
    localStorage.setItem("pokemon-checklist-state-v4", JSON.stringify(legacy));
    localStorage.setItem(key, JSON.stringify({ ...legacy, schemaVersion: 5, starred: [], starredForms: ["52:alolan"] }));
  }, STORAGE_KEY);
  await page.reload();
  await expect(page.locator("#dex-search")).toBeAttached();
}

for (const [device, width] of [["desktop", 1440], ["phone", 390]] as const) {
  test.describe(device, () => {
    test.use({ viewport: { width, height: 950 }, isMobile: device === "phone", hasTouch: device === "phone" });
    test("source SOS scope and weather footnotes reach the guide", async ({ page }, info) => {
      const errors: string[] = [];
      page.on("pageerror", error => errors.push(error.message));
      page.on("console", message => {
        if (message.type() === "error") errors.push(message.text());
      });
      // Listen before fixture reload: reconciliation warnings occur on first render.
      await openRegionalFixture(page, info.project.name);
      await page.locator("#header-settings-toggle").click();
      await page.getByLabel("Weather SOS", { exact: true }).check();
      await page.getByRole("button", { name: "Close settings", exact: true }).click();
      const route1 = page.locator('details[data-location-id="melemele-island/route-1"]');
      if (!(await route1.evaluate(el => (el as HTMLDetailsElement).open))) await route1.locator("summary").click();
      const calls = route1.locator(".encounter-group").filter({ has: page.getByText("SOS Calls", { exact: true }) });
      await expect(calls.getByRole("button", { name: "Rattata (Kanto)", exact: true })).toHaveCount(1);
      await expect(calls.getByRole("button", { name: "Pikachu", exact: true })).toHaveCount(1);
      await expect(calls.getByRole("button", { name: "Happiny", exact: true })).toHaveCount(1);
      const rattata = calls.locator("tr").filter({ has: page.getByRole("button", { name: "Rattata (Alolan)", exact: true }) });
      await expect(rattata.locator("td").first()).toHaveText("—");
      const outskirts = page.locator('details[data-location-id="melemele-island/hauoli-outskirts"]');
      if (!(await outskirts.evaluate(el => (el as HTMLDetailsElement).open))) await outskirts.locator("summary").click();
      await expect(outskirts.getByRole("button", { name: "Rattata (Kanto)", exact: true })).toHaveCount(0);
      const desert = page.locator('details[data-location-id="ulaula-island/haina-desert"]');
      if (!(await desert.evaluate(el => (el as HTMLDetailsElement).open))) await desert.locator("summary").click();
      const weather = desert.locator(".encounter-group").filter({ has: page.getByText("Weather SOS", { exact: true }) });
      const castform = weather.locator("tr").filter({ has: page.getByRole("button", { name: "Castform", exact: true }) });
      await expect(castform).toHaveCount(2);
      const sand = castform.filter({ has: page.getByText("Sandstorm", { exact: true }) });
      await expect(sand.locator("td").first()).toHaveText("1%");
      await expect(sand).toContainText("Guide-reported SOS encounter rate");
      const rainHail = castform.filter({ has: page.getByText("Rain, Hail", { exact: true }) });
      await expect(rainHail.locator("td").first()).toHaveText("11%");
      await desert.locator("img").evaluateAll(images => Promise.all(images.map(image => (image as HTMLImageElement).decode().catch(() => {}))));
      await sand.evaluate(el => el.scrollIntoView({ block: "center" }));
      await expect(sand).toBeInViewport();
      await page.screenshot({ path: info.outputPath(`haina-source-footnote-${device}.png`) });
      const route15 = page.locator('details[data-location-id="ulaula-island/route-15-16"]');
      if (!(await route15.evaluate(el => (el as HTMLDetailsElement).open))) await route15.locator("summary").click();
      const unresolved = route15.locator("tr").filter({ has: page.getByRole("button", { name: "Crabrawler", exact: true }) });
      await expect(unresolved).toContainText("Caller availability is unverified");
      await expect(unresolved).toContainText("do not assume Shuckle calls Crabominable");
      await route15.locator("img").evaluateAll(images => Promise.all(images.map(image => (image as HTMLImageElement).decode().catch(() => {}))));
      await unresolved.evaluate(el => el.scrollIntoView({ block: "center" }));
      await expect(unresolved).toBeInViewport();
      await page.screenshot({ path: info.outputPath(`unverified-caller-${device}.png`) });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      expect(errors).toEqual([]);
    });
    test("guide status edits and Undo affect only the exact regional form", async ({ page }, info) => {
      await openRegionalFixture(page, info.project.name);
      const before = await page.evaluate(key => JSON.parse(localStorage.getItem(key)!), STORAGE_KEY);
      const school = page.locator('details[data-location-id="melemele-island/trainers-school"]');
      if (!(await school.evaluate(el => (el as HTMLDetailsElement).open))) await school.locator("summary").click();
      const row = school.locator("tr").filter({ has: page.getByRole("button", { name: "Meowth (Alolan)", exact: true }) });
      const alolan = row.locator('button[data-form="52:alolan"]');
      const kanto = row.locator('button[data-form="52:kanto"]');
      await expect(alolan).toHaveCount(1);
      await expect(kanto).toHaveCount(1);
      await expect(alolan).toHaveAccessibleName(/Meowth \(Alolan\).*status: Caught/);
      await expect(kanto).toHaveAccessibleName(/Meowth \(Kanto\).*status: Not caught/);
      await expect(row.locator('button[data-action="species"][data-species="52"]')).toHaveCount(0);
      await expect(row.locator("td").first()).toHaveText("15%");
      await kanto.click();
      await expect(kanto).toHaveAccessibleName(/status: Caught/);
      await expect(alolan).toHaveAccessibleName(/status: Caught/);
      await page.getByRole("button", { name: "Undo", exact: true }).click();
      await expect(kanto).toHaveAccessibleName(/status: Not caught/);
      await expect(alolan).toHaveAccessibleName(/status: Caught/);
      for (const label of ["Caught", "Seen", "Not caught"]) {
        await kanto.click();
        await expect(kanto).toHaveAccessibleName(new RegExp(`status: ${label}\\.`));
        await expect(alolan).toHaveAccessibleName(/status: Caught/);
      }
      // Collapsed collection browsing must not turn an explicitly known guide
      // encounter back into the shared species badge.
      if (device === "phone") await page.locator("#header-settings-toggle").click();
      await page.locator("#forms-toggle").click();
      if (device === "phone") await page.getByRole("button", { name: "Close settings", exact: true }).click();
      await expect(alolan).toHaveCount(1);
      await expect(kanto).toHaveCount(1);
      await expect(kanto).toHaveAccessibleName(/Meowth \(Kanto\).*status: Not caught/);
      await expect(alolan).toHaveAccessibleName(/Meowth \(Alolan\).*status: Caught/);
      await alolan.scrollIntoViewIfNeeded();
      // Chromium can clip a fractional table-border pixel on desktop; require
      // essentially the whole compact control, not merely any intersection.
      await expect(alolan).toBeInViewport({ ratio: 0.98 });
      await page.screenshot({ path: info.outputPath(`guide-status-caller-${device}.png`) });
      await kanto.scrollIntoViewIfNeeded();
      await expect(kanto).toBeInViewport({ ratio: 0.98 });
      await page.screenshot({ path: info.outputPath(`guide-status-ally-${device}.png`) });
      const after = await page.evaluate(key => JSON.parse(localStorage.getItem(key)!), STORAGE_KEY);
      for (const field of ["species", "forms", "starred", "starredForms"]) expect(after[field]).toEqual(before[field]);
    });
    test("guide caller and SOS links open the exact form and only its locations", async ({ page }, info) => {
      await openRegionalFixture(page, info.project.name);
      const before = await page.evaluate(key => JSON.parse(localStorage.getItem(key)!), STORAGE_KEY);
      const school = page.locator('details[data-location-id="melemele-island/trainers-school"]');
      if (!(await school.evaluate(el => (el as HTMLDetailsElement).open))) await school.locator("summary").click();
      const caller = school.getByRole("button", { name: "Meowth (Alolan)", exact: true });
      const ally = school.getByRole("button", { name: "Meowth (Kanto)", exact: true });
      await expect(caller).toHaveCount(1);
      await expect(ally).toHaveCount(1);
      const row = school.locator("tr").filter({ has: page.getByRole("button", { name: "Meowth (Alolan)", exact: true }) });
      await expect(row.locator("td").first()).toHaveText("15%");
      await ally.click();
      await expect(page.locator("#dex-selection .selected-title")).toContainText("Meowth (Kanto)");
      await expect(page.locator("#dex-selection .location-links > ul > li")).toHaveCount(1);
      await expect(page.locator("#dex-selection .location-links > ul")).toContainText("SOS ally");
      await expect(page.locator("#dex-selection .location-links > ul")).not.toContainText("wild encounter");
      await expect(page.locator("#dex-selection .also-catchable")).toHaveCount(0);
      await expect(page.locator("#dex-selection")).toBeFocused();
      // Visibility/focus can pass mid-transition. Require the whole drawer to
      // settle inside the viewport before claiming readable screenshot coverage.
      await expect.poll(() => page.locator("#pokedex").evaluate(el => {
        const rect = el.getBoundingClientRect();
        return rect.left >= -1 && rect.right <= innerWidth + 1;
      })).toBe(true);
      await page.screenshot({ path: info.outputPath(`guide-kanto-details-${device}.png`) });
      await page.locator("#dex-selection .location-links > ul a").click();
      await expect(row).toBeFocused();
      if (device === "phone") await expect(page.locator("#pokedex")).toHaveAttribute("aria-hidden", "true");
      await caller.click();
      await expect(page.locator("#dex-selection .selected-title")).toContainText("Meowth (Alolan)");
      await expect(page.locator("#dex-selection .location-links > ul > li")).toHaveCount(1);
      await expect(page.locator("#dex-selection .location-links > ul")).toContainText("wild encounter");
      await expect(page.locator("#dex-selection .location-links > ul")).not.toContainText("SOS ally");
      const after = await page.evaluate(key => JSON.parse(localStorage.getItem(key)!), STORAGE_KEY);
      for (const field of ["species", "forms", "starred", "starredForms"]) expect(after[field]).toEqual(before[field]);
    });
    test("surfaces legacy ownership without inventing a form", async ({ page }, info) => {
      await openRegionalFixture(page, info.project.name);
      await page.evaluate(() => {
        const key = "pokemon-checklist-state-v5";
        const state = JSON.parse(localStorage.getItem(key)!);
        state.species = { "52": "caught" };
        state.forms = {};
        localStorage.setItem(key, JSON.stringify(state));
      });
      await page.reload();
      if (device === "phone") await page.locator("#sidebar-toggle").tap();
      await page.locator("#dex-search").fill("Meowth");
      await page.locator('.dex-row[data-target="52:alolan"] .dex-select').click();
      await expect(page.locator(".form-ownership-warning")).toContainText("recorded without a form");
      const saved = await page.evaluate(key => JSON.parse(localStorage.getItem(key)!), STORAGE_KEY);
      expect(saved.forms).toEqual({});
      expect(saved.species["52"]).toBe("caught");
      await page.locator('.dex-row[data-target="52:kanto"] .dex-select').click();
      await expect(page.locator(".form-ownership-warning")).toBeVisible();
      await expect(page.locator("#dex-selection .selected-title")).toContainText("Meowth (Kanto)");
      await page.locator(".form-ownership-warning").scrollIntoViewIfNeeded();
      await expect(page.locator(".form-ownership-warning")).toBeInViewport();
      await page.screenshot({ path: info.outputPath(`unresolved-form-${device}.png`) });
      await page.locator('.dex-row[data-target="52:kanto"] .status-button').click();
      await expect(page.locator(".form-ownership-warning")).toHaveCount(0);
      const resolved = await page.evaluate(key => JSON.parse(localStorage.getItem(key)!), STORAGE_KEY);
      expect(resolved.forms).toEqual({ "52:kanto": "caught" });
      expect(resolved.species["52"]).toBe("caught");
    });
    test("popular moves use the selected form and change actual teaching routes by game", async ({ page }, info) => {
      await openRegionalFixture(page, info.project.name);
      if (device === "phone") await page.locator("#sidebar-toggle").tap();
      await page.locator("#dex-search").fill("Meowth");
      await page.locator('.dex-row[data-target="52:alolan"] .dex-select').click();
      await page.locator(".popular-moves > summary").click();
      await expect(page.locator(".final-moves h3")).toContainText("Persian (Alolan)");
      await expect(page.locator('.final-moves li[data-move="partingshot"] .move-routes')).toContainText("On evolution");
      const knock = page.locator('.final-moves li[data-move="knockoff"] .move-routes');
      const switchMode = async (value: string) => {
        if (device === "phone") {
          await page.locator("#drawer-close").tap();
          await page.locator("#header-settings-toggle").tap();
        }
        await page.locator("#mode-select").selectOption(value);
        if (device === "phone") {
          await page.getByRole("button", { name: "Close settings", exact: true }).tap();
          await page.locator("#sidebar-toggle").tap();
        }
      };
      await switchMode("moon");
      await expect(knock).toContainText("No verified native learning route in Pokémon Moon");
      await switchMode("ultra-moon");
      await expect(knock).toContainText("Tutor");
      await page.screenshot({ path: info.outputPath(`regional-moves-${device}.png`), fullPage: true });
      await page.locator('.dex-row[data-target="52:kanto"] .dex-select').click();
      await expect(page.locator(".final-moves h3")).toContainText("Persian (Kanto)");
      await expect(page.locator(".final-moves")).not.toContainText("Parting Shot");
    });
    test("No forms collapses selected regional details without erasing either form", async ({ page }, info) => {
      await openRegionalFixture(page, info.project.name);
      if (device === "phone") await page.locator("#sidebar-toggle").tap();
      await page.locator("#dex-search").fill("Meowth");
      await page.locator('.dex-row[data-target="52:kanto"] .dex-select').click();
      const before = await page.evaluate(key => JSON.parse(localStorage.getItem(key)!), STORAGE_KEY);
      const toggle = async () => {
        if (device === "phone") {
          await page.locator("#drawer-close").tap();
          await page.locator("#header-settings-toggle").tap();
        }
        await page.locator("#forms-toggle").click();
        if (device === "phone") {
          await page.getByRole("button", { name: "Close settings", exact: true }).tap();
          await page.locator("#sidebar-toggle").tap();
        }
      };
      await toggle();
      await expect(page.locator("#dex-selection .selected-title")).not.toContainText("Kanto");
      await expect(page.locator("#dex-selection .selected-title")).not.toContainText("Alolan");
      await expect(page.locator("#dex-selection .pokemon-facts-expanded .type-marks")).toHaveAttribute("aria-label", "Types: Dark");
      await expect(page.locator("#dex-list .dex-row:not([hidden])")).toHaveCount(1);
      await toggle();
      await expect(page.locator("#dex-selection .selected-title")).toContainText("Meowth (Kanto)");
      await expect(page.locator("#dex-list .dex-row:not([hidden])")).toHaveCount(2);
      const after = await page.evaluate(key => JSON.parse(localStorage.getItem(key)!), STORAGE_KEY);
      for (const field of ["species", "forms", "starred", "starredForms"]) expect(after[field]).toEqual(before[field]);
    });
    test("game mode changes the actual evolution method without changing ownership", async ({ page }, info) => {
      await openRegionalFixture(page, info.project.name);
      if (device === "phone") await page.locator("#sidebar-toggle").tap();
      await page.locator("#dex-search").fill("Charjabug");
      await page.locator('.dex-row[data-target="737"] .dex-select').click();
      const vikavolt = page.locator('.evolution-stage[data-target="738"]');
      await expect(vikavolt).toContainText("Thunder Stone");
      const before = await page.evaluate(key => JSON.parse(localStorage.getItem(key)!), STORAGE_KEY);
      if (device === "phone") {
        await page.locator("#drawer-close").tap();
        await page.locator("#header-settings-toggle").tap();
      }
      await page.locator("#mode-select").selectOption("ultra-moon");
      if (device === "phone") {
        await page.getByRole("button", { name: "Close settings", exact: true }).tap();
        await page.locator("#sidebar-toggle").tap();
      }
      await expect(vikavolt).toContainText("special magnetic field");
      await expect(vikavolt).not.toContainText("Thunder Stone");
      const after = await page.evaluate(key => JSON.parse(localStorage.getItem(key)!), STORAGE_KEY);
      for (const field of ["species", "forms", "starred", "starredForms"]) expect(after[field]).toEqual(before[field]);
    });
    test("branching evolution families expand without clipping stage names", async ({ page }, info) => {
      await openRegionalFixture(page, info.project.name);
      if (device === "phone") await page.locator("#sidebar-toggle").tap();
      await page.locator("#dex-search").fill("Eevee");
      await page.locator('.dex-row[data-target="133"] .dex-select').click();
      const family = page.locator(".evolution-controls details");
      await expect(family).not.toHaveAttribute("open", "");
      await family.locator("summary").click();
      await expect(family.locator(".evolution-stage")).toHaveCount(9);
      for (const name of await family.locator(".evolution-name").all()) {
        await expect.poll(() => name.evaluate(node => node.clientWidth > 0 && node.scrollWidth <= node.clientWidth + 1)).toBe(true);
      }
      expect(await family.evaluate(node => node.scrollWidth <= node.clientWidth + 1)).toBe(true);
    });
    test("evolution stages keep regional identities and independent ownership", async ({ page }, info) => {
      await openRegionalFixture(page, info.project.name);
      if (device === "phone") await page.locator("#sidebar-toggle").tap();
      await page.locator("#dex-search").fill("Meowth");
      // Shared pre-feature controls let the old standalone artifact reach the
      // missing evolution-panel assertion instead of timing out on new markup.
      await page.locator("#dex-list .dex-row:not([hidden]) .dex-select").first().click();
      const stages = page.locator("#dex-selection .evolution-stage");
      await expect(stages).toHaveCount(2);
      await expect(stages.nth(0)).toContainText("Meowth (Alolan)");
      await expect(stages.nth(1)).toContainText("Persian (Alolan)");
      await stages.nth(1).locator(".status-button").click();
      await expect(stages.nth(0).locator(".status-button")).toHaveClass(/status-caught/);
      await expect(stages.nth(1).locator(".status-button")).toHaveClass(/status-caught/);
      await stages.nth(1).locator(".evolution-name").click();
      await expect(page.locator("#dex-selection .selected-title")).toContainText("Persian (Alolan)");
      await expect(page.locator("#dex-selection .selected-title .status-button")).toHaveAttribute("data-form", "53:alolan");
      const regional = await page.evaluate(key => JSON.parse(localStorage.getItem(key)!), STORAGE_KEY);
      expect(regional.forms["52:alolan"]).toBe("caught");
      expect(regional.forms["53:alolan"]).toBe("caught");
      expect(regional.forms["53:kanto"] ?? "none").toBe("none");
      await page.locator("#dex-search").fill("Spheal");
      await page.locator('.dex-row[data-target="363"] .dex-select').click();
      await expect(stages).toHaveCount(3);
      await stages.nth(0).locator(".status-button").click();
      await stages.nth(1).locator(".status-button").click();
      await expect(stages.nth(0).locator(".status-button")).toHaveClass(/status-caught/);
      await expect(stages.nth(1).locator(".status-button")).toHaveClass(/status-caught/);
      await expect(stages.nth(2).locator(".status-button")).toHaveClass(/status-none/);
      await expect(page.getByRole("button", { name: /Record evolution/i })).toHaveCount(0);
      await page.screenshot({ path: info.outputPath(`evolution-stages-${device}.png`) });
    });
    test("selects exact regional facts rather than a shared generic header", async ({ page }, info) => {
      await openRegionalFixture(page, info.project.name);
      if (device === "phone") await page.locator("#sidebar-toggle").tap();
      await page.locator("#dex-search").fill("Meowth");
      const alolan = page.locator('.dex-row[data-target="52:alolan"] .dex-select');
      const kanto = page.locator('.dex-row[data-target="52:kanto"] .dex-select');
      await alolan.click();
      await expect(page.locator("#dex-selection .selected-title")).toContainText("Meowth (Alolan)");
      await expect(page.locator("#dex-selection > .type-labels, #dex-selection .pokemon-facts-expanded .type-marks")).toHaveAttribute("aria-label", "Types: Dark");
      await expect(page.locator("#dex-selection .selected-title .status-button")).toHaveAttribute("data-form", "52:alolan");
      await expect(page.locator("#dex-selection .form-summary")).toHaveCount(0);
      await expect(alolan).toHaveAttribute("aria-current", "true");
      await kanto.click();
      await expect(page.locator("#dex-selection .selected-title")).toContainText("Meowth (Kanto)");
      await expect(page.locator("#dex-selection > .type-labels, #dex-selection .pokemon-facts-expanded .type-marks")).toHaveAttribute("aria-label", "Types: Normal");
      await expect(page.locator("#dex-selection .selected-title .status-button")).toHaveAttribute("data-form", "52:kanto");
      await expect(alolan).toHaveAttribute("aria-current", "false");
      await expect(kanto).toHaveAttribute("aria-current", "true");
      await page.screenshot({ path: info.outputPath(`regional-details-${device}.png`) });
    });
    test("splits regional Pokédex rows with independent status and favorites", async ({ page }, info) => {
      const errors: string[] = [];
      page.on("pageerror", error => errors.push(error.message));
      await openRegionalFixture(page, info.project.name);
      if (device === "phone") await page.locator("#sidebar-toggle").tap();
      await page.locator("#dex-search").fill("Meowth");
      const visible = page.locator("#dex-list .dex-row:not([hidden])");
      await expect(visible).toHaveCount(2);
      await expect(page.locator("#dex-count")).toContainText("2 of 825 collection targets");
      await expect(page.locator("#dex-count")).toContainText("Not caught 824 / Seen 0 / Caught 1");
      const alolan = visible.and(page.locator('[data-target="52:alolan"]'));
      const kanto = visible.and(page.locator('[data-target="52:kanto"]'));
      await expect(alolan.locator(".dex-name")).toContainText("Meowth (Alolan)");
      await expect(kanto.locator(".dex-name")).toContainText("Meowth (Kanto)");
      for (const name of await visible.locator(".dex-name").all()) {
        await expect.poll(() => name.evaluate(node => node.clientWidth > 0 && node.scrollWidth <= node.clientWidth + 1)).toBe(true);
      }
      await expect(alolan.locator(".type-marks")).toHaveAttribute("aria-label", "Types: Dark");
      await expect(kanto.locator(".type-marks")).toHaveAttribute("aria-label", "Types: Normal");
      await expect(alolan.locator(".status-text")).toHaveText("Caught");
      await expect(kanto.locator(".status-text")).toHaveText("Not caught");
      await kanto.locator('[data-action="form"]').click();
      await expect(kanto.locator(".status-text")).toHaveText("Caught");
      await expect(alolan.locator(".status-text")).toHaveText("Caught");
      await kanto.locator('[data-action="star"]').click();
      await alolan.locator('[data-action="star"]').click();
      await expect(kanto.locator('[data-action="star"]')).toHaveAttribute("aria-pressed", "true");
      await expect(alolan.locator('[data-action="star"]')).toHaveAttribute("aria-pressed", "false");
      const saved = await page.evaluate(key => JSON.parse(localStorage.getItem(key)!), STORAGE_KEY);
      expect(saved.forms).toMatchObject({ "52:alolan": "caught", "52:kanto": "caught" });
      expect(saved.species["52"]).toBe("caught");
      expect(saved.starredForms).toEqual(["52:kanto"]);
      await page.locator("#dex-search").fill("Alolan Meowth");
      await expect(visible).toHaveCount(1);
      await expect(visible.locator(".dex-name")).toContainText("Meowth (Alolan)");
      await page.screenshot({ path: info.outputPath(`regional-dex-${device}.png`) });
      expect(errors).toEqual([]);
    });
  });
}
