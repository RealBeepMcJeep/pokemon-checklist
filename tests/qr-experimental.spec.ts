import { expect, test, type Page } from '@playwright/test';
import { createServer, type Server } from 'node:http';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { execFileSync } from 'node:child_process';

const metadata = JSON.parse(readFileSync(resolve('references/qr-codes/gen7-form-types.json'), 'utf8'));
const names = JSON.parse(readFileSync(resolve('data/pokemon.json'), 'utf8'));
const file = pathToFileURL(resolve('qr-experimental.html')).href;
let server: Server;
let hosted = '';

async function verifyScreenshot(page: Page, path: string, dex: number, form: number) {
  await page.locator('#scan-image').screenshot({ path });
  const imageData = await page.locator('#scan-image').getAttribute('src');
  const code = `import base64,json,sys
from io import BytesIO
from PIL import Image
import zxingcpp
from tools.qr_codec import verify_ordinary_payload
data=json.load(sys.stdin)
def decode(image):
    symbols=zxingcpp.read_barcodes(image,formats=zxingcpp.BarcodeFormat.QRCode)
    assert len(symbols)==1
    return bytes(symbols[0].bytes)
raw=decode(Image.open(data['path']))
assert raw==decode(Image.open(BytesIO(base64.b64decode(data['png'].split(',')[1]))))
d=verify_ordinary_payload(raw)
assert (d.species_id,d.form,d.gender,d.shiny_flag,d.both_genders_flag,d.key_index)==(data['dex'],data['form'],0,0,0,3)
print('Screenshot raw payload and signed fields verified')`;
  // Use the configured dev interpreter locally and setup-python's interpreter in CI.
  const result = execFileSync(process.env.QR_TEST_PYTHON ?? 'python', ['-c', code], {
    input: JSON.stringify({ path, png: imageData, dex, form }), encoding: 'utf8', timeout: 30_000,
  });
  expect(result).toContain('Screenshot raw payload and signed fields verified');
}

test.beforeAll(async () => {
  server = createServer((request, response) => {
    if (request.url !== '/qr-experimental.html') { response.writeHead(404).end(); return; }
    response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
    response.end(readFileSync(resolve('qr-experimental.html')));
  });
  await new Promise<void>(done => server.listen(0, '127.0.0.1', done));
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('No HTTP address');
  hosted = `http://127.0.0.1:${address.port}/qr-experimental.html`;
});
test.afterAll(async () => {
  if (server?.listening) await new Promise<void>(done => server.close(() => done()));
});

async function open(page: Page, project: string, hash = '') {
  const network: string[] = [];
  const errors: string[] = [];
  const url = project === 'standalone-file' ? file : hosted;
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => {
    if (/^https?:/.test(request.url()) && request.url() !== hosted) network.push(request.url());
  });
  await page.route(/^https?:/, route => route.request().url() === hosted ? route.continue() : route.abort());
  await page.goto(url + hash);
  await expect(page.locator('.qr-card')).toHaveCount(1116);
  return { network, errors };
}

test('all 807 species and every pinned form row, exact names/types, sort and combined filters', async ({ page }, info) => {
  const logs = await open(page, info.project.name);
  const rows = await page.locator('.qr-card').evaluateAll(cards => cards.map(card => {
    const d = (card as HTMLElement).dataset;
    return { dex: Number(d.dex), form: Number(d.form), name: d.name, types: d.types!.split(' ') };
  }));
  expect([...new Set(rows.map(row => row.dex))]).toEqual(Array.from({ length: 807 }, (_, i) => i + 1));
  expect(rows.map(row => `${row.dex}:${row.form}`).sort()).toEqual(Object.keys(metadata.typesBySpeciesForm).sort());
  for (const row of rows) {
    expect(row.name).toBe(names.find((name: { id: number }) => name.id === row.dex).name);
    expect(row.types).toEqual(metadata.typesBySpeciesForm[`${row.dex}:${row.form}`]);
  }
  for (const order of ['dex-desc', 'name-asc', 'name-desc', 'dex-asc']) {
    await page.locator('#sort-order').selectOption(order);
    const data = await page.locator('.qr-card').evaluateAll(cards => cards.map(card => {
      const d = (card as HTMLElement).dataset;
      return { dex: Number(d.dex), form: Number(d.form), name: d.name! };
    }));
    const collator = new Intl.Collator('en', { sensitivity: 'base' });
    for (let i = 1; i < data.length; i++) {
      const a = data[i - 1], b = data[i];
      const comparison = order.startsWith('dex') ? a.dex - b.dex : collator.compare(a.name, b.name);
      expect((order.endsWith('desc') ? -1 : 1) * comparison).toBeLessThanOrEqual(0);
      if (a.dex === b.dex) expect(a.form).toBeLessThanOrEqual(b.form);
    }
  }
  await page.locator('#search').fill('Rattata Alola');
  await page.locator('#type-filter').selectOption('Dark');
  await page.locator('#library-filter').selectOption('generated');
  await expect(page.locator('.qr-card:not([hidden])')).toHaveCount(1);
  await expect(page.locator('#qr-19-1')).toBeVisible();
  await page.locator('#search').fill('no matching species');
  await expect(page.locator('#empty-state')).toBeVisible();
  await expect(page.locator('.gift-card')).toHaveCount(0);
  expect(logs).toEqual({ network: [], errors: [] });
});

test('360, 390 and 1440 layout, full viewport viewer, guide links and screenshot evidence', async ({ page }, info) => {
  const logs = await open(page, info.project.name);
  for (const width of [360, 390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBe(0);
    await page.locator('#search').fill('Bulbasaur');
    await page.screenshot({ path: info.outputPath(`experimental-${width}.png`) });
    await page.locator('#qr-1-0 .qr-original').click();
    const dialog = page.locator('#scan-view');
    await expect(dialog).toBeVisible();
    const box = await dialog.boundingBox();
    expect(box?.width).toBe(width);
    expect(box?.height).toBe(900);
    await expect(page.locator('#scan-library-membership')).toContainText('console untested');
    await expect(page.locator('#scan-close')).toBeFocused();
    await expect(page.locator('html')).toHaveCSS('overflow', 'hidden');
    await expect.poll(() => page.locator('#scan-image').evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)).toBe(true);
    await verifyScreenshot(page, info.outputPath(`raw-qr-1-0-${width}.png`), 1, 0);
    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();
    await expect(page.locator('#qr-1-0 .card-open')).toBeFocused();
  }
  await page.locator('[data-qr-target="qr-479-1"]').click();
  await expect(page.locator('#scan-title')).toContainText('Rotom');
  await page.locator('#scan-next').click();
  await expect(page.locator('#scan-title')).not.toContainText('Bulbasaur');
  await page.goBack();
  await expect(page.locator('#scan-view')).toBeHidden();
  expect(logs).toEqual({ network: [], errors: [] });
});

test('true touch-mobile deep link and representative form/boundary QR screenshots', async ({ browser }, info) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const page = await context.newPage();
  const logs = await open(page, info.project.name, '#qr-807-0');
  expect(await page.evaluate(() => matchMedia('(pointer: coarse)').matches)).toBe(true);
  await expect(page.locator('#scan-title')).toContainText('Zeraora');
  for (const [dex, form] of [[807, 0], [19, 1], [201, 1], [479, 1]]) {
    if (dex !== 807) {
      await page.locator('#scan-close').click();
      await page.locator(`[data-qr-target="qr-${dex}-${form}"]`).click();
    }
    await expect.poll(() => page.locator('#scan-image').evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)).toBe(true);
    await verifyScreenshot(page, info.outputPath(`raw-qr-${dex}-${form}-touch.png`), dex, form);
    await page.screenshot({ path: info.outputPath(`viewer-${dex}-${form}-touch.png`) });
  }
  expect(logs).toEqual({ network: [], errors: [] });
  await context.close();
});

test('Random shuffles the full catalogue before filtering and each explicit reshuffle', async ({ page }, info) => {
  await page.addInitScript(() => {
    let seed = 0x12345678;
    Math.random = () => {
      seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
      return seed / 4294967296;
    };
  });
  const logs = await open(page, info.project.name);
  await expect(page.locator('#sort-order option[value="random"]')).toHaveCount(1);
  const ids = () => page.locator('.qr-card').evaluateAll(cards => cards.map(card => card.id));
  const original = await ids();
  let seed = 0x12345678;
  const shuffled = (input: string[]) => {
    const output = [...input];
    for (let i = output.length - 1; i > 0; i--) {
      seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
      const j = Math.floor((seed / 4294967296) * (i + 1));
      [output[i], output[j]] = [output[j], output[i]];
    }
    return output;
  };
  // Hide almost everything first: Random must shuffle hidden records too.
  await page.locator('#search').fill('Rattata Alola');
  await page.locator('#type-filter').selectOption('Dark');
  await page.locator('#sort-order').selectOption('random');
  const first = await ids();
  expect(first).toEqual(shuffled(original));
  expect(first).not.toEqual(original);
  expect([...first].sort()).toEqual([...original].sort());
  await expect(page.locator('.qr-card:not([hidden])')).toHaveCount(1);
  await expect(page.locator('#shuffle-again')).toBeVisible();
  await page.locator('#sort-order').selectOption('random');
  const selectedAgain = await ids();
  expect(selectedAgain).toEqual(shuffled(first));
  await page.locator('#shuffle-again').click();
  const second = await ids();
  expect(second).toEqual(shuffled(selectedAgain));
  expect(second).not.toEqual(selectedAgain);
  await page.locator('#search').fill('');
  await page.locator('#type-filter').selectOption('');
  expect(await ids()).toEqual(second); // Filtering must not reshuffle implicitly.
  await expect(page.locator('.qr-card:not([hidden])')).toHaveCount(original.length);
  const next = page.locator('.qr-card').nth(1);
  const expectedImage = await next.locator('.qr-original').getAttribute('src');
  const dex = Number(await next.getAttribute('data-dex'));
  const form = Number(await next.getAttribute('data-form'));
  await page.locator('.qr-card').first().locator('.card-open').click();
  await page.locator('#scan-next').click();
  await expect(page.locator('#scan-image')).toHaveAttribute('src', expectedImage!);
  await verifyScreenshot(page, info.outputPath('random-next-qr.png'), dex, form);
  await page.locator('#scan-prev').click();
  await expect(page.locator('#scan-image')).toHaveAttribute('src', (await page.locator('.qr-card').first().locator('.qr-original').getAttribute('src'))!);
  await page.locator('#scan-close').click();
  await page.locator('#sort-order').selectOption('dex-asc');
  expect(await ids()).toEqual(original);
  await expect(page.locator('#shuffle-again')).toBeHidden();
  await page.locator('#sort-order').selectOption('random');
  expect(await ids()).toEqual(shuffled(original));
  expect(logs).toEqual({ network: [], errors: [] });
});

test('Random controls fit real touch phones and reshuffle even when no QR matches', async ({ browser }, info) => {
  const context = await browser.newContext({ viewport: { width: 360, height: 844 }, isMobile: true, hasTouch: true });
  const page = await context.newPage();
  const logs = await open(page, info.project.name);
  expect(await page.evaluate(() => matchMedia('(pointer: coarse)').matches)).toBe(true);
  await page.locator('#sort-order').selectOption('random');
  for (const width of [320, 360, 390]) {
    await page.setViewportSize({ width, height: 844 });
    const select = await page.locator('#sort-order').boundingBox();
    const button = await page.locator('#shuffle-again').boundingBox();
    expect(select!.x).toBeGreaterThanOrEqual(0);
    expect(select!.x + select!.width).toBeLessThanOrEqual(button!.x);
    expect(button!.x + button!.width).toBeLessThanOrEqual(width);
    expect(button!.height).toBeGreaterThanOrEqual(44);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const labelFits = await page.locator('#sort-order').evaluate((node: HTMLSelectElement) => {
      const style = getComputedStyle(node);
      const ctx = document.createElement('canvas').getContext('2d')!;
      ctx.font = style.font;
      return ctx.measureText(node.selectedOptions[0].text).width + parseFloat(style.paddingLeft) + parseFloat(style.paddingRight) + 24 <= node.clientWidth;
    });
    expect(labelFits).toBe(true);
  }
  await page.locator('#search').fill('no matching species anywhere');
  await expect(page.locator('#empty-state')).toBeVisible();
  const before = await page.locator('.qr-card').evaluateAll(cards => cards.map(card => card.id));
  await page.locator('#shuffle-again').tap();
  const after = await page.locator('.qr-card').evaluateAll(cards => cards.map(card => card.id));
  expect(after).not.toEqual(before);
  expect([...after].sort()).toEqual([...before].sort());
  await expect(page.locator('#empty-state')).toBeVisible();
  await page.locator('#search').fill('');
  await expect(page.locator('.qr-card:not([hidden])')).toHaveCount(before.length);
  expect(await page.locator('.qr-card').evaluateAll(cards => cards.map(card => card.id))).toEqual(after);
  await page.screenshot({ path: info.outputPath('random-touch-controls.png') });
  expect(logs).toEqual({ network: [], errors: [] });
  await context.close();
});
