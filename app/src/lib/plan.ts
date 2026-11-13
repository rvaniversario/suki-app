/**
 * Weekly plan (SPEC section 6). All tunable numbers are named constants here,
 * and every rule is covered by plan.test.ts.
 */
import { CATEGORIES, type Category, type LatestItem } from './types';

export const SKIP_SCORE = 10; // score >= this -> skip this week
export const MULTIPLIER_SLOPE = 0.1; // m = 1 - slope * score
export const MIN_MULTIPLIER = 0.5;
export const MAX_MULTIPLIER = 2;
export const STEP_KG = 0.25;
export const MORE_ABOVE = 1.1;
export const LESS_BELOW = 0.9;

export type Advice = 'more' | 'usual' | 'less' | 'skip';

export type UsualKg = Record<Category, number>;

export interface PlanOverrides {
  /** Item chosen by hand for a category (from the Item screen). */
  picks?: Partial<Record<Category, string>>;
  /** Quantity set by hand with the stepper. */
  qty?: Partial<Record<Category, number>>;
}

export interface PlanRow {
  category: Category;
  item: LatestItem;
  score: number | null;
  multiplier: number;
  suggestedKg: number;
  kg: number;
  advice: Advice;
  manual: boolean;
  cost: number;
  costAtBaseline: number;
}

export interface Plan {
  rows: PlanRow[];
  total: number;
  totalAtBaseline: number;
  /** total - totalAtBaseline; negative means cheaper than usual. */
  diff: number;
  /** Suggested quantities were cut to fit the budget. */
  trimmed: boolean;
  /** Amount over budget after trimming (manual changes are never trimmed). */
  overBudget: number | null;
}

export const clamp = (x: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, x));

export const roundToStep = (kg: number, step = STEP_KG) => {
  const r = Math.round(kg / step) * step;
  return Math.max(0, Math.round(r * 100) / 100);
};

export function multiplier(score: number | null): number {
  if (score === null) return 1;
  if (score >= SKIP_SCORE) return 0;
  return Math.round(clamp(1 - MULTIPLIER_SLOPE * score, MIN_MULTIPLIER, MAX_MULTIPLIER) * 1000) / 1000;
}

export function advice(m: number): Advice {
  if (m === 0) return 'skip';
  if (m > MORE_ABOVE) return 'more';
  if (m < LESS_BELOW) return 'less';
  return 'usual';
}

export function suggestedKg(usual: number, score: number | null): number {
  return roundToStep(usual * multiplier(score));
}

const isPlannable = (i: LatestItem) => i.price !== null && i.unit === 'kg';

/** The tracked item with the lowest score in a category (items without a baseline only as a last resort). */
export function pickItem(items: LatestItem[], category: Category, tracked: Set<string>, pick?: string): LatestItem | null {
  const candidates = items.filter((i) => i.category === category && tracked.has(i.id) && isPlannable(i));
  if (pick) {
    const chosen = candidates.find((i) => i.id === pick);
    if (chosen) return chosen;
  }
  const scored = candidates.filter((i) => i.pctVsBaseline !== null);
  if (scored.length) {
    return scored.reduce((best, i) => ((i.pctVsBaseline as number) < (best.pctVsBaseline as number) ? i : best));
  }
  return candidates[0] ?? null;
}

const money = (x: number) => Math.round(x * 100) / 100;

function costs(row: Pick<PlanRow, 'kg' | 'item'>) {
  const price = row.item.price ?? 0;
  return { cost: money(row.kg * price), costAtBaseline: money(row.kg * (row.item.baseline ?? price)) };
}

export function computePlan(
  items: LatestItem[],
  tracked: Set<string>,
  usualKg: UsualKg,
  budget: number | null,
  overrides: PlanOverrides = {},
): Plan {
  const rows: PlanRow[] = [];
  for (const category of CATEGORIES) {
    const item = pickItem(items, category, tracked, overrides.picks?.[category]);
    if (!item) continue;
    const score = item.pctVsBaseline;
    const m = multiplier(score);
    const suggested = roundToStep(usualKg[category] * m);
    const manualQty = overrides.qty?.[category];
    const manual = manualQty !== undefined;
    const kg = manual ? roundToStep(manualQty) : suggested;
    rows.push({ category, item, score, multiplier: m, suggestedKg: suggested, kg, advice: advice(m), manual, cost: 0, costAtBaseline: 0 });
  }

  const sum = () => money(rows.reduce((s, r) => s + r.kg * (r.item.price ?? 0), 0));
  let trimmed = false;
  if (budget !== null && budget >= 0) {
    // Cut suggested (not manual) quantities in 0.25 kg steps, always from the item
    // that is priciest against its usual price, until the plan fits.
    while (sum() > budget) {
      const candidates = rows.filter((r) => !r.manual && r.kg > 0);
      if (!candidates.length) break;
      const worst = candidates.reduce((a, b) => ((b.score ?? 0) > (a.score ?? 0) ? b : a));
      worst.kg = roundToStep(worst.kg - STEP_KG);
      trimmed = true;
    }
  }

  for (const r of rows) Object.assign(r, costs(r));
  const total = sum();
  const totalAtBaseline = money(rows.reduce((s, r) => s + r.costAtBaseline, 0));
  const overBudget = budget !== null && total > budget ? money(total - budget) : null;
  return { rows, total, totalAtBaseline, diff: money(total - totalAtBaseline), trimmed, overBudget };
}
