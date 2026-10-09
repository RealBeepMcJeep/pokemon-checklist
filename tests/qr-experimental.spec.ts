import { expect, test, type Page } from '@playwright/test';
import { createServer, type Server } from 'node:http';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { execFileSync } from 'node:child_process';

const metadata = JSON.parse(readFileSync(resolve('references/qr-codes/gen7-form-types.json'), 'utf8'));
const file = pathToFileURL(resolve('qr-experimental.html')).href;
let server: Server;
let hosted = '';

// Decode QR images with zxing-cpp and check each against the card's expected payload and signed fields.
function verifyDecoded(items: { png: string; payload: string; dex: number; form: number; gender: number; shiny: number }[]) {
  const code = `import base64,json,sys
from io import BytesIO
from PIL import Image
import zxingcpp
from tools.qr_codec import verify_ordinary_payload
items=json.load(sys.stdin)
for item in items:
    symbols=zxingcpp.read_barcodes(Image.open(BytesIO(base64.b64decode(item['png'].split(',')[1]))),formats=zxingcpp.BarcodeFormat.QRCode)
    assert len(symbols)==1
    raw=bytes(symbols[0].bytes)
    assert raw==base64.b64decode(item['payload'])
    d=verify_ordinary_payload(raw)
    assert (d.species_id,d.form,d.gender,d.shiny_flag,d.both_genders_flag,d.key_index)==(item['dex'],item['form'],item['gender'],item['shiny'],0,3)
print(f'{len(items)} rendered QR codes decoded and verified')`;
  // Use the configured dev interpreter locally and setup-python's interpreter in CI.
  const result = execFileSync(process.env.QR_TEST_PYTHON ?? 'python', ['-c', code], {
    input: JSON.stringify(items), encoding: 'utf8', timeout: 300_000, maxBuffer: 64 * 1024 * 1024,
  });
  expect(result).toContain(`${items.length} rendered QR codes decoded and verified`);
}

const GENDER: Record<string, number> = { m: 0, f: 1, u: 2 };

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
  await expect(page.locator('.qr-card')).toHaveCount(1082);
  await expect(page.locator('.blocked-row')).toHaveCount(28);
  return { network, errors };
}

test('every scannable form row is a card, blocked rows sit apart, and sort and filters cover both', async ({ page }, info) => {
  const logs = await open(page, info.project.name);
  const rows = await page.locator('.qr-card, .blocked-row').evaluateAll(items => items.flatMap(item => {
    const d = (item as HTMLElement).dataset;
    return (d.forms ?? d.form!).split(' ').map(form => `${d.dex}:${form}`);
  }));
  expect(rows.sort()).toEqual(Object.keys(metadata.typesBySpeciesForm).sort());
  const blocked = await page.locator('.blocked-row').evaluateAll(items => items.map(item => Number((item as HTMLElement).dataset.dex)));
  expect(blocked).toEqual([...blocked].sort((a, b) => a - b));
  expect(new Set(blocked)).toEqual(new Set([25, ...Array.from({ length: 23 }, (_, i) => 785 + i)]));
  await expect(page.locator('.blocked-row img.qr-original')).toHaveCount(0);
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
  await expect(page.locator('.qr-card:not([hidden])')).toHaveCount(1);
  await expect(page.locator('#qr-19-1')).toBeVisible();
  await page.locator('#type-filter').selectOption('');
  await page.locator('#search').fill('');
  await page.locator('#tested-filter').selectOption('tested');
  await expect(page.locator('.qr-card:not([hidden])')).toHaveCount(11);
  await expect(page.locator('#not-scannable')).toBeHidden();
  await page.locator('#tested-filter').selectOption('');
  await page.locator('#search').fill('Tapu');
  await expect(page.locator('.qr-card:not([hidden])')).toHaveCount(0);
  await expect(page.locator('#empty-state')).toContainText('in the list below');
  await expect(page.locator('.blocked-row:not([hidden])')).toHaveCount(4);
  await expect(page.locator('#blocked-heading')).toHaveText('Can’t be added with a QR code (4)');
  await expect(page.locator('#result-count')).toContainText('4 more below');
  await page.locator('#search').fill('mega charizard');
  await expect(page.locator('.qr-card:not([hidden])')).toHaveCount(2);
  expect(logs).toEqual({ network: [], errors: [] });
});

test('gender and shiny switches change the drawn code, and every variant decodes exactly', async ({ page }, info) => {
  test.setTimeout(420_000);
  const logs = await open(page, info.project.name);
  const card = page.locator('#qr-592-0');
  await page.locator('#search').fill('Frillish');
  const gender = card.locator('.gender-switch');
  const shiny = card.locator('.shiny-switch');
  await expect(gender).toHaveAttribute('aria-label', 'Male. Switch to female');
  await expect(shiny).toHaveAttribute('aria-checked', 'false');
  const before = await card.locator('.qr-original').getAttribute('src');
  await gender.click();
  await expect(gender).toHaveAttribute('aria-label', 'Female. Switch to male');
  await expect(card).toHaveAttribute('data-gender', 'f');
  await shiny.click();
  await expect(shiny).toHaveAttribute('aria-checked', 'true');
  await expect(card).toHaveClass(/is-shiny/);
  const after = await card.locator('.qr-original').getAttribute('src');
  expect(after).not.toBe(before);
  await shiny.press('Space');
  await expect(shiny).toHaveAttribute('aria-checked', 'false');
  await expect(page.locator('#qr-150-0 .gender-switch')).toHaveCount(0);
  await expect(page.locator('#qr-150-0 .gender-fixed')).toContainText('Genderless');
  await expect(page.locator('#qr-658-2 .gender-fixed')).toContainText('Male only');
  await expect(page.locator('#qr-670-0 .gender-fixed')).toContainText('Female only');
  // Draw every variant with the page's own library and decode it outside the browser.
  const items = await page.evaluate(() => {
    const out: { png: string; payload: string; dex: number; form: number; gender: string; shiny: number }[] = [];
    for (const element of document.querySelectorAll<HTMLElement>('.qr-card')) {
      for (const [key, payload] of Object.entries(element.dataset)) {
        if (!/^qr[A-Z]/.test(key) || !payload) continue;
        // @ts-expect-error qrcode-generator is inlined as a global
        const code = qrcode(0, 'L'); code.addData(atob(payload), 'Byte'); code.make();
        const variant = key.slice(2).toLowerCase();
        out.push({ png: code.createDataURL(3, 12), payload, dex: Number(element.dataset.dex), form: Number(element.dataset.form),
          gender: variant[0], shiny: variant.endsWith('s') ? 1 : 0 });
      }
    }
    return out;
  });
  expect(items).toHaveLength(3810);
  verifyDecoded(items.map(item => ({ ...item, gender: GENDER[item.gender] })));
  expect(logs).toEqual({ network: [], errors: [] });
});

test('360, 390 and 1440 layout, full viewport viewer with switches, and screenshot evidence', async ({ page }, info) => {
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
    await expect(page.locator('#scan-close')).toBeFocused();
    await expect(page.locator('html')).toHaveCSS('overflow', 'hidden');
    await page.locator('#scan-shiny').click();
    await expect(page.locator('#qr-1-0 .shiny-switch')).toHaveAttribute('aria-checked', 'true');
    await expect(page.locator('#scan-variant')).toContainText('Shiny');
    await page.locator('#scan-gender').click();
    await expect(page.locator('#qr-1-0')).toHaveAttribute('data-gender', 'f');
    await expect.poll(() => page.locator('#scan-image').evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)).toBe(true);
    const payload = await page.locator('#qr-1-0').getAttribute('data-qr-fs');
    const png = await page.locator('#scan-image').getAttribute('src');
    verifyDecoded([{ png: png!, payload: payload!, dex: 1, form: 0, gender: 1, shiny: 1 }]);
    await page.screenshot({ path: info.outputPath(`viewer-${width}.png`) });
    await page.locator('#scan-shiny').click();
    await page.locator('#scan-gender').click();
    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();
    await expect(page.locator('#qr-1-0 .card-open')).toBeFocused();
  }
  expect(logs).toEqual({ network: [], errors: [] });
});

test('touch-mobile deep links open a card or point at a blocked row', async ({ browser }, info) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const page = await context.newPage();
  const logs = await open(page, info.project.name, '#qr-150-0');
  expect(await page.evaluate(() => matchMedia('(pointer: coarse)').matches)).toBe(true);
  await expect(page.locator('#scan-title')).toContainText('Mewtwo');
  await expect(page.locator('#scan-variant')).toContainText('Genderless');
  await page.locator('#scan-close').click();
  await page.goto((info.project.name === 'standalone-file' ? file : hosted) + '#qr-807-0');
  await expect(page.locator('#scan-view')).toBeHidden();
  await expect(page.locator('#qr-807-0')).toHaveClass(/is-target/);
  await expect(page.locator('#qr-807-0')).toBeInViewport();
  await page.goto((info.project.name === 'standalone-file' ? file : hosted) + '#qr-25-3');
  await expect(page.locator('#qr-25-1')).toHaveClass(/is-target/);
  await expect(page.locator('#qr-807-0')).not.toHaveClass(/is-target/);
  expect(logs).toEqual({ network: [], errors: [] });
  await context.close();
});
