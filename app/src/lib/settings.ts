import type { Category } from './types';

export const SETTINGS_KEY = 'suki.settings';
export const SETTINGS_VERSION = 1;

export type Theme = 'system' | 'light' | 'dark';
export type Language = 'en' | 'fil';

export interface Settings {
  v: number;
  region: string | null;
  usualKg: Record<Category, number>;
  /** Weekly budget in pesos; null means no limit. */
  budget: number | null;
  /** null means "the catalog's featured items". */
  trackedIds: string[] | null;
  theme: Theme;
  /** null means "follow the browser". */
  language: Language | null;
  alerts: boolean;
  updatedAt: string | null;
}

export const DEFAULT_USUAL_KG: Record<Category, number> = { fish: 1, pork: 1, chicken: 1, beef: 0.5 };

export function defaultSettings(): Settings {
  return {
    v: SETTINGS_VERSION,
    region: null,
    usualKg: { ...DEFAULT_USUAL_KG },
    budget: null,
    trackedIds: null,
    theme: 'system',
    language: null,
    alerts: false,
    updatedAt: null,
  };
}

const num = (x: unknown, fallback: number) => (typeof x === 'number' && Number.isFinite(x) && x >= 0 ? x : fallback);

/** Coerce anything (old versions, partial objects, junk) into valid settings. */
export function normalize(raw: unknown): Settings {
  const d = defaultSettings();
  if (!raw || typeof raw !== 'object') return d;
  const r = raw as Record<string, unknown>;
  const kg = (r.usualKg ?? {}) as Record<string, unknown>;
  return {
    v: SETTINGS_VERSION,
    region: typeof r.region === 'string' ? r.region : null,
    usualKg: {
      fish: num(kg.fish, d.usualKg.fish),
      pork: num(kg.pork, d.usualKg.pork),
      chicken: num(kg.chicken, d.usualKg.chicken),
      beef: num(kg.beef, d.usualKg.beef),
    },
    budget: typeof r.budget === 'number' && Number.isFinite(r.budget) && r.budget >= 0 ? r.budget : null,
    trackedIds: Array.isArray(r.trackedIds) ? r.trackedIds.filter((x): x is string => typeof x === 'string') : null,
    theme: r.theme === 'light' || r.theme === 'dark' ? r.theme : 'system',
    language: r.language === 'en' || r.language === 'fil' ? r.language : null,
    alerts: r.alerts === true,
    updatedAt: typeof r.updatedAt === 'string' ? r.updatedAt : null,
  };
}

export function loadSettings(): Settings {
  try {
    return normalize(JSON.parse(localStorage.getItem(SETTINGS_KEY) ?? 'null'));
  } catch {
    return defaultSettings();
  }
}

export function saveSettings(s: Settings): void {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
  } catch {
    /* storage full or blocked: settings still apply for this session */
  }
}

/** Fields that sync between devices (alerts and region-specific push state are per device but harmless to sync). */
const SHOPPING_FIELDS = ['usualKg', 'budget', 'trackedIds', 'theme', 'language', 'alerts'] as const;

/** True when nothing but the region has been changed from the defaults. */
export function isDefault(s: Settings): boolean {
  const d = defaultSettings();
  return SHOPPING_FIELDS.every((k) => JSON.stringify(s[k]) === JSON.stringify(d[k]));
}

export type MergeResult =
  | { settings: Settings; kept: 'remote'; upload: false }
  | { settings: Settings; kept: 'local'; upload: true }
  | { settings: Settings; kept: null; upload: boolean };

/**
 * Decide what to keep when a user signs in (SPEC section 17):
 * - no remote row: keep local and upload it;
 * - local still defaults: take remote (keeping this device's region if remote has none);
 * - both changed: newer updatedAt wins, and the caller tells the user which was kept.
 */
export function mergeOnSignIn(local: Settings, remote: Settings | null): MergeResult {
  if (!remote) return { settings: local, kept: null, upload: true };
  if (isDefault(local)) {
    return { settings: { ...remote, region: remote.region ?? local.region }, kept: null, upload: false };
  }
  if (isDefault(remote)) return { settings: local, kept: null, upload: true };
  const l = Date.parse(local.updatedAt ?? '') || 0;
  const r = Date.parse(remote.updatedAt ?? '') || 0;
  if (r > l) return { settings: remote, kept: 'remote', upload: false };
  return { settings: local, kept: 'local', upload: true };
}
