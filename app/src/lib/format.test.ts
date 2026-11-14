import { daysSince, kg, peso, pesoWhole } from './format';
import { rankItems } from './ranking';
import { mk } from '../test/fixtures';

describe('format', () => {
  it('prices per kilo with two decimals, totals whole', () => {
    expect(peso(150.3)).toBe('₱150.30');
    expect(peso(1234.5)).toBe('₱1,234.50');
    expect(peso(null)).toBe('—');
    expect(pesoWhole(712.6)).toBe('₱713');
    expect(peso(150.3, 'fil')).toBe('₱150.30');
  });
  it('quantities with fractions', () => {
    expect(kg(2)).toBe('2 kg');
    expect(kg(0.5)).toBe('½ kg');
    expect(kg(0.25)).toBe('¼ kg');
    expect(kg(1.75)).toBe('1¾ kg');
    expect(kg(0)).toBe('0');
  });
  it('days since a report in Manila time', () => {
    expect(daysSince('2026-11-10', new Date('2026-11-13T01:00:00Z'))).toBe(3);
    expect(daysSince('2026-11-10', new Date('2026-11-13T17:00:00Z'))).toBe(4); // already the 14th in Manila
  });
});

describe('ranking', () => {
  const items = [
    mk('beef', 'beef', 450, 12),
    mk('chicken', 'chicken', 180, 2),
    mk('fish', 'fish', 150, -8),
    mk('pork', 'pork', 320, -4),
    mk('nohist', 'fish', 100, null),
    mk('noprice', 'fish', 100, -20, { price: null }),
    mk('egg', 'eggs', 9, -10, { unit: 'pc' }),
  ];
  const all = new Set(items.map((i) => i.id));

  it('ranks by score, most below usual first, not by price', () => {
    expect(rankItems(items, all).ranked.map((i) => i.id)).toEqual(['egg', 'fish', 'pork', 'chicken', 'beef']);
  });
  it('hides items with no price today, ranks any unit by score, puts unscored items apart', () => {
    const { ranked, unranked } = rankItems(items, all);
    expect(ranked.find((i) => i.id === 'noprice')).toBeUndefined();
    expect(ranked.find((i) => i.id === 'egg')?.unit).toBe('pc');
    expect(unranked.map((i) => i.id)).toEqual(['nohist']);
  });
  it('filters by category and tracked goods', () => {
    expect(rankItems(items, all, 'fish').ranked.map((i) => i.id)).toEqual(['fish']);
    expect(rankItems(items, new Set(['beef'])).ranked.map((i) => i.id)).toEqual(['beef']);
  });
});
