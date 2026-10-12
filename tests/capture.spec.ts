import { test, expect, type Page } from "@playwright/test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";
async function open(page: Page, project: string) {
  await page.goto(
    project === "standalone-file"
      ? pathToFileURL(resolve("index.html")).href
      : "/",
  );
  await page.locator("#tools-toggle").click();
}
async function choose(page: Page, kind: "species" | "ball", name: string) {
  await page.locator(`#catch-${kind}-name`).click();
  await page.locator(`#catch-${kind}`).fill(name);
  await page.getByRole("option", {name, exact:true}).click();
}
test("calculator autocomplete is keyboard and pointer selectable without stale results", async ({page}, info) => {
  await open(page, info.project.name);
  await expect(page.locator("#catch-species-name")).toHaveText("Pikachu");
  const before = await page.locator("#catch-result").textContent();
  await page.locator("#catch-species-name").click();
  const species = page.locator("#catch-species");
  await species.fill("not a pokemon");
  await expect(page.locator("#catch-result")).toHaveText(before!);
  await expect(page.locator("#catch-error")).toHaveCount(0);
  await species.fill("Rattata"); await species.press("ArrowDown"); await species.press("ArrowDown"); await species.press("Enter");
  await expect(page.locator("#catch-species-name")).toHaveText("Rattata");
  await page.locator("#catch-species-name").click(); await species.fill("Rattata"); await species.press("ArrowUp"); await species.press("Enter");
  await expect(page.locator("#catch-species-name")).toHaveText("Rattata");
  await choose(page,"ball","Ultra Ball");
  await expect(page.locator("#catch-ball-name")).toHaveText("Ultra Ball");
  await expect(page.locator("#catch-breakdown")).toContainText("Ball ×2");
});
test("HP and exclusive status update probability and reject fainted targets", async ({
  page,
}, info) => {
  await open(page, info.project.name);
  const result = page.locator("#catch-result"),
    before = await result.textContent();
  await page.getByLabel("HP remaining (approximate %)").fill("10");
  await expect(result).not.toHaveText(before!);
  await page.getByRole("button", { name: "Asleep ×2.5", exact: true }).click();
  await page.getByRole("button", { name: "Paralyzed ×1.5", exact: true }).click();
  await expect(page.getByRole("button", { name: "Asleep ×2.5", exact: true })).toHaveAttribute("aria-pressed", "false");
  await expect(page.locator("#catch-breakdown")).toContainText("Status ×1.5");
  await page.getByRole("button", { name: "None ×1", exact: true }).click();
  await expect(page.getByRole("button", { name: "Paralyzed ×1.5", exact: true })).toHaveAttribute("aria-pressed", "false");
  await page.getByLabel("Exact HP inputs").check();
  await page.getByLabel("Current HP", { exact: true }).fill("0");
  await expect(result).toHaveCount(0);
  await page.getByRole("button", { name: "Set 1 HP", exact: true }).click();
  await expect(page.getByLabel("Current HP", { exact: true })).toHaveValue("1");
  await expect(result).toBeVisible();
});
test("conditional ball fields apply first-turn and environmental rules", async ({
  page,
}, info) => {
  await open(page, info.project.name);
  await choose(page,"ball","Quick Ball");
  await expect(page.getByLabel("Turn number")).toHaveValue("1");
  await expect(page.locator("#catch-breakdown")).toContainText("Ball ×5");
  await page.getByLabel("Turn number").fill("2");
  await expect(page.locator("#catch-breakdown")).toContainText("Ball ×1");
  await choose(page,"ball","Dusk Ball");
  await expect(page.getByLabel("Turn number")).toHaveCount(0);
  await page.getByRole("button",{name:"Inside a cave",exact:true}).click();
  await expect(page.locator("#catch-breakdown")).toContainText("Ball ×3");
  await choose(page,"ball","Love Ball");
  await page.getByRole("button",{name:"Same species as your active Pokémon",exact:true}).click();
  await page.getByRole("button",{name:"Opposite male / female genders",exact:true}).click();
  await expect(page.locator("#catch-breakdown")).toContainText("Ball ×8");
});
test("historical critical, Roto and marked rate override expose assumptions", async ({
  page,
}, info) => {
  await open(page, info.project.name);
  const result = page.locator("#catch-result"),
    before = await result.textContent();
  await page
    .getByText("Optional modifiers & hack override", { exact: true })
    .click();
  await page.getByLabel("Historical registered-caught species").fill("601");
  await expect(result).not.toHaveText(before!);
  await expect(page.locator("#catch-breakdown")).toContainText("Dex ×2.5");
  await page.getByLabel("Roto Catch ×2.5").check();
  await expect(page.locator("#catch-breakdown")).toContainText("Roto ×2.5");
  await page.getByLabel("Override stock catch rate").check();
  await page.getByLabel("Catch rate override (0–255)").fill("0");
  await expect(result).toContainText("0.00%");
  await expect(page.locator("#catch-breakdown")).toContainText("OVERRIDE");
  await page.getByRole("button", { name: "Close tools" }).click();
  await page.locator("#mode-select").selectOption("sun");
  await page.locator("#tools-toggle").click();
  await expect(page.getByLabel("Roto Catch ×2.5")).toBeDisabled();
  await choose(page,"species","Poipole");
  await expect(result).toHaveCount(0);
  await expect(page.locator("#catch-error")).toContainText("unavailable");
});
test("equation notes qualify the model and link pinned evidence", async ({
  page,
}, info) => {
  await open(page, info.project.name);
  await page.getByText("Equation, data & assumptions", { exact: true }).click();
  await expect(page.locator("#catch-notes")).toContainText("not bit-exact");
  await expect(page.locator("#catch-notes")).toContainText("Prismatic");
  await expect(page.locator("#catch-notes")).toContainText("q⁴");
});
for (const width of [360, 412, 1440])
  test(`Tools remains offline, save-safe and contained at ${width}px`, async ({
    browser,
  }, info) => {
    const context = await browser.newContext({
      viewport: { width, height: 900 },
      hasTouch: true,
      isMobile: width < 500,
    });
    const page = await context.newPage();
    const errors: string[] = [],
      remote: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("request", (r) => {
      if (/^https?:/.test(r.url()) && !r.url().startsWith("http://127.0.0.1:"))
        remote.push(r.url());
    });
    await page.goto(
      info.project.name === "standalone-file"
        ? pathToFileURL(resolve("index.html")).href
        : "/",
    );
    await page.evaluate(() =>
      localStorage.setItem(
        "pokemon-checklist-state-v3",
        JSON.stringify({
          schemaVersion: 3,
          species: { "1": "caught" },
          forms: {},
          starred: [25],
          settings: { forms: false, mode: "photonic-prismatic" },
        }),
      ),
    );
    await page.reload();
    await expect(page.locator("#overall-text [data-status]")).toHaveText(["Not caught 806", "Seen 0", "Caught 1"]);
    const before = await page.evaluate(() =>
      Object.fromEntries(
        Object.entries(localStorage).filter(([k]) =>
          /state|last-good|records|outbox/.test(k),
        ),
      ),
    );
    await page.locator("#tools-toggle").tap();
    await page.locator("#catch-ball-name").tap();
    await page.getByRole("combobox", { name: "Ball" }).fill("Net");
    await page.getByRole("option", { name: "Net Ball", exact: true }).tap();
    await choose(page,"species","Squirtle");
    await expect(page.locator("#catch-breakdown")).toContainText("Ball ×3.5");
    await page.getByRole("button", { name: "Asleep ×2.5", exact: true }).click();
    await expect(page.locator("#catch-result")).toBeVisible();
    const measured = await page
      .locator("#tools-panel")
      .evaluate((el) => ({
        scroll: el.scrollWidth,
        client: el.clientWidth,
        rect: el.getBoundingClientRect().toJSON(),
        labels: [...el.querySelectorAll("label,summary,button")]
          .filter((e) => e.getClientRects().length)
          .map((e) => ({
            text: e.textContent,
            scroll: e.scrollWidth,
            client: e.clientWidth,
          })),
      }));
    expect(measured.scroll).toBeLessThanOrEqual(measured.client);
    expect(measured.rect.x).toBeGreaterThanOrEqual(0);
    expect(measured.rect.right).toBeLessThanOrEqual(width);
    for (const label of measured.labels)
      expect(label.scroll, label.text ?? "").toBeLessThanOrEqual(
        label.client + 1,
      );
    await page.screenshot({
      path: info.outputPath(`tools-${width}.png`),
      fullPage: false,
    });
    await page.locator("#catch-result").scrollIntoViewIfNeeded();
    await page.screenshot({
      path: info.outputPath(`tools-${width}-result.png`),
    });
    await page.getByRole("button", { name: "Close tools" }).tap();
    expect(
      await page.evaluate(() =>
        Object.fromEntries(
          Object.entries(localStorage).filter(([k]) =>
            /state|last-good|records|outbox/.test(k),
          ),
        ),
      ),
    ).toEqual(before);
    expect(remote).toEqual([]);
    expect(errors).toEqual([]);
    await context.close();
  });
test("Master Ball reports a bypass only with legal HP", async ({
  page,
}, info) => {
  await open(page, info.project.name);
  await choose(page,"ball","Master Ball");
  await expect(page.locator("#catch-result")).toContainText("100.00%");
  await expect(page.locator("#catch-breakdown")).toContainText(
    "Master Ball bypasses",
  );
  await page.getByLabel("Exact HP inputs").check();
  await page.getByLabel("Current HP", { exact: true }).fill("0");
  await expect(page.locator("#catch-result")).toHaveCount(0);
});
test("Tools opens subordinate QR links and closes with restored focus", async ({
  page,
}, info) => {
  await open(page, info.project.name);
  const panel = page.locator("#tools-panel");
  await expect(panel).toBeVisible();
  await expect(panel.getByRole("link", { name: "QR archive" })).toHaveAttribute(
    "href",
    "qr.html",
  );
  await expect(
    panel.getByRole("link", { name: "Experimental QR" }),
  ).toHaveAttribute("href", "qr-experimental.html");
  await page.keyboard.press("Escape");
  await expect(panel).not.toBeVisible();
  await expect(page.locator("#tools-toggle")).toBeFocused();
});
