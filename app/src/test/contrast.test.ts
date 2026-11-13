import { readFileSync } from 'node:fs';
import { join } from 'node:path';

/** SPEC section 9: every text/background pair must reach 4.5:1 in both themes. */
const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8');

function tokens(selector: string): Record<string, string> {
  const start = css.indexOf(`${selector} {`);
  const block = css.slice(start, css.indexOf('}', start));
  return Object.fromEntries([...block.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})/g)].map((m) => [m[1], m[2]]));
}

function luminance(hex: string): number {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((x) => (x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}

const ratio = (a: string, b: string) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

const PAIRS: [string, string][] = [
  ['ink', 'ground'],
  ['ink', 'surface'],
  ['muted', 'ground'],
  ['muted', 'surface'],
  ['primary', 'surface'],
  ['primary', 'ground'],
  ['on-primary', 'primary'],
  ['buy-fg', 'buy-bg'],
  ['ok-fg', 'ok-bg'],
  ['skip-fg', 'skip-bg'],
  ['skip-fg', 'surface'],
  ['ok-fg', 'surface'],
  ['muted', 'segment-bg'],
  ['ink', 'segment-bg'],
  ['ok-fg', 'segment-bg'],
];

describe.each([
  ['light', ':root'],
  ['dark', ":root[data-theme='dark']"],
])('%s theme', (_name, selector) => {
  const light = tokens(':root');
  const t = { ...light, ...tokens(selector) };
  it.each(PAIRS)('%s on %s reaches 4.5:1', (fg, bg) => {
    expect(t[fg], fg).toBeDefined();
    expect(t[bg], bg).toBeDefined();
    expect(ratio(t[fg], t[bg])).toBeGreaterThanOrEqual(4.5);
  });
});
