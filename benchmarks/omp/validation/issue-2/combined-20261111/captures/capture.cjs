const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(path.resolve('js/node_modules/playwright-core'));
(async()=>{
 const root='logos/issue-2-completion/pr-evidence';
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 const page=await browser.newPage({viewport:{width:760,height:700},deviceScaleFactor:1});
 for(const [kind,revision] of [['before','3ca26d0 (main)'],['after','3eeeeae (combined source)']]){
  const escaped=fs.readFileSync(`${root}/${kind}.txt`,'utf8').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
  await page.setContent(`<html><meta charset="utf-8"><style>body{margin:0;padding:24px;background:#edf2f7;color:#16233b;font:19px system-ui}h1{font-size:27px;margin:0 0 8px}p{margin:0 0 20px;color:#3c4a60}pre{margin:0;background:white;border:1px solid #bac7d6;border-radius:8px;padding:22px;font:23px/1.5 monospace;white-space:pre-wrap}</style><h1>${kind==='before'?'Before':'After'}: provider accounting</h1><p>${revision}<br>Actual synthetic HTTP output · no live charge<br>Rendered command output · same script and inputs</p><pre>${escaped}</pre></html>`);
  await page.screenshot({path:`${root}/${kind}.png`,fullPage:true});
 }
 await browser.close();
})();
