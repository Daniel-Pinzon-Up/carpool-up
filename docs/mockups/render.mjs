// Exporta cada pantalla de los mockups como PNG individual y arma un PDF con una pantalla por
// pagina. Usa el Playwright del frontend:
//
//   cd frontend && node ../docs/mockups/render.mjs          movil (mockups.html -> png/)
//   cd frontend && node ../docs/mockups/render.mjs pc       escritorio (mockups-pc.html -> png-pc/)
import { createRequire } from 'node:module';
import { mkdirSync, readFileSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(join(here, '../../frontend/package.json'));
const { chromium } = require('@playwright/test');

const slug = (text) =>
  text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');

const pc = process.argv[2] === 'pc';
const source = pc ? 'mockups-pc.html' : 'mockups.html';
const out = join(here, pc ? 'png-pc' : 'png');
const pdfName = pc ? 'Carpool-UP-mockups-pc.pdf' : 'Carpool-UP-mockups.pdf';
rmSync(out, { recursive: true, force: true });
mkdirSync(out);

const browser = await chromium.launch({ channel: 'chrome' });
const page = await browser.newPage({ deviceScaleFactor: 2, viewport: { width: 1700, height: 1000 } });
await page.goto(pathToFileURL(join(here, source)).href);
await page.waitForSelector('body[data-ready="1"]');

const frames = await page.$$('.frame');
const files = [];
for (const frame of frames) {
  const n = await frame.getAttribute('data-n');
  const title = await frame.getAttribute('data-t');
  const file = `${n}-${slug(title)}.png`;
  await frame.screenshot({ path: join(out, file) });
  files.push({ file, desktop: (await frame.getAttribute('class')).includes(' d') });
}

// PDF: una pantalla por pagina, A4 horizontal, centrada.
const pdf = await browser.newPage();
const pages = files
  .map(({ file, desktop }) => {
    const data = readFileSync(join(out, file)).toString('base64');
    return `<div class="p"><img src="data:image/png;base64,${data}" class="${desktop ? 'd' : 'm'}"></div>`;
  })
  .join('');
await pdf.setContent(`<!doctype html><style>
  @page { size: A4 landscape; margin: 0 }
  body { margin: 0 }
  .p { width: 297mm; height: 210mm; display: flex; align-items: center; justify-content: center; page-break-after: always; }
  img.d { width: 277mm } img.m { height: 196mm }
</style>${pages}`);
await pdf.waitForLoadState('load');
await pdf.pdf({ path: join(here, pdfName), preferCSSPageSize: true, printBackground: true });

await browser.close();
console.log(`${files.length} pantallas exportadas en ${out} y ${pdfName}`);
