import type { LatestItem } from '../lib/types';

export function mk(id: string, category: LatestItem['category'], price: number, pct: number | null, extra: Partial<LatestItem> = {}): LatestItem {
  return {
    id,
    name: id,
    category,
    unit: 'kg',
    price,
    low: null,
    high: null,
    baseline: pct === null ? null : Math.round((price / (1 + pct / 100)) * 100) / 100,
    pctVsBaseline: pct,
    status: pct === null ? null : pct <= -4 ? 'buy' : pct >= 5 ? 'skip' : 'ok',
    daysOfHistory: 90,
    featured: true,
    ...extra,
  };
}

