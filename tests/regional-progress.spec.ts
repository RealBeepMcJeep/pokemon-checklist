import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const KEY = "pokemon-checklist-state-v5";
for (const width of [390, 1440]) test.describe(`regional progress ${width}px`, () => {
  test.use({ viewport: { width, height: 950 }, isMobile: width === 390, hasTouch: width === 390 });
  test("missing Kanto SOS form drives completion, Catch next, exact edit and Undo", async ({ page }, info) => {
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    const pokemon = JSON.parse(await readFile(resolve("data/pokemon.json"), "utf8"));
    const regional = JSON.parse(await readFile(resolve("data/regional-forms.json"), "utf8"));
    const forms: Record<string, string> = Object.fromEntries(Object.keys(regional.forms).map(key => [key, "caught"]));
    delete forms["52:kanto"];
    const fixture = { schemaVersion: 5, species: Object.fromEntries(pokemon.map((p: { id: number }) => [p.id, "caught"])),
      forms, starred: [], starredForms: [], settings: { forms: true, mode: "photonic-prismatic", unlocks: ["sos"] } };
    const read = () => page.evaluate(key => JSON.parse(localStorage.getItem(key)!), KEY);
    await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
    await page.evaluate(value => { localStorage.clear(); localStorage.setItem("pokemon-checklist-state-v5", JSON.stringify(value)); }, fixture);
    await page.reload();
    await expect(page.getByText("Your saved checklist could not be read", { exact: false })).toHaveCount(0);
    expect(await read()).toEqual(fixture);
    const school = page.locator('[data-location-progress="melemele-island/trainers-school"]');
    await expect(school).toHaveCount(1);
    await expect(school).not.toHaveClass(/complete/);
    await expect(school.getByRole("group")).toHaveAttribute("aria-label", /Not caught 1, Seen 0, Caught \d+/);
    await expect(school.locator("[data-backtrack]")).toHaveCount(1);
    const next = page.locator(".catch-next");
    await expect(next).toHaveCount(1);
    await expect(next.locator(".catch-next-name")).toHaveText(["Meowth (Kanto)"]);

    await page.locator("#header-settings-toggle").click();
    await page.getByLabel("SOS Calls", { exact: true }).uncheck();
    await page.getByRole("button", { name: "Close settings", exact: true }).click();
    await expect(school).toHaveClass(/complete/);
    await expect(school.locator("[data-backtrack]")).toHaveCount(0);
    await expect(school.locator(".locked-count")).toContainText(/Locked [1-9]\d*/);
    await expect(page.locator(".catch-next-done")).toHaveCount(1);
    await page.locator("#header-settings-toggle").click();
    await page.getByLabel("SOS Calls", { exact: true }).check();
    await page.getByRole("button", { name: "Close settings", exact: true }).click();
    await expect(school).not.toHaveClass(/complete/);

    if (width === 390) await page.locator("#header-settings-toggle").click();
    await page.locator("#forms-toggle").click();
    if (width === 390) await page.getByRole("button", { name: "Close settings", exact: true }).click();
    await expect(school).toHaveClass(/complete/);
    await expect(page.locator(".catch-next-done")).toHaveCount(1);
    expect((await read()).forms).toEqual(fixture.forms);
    if (width === 390) await page.locator("#header-settings-toggle").click();
    await page.locator("#forms-toggle").click();
    if (width === 390) await page.getByRole("button", { name: "Close settings", exact: true }).click();
    await expect(school).not.toHaveClass(/complete/);
    expect(await read()).toEqual(fixture);

    if (width === 390) await page.getByRole("button", { name: "Pokédex", exact: true }).click();
    if (!await next.evaluate(element => (element as HTMLDetailsElement).open)) await next.locator("summary").click();
    const control = next.locator('[data-form="52:kanto"]');
    await expect(control).toHaveCount(1);
    await expect(control).toHaveAccessibleName(/Meowth \(Kanto\) catch next status: Not caught/);
    await page.screenshot({ path: info.outputPath(`missing-kanto-${width}.png`) });
    await control.click();
    await expect(page.locator(".catch-next-done")).toHaveCount(1);
    await expect(school).toHaveClass(/complete/);
    await expect(page.locator('[data-location-id="melemele-island/trainers-school"]')).not.toHaveAttribute("open");
    expect(await read()).toEqual({ ...fixture, forms: { ...fixture.forms, "52:kanto": "caught" } });
    if (width === 390) await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "Undo", exact: true }).click();
    await expect(school).not.toHaveClass(/complete/);
    expect(await read()).toEqual(fixture);
    expect(errors).toEqual([]);
  });
});
