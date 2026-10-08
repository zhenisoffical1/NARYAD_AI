const { chromium } = require('@playwright/test');
const path = require('path');
(async () => {
  const b = await chromium.launch({ channel: 'chrome' });
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  await p.goto('file:///' + path.resolve(__dirname, 'slides.html').replace(/\\/g, '/'));
  await p.waitForLoadState('networkidle');
  await p.evaluate(() => document.fonts.ready);
  await p.pdf({ path: path.resolve(__dirname, '..', 'ZHETEL_NaryadAI.pdf'), width: '1920px', height: '1080px', printBackground: true });
  await p.screenshot({ path: path.resolve(__dirname, 'preview.png'), fullPage: true });
  await b.close();
})();
