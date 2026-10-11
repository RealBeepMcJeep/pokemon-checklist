import { test, expect, type Page } from "@playwright/test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";
async function open(page: Page, project: string) {
  await page.goto(
    project === "standalone-file"
      ? pathToFileURL(resolve("index.html")).href
      : `http://127.0.0.1:${process.env.PW_PORT ?? 4173}/`,
  );
  await page.locator("#tools-toggle").click();
}

for (const width of [360, 412])
  test(`touch swipe scrolls suggestions without choosing at ${width}`, async ({
    browser,
  }, info) => {
    const context = await browser.newContext({
      viewport: { width, height: 900 },
      hasTouch: true,
      isMobile: true,
    });
    const page = await context.newPage();
    await open(page, info.project.name);
    const input = page.locator("#catch-species"),
      list = page.locator("#catch-species-list");
    await page.locator("#catch-species-name").tap();
    await input.fill("a");
    const b = (await list.boundingBox())!;
    const cdp = await context.newCDPSession(page);
    const x = b.x + b.width / 2,
      y = b.y + b.height - 25;
    await cdp.send("Input.dispatchTouchEvent", {
      type: "touchStart",
      touchPoints: [{ x, y }],
    });
    for (let i = 1; i <= 8; i++) {
      await cdp.send("Input.dispatchTouchEvent", {
        type: "touchMove",
        touchPoints: [{ x, y: y - i * 18 }],
      });
      await page.waitForTimeout(25);
    }
    await cdp.send("Input.dispatchTouchEvent", {
      type: "touchEnd",
      touchPoints: [],
    });
    await expect(input).toHaveValue("a");
    await expect(list).toBeVisible();
    await expect
      .poll(() => list.evaluate((el) => el.scrollTop))
      .toBeGreaterThan(0);
    console.log(
      "TOUCH_SCROLL",
      info.project.name,
      width,
      await list.evaluate((el) => el.scrollTop),
    );
    await input.fill("Rattata");
    await page
      .getByRole("option", { name: "Rattata — Alolan", exact: true })
      .tap();
    await expect(input).toBeHidden();
    await expect(page.locator("#catch-species-name")).toHaveText("Rattata — Alolan");
    await expect(list).toHaveCount(0);
    await context.close();
  });

for (const [field, value, message] of [
  [
    "Current HP",
    "150",
    "Current HP must be a whole number from 1 to Maximum HP",
  ],
  ["Current HP", "0", "Current HP must be a whole number from 1 to Maximum HP"],
  [
    "Current HP",
    "1.5",
    "Current HP must be a whole number from 1 to Maximum HP",
  ],
  ["Maximum HP", "0", "Maximum HP must be a whole number from 1 to 65535"],
  ["Maximum HP", "1.5", "Maximum HP must be a whole number from 1 to 65535"],
  ["Maximum HP", "", "Maximum HP must be a whole number from 1 to 65535"],
])
  test(`actionable exact HP error for ${field}=${value}`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width: 360, height: 740 });
    await open(page, info.project.name);
    await page.getByLabel("Exact HP inputs").check();
    await page.getByLabel(field, { exact: true }).fill(value);
    await expect(page.getByLabel(field, { exact: true })).toHaveAttribute(
      "aria-invalid",
      "true",
      { timeout: 1000 },
    );
    await expect(page.locator("#catch-error")).toContainText(message);
    await expect(page.locator("#catch-result")).toHaveCount(0);
    await onscreen(page, "#catch-error");
    await page.screenshot({
      path: info.outputPath(`invalid-${field}-${value || "empty"}.png`),
    });
  });

test("percent to exact preserves ratio using the current maximum", async ({
  page,
}, info) => {
  await open(page, info.project.name);
  const slider = page.getByLabel("HP remaining (approximate %)");
  await slider.fill("30");
  const before = await page.locator("#catch-result").textContent();
  await page.getByLabel("Exact HP inputs").check();
  await expect(page.getByLabel("Current HP", { exact: true })).toHaveValue(
    "30",
    { timeout: 1000 },
  );
  await expect(page.locator("#catch-result")).toHaveText(before!);
  await expect(page.getByText(/Percent mode estimates/)).toHaveCount(0);
  await page.getByLabel("Maximum HP", { exact: true }).fill("200");
  await page.getByLabel("Exact HP inputs").uncheck();
  await slider.fill("25");
  await page.getByLabel("Exact HP inputs").check();
  await expect(page.getByLabel("Current HP", { exact: true })).toHaveValue(
    "50",
  );
});

for (const width of [360, 412])
  test(`mobile action targets have room at ${width}`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 740 });
    await open(page, info.project.name);
    for (const name of ["Close tools", "Set 1 HP"]) {
      const height = await page
        .getByRole("button", { name, exact: true })
        .evaluate((el) => el.getBoundingClientRect().height);
      expect(height, name).toBeGreaterThanOrEqual(44);
    }
    await page.getByLabel("Exact HP inputs").check();
    const gap = await page.evaluate(
      () =>
        document
          .querySelector<HTMLButtonElement>(
            "#catch-calculator fieldset button",
          )!
          .getBoundingClientRect().top -
        document
          .querySelector<HTMLInputElement>('input[max="65535"]')!
          .getBoundingClientRect().bottom,
    );
    expect(gap).toBeGreaterThanOrEqual(8);
  });

async function onscreen(page: Page, selector: string) {
  const r = await page.locator(selector).evaluate((el) => {
    const r = el.getBoundingClientRect(),
      p = document.querySelector("#tools-panel")!.getBoundingClientRect();
    return {
      top: r.top,
      bottom: r.bottom,
      min: p.top,
      max: p.bottom,
      height: r.height,
    };
  });
  expect(r.top).toBeGreaterThanOrEqual(r.min);
  expect(r.bottom).toBeLessThanOrEqual(r.max);
  return r;
}
for (const width of [360, 412, 1440])
  test(`Close tools stays reachable after scrolling at ${width}`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 740 });
    await open(page, info.project.name);
    await page.locator("#tools-panel").evaluate((el) => (el.scrollTop = 700));
    await onscreen(page, ".tools-heading");
    await page
      .getByRole("button", { name: "Close tools", exact: true })
      .click();
    await expect(page.locator("#tools-panel")).not.toBeVisible();
    await expect(page.locator("#tools-toggle")).toBeFocused();
  });

for (const width of [360, 412, 1440])
  test(`live feedback stays on screen at ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: width === 360 ? 740 : 900 });
    await open(page, info.project.name);
    await onscreen(page, "#catch-result");
    await page.locator("#catch-ball-name").click();
    await page.locator("#catch-ball").fill("Quick Ball");
    await page.getByRole("option",{name:"Quick Ball",exact:true}).click();
    await page.getByLabel("Turn number").fill("2");
    await onscreen(page, "#catch-result");
    await page.getByLabel("HP remaining (approximate %)").fill("30");
    await onscreen(page, "#catch-result");
    await page.getByRole("button",{name:"Asleep ×2.5",exact:true}).click();
    await onscreen(page, "#catch-result");
    await page
      .getByText("Optional modifiers & hack override", { exact: true })
      .click();
    await page.getByLabel("Historical registered-caught species").fill("700");
    const result = await onscreen(page, "#catch-result");
    expect(result.height).toBeLessThan(100);
    await page.screenshot({ path: info.outputPath(`feedback-${width}.png`) });
  });
