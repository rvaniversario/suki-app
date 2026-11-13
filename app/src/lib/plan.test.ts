import { advice, computePlan, multiplier, pickItem, roundToStep, suggestedKg } from './plan';
import { mk } from '../test/fixtures';

const USUAL = { fish: 1, pork: 1, chicken: 1, beef: 0.5 };

describe('multiplier', () => {
  it('follows the spec examples', () => {
    expect(multiplier(-8)).toBe(1.8);
    expect(multiplier(5)).toBe(0.5);
    expect(multiplier(0)).toBe(1);
  });
  it('clamps to 0.5..2', () => {
    expect(multiplier(-30)).toBe(2);
    expect(multiplier(9.9)).toBe(0.5);
  });
  it('skips at +10 and above', () => {
    expect(multiplier(10)).toBe(0);
    expect(multiplier(25)).toBe(0);
  });
  it('is 1 without a baseline', () => {
    expect(multiplier(null)).toBe(1);
  });
});

describe('advice labels', () => {
  it.each([
    [1.8, 'more'],
    [1.1, 'usual'],
    [1, 'usual'],
    [0.9, 'usual'],
    [0.5, 'less'],
    [0, 'skip'],
  ] as const)('m=%s -> %s', (m, label) => expect(advice(m)).toBe(label));
});

describe('rounding', () => {
  it('rounds to the nearest 0.25 kg', () => {
    expect(roundToStep(1.8)).toBe(1.75);
    expect(roundToStep(1.88)).toBe(2);
    expect(roundToStep(0.62)).toBe(0.5);
    expect(roundToStep(0.63)).toBe(0.75);
    expect(suggestedKg(1, -8)).toBe(1.75);
    expect(suggestedKg(0.5, -8)).toBe(1);
  });
});

describe('pickItem', () => {
  const items = [mk('a', 'fish', 100, -2), mk('b', 'fish', 200, -9), mk('c', 'fish', 50, null), mk('d', 'fish', 80, -20, { price: null })];
  it('picks the tracked item with the lowest score', () => {
    expect(pickItem(items, 'fish', new Set(['a', 'b', 'c', 'd']))?.id).toBe('b');
  });
  it('only considers tracked items', () => {
    expect(pickItem(items, 'fish', new Set(['a', 'c']))?.id).toBe('a');
  });
  it('falls back to an unscored item when nothing has a baseline', () => {
    expect(pickItem(items, 'fish', new Set(['c']))?.id).toBe('c');
  });
  it('honours a manual pick', () => {
    expect(pickItem(items, 'fish', new Set(['a', 'b']), 'a')?.id).toBe('a');
  });
});

describe('computePlan', () => {
  const items = [
    mk('tilapia', 'fish', 150.34, -8),
    mk('kasim', 'pork', 320.84, -4),
    mk('chicken', 'chicken', 183.58, 2),
    mk('rump', 'beef', 450.26, 12),
  ];
  const all = new Set(items.map((i) => i.id));

  it('builds one row per category with suggested kilos and totals', () => {
    const plan = computePlan(items, all, USUAL, null);
    expect(plan.rows.map((r) => [r.category, r.kg, r.advice])).toEqual([
      ['fish', 1.75, 'more'],
      ['pork', 1.5, 'more'],
      ['chicken', 0.75, 'less'],
      ['beef', 0, 'skip'],
    ]);
    const expected = 1.75 * 150.34 + 1.5 * 320.84 + 0.75 * 183.58;
    expect(plan.total).toBeCloseTo(expected, 2);
    expect(plan.diff).toBeLessThan(0);
    expect(plan.trimmed).toBe(false);
    expect(plan.overBudget).toBeNull();
  });

  it('leaves out categories with no tracked items', () => {
    const plan = computePlan(items, new Set(['tilapia']), USUAL, null);
    expect(plan.rows.map((r) => r.category)).toEqual(['fish']);
  });

  it('applies manual quantities and never trims them', () => {
    const plan = computePlan(items, all, USUAL, 100, { qty: { fish: 3 } });
    const fish = plan.rows.find((r) => r.category === 'fish')!;
    expect(fish.kg).toBe(3);
    expect(fish.manual).toBe(true);
    expect(plan.overBudget).toBeCloseTo(plan.total - 100, 2);
  });

  it('trims to budget from the priciest-against-usual item first, in 0.25 kg steps', () => {
    const plan = computePlan(items, all, USUAL, 600);
    // chicken (+2) is the highest score with kg > 0, so it goes first, then pork (-4), then fish (-8)
    const kgs = Object.fromEntries(plan.rows.map((r) => [r.category, r.kg]));
    expect(plan.trimmed).toBe(true);
    expect(plan.total).toBeLessThanOrEqual(600);
    expect(kgs.chicken).toBe(0);
    expect(kgs.fish).toBe(1.75);
    expect(kgs.pork).toBe(1); // 1.5 -> 1.25 -> 1: total 263.10 + 320.84 = 583.94
    expect(plan.overBudget).toBeNull();
  });

  it('stops at zero when the budget cannot be met', () => {
    const plan = computePlan(items, all, USUAL, 0);
    expect(plan.rows.every((r) => r.kg === 0)).toBe(true);
    expect(plan.total).toBe(0);
  });

  it('prices at baseline for the comparison line', () => {
    const plan = computePlan([mk('tilapia', 'fish', 90, -10)], new Set(['tilapia']), USUAL, null);
    // -10% -> m = 2 -> 2 kg; baseline 100 -> 200 at usual prices; 180 now
    expect(plan.rows[0].kg).toBe(2);
    expect(plan.total).toBe(180);
    expect(plan.totalAtBaseline).toBe(200);
    expect(plan.diff).toBe(-20);
  });
});
