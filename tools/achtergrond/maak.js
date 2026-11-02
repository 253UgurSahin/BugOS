// Maak de BugOS-achtergrond "Stip" (licht en donker) op volle grootte.
// Gebruik: node tools/achtergrond/maak.js <uitvoermap>
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
(async () => {
  const uit = process.argv[2] || 'achtergronden';
  const html = 'file://' + path.resolve(__dirname, 'stip.html');
  const maten = [[3840, 2160], [3840, 2400]];
  const browser = await chromium.launch();
  for (const thema of ['licht', 'donker']) {
    for (const [w, h] of maten) {
      const page = await browser.newPage({ viewport: { width: w, height: h } });
      await page.goto(`${html}?w=${w}&h=${h}&t=${thema}&v=a`);
      await page.waitForFunction(() => document.title === 'klaar', null, { timeout: 300000 });
      const doel = path.join(uit, thema, `${w}x${h}.png`);
      fs.mkdirSync(path.dirname(doel), { recursive: true });
      await (await page.$('canvas')).screenshot({ path: doel });
      console.log(doel);
      await page.close();
    }
  }
  await browser.close();
})();
