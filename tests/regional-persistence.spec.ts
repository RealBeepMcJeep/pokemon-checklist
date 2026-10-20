import { expect, test } from "@playwright/test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";
import { readFile } from "node:fs/promises";

const currentKey = "pokemon-checklist-state-v5";
const legacyKey = "pokemon-checklist-state-v4";
const mode = "photonic-prismatic";
const memory = (namespace: string) => `pokemon-checklist-last-area-v1:${namespace}:${mode}`;
const legacy = { schemaVersion: 4, species: { "25": "caught", "52": "caught" }, forms: { "52:alolan": "caught", "52:kanto": "caught" }, starred: [25, 52], settings: { forms: true, mode, unlocks: ["sos"] } };

for (const [device, width] of [["desktop", 1440], ["phone", 390]] as const) {
  test(`legacy area continuity and native v5 backup roundtrip: ${device}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 950 });
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    if (info.project.name === "standalone-file") {
      await page.route(/^https?:\/\//, route => route.abort("blockedbyclient"));
      await page.goto(pathToFileURL(resolve("index.html")).href);
    } else await page.goto("/");
    await expect(page.locator("details.location")).toHaveCount(60);
    const areaId = await page.locator("details.location").nth(12).getAttribute("data-location-id");
    const linkedHash = await page.locator("details.location").nth(8).getAttribute("id");
    const linkedArea = await page.locator("details.location").nth(8).getAttribute("data-location-id");
    expect(areaId).toBeTruthy();
    expect(linkedHash).toBeTruthy();
    await page.evaluate(({ legacyKey, legacy, oldMemory, areaId }) => {
      localStorage.clear();
      localStorage.setItem(legacyKey, JSON.stringify(legacy));
      localStorage.setItem(oldMemory, areaId!);
      history.replaceState(null, "", location.href.split("#")[0]);
    }, { legacyKey, legacy, oldMemory: memory(legacyKey), areaId });
    await page.reload();
    await expect(page.locator("#forms-toggle")).toHaveAttribute("aria-pressed", "true");
    const before = await page.evaluate(key => JSON.parse(localStorage.getItem(key)!), currentKey);
    expect(before).toEqual({ ...legacy, schemaVersion: 5, starredForms: [] });
    await expect(page.locator("#notice")).not.toContainText(/could not be read|not saved|starting a fresh/i);
    const restored = page.locator(`[data-location-id="${areaId}"]`);
    await expect(restored).toHaveCount(1);
    await expect(restored).toHaveJSProperty("open", true, { timeout: 3000 });
    await expect(restored.locator("summary")).toBeFocused();
    expect(await page.evaluate(key => localStorage.getItem(key), memory(currentKey))).toBe(areaId);
    await expect.poll(async () => {
      const summary = await restored.locator("summary").boundingBox();
      const header = await page.locator(".app-header").boundingBox();
      return summary !== null && header !== null && summary.y >= header.y + header.height - 1 && summary.y < 800;
    }).toBe(true);
    await page.screenshot({ path: info.outputPath(`migrated-area-${device}.png`) });

    if (device === "phone") await page.locator("#header-settings-toggle").click();
    await expect(page.locator("#export-button")).toBeVisible();
    const [download] = await Promise.all([page.waitForEvent("download", { timeout: 15000 }), page.locator("#export-button").click()]);
    expect(download.suggestedFilename()).toBe("pokemon-checklist-state-v5.json");
    const contents = await readFile((await download.path())!, "utf8");
    expect(JSON.parse(contents)).toEqual(before);
    page.once("dialog", dialog => dialog.accept());
    await page.locator("#import-file").setInputFiles({ name: "legacy-v1.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify({ schemaVersion: 1, species: { "731": "seen" }, forms: {}, settings: { forms: false } })) });
    await expect(page.locator("#notice")).toContainText("Backup restored.");
    expect(await page.evaluate(key => JSON.parse(localStorage.getItem(key)!).species, currentKey)).toEqual({ "731": "seen" });
    page.once("dialog", dialog => dialog.accept());
    await page.locator("#import-file").setInputFiles({ name: download.suggestedFilename(), mimeType: "application/json", buffer: Buffer.from(contents) });
    await expect(page.locator("#notice")).toContainText("Backup restored.");
    // The same notice is already present from the first import. Wait for the
    // actual async file-read/confirmation commit, not that stale success text.
    await expect.poll(async () => page.evaluate(key => JSON.parse(localStorage.getItem(key)!), currentKey)).toEqual(before);

    await page.evaluate(({ key, hash }) => {
      localStorage.removeItem(key);
      history.replaceState(null, "", `${location.href.split("#")[0]}#${hash}`);
    }, { key: memory(currentKey), hash: linkedHash! });
    await page.reload();
    await expect(page.locator(`[data-location-id="${linkedArea}"]`)).toHaveJSProperty("open", true);
    expect(await page.evaluate(key => JSON.parse(localStorage.getItem(key)!), currentKey)).toEqual(before);
    expect(await page.evaluate(key => localStorage.getItem(key), legacyKey)).toBe(JSON.stringify(legacy));
    expect(errors).toEqual([]);
  });
}
