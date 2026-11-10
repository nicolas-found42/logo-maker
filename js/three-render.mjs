/** Headless three.js render: load a served three-page.html, wait for frames, screenshot.
 * Reads one JSON object on stdin: {url, out_png, width, height, wait_ms}.
 * Prints one JSON object as the last stdout line.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { chromium } from 'playwright-core';

const raw = readFileSync(0, 'utf8');
const { url, out_png, width, height, wait_ms } = JSON.parse(raw);
const started = Date.now();

const browser = await chromium.launch({
  channel: 'chrome',
  headless: true,
  args: ['--enable-unsafe-swiftshader', '--no-sandbox', '--disable-dev-shm-usage'],
});
let page;
try {
  const context = await browser.newContext({ viewport: { width, height } });
  page = await context.newPage();
  const errors = [];
  page.on('pageerror', (err) => errors.push(String(err)));
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(msg.text().slice(0, 500));
  });
  await page.goto(url, { waitUntil: 'load', timeout: wait_ms ?? 120000 });
  await page.waitForFunction(
    () => window.__renderDone === true || window.__renderError !== undefined,
    { timeout: wait_ms ?? 120000 },
  );
  const renderError = await page.evaluate(() => window.__renderError);
  if (renderError) throw new Error(`page render failed: ${renderError}`);
  await page.screenshot({ path: out_png, omitBackground: true });
  if (errors.length) process.stderr.write(`page console errors:\n${errors.join('\n')}\n`);
} finally {
  await browser.close();
}
writeFileSync(1, JSON.stringify({ ok: true, out_png, ms: Date.now() - started }) + '\n');
