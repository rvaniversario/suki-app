import { useEffect, useState } from 'react';
import type { Theme } from './settings';

const THEME_COLOR = { light: '#F4F6F3', dark: '#0F1614' } as const;

export function resolveTheme(theme: Theme, prefersDark: boolean): 'light' | 'dark' {
  if (theme === 'system') return prefersDark ? 'dark' : 'light';
  return theme;
}

function prefersDarkNow(): boolean {
  return typeof window !== 'undefined' && !!window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
}

/** Applies the theme to <html data-theme> and <meta name="theme-color">. */
export function useApplyTheme(theme: Theme): 'light' | 'dark' {
  const [prefersDark, setPrefersDark] = useState(prefersDarkNow);
  useEffect(() => {
    if (!window.matchMedia) return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const on = () => setPrefersDark(mq.matches);
    mq.addEventListener?.('change', on);
    return () => mq.removeEventListener?.('change', on);
  }, []);
  const resolved = resolveTheme(theme, prefersDark);
  useEffect(() => {
    document.documentElement.dataset.theme = resolved;
    let meta = document.querySelector('meta[name="theme-color"]');
    if (!meta) {
      meta = document.createElement('meta');
      meta.setAttribute('name', 'theme-color');
      document.head.appendChild(meta);
    }
    meta.setAttribute('content', THEME_COLOR[resolved]);
  }, [resolved]);
  return resolved;
}
