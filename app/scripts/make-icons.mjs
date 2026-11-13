// Renders the PWA icon PNGs from inline SVG with Playwright's Chromium.
// Run once after changing the icon: `node scripts/make-icons.mjs`.
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const out = join(dirname(fileURLToPath(import.meta.url)), '..', 'public', 'icons');
mkdirSync(out, { recursive: true });

// The app's "Today" mark: three ranked bars. Maskable keeps everything inside the 80% safe zone.
const mark = (size, { radius, inset, bg = '#0B5D51', fg = '#FFFFFF' }) => {
  const s = size;
  const w = s * (1 - 2 * inset);
  const x0 = s * inset + w * 0.2;
  const stroke = w * 0.085;
  const line = (y, len) =>
    `<path d="M${x0} ${s * inset + w * y}h${w * len}" stroke="${fg}" stroke-width="${stroke}" stroke-linecap="round"/>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${s}" height="${s}" viewBox="0 0 ${s} ${s}">
    <rect width="${s}" height="${s}" rx="${s * radius}" fill="${bg}"/>
    ${line(0.33, 0.6)}${line(0.5, 0.42)}${line(0.67, 0.24)}</svg>`;
};

const icons = [
  ['icon-192.png', 192, { radius: 0.22, inset: 0 }],
  ['icon-512.png', 512, { radius: 0.22, inset: 0 }],
  ['maskable-512.png', 512, { radius: 0, inset: 0.12 }],
  ['apple-touch-icon.png', 180, { radius: 0, inset: 0 }],
  ['badge-72.png', 72, { radius: 0, inset: 0, bg: 'transparent' }],
];

const browser = await chromium.launch();
const page = await browser.newPage();
for (const [name, size, opts] of icons) {
  await page.setViewportSize({ width: size, height: size });
  await page.setContent(`<html><body style="margin:0;background:transparent">${mark(size, opts)}</body></html>`);
  await page.locator('svg').screenshot({ path: join(out, name), omitBackground: true });
  console.log('wrote', name);
}
await browser.close();
