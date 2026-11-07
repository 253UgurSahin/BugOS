// Zet SVG-bestanden om naar PNG (doorzichtige achtergrond), met Chromium.
// Gebruik: node tools/brand/png.js <svg> <png> <breedte> [<svg> <png> <breedte> ...]
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const args = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage();
  for (let i = 0; i < args.length; i += 3) {
    const [bron, doel, breedte] = [args[i], args[i + 1], Number(args[i + 2])];
    const svg = fs.readFileSync(bron, 'utf8');
    const vb = svg.match(/viewBox="([\d.\s-]+)"/)[1].split(/\s+/).map(Number);
    const hoogte = Math.round(breedte * vb[3] / vb[2]);
    await page.setViewportSize({ width: breedte, height: hoogte });
    const data = 'data:image/svg+xml;base64,' + Buffer.from(svg).toString('base64');
    await page.setContent(`<html><body style="margin:0;background:transparent"><img src="${data}" style="width:${breedte}px;height:${hoogte}px;display:block"></body></html>`);
    await page.waitForTimeout(50);
    fs.mkdirSync(path.dirname(doel), { recursive: true });
    await page.screenshot({ path: doel, omitBackground: true, clip: { x: 0, y: 0, width: breedte, height: hoogte } });
    console.log(`${doel} (${breedte}x${hoogte})`);
  }
  await browser.close();
})();
