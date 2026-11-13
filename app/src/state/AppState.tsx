import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useLatest, useRegions, type Async } from '../lib/data';
import { computePlan, type Plan, type PlanOverrides } from '../lib/plan';
import { loadOverrides, saveOverrides } from '../lib/planStore';
import { loadSettings, saveSettings, SETTINGS_KEY, type Settings } from '../lib/settings';
import type { Latest, LatestItem, Region } from '../lib/types';

interface AppState {
  settings: Settings;
  /** Change settings from the UI (bumps updatedAt). */
  update: (patch: Partial<Settings>) => void;
  /** Replace settings from sync (keeps the given updatedAt). */
  replace: (s: Settings) => void;
  regions: Async<Region[]>;
  region: Region | null;
  latest: Async<Latest>;
  tracked: Set<string>;
  plan: Plan | null;
  overrides: PlanOverrides;
  setOverrides: (o: PlanOverrides) => void;
  firstRun: boolean;
}

const Ctx = createContext<AppState | null>(null);

export function featuredIds(items: LatestItem[]): string[] {
  return items.filter((i) => i.featured).map((i) => i.id);
}

export function AppStateProvider({ children, initial }: { children: ReactNode; initial?: Settings }) {
  const firstRun = useRef(typeof localStorage !== 'undefined' && !safeHas(SETTINGS_KEY)).current;
  const [settings, setSettings] = useState<Settings>(() => initial ?? loadSettings());

  const update = useCallback((patch: Partial<Settings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch, updatedAt: new Date().toISOString() };
      saveSettings(next);
      return next;
    });
  }, []);
  const replace = useCallback((s: Settings) => {
    saveSettings(s);
    setSettings(s);
  }, []);

  // Other tabs.
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === SETTINGS_KEY) setSettings(loadSettings());
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  const regions = useRegions();
  const region = useMemo(
    () => regions.data?.find((r) => r.id === settings.region && r.status === 'daily') ?? null,
    [regions.data, settings.region],
  );
  const latest = useLatest(region?.id ?? null);

  const tracked = useMemo(
    () => new Set(settings.trackedIds ?? featuredIds(latest.data?.items ?? [])),
    [settings.trackedIds, latest.data],
  );

  const asOf = latest.data?.asOf ?? '';
  const [overrides, setOverridesState] = useState<PlanOverrides>({});
  useEffect(() => {
    if (region && asOf) setOverridesState(loadOverrides(region.id, asOf));
  }, [region, asOf]);
  const setOverrides = useCallback(
    (o: PlanOverrides) => {
      setOverridesState(o);
      if (region && asOf) saveOverrides(region.id, asOf, o);
    },
    [region, asOf],
  );

  const plan = useMemo(
    () => (latest.data ? computePlan(latest.data.items, tracked, settings.usualKg, settings.budget, overrides) : null),
    [latest.data, tracked, settings.usualKg, settings.budget, overrides],
  );

  const value: AppState = {
    settings,
    update,
    replace,
    regions,
    region,
    latest,
    tracked,
    plan,
    overrides,
    setOverrides,
    firstRun,
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

function safeHas(key: string): boolean {
  try {
    return localStorage.getItem(key) !== null;
  } catch {
    return false;
  }
}

export function useApp(): AppState {
  const v = useContext(Ctx);
  if (!v) throw new Error('useApp outside AppStateProvider');
  return v;
}
