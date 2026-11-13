import type { Language } from './settings';

const LOCALE: Record<Language, string> = { en: 'en-PH', fil: 'fil-PH' };

/** Per-kilo prices: peso sign and two decimals in both languages. */
export function peso(x: number | null | undefined, lang: Language = 'en'): string {
  if (x === null || x === undefined) return '—';
  return '₱' + new Intl.NumberFormat(LOCALE[lang], { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(x);
}

/** Totals: whole pesos. */
export function pesoWhole(x: number, lang: Language = 'en'): string {
  return '₱' + new Intl.NumberFormat(LOCALE[lang], { maximumFractionDigits: 0 }).format(Math.round(x));
}

const FRACTIONS: Record<number, string> = { 0.25: '¼', 0.5: '½', 0.75: '¾' };

/** 2 -> "2 kg", 0.5 -> "½ kg", 1.25 -> "1¼ kg", 0 -> "0". */
export function kg(x: number): string {
  if (x <= 0) return '0';
  const whole = Math.floor(x + 1e-9);
  const frac = Math.round((x - whole) * 100) / 100;
  const f = FRACTIONS[frac];
  if (frac && !f) return `${x.toFixed(2).replace(/0+$/, '')} kg`;
  return `${whole ? whole : ''}${f ?? ''} kg`;
}

export function dateLong(iso: string, lang: Language = 'en'): string {
  return new Intl.DateTimeFormat(LOCALE[lang], { month: 'long', day: 'numeric', year: 'numeric', timeZone: 'UTC' }).format(
    new Date(`${iso}T00:00:00Z`),
  );
}

export function dateShort(iso: string, lang: Language = 'en'): string {
  return new Intl.DateTimeFormat(LOCALE[lang], { month: 'short', day: 'numeric', timeZone: 'UTC' }).format(new Date(`${iso}T00:00:00Z`));
}

/** Whole days between an ISO date and today (in Manila). */
export function daysSince(iso: string, now = new Date()): number {
  const manila = new Date(now.getTime() + 8 * 3600 * 1000).toISOString().slice(0, 10);
  return Math.round((Date.parse(`${manila}T00:00:00Z`) - Date.parse(`${iso}T00:00:00Z`)) / 86400000);
}

export const pctAbs = (x: number) => `${Math.abs(Math.round(x))}`;
