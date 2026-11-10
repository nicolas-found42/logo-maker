const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(path.resolve('js/node_modules/playwright-core'));
(async () => {
 const browser = await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 const page = await browser.newPage({viewport:{width:1280,height:700},deviceScaleFactor:1});
 for (const kind of ['before','after']) {
  const output=fs.readFileSync(`logos/issue-2-pr-evidence/${kind}.txt`,'utf8');
  const escaped=output.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
  await page.setContent(`<html><head><meta charset="utf-8"><style>body{margin:0;background:#f1f5f9;color:#0f172a;font:20px system-ui;padding:40px}h1{font-size:30px;margin:0 0 12px}p{color:#475569;margin:0 0 26px}pre{background:white;border:1px solid #cbd5e1;border-radius:12px;padding:28px;font:18px/1.65 ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere}</style></head><body><h1>${kind==='before'?'Before':'After'} — recorded Fold decision</h1><p>Real command output · same inputs · headless browser capture</p><pre>${escaped}</pre></body></html>`);
  await page.screenshot({path:`logos/issue-2-pr-evidence/${kind}.png`,fullPage:true});
 }
 await browser.close();
})();
