import { createContext, useContext, useMemo, type ReactNode } from 'react';
import en from './locales/en.json';
import fil from './locales/fil.json';
import type { Language } from './lib/settings';

type Dict = Record<string, unknown>;
export const DICTS: Record<Language, Dict> = { en, fil };

export function detectLanguage(langs: readonly string[] = typeof navigator !== 'undefined' ? navigator.languages ?? [navigator.language] : []): Language {
  const first = (langs[0] ?? '').toLowerCase();
  return first.startsWith('fil') || first.startsWith('tl') ? 'fil' : 'en';
}

function lookup(dict: Dict, key: string): string | undefined {
  let cur: unknown = dict;
  for (const part of key.split('.')) {
    if (!cur || typeof cur !== 'object') return undefined;
    cur = (cur as Dict)[part];
  }
  return typeof cur === 'string' ? cur : undefined;
}

export type TFunction = (key: string, vars?: Record<string, string | number>) => string;

export function makeT(lang: Language): TFunction {
  return (key, vars) => {
    let s = lookup(DICTS[lang], key) ?? lookup(DICTS.en, key) ?? key;
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.split(`{{${k}}}`).join(String(v));
    return s;
  };
}

interface I18n {
  lang: Language;
  t: TFunction;
}

const Ctx = createContext<I18n>({ lang: 'en', t: makeT('en') });

export function I18nProvider({ lang, children }: { lang: Language; children: ReactNode }) {
  const value = useMemo(() => ({ lang, t: makeT(lang) }), [lang]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useI18n = () => useContext(Ctx);

/** All dotted keys of a dictionary (for the parity test). */
export function keysOf(dict: Dict, prefix = ''): string[] {
  return Object.entries(dict).flatMap(([k, v]) => {
    if (k === '_meta') return [];
    const key = prefix ? `${prefix}.${k}` : k;
    return v && typeof v === 'object' ? keysOf(v as Dict, key) : [key];
  });
}
