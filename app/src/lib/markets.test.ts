import { describe, expect, it } from 'vitest';
import { marketPrice, pctVsRegion, sortMarkets } from './markets';
import type { MarketIndex, MarketPrices } from './types';

describe('markets', () => {
  it('lists every market by name, old data included', () => {
    const index: MarketIndex = {
      region: 'davao',
      source: 'DA Bantay Presyo',
      markets: [
        { code: '1', name: 'Old Market', lat: null, lng: null, latest: '2026-09-01', items: 10 },
        { code: '2', name: 'Bankerohan', lat: null, lng: null, latest: '2026-11-12', items: 60 },
        { code: '3', name: 'Agdao', lat: null, lng: null, latest: null, items: 0 },
      ],
    };
    expect(sortMarkets(index).map((m) => m.code)).toEqual(['3', '2', '1']);
  });

  it('returns the newest price however old', () => {
    const prices: MarketPrices = {
      code: '2',
      name: 'Bankerohan',
      region: 'davao',
      latest: '2026-11-12',
      items: { 'fish.tilapia': { d: '2026-11-12', p: 160 }, 'beef.rump': { d: '2026-09-01', p: 420 } },
    };
    expect(marketPrice(prices, 'fish.tilapia')?.p).toBe(160);
    expect(marketPrice(prices, 'beef.rump')).toEqual({ d: '2026-09-01', p: 420 });
    expect(marketPrice(prices, 'pork.kasim')).toBeNull();
  });

  it('compares with the regional price', () => {
    expect(pctVsRegion(170, 160)).toBe(6);
    expect(pctVsRegion(150, 160)).toBe(-6);
    expect(pctVsRegion(null, 160)).toBeNull();
  });
});
