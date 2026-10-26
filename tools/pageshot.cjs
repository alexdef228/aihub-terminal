// Снимок странички docs/index.html целиком — посмотреть перед публикацией.
//   node tools/pageshot.cjs <куда.png>
const { chromium } = require('playwright');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
(async () => {
  const b = await chromium.launch({ channel: 'msedge' });
  const p = await b.newPage({ viewport: { width: 1280, height: 900 } });
  await p.goto(pathToFileURL(path.resolve(__dirname, '../docs/index.html')).href);
  await p.screenshot({ path: process.argv[2], fullPage: true });
  await b.close();
})();
