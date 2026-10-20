import { expect, test } from "@playwright/test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

for (const width of [360, 412]) test(`mobile identity and command layout switch together at ${width}px`, async ({ page }, info) => {
  await page.setViewportSize({ width, height: 844 });
  await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
  // Startup owns an intentional section scroll; do not race it with test input.
  await expect(page.locator("details.location[open] > summary").first()).toBeFocused();
  await page.evaluate(() => scrollTo(0, 0));
  await expect(page.locator(".app-header")).not.toHaveClass(/is-scrolled/);
  await expect(page.locator(".mobile-identity")).toHaveCSS("opacity", "1");
  const compact = await page.evaluate(async () => {
    scrollTo(0, 500); dispatchEvent(new Event("scroll"));
    await Promise.resolve(); await Promise.resolve();
    const identity = document.querySelector<HTMLElement>(".mobile-identity")!;
    return { scrolled: document.querySelector(".app-header")!.classList.contains("is-scrolled"), opacity: getComputedStyle(identity).opacity, height: identity.getBoundingClientRect().height };
  });
  expect(compact.scrolled).toBe(true);
  // The grid changes immediately: a still-visible identity would overlap it,
  // and opacity=1 would falsely satisfy the old expanded-state test predicate.
  expect(compact.opacity).toBe("0");
  expect(compact.height).toBe(0);
  const expanded = await page.evaluate(async () => {
    scrollTo(0, 0); dispatchEvent(new Event("scroll"));
    await Promise.resolve(); await Promise.resolve();
    const identity = document.querySelector<HTMLElement>(".mobile-identity")!;
    const count = document.querySelector("#overall-text")!.getBoundingClientRect();
    const command = document.querySelector("#tools-toggle")!.getBoundingClientRect();
    return { scrolled: document.querySelector(".app-header")!.classList.contains("is-scrolled"), opacity: getComputedStyle(identity).opacity, height: identity.getBoundingClientRect().height, countTop: count.y, commandBottom: command.bottom };
  });
  expect(expanded.scrolled).toBe(false);
  expect(expanded.opacity).toBe("1");
  expect(expanded.height).toBe(24);
  expect(expanded.countTop).toBeGreaterThanOrEqual(expanded.commandBottom);
});
