import type { PlanOverrides } from './plan';
import type { Category } from './types';

/** Manual plan changes, kept until the next report date (or a region change). */
export const PLAN_KEY = 'suki.plan';

interface Stored extends PlanOverrides {
  region: string;
  asOf: string;
}

export function loadOverrides(region: string, asOf: string): PlanOverrides {
  try {
    const s = JSON.parse(localStorage.getItem(PLAN_KEY) ?? 'null') as Stored | null;
    if (s && s.region === region && s.asOf === asOf) return { picks: s.picks ?? {}, qty: s.qty ?? {} };
  } catch {
    /* ignore unreadable data */
  }
  return { picks: {}, qty: {} };
}

export function saveOverrides(region: string, asOf: string, o: PlanOverrides): void {
  try {
    localStorage.setItem(PLAN_KEY, JSON.stringify({ region, asOf, picks: o.picks ?? {}, qty: o.qty ?? {} }));
  } catch {
    /* storage unavailable */
  }
}

export function withQty(o: PlanOverrides, category: Category, kg: number | undefined): PlanOverrides {
  const qty = { ...(o.qty ?? {}) };
  if (kg === undefined) delete qty[category];
  else qty[category] = kg;
  return { ...o, qty };
}

export function withPick(o: PlanOverrides, category: Category, itemId: string, kg: number): PlanOverrides {
  return { picks: { ...(o.picks ?? {}), [category]: itemId }, qty: { ...(o.qty ?? {}), [category]: kg } };
}
