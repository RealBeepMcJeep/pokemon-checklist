import { expect, test } from "@playwright/test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

test("overall summaries preserve global counts and active-mode forms", async ({ page }, info) => {
  await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
  const overall = page.locator("#overall-text [data-status]");
  await expect(overall).toHaveText(["Not caught 807", "Seen 0", "Caught 0"]);
  await page.locator("#forms-toggle").click();
  await expect(page.locator("#form-progress [data-status]")).toHaveText(["Not caught 48", "Seen 0", "Caught 0"]);
  await page.locator("#mode-select").selectOption("sun");
  await expect(page.locator("#form-progress [data-status]")).toHaveText(["Not caught 14", "Seen 0", "Caught 0"]);
  await page.locator("#dex-search").fill("731");
  // Tracking splits the 18 regional species into two targets: 807 + 18.
  await expect(page.locator("#dex-count")).toContainText("1 of 825 collection targets");
  for (const counts of [[806,0,1],[806,1,0],[807,0,0]]) {
    await page.locator('#dex-list [data-action="species"][data-species="731"]').click();
    const labels = [`Not caught ${counts[0]}`, `Seen ${counts[1]}`, `Caught ${counts[2]}`];
    // Overall stays species-based (807); the split Pokédex counts collection targets (825).
    const targets = [`Not caught ${counts[0] + 18}`, `Seen ${counts[1]}`, `Caught ${counts[2]}`];
    await expect(overall).toHaveText(labels);
    await expect(page.locator("#dex-count [data-status]")).toHaveText(targets);
  }
});
for (const width of [360,412,1440]) {
  test(`seeded counters fit at ${width}px without changing save or list rendering`, async ({ page }, info) => {
    await page.setViewportSize({width,height:900});
    const url = info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/";
    if (info.project.name === "standalone-file") await page.route(/^https?:\/\//,route=>route.abort());
    await page.goto(url);
    await page.evaluate(() => localStorage.setItem("pokemon-checklist-state-v4", JSON.stringify({schemaVersion:3,species:{10:"seen",731:"caught"},forms:{"19:alolan":"seen","37:alolan":"caught"},starred:[],settings:{forms:true,mode:"photonic-prismatic"}})));
    await page.reload();
    await expect(page.locator("#overall-text [data-status]")).toHaveText(["Not caught 805","Seen 1","Caught 1"]);
    await expect(page.locator("#form-progress [data-status]")).toHaveText(["Not caught 46","Seen 1","Caught 1"]);
    const saved = await page.evaluate(()=>localStorage.getItem("pokemon-checklist-state-v5"));
    await page.evaluate(()=>scrollTo(0,0));
    // Let the sticky header's composited position settle after startup focus scrolling.
    await page.waitForTimeout(200);
    await page.screenshot({path:info.outputPath(`status-${width}-header.png`)});
    const geometry = await page.evaluate(() => {
      const triples = [...document.querySelectorAll<HTMLElement>(".status-counts")].filter(el=>el.getBoundingClientRect().width && !el.closest('[aria-hidden="true"]'));
      return {overflow:document.documentElement.scrollWidth>innerWidth, clipped:triples.filter(el=>el.scrollWidth>el.clientWidth || el.getBoundingClientRect().right>innerWidth).length};
    });
    expect(geometry).toEqual({overflow:false,clipped:0});
    await expect(page.locator('#overall-text [data-status="none"]')).toHaveCSS("color","rgb(255, 154, 154)");
    const longest = await page.locator("details.location:has(.status-counts) .location-title").evaluateAll(els=>els.map(el=>el.textContent!).sort((a,b)=>b.length-a.length)[0]);
    const area = page.locator("details.location").filter({has:page.locator(".location-title",{hasText:longest})}).first();
    await area.scrollIntoViewIfNeeded();
    await area.locator("summary").screenshot({path:info.outputPath(`status-${width}-long-area.png`)});
    if (width<1000) await page.locator("#sidebar-toggle").click();
    await expect(page.locator(".dex-row")).toHaveCount(825);
    await page.locator("#dex-search").fill("731");
    await expect(page.locator("#dex-count")).toContainText("1 of 825 collection targets");
    await expect(page.locator("#dex-count [data-status]")).toHaveText(["Not caught 821","Seen 2","Caught 2"]);
    expect(await page.evaluate(()=>localStorage.getItem("pokemon-checklist-state-v5"))).toBe(saved);
    const bystander = page.locator('#dex-list [data-action="select"][data-species="500"]');
    const renders = await bystander.getAttribute("data-renders");
    await page.locator('#dex-list [data-action="species"][data-species="731"]').click();
    await expect(page.locator("#overall-text [data-status]")).toHaveText(["Not caught 805","Seen 2","Caught 0"]);
    await expect(bystander).toHaveAttribute("data-renders",renders!);
  });
}

test("location counts are ordered labeled mutually exclusive buckets", async ({ page }, info) => {
  await page.goto(info.project.name === "standalone-file" ? pathToFileURL(resolve("index.html")).href : "/");
  const progress = page.locator(".location-progress").first();
  await expect(progress.locator("[data-status]")).toHaveText(["Not caught 23", "Seen 0", "Caught 0"]);
  const button = page.locator('[data-action="species"][data-species="731"]').first();
  for (const counts of [[22,0,1],[22,1,0],[23,0,0]]) {
    await button.click();
    await expect(progress.locator("[data-status]")).toHaveText([`Not caught ${counts[0]}`, `Seen ${counts[1]}`, `Caught ${counts[2]}`]);
  }
  await expect(progress).not.toContainText("Complete");
});
