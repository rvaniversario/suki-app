import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { DICTS, detectLanguage, keysOf, makeT } from '../i18n';

describe('translations', () => {
  it('have the same keys in every language', () => {
    const en = new Set(keysOf(DICTS.en));
    const fil = new Set(keysOf(DICTS.fil));
    expect([...en].filter((k) => !fil.has(k))).toEqual([]);
    expect([...fil].filter((k) => !en.has(k))).toEqual([]);
  });

  it('keep the same placeholders in every language', () => {
    const vars = (s: string) => (s.match(/\{\{\w+\}\}/g) ?? []).sort().join();
    const t = { en: makeT('en'), fil: makeT('fil') };
    for (const k of keysOf(DICTS.en)) expect([k, vars(t.fil(k))]).toEqual([k, vars(t.en(k))]);
  });

  it('marks the Filipino file as unreviewed until a native speaker checks it', () => {
    expect((DICTS.fil as { _meta: { reviewed: boolean } })._meta.reviewed).toBe(false);
  });

  it('defaults to Filipino for fil and tl browsers', () => {
    expect(detectLanguage(['fil-PH'])).toBe('fil');
    expect(detectLanguage(['tl'])).toBe('fil');
    expect(detectLanguage(['en-US', 'fil'])).toBe('en');
  });

  it('every t() key used in the code exists', () => {
    const src = join(__dirname, '..');
    const files: string[] = [];
    const walk = (d: string) =>
      readdirSync(d, { withFileTypes: true }).forEach((e) => {
        const p = join(d, e.name);
        if (e.isDirectory()) walk(p);
        else if (/\.tsx?$/.test(e.name) && !e.name.includes('.test.')) files.push(p);
      });
    walk(src);
    const keys = new Set(keysOf(DICTS.en));
    const missing: string[] = [];
    for (const f of files) {
      for (const m of readFileSync(f, 'utf8').matchAll(/\bt\('([a-zA-Z0-9_.]+)'/g)) {
        if (!keys.has(m[1])) missing.push(`${f}: ${m[1]}`);
      }
    }
    expect(missing).toEqual([]);
  });
});
